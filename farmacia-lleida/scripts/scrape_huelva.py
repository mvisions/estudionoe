#!/usr/bin/env python3
"""Import the official COFH monthly municipality posters."""
import argparse
import calendar
import hashlib
import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import MONTHS, clean, pdf_pages, saved_address_signature, street_query

SOURCE = "https://cofhuelva.org/cuadro-de-guardias"
SEARCH = SOURCE + "/buscador-de-farmacias"
DOWNLOAD = "https://cofhuelva.org/template/modules/cuadro-de-guardias/downloader.php"
LOCATOR = "https://cofhuelva.org/localizador"


def locator_address(address):
    address = re.sub(r"^(CL|C|PL|PS|AV)\s+(?!/)", lambda m:
                     {"CL":"Calle", "C":"Calle", "PL":"Plaza", "PS":"Paseo", "AV":"Avenida"}[m[1].upper()]+" ",
                     address, flags=re.I)
    address = re.sub(r"^Av\.\s*", "Avenida ", address, flags=re.I)
    address = re.sub(r"^Urbanizacion\b", "Urbanización", address, flags=re.I)
    address = re.sub(r"(\besquina\s+)C\s+", r"\1Calle ", address, flags=re.I)
    address = re.sub(r"\bC\.C\.\s*", "Centro comercial ", address, flags=re.I)
    address = re.sub(r"^(Centro comercial\s+){2}", "Centro comercial ", address, flags=re.I)
    return street_query(address)


def match_official_locations(rows, points):
    def city_key(city):
        return slugify(re.sub(r"^Vva\.\s*", "Villanueva ", city, flags=re.I))

    def key(address, city):
        address = locator_address(address)
        signature = saved_address_signature(address, city_key(city))
        if signature:
            return signature
        # Explicit named sites without a house number can match only their full address.
        if re.search(r"\bs\s*/?\s*n\b|\besquina\b|centro comercial", address, re.I):
            return city_key(city), slugify(re.sub(r"\bs\s*/?\s*n\b", "", address, flags=re.I))
        return None

    for row in rows:
        address_key = key(row["direccion"], row["localidad"])
        if not address_key:
            continue
        matches = [point for point in points if key(point["direccion"], point["localidad"]) == address_key]
        if len(matches)==1:
            point = matches[0]
            row.update(lat=point["lat"], lng=point["lng"], precision_ubicacion="farmacia",
                       fuente_coordenadas=point["fuente_coordenadas"])
            if not row.get("nombre"):
                row["nombre"] = point["nombre"]


def parse_locator(content):
    section=re.search(r"const Pharmacies\s*=\s*\[(.*?)\];",content,re.S)
    if not section:
        raise ValueError("Localizador oficial sin lista de coordenadas reconocible.")
    entries=re.findall(
        r"position:\s*\{\s*lat:\s*([-\d.]+),\s*lng:\s*([-\d.]+)\s*\},\s*title:\s*'(.+?)',",
        section[1],re.S)
    rows=[]
    for lat,lng,title in entries:
        name=re.search(r"<h4>(.*?)</h4>",title,re.S)
        address=re.search(r"<p>(.*?)</p>",title,re.S)
        if not name or not address:
            raise ValueError("Localizador oficial sin identidad/dirección.")
        parts=clean(html.unescape(address[1])).rsplit(",",2)
        if len(parts)!=3 or slugify(parts[-1])!="huelva":
            raise ValueError("Dirección del localizador sin municipio/provincia reconocibles.")
        street,city,_=parts
        street=re.sub(r"^C\s*\.\s*","Calle ",street,flags=re.I)
        street=locator_address(street.strip())
        a,b=float(lat),float(lng)
        if not (36.7<a<38.5 and -7.6<b<-6.0):
            print(f"AVISO localizador Huelva: coordenadas inválidas {lat},{lng}",flush=True)
            continue
        key=hashlib.sha256(f"{slugify(city)}:{slugify(street)}".encode()).hexdigest()[:16]
        rows.append({"id":f"cof-huelva-localizador-{key}","nombre":clean(html.unescape(name[1])),
                     "direccion":street,"localidad":city.strip(),"provincia":"Huelva",
                     "lat":a,"lng":b,"precision_ubicacion":"farmacia","fuente_coordenadas":LOCATOR})
    if entries and not rows:
        raise ValueError("El localizador no aporta ninguna coordenada válida.")
    return rows


