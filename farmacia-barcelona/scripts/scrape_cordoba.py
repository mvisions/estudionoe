#!/usr/bin/env python3
"""Import COFCO dated public municipality day/night guardia results."""
import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import OUT_DIR, write_json
from scrape_sevilla import clean


def source_url(year):
    return f"https://www.cofco.org/aplicaciones/guardias/farmacias{year}.php"


def request(url, params=None):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(params).encode() if params else None,
                               headers={"User-Agent":"FarmaciasDeGuardiaTracker/1.0",
                                        "Accept":"text/html", "Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req,timeout=45) as response:
        return response.read().decode("utf-8")


def selectors(content):
    match=re.search(r'<select[^>]*name="sltCiudad"[^>]*>(.*?)</select>',content,re.S|re.I)
    if not match:
        raise ValueError("El colegio no publica un selector municipal reconocible.")
    rows=[{"codigo":code,"nombre":clean(html.unescape(name))}
          for code,name in re.findall(r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>',match[1],re.S)]
    if not rows:
        raise ValueError("Selector municipal vacío.")
    return rows


def text(value):
    return clean(html.unescape(re.sub(r"<[^>]+>"," ",value)))


def parse_schedule(content,target,town,source,errors=None):
    date_link = re.search(r"resultados\d{4}\((\d+),(\d+),(\d+),(\d+)\)",content)
    if not date_link or date(*(int(date_link[i]) for i in (3,2,1))) != target:
        raise ValueError("La respuesta no confirma la fecha solicitada.")
    if date_link[4]!=town["codigo"]:
        raise ValueError("El colegio no respeta el municipio solicitado.")
    if not re.search(r"FARMACIAS DE GUARDIA EN .*? EL D[IÍ]A",text(content),re.I):
        raise ValueError("Respuesta sin cabecera de calendario.")
    headings=list(re.finditer(r'<div[^>]*class="textosubtitular"[^>]*>(.*?)</div>',content,re.S|re.I))
    rows=[]
    for index,heading in enumerate(headings):
        period=text(heading[1])
        if not period.startswith("FARMACIA DE GUARDIA"):
            continue
        section=content[heading.end():headings[index+1].start() if index+1<len(headings) else len(content)]
        for match in re.finditer(r'<tr[^>]*>(.*?)</tr>',section,re.S|re.I):
            cells=re.findall(r'<td[^>]*class="textofarmacias"[^>]*>(.*?)</td>',match[1],re.S|re.I)
            if len(cells)<2:
                continue
            identifier=re.search(r'ampliada\.php\?id=(\d+)',cells[0])
            if not identifier:
                raise ValueError("Farmacia sin identificador oficial.")
            address=text(cells[0]).split("|")[0].strip()
            locality=text(cells[1])
            sector=""
            if town["nombre"].strip().upper()=="CORDOBA" and locality.upper().startswith("ZONA "):
                sector=locality
                locality="Córdoba"
            elif locality.upper()=="AGUILAR DE LA FRA.":
                locality="Aguilar de la Frontera"
            phone=re.search(r"tel:(\d+)",cells[0])
            if not address or not locality:
                error=f"Farmacia {identifier[1]} sin dirección/localidad oficial; no se infiere la ubicación."
                if errors is None:
                    raise ValueError(error)
                errors.append(error)
                print(f"AVISO {town['nombre']}: {error}",flush=True)
                continue
            rows.append({"id":f"cof-cordoba-{identifier[1]}","nombre":"","direccion":address,
                         "localidad":locality.title(),"localidades_atendidas":[town["nombre"]],
                         "sector":sector,
                         "provincia":"Córdoba","telefono":phone[1] if phone else None,
                         "guardia":True,"guardia_franjas":[period],"fecha_guardia":target.isoformat(),
                         "lat":None,"lng":None,"fuente":source})
    if not rows:
        raise ValueError("Sin farmacias confirmadas para esta consulta; no se supone ausencia de guardias.")
    return merge_rows(rows)


def run(target,cache,offline=False,use_geocoder=False,allow_address=False):
    source=source_url(target.year)
    cache.mkdir(parents=True,exist_ok=True)
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    try:
        if offline:
            index=json.loads((cache/"indice.json").read_text())
            if index["fecha"]!=target.isoformat():
                raise ValueError("La caché no corresponde a la fecha solicitada.")
            towns=index["consultas"]
        else:
            towns=selectors(request(source))
    except (OSError,ValueError,KeyError) as error:
        return publish(target,"Córdoba",source,[],[{"nombre":"Índice provincial","estado":"error","error":str(error)}])

    def collect(town):
        report={**town,"estado":"error"}
        rows=[]
        try:
            path=cache/f"{target}-{town['codigo']}.html"
            if offline:
                content=path.read_text()
            else:
                time.sleep(1.1)
                content=request(source,{"dia":f"{target.day:02d}","mes":f"{target.month:02d}",
                                        "ano":str(target.year),"sltCiudad":town["codigo"]})
                path.write_text(content)
            errors=[]
            rows=parse_schedule(content,target,town,source,errors)
            report.update(estado="parcial" if errors else "disponible",farmacias=len(rows))
            if errors:
                report["error"]=" · ".join(errors)
        except (OSError,ValueError,KeyError) as error:
            report["error"]=str(error)
        print(f"Córdoba {town['nombre']}: {len(rows)} guardias, {report['estado']}",flush=True)
        return rows,report

    collected=[collect(town) for town in towns]
    rows=merge_rows([row for batch,_ in collected for row in batch])
    reports=[report for _,report in collected]
    write_json(cache/"indice.json",{"fecha":target.isoformat(),"consultas":reports})
    try:
        locate_and_catalogue(rows,"Córdoba",use_geocoder=use_geocoder,allow_address=allow_address)
    except (OSError,ValueError,KeyError) as error:
        reports.append({"nombre":"Ubicaciones","estado":"error","error":str(error)})
    return publish(target,"Córdoba",source,rows,reports)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha",type=date.fromisoformat,default=date.today())
    parser.add_argument("--cache-documentos",type=Path,default=Path.home()/".local/state/farmacia/cordoba")
    parser.add_argument("--sin-red",action="store_true")
    parser.add_argument("--geocode",action="store_true")
    parser.add_argument("--permitir-direccion-exacta",action="store_true",
                        help="Aceptar edificios de dirección exacta, indicando verificación pendiente.")
    args=parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite consultas de geocodificación.")
    raise SystemExit(0 if run(args.fecha,args.cache_documentos,args.sin_red,args.geocode,args.permitir_direccion_exacta) else 1)