def collect_locator(cache,offline):
    path=cache/"localizador.json"
    if offline:
        if not path.exists():
            print("AVISO: caché anterior sin localizador; ubicaciones oficiales pendientes.",flush=True)
            return [],[]
        data=json.loads(path.read_text())
        return data["farmacias"],data["errores"]
    content=fetch(LOCATOR).decode("utf-8")
    towns=selectors(content.replace('name="locality"','name="guardia"'))
    points=parse_locator(content)
    errors=[]
    for town in towns:
        try:
            url=LOCATOR+"/buscador-de-farmacias?"+urllib.parse.urlencode({"locality":town["codigo"]})
            points.extend(parse_locator(fetch(url).decode("utf-8")))
        except (OSError,ValueError) as error:
            errors.append(f"{town['nombre']}: {error}")
            print(f"ERROR localizador Huelva {town['nombre']}: {error}",flush=True)
    points=list({row["id"]:row for row in points}.values())
    write_json(path,{"farmacias":points,"errores":errors})
    return points,errors


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def selectors(content):
    match = re.search(r'<select[^>]*name=[\'"]guardia[\'"][^>]*>(.*?)</select>', content, re.S | re.I)
    if not match:
        raise ValueError("El colegio no publica su selector municipal.")
    rows = [{"codigo":code, "nombre":clean(html.unescape(name))}
            for code, name in re.findall(r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', match[1], re.S)]
    if not rows:
        raise ValueError("Selector municipal vacío.")
    return rows


def document_links(content, target):
    result = []
    for url in re.findall(r'href="([^"]*downloader\.php\?[^"]+)"', content):
        url = html.unescape(url)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        label = params.get("localty", [""])[0]
        if str(target.year) not in label:
            continue
        month = next((v for k,v in MONTHS.items() if len(k)>3 and re.search(rf"\b{k}\b", slugify(label).replace("-", " "))), None)
        if month == target.month and "/cuadro-de-guardias/" in url:
            result.append(urllib.parse.quote(url, safe=":/?=&%"))
    return list(dict.fromkeys(result))


def pharmacy(name, address, locality, serving, period, target, source):
    if not address or not re.search(r"\d|\bs/n\b|\besquina\b", address, re.I):
        raise ValueError(f"Casilla sin dirección identificable: {serving}: {address}")
    prefixes = {"CL":"Calle", "PL":"Plaza", "AV":"Avenida", "CE":"Centro comercial", "UR":"Urbanización"}
    address = re.sub(r"^(CL|PL|AV|CE|UR)\s*/\s*", lambda m:prefixes[m[1].upper()]+" ", address, flags=re.I)
    identifier = hashlib.sha256(f"{slugify(locality)}:{slugify(street_query(address))}".encode()).hexdigest()[:16]
    return {"id":f"cof-huelva-{identifier}", "nombre":name, "direccion":address,
            "localidad":locality, "localidades_atendidas":[serving], "provincia":"Huelva",
            "telefono":None, "lat":None, "lng":None, "guardia":True,
            "fecha_guardia":target.isoformat(), "guardia_franjas":[period], "fuente":source}


def parse_grid(page, target, town, source):
    lines = page["lines"]
    days = [line for line in lines if re.fullmatch(r"\d{1,2}", line["text"])
            and 1 <= int(line["text"]) <= calendar.monthrange(target.year, target.month)[1] and line["y"]>70]
    starts = []
    for line in sorted(days, key=lambda row:row["x"]):
        if not starts or line["x"]-starts[-1]>25:
            starts.append(line["x"])
    if len(starts) != 7:
        raise ValueError("Calendario sin siete columnas reconocibles.")
    cells = [line for line in days if int(line["text"])==target.day
             and min(range(7),key=lambda i:abs(starts[i]-line["x"]))==target.weekday()]
    if len(cells) != 1:
        raise ValueError("No se identifica una casilla única para la fecha y día de la semana.")
    cell = cells[0]
    col = min(range(7), key=lambda i:abs(starts[i]-cell["x"]))
    bottom = min((d["y"] for d in days if d["y"]>cell["y"]+8), default=cell["y"]+80)
    spacing = (starts[-1]-starts[0])/6
    text = [line["text"] for line in sorted(lines,key=lambda r:(r["y"],r["x"]))
            if cell["y"]+3 < line["y"] < bottom and starts[col]-2 <= line["x"] < starts[col]+spacing-2]
    address_index = next((i for i,value in enumerate(text) if re.match(
        r"^(?:c/|(?:CL|PL|AV|CE|UR)\s*/|calle|avd|av\.|avenida|p[ºz]|plaza|paseo|ctra|carretera|barrio|urb)", value, re.I)), None)
    if address_index is None:
        raise ValueError(f"Formato de casilla pendiente: {' | '.join(text)}")
    city_start = len(text)
    while city_start>address_index+1 and text[city_start-1].isupper():
        city_start -= 1
    locality = clean(" ".join(text[city_start:])).title() if city_start<len(text) else town
    address = clean(" ".join(text[address_index:city_start]))
    note = "Guardia según calendario municipal; consultar horario del cartel y confirmar por teléfono"
    notices = [line["text"] for line in lines if "LOCALIZAD" in line["text"].upper() or "PRESENCIAL" in line["text"].upper()]
    if notices:
        note += " · " + " ".join(notices)
    return [pharmacy(clean(" ".join(text[:address_index])), address, locality, town, note, target, source)]


def parse_capital(page, target, source, town="Huelva"):
    lines = page["lines"]
    hours = next((r["text"] for r in lines if r["text"].startswith("DIURNO")), None)
    full = next((r for r in lines if re.search(r"FARMACIAS\s+24H", r["text"])), None)
    sunday = next((r for r in lines if r["text"] == "DOMINGOS"), None)
    holiday = next((r for r in lines if r["text"].startswith("FESTIVOS")), None)
    weekday = next((r for r in lines if r["text"] == "DE LUNES A VIERNES"), None)
    saturday = next((r for r in lines if r["text"] == "SÁBADOS"), None)
    if not all((hours,full,sunday,holiday,weekday,saturday)):
        raise ValueError("Formato del cuadro de la capital no reconocido.")
    holiday_dates = re.findall(r"\d{2}/\d{2}/\d{4}", holiday["text"])
    is_holiday = target.strftime("%d/%m/%Y") in holiday_dates
    left = target.weekday()<5 or is_holiday
    section = holiday if is_holiday else sunday if target.weekday()==6 else weekday if left else saturday
    bottom = full["y"] if is_holiday or target.weekday()==6 else sunday["y"]
    rows = []
    for line in lines:
        dates=re.findall(r"\d{2}/\d{2}/\d{4}",line["text"])
        if dates and target.strftime("%d/%m/%Y") not in dates:
            continue
        day_range=re.search(r"Guardia del (\d+) al (\d+)",line["text"],re.I)
        if day_range and not int(day_range[1])<=target.day<=int(day_range[2]):
            continue
        name=""
        address=line["text"]
        if address.startswith(("Farmacia","Fcia")):
            match=re.search(r"\(((?:C/|Avda\.).*?)\)",address,re.I)
            if not match:
                raise ValueError("Dirección no reconocible en cuadro de atención continuada.")
            name=clean(address[:match.start()])
            address=match[1]
        if section["y"]+5 < line["y"] < bottom and (line["x"] < page["width"]/2) == left:
            rows.append(pharmacy(name, address, town, town, hours, target, source))
        elif line["y"]>full["y"]+5:
            rows.append(pharmacy(name, address, town, town, "Farmacia 24 horas", target, source))
    if not rows:
        raise ValueError("Capital sin direcciones confirmadas.")
    return rows


def parse_document(pages, target, town, source):
    month = next(k for k,v in MONTHS.items() if v==target.month and len(k)>3)
    rows = []
    capital = False
    for page in pages:
        top = " ".join(r["text"] for r in page["lines"] if r["y"]<85)
        if not re.search(rf"\b{month}\b", slugify(top).replace("-", " ")):
            raise ValueError("El PDF no coincide con el mes solicitado.")
        if "ATENCIÓN CONTINUADA" in top:
            capital = True
            rows.extend(parse_capital(page, target, source,town))
        else:
            rows.extend(parse_grid(page, target, town, source))
    if not rows:
        raise ValueError("Documento sin guardias interpretables para la fecha.")
    return merge_rows(rows), capital


def run(target, cache, offline=False, use_geocoder=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if offline:
            index = json.loads((cache/"indice.json").read_text())
            if index["fecha"]!=target.isoformat():
                raise ValueError("La caché no corresponde a la fecha solicitada.")
            towns = index["consultas"]
        else:
            towns = selectors(fetch(SOURCE).decode("utf-8"))
    except (OSError, ValueError) as error:
        return publish(target,"Huelva",SOURCE,[],[{"nombre":"Índice provincial","estado":"error","error":str(error)}])

    def collect(town):
        rows = []
        report = {**town,"estado":"error"}
        try:
            if offline:
                documents = [json.loads(p.read_text()) for p in cache.glob("*.json")
                             if p.name not in ("indice.json","localizador.json")]
                links = [d["url"] for d in documents if slugify(
                    re.sub(r"\s+\w+\s+\d{4}$", "", urllib.parse.parse_qs(
                        urllib.parse.urlparse(d["url"]).query)["localty"][0]))==slugify(town["nombre"])]
            else:
                content = fetch(SEARCH+"?"+urllib.parse.urlencode({"guardia":town["codigo"]})).decode("utf-8")
                links = document_links(content, target)
            if not links:
                raise ValueError("Sin PDF publicado para el mes y año solicitados.")
            incomplete = False
            for url in links:
                key = hashlib.sha256(url.encode()).hexdigest()
                data = (cache/f"{key}.pdf").read_bytes() if offline else fetch(url)
                if not data.startswith(b"%PDF"):
                    raise ValueError("La descarga oficial no es un PDF.")
                digest = hashlib.sha256(data).hexdigest()
                stored = cache / f"{key}.json"
                previous = json.loads(stored.read_text()) if stored.exists() else {}
                pages = previous["pages"] if previous.get("sha256")==digest else pdf_pages(data)
                (cache/f"{key}.pdf").write_bytes(data)
                write_json(stored, {"sha256":digest,"pages":pages,"url":url})
                parsed, capital = parse_document(pages,target,town["nombre"],url)
                rows.extend(parsed)
                incomplete |= capital
            report.update(estado="parcial" if incomplete else "disponible",documentos=links,farmacias=len(rows))
            if incomplete:
                report["error"]="Cuadro diurno y farmacias 24h confirmados; no se certifica el resto de turnos nocturnos de la capital."
        except (OSError, ValueError, KeyError, ET.ParseError, subprocess.CalledProcessError) as error:
            report["error"]=str(error)
        print(f"Huelva {town['nombre']}: {len(rows)} guardias, {report['estado']}",flush=True)
        return rows,report

    with ThreadPoolExecutor(max_workers=4) as pool:
        collected = list(pool.map(collect,towns))
    rows = merge_rows([row for batch,_ in collected for row in batch])
    reports = [report for _,report in collected]
    write_json(cache/"indice.json",{"fecha":target.isoformat(),"consultas":reports})
    try:
        official,location_errors=collect_locator(cache,offline)
        match_official_locations(rows,official)
        if location_errors:
            reports.append({"nombre":"Localizador provincial","estado":"error",
                            "error":" · ".join(location_errors)})
        capital_towns={row["fuente"]:row["localidad"] for row in rows
                       if any("DIURNO" in period or "Farmacia 24 horas" in period
                              for period in row["guardia_franjas"])}
        catalog_path=OUT_DIR/"farmacias-huelva.json"
        if capital_towns and catalog_path.exists():
            saved=json.loads(catalog_path.read_text())
            write_json(catalog_path,[row for row in saved
                       if row.get("fuente") not in capital_towns
                       or row["localidad"]==capital_towns[row["fuente"]]])
        locate_and_catalogue(rows,"Huelva",use_geocoder=use_geocoder,official_points=official)
    except (OSError,ValueError,KeyError) as error:
        reports.append({"nombre":"Ubicaciones","estado":"error","error":str(error)})
    authoritative={url for report in reports if report["estado"] in ("disponible","parcial")
                   for url in report.get("documentos",[])}
    return publish(target,"Huelva",SOURCE,rows,reports,authoritative_sources=authoritative)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha",type=date.fromisoformat,default=date.today())
    parser.add_argument("--cache-documentos",type=Path,default=Path.home()/".local/state/farmacia/huelva")
    parser.add_argument("--sin-red",action="store_true",help="Reproducir solo la caché de la misma fecha.")
    parser.add_argument("--geocode",action="store_true",help="Contrastar ubicaciones con POI de farmacia exactos.")
    args=parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite consultas de geocodificación.")
    raise SystemExit(0 if run(args.fecha,args.cache_documentos,args.sin_red,args.geocode) else 1)
