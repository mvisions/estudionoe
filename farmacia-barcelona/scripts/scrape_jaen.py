#!/usr/bin/env python3
"""Import the public Jaén municipality index and dated official duty posters."""
import argparse
import hashlib
import html
import http.cookiejar
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import MONTHS, clean, pdf_pages, saved_address_signature, street_query

BASE = "https://www.farmaceuticosdejaen.es/"
SOURCE = BASE + "Paginas/Farmacias_Guardia.asp"
DIRECTORY = BASE + "Paginas/Farmacias.asp"
ADDRESS = re.compile(r"\b(?:C\s*/|Calle\b|AVDA?\.?\s|AVD\.?\s|AVENIDA\b|PASEO\b|P[º°]\s*|PLAZA\b|PZA\.?\s|CTRA\.?\s|CARRETERA\b)", re.I)
PHONE = re.compile(r"(?<!\d)[689](?:[\s.-]*\d){8}(?!\d)")


def parse_catalogue(content):
    expected = re.search(r"(\d+) FARMACIAS ENCONTRADAS:", content)
    parts = re.split(r'<div class="card mt-2">', content)[1:]
    rows = []
    for part in parts:
        number = re.search(r"Nº Farmacia:\s*(\d+)", part)
        owner_block = re.search(r"Propietarios?\s*</div>(.*?)Datos farmacia", part, re.S)
        data = re.search(r"Datos farmacia\s*</div>(.*?)(?:</div>\s*</div>\s*</div>|<div>\s*<div class=\"centro)", part, re.S)
        if not number or not owner_block or not data:
            raise ValueError("Ficha del directorio sin identidad reconocible.")
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", v))) for v in re.findall(
            r'<div class="col-[^"]*">(.*?)</div>', data[1], re.S)]
        city = next((v.removeprefix("Población:").strip() for v in cells if v.startswith("Población:")), "")
        phone = next((v.removeprefix("Teléfono:").strip() for v in cells if v.startswith("Teléfono:")), "")
        if not cells or not city or not cells[0]:
            raise ValueError("Ficha del directorio sin dirección/población.")
        owner = clean(html.unescape(re.sub(r"<[^>]+>", " ", owner_block[1])))
        rows.append({"id": f"cof-jaen-{number[1]}", "numero_colegio": number[1],
                     "nombre": owner, "direccion": cells[0], "localidad": city.title(),
                     "provincia": "Jaén", "telefono": re.sub(r"\D", "", phone) or None,
                     "lat": None, "lng": None, "guardia": False, "fuente": DIRECTORY})
    if not expected:
        raise ValueError("El directorio no confirma el número de farmacias.")
    return rows, int(expected[1])


def load_directory(opener, cache):
    content = request(opener, DIRECTORY, {"formBuscar": "si"}).decode("cp1252")
    rows, total = parse_catalogue(content)
    if not rows:
        raise ValueError("Directorio sin farmacias.")
    page = 2
    while len(rows) < total:
        content = request(opener, DIRECTORY + f"?page={page}&TextoBuscar=").decode("cp1252")
        batch, reported = parse_catalogue(content)
        if reported != total or not batch or any(r["id"] in {v["id"] for v in rows} for r in batch):
            raise ValueError("Paginación del directorio incompleta o repetida.")
        rows.extend(batch)
        page += 1
        time.sleep(0.2)
    if len(rows) != total:
        raise ValueError("El número de farmacias no coincide con el directorio.")
    write_json(cache / "directorio.json", rows)
    print(f"Directorio oficial: {len(rows)} farmacias contrastadas.", flush=True)
    return rows


def request(opener, url, params=None):
    with opener.open(urllib.request.Request(
        url, data=urllib.parse.urlencode(params).encode() if params else None,
        headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"},
    ), timeout=40) as response:
        return response.read()


class DocumentIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.text = []
        self.links = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "BordeGrisAbajo" in attrs.get("class", ""):
                self.depth = 1
                self.text, self.links = [], []
        if tag == "a" and self.depth and "MostrarDocumento.asp?" in attrs.get("href", ""):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth and self.links:
                label = clean(" ".join(self.text))
                year = re.search(r"\b(20\d{2})\b", label)
                month = next((MONTHS[w] for w in slugify(label).split("-") if w in MONTHS), None)
                if year:
                    for link in self.links:
                        self.rows.append({"anio": int(year[0]), "mes": month,
                                          "url": urllib.parse.urljoin(SOURCE, link),
                                          "nombre": label})

    def handle_data(self, text):
        if self.depth:
            self.text.append(text)


def choose_documents(rows, target):
    current = [r for r in rows if r["anio"] == target.year and r["mes"] == target.month]
    if current:
        return current
    return [r for r in rows if r["anio"] == target.year and r["mes"] is None]


def collect(target, cache):
    cache.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request(opener, BASE)
    load_directory(opener, cache)
    content = request(opener, SOURCE).decode("cp1252")
    selector = re.search(r'<select[^>]+id="idPoblacion".*?</select>', content, re.S)
    if not selector:
        raise ValueError("La fuente oficial no contiene el selector de poblaciones.")
    municipalities = [(c, html.unescape(n).strip()) for c, n in re.findall(
        r'<option value="(\d+)"[^>]*>(.*?)</option>', selector[0], re.S)]
    if not municipalities:
        raise ValueError("Selector oficial sin poblaciones.")
    queries, documents = [], {}
    for i, (code, city) in enumerate(municipalities, 1):
        try:
            content = request(opener, SOURCE, {"idPoblacion": code, "formBuscar": "si"}).decode("cp1252")
            if "FARMACIAS DE GUARDIA ENCONTRADAS EN:" not in content:
                raise ValueError("El formulario no confirma resultados para la población.")
            parser = DocumentIndex()
            parser.feed(content)
            selected = choose_documents(parser.rows, target)
            query = {"codigo": code, "nombre": city, "documentos": selected}
            for item in selected:
                url = item["url"]
                if url in documents:
                    continue
                if urllib.parse.urlparse(url).hostname != urllib.parse.urlparse(BASE).hostname:
                    raise ValueError("Documento fuera del Colegio oficial.")
                key = hashlib.sha256(url.encode()).hexdigest()
                try:
                    content = request(opener, urllib.parse.quote(url, safe=":/?=&%"))
                    if not content.startswith(b"%PDF"):
                        raise ValueError("El cartel oficial no es PDF.")
                    digest = hashlib.sha256(content).hexdigest()
                    pdf = cache / f"{key}.pdf"
                    pdf.write_bytes(content)
                    converted = cache / f"{key}.json"
                    saved = json.loads(converted.read_text()) if converted.exists() else None
                    pages = saved["pages"] if saved and saved["sha256"] == digest else pdf_pages(content)
                    if not saved or saved["sha256"] != digest:
                        write_json(converted, {"sha256": digest, "pages": pages})
                    documents[url] = {"archivo": pdf.name, "convertido": converted.name}
                except (OSError, ValueError, subprocess.CalledProcessError) as error:
                    documents[url] = {"error": str(error)}
            queries.append(query)
            print(f"{i}/{len(municipalities)} {city}: {len(selected)} carteles vigentes", flush=True)
        except (OSError, ValueError) as error:
            queries.append({"codigo": code, "nombre": city, "error": str(error)})
            print(f"ERROR {city}: {error}", flush=True)
        time.sleep(0.2)
    index = {"fecha": target.isoformat(), "consultas": queries, "documentos": documents}
    write_json(cache / "indice.json", index)
    return index


def identity_tokens(value):
    return {w for w in slugify(value).split("-") if w not in {
        "farmacia", "fcia", "lda", "ldo", "ldas", "ldos", "d", "da", "de", "del",
        "la", "el", "los", "las", "calle", "avenida", "avda", "av", "pza", "plaza",
        "paseo", "n", "no", "numero", "num", "localizada", "guardia",
    }}


VERIFIED_NICKNAMES = {
    "Alcaudete": {
        "muralla": "cof-jaen-5",
        "bigote": "cof-jaen-222",
        "plaza": "cof-jaen-4",
        "zagales": "cof-jaen-306",
    },
    "Valdepeñas de Jaen": {
        "velasco": "cof-jaen-161",
        "valenzuela": "cof-jaen-161",
    },
}


def resolve_label(label, city, directory):
    text = clean(label).strip("-• ")
    # Verified nickname mapping (contrastado con fuentes externas: web de la
    # farmacia y directorios públicos). Solo se usa cuando la asociación es
    # inequívoca.
    nicknames = None
    for key, val in VERIFIED_NICKNAMES.items():
        if key.lower() == city.lower():
            nicknames = val
            break
    if not nicknames:
        nicknames = {}
    slug_tokens = set(slugify(text).split("-"))
    lowered_tokens = {t.lower() for t in identity_tokens(text)} | slug_tokens
    for nick, pharmacy_id in nicknames.items():
        if nick in lowered_tokens:
            match = next((r for r in directory if r["id"] == pharmacy_id), None)
            if match:
                return match
    # Some grouping labels refer to a different municipality than the requested one.
    cities = sorted({r["localidad"] for r in directory}, key=len, reverse=True)
    matched_city = next((v for v in cities if re.search(r"(?:^|-)" + re.escape(slugify(v)) + r"(?:-|$)", slugify(text))), None)
    if not matched_city:
        prefixes = [v for v in cities if len(slugify(text).split("-")[0]) >= 5
                    and slugify(v).startswith(slugify(text).split("-")[0]+"-")]
        if len(prefixes)==1:
            matched_city = prefixes[0]
    locality = matched_city or city
    candidates = [r for r in directory if slugify(r["localidad"]) == slugify(locality)]
    tokens = identity_tokens(text)
    phone = PHONE.search(text)
    numbers = {w for w in tokens if w.isdigit()}
    # Owner-focused tokens (text before the first address keyword) for better matching.
    address_match = ADDRESS.search(text)
    if address_match:
        owner_tokens = identity_tokens(text[:address_match.start()])
    else:
        owner_tokens = tokens
    matches = []
    strict_matches = []
    for row in candidates:
        road = identity_tokens(row["direccion"])
        owner = identity_tokens(row["nombre"])
        street_words = (road & tokens) - numbers
        owner_words = owner & owner_tokens
        exact_phone = bool(phone and re.sub(r"\D", "", phone[0]) == row["telefono"])
        street_match = bool(numbers and numbers <= road and street_words
                            and (len(street_words) >= 2 or any(len(w) >= 5 for w in street_words)))
        owner_match = (len(owner_words) >= 2 or (bool(matched_city) and bool(owner_words))
                       or (bool(owner_words) and any(len(w) >= 5 for w in street_words)))
        one_pharmacy = len(candidates) == 1 and (tokens <= identity_tokens(locality)
                                               or slugify(text) == "guardia-localizada")
        if exact_phone or street_match or owner_match or one_pharmacy:
            matches.append(row)
        # Strict: owner match reinforced by address or unique pharmacy.
        if exact_phone or (owner_match and street_match) or one_pharmacy:
            strict_matches.append(row)
    # Prefer strict matches when they identify a single pharmacy.
    if len(strict_matches) == 1:
        matches = strict_matches
    # Fall back to a single shared token between cartel and pharmacy name.
    if not matches and owner_tokens:
        distinctive = [r for r in candidates if identity_tokens(r["nombre"]) & owner_tokens]
        if len(distinctive) == 1:
            matches = distinctive
    if not matches:
        matches = [r for r in directory if len(identity_tokens(r["nombre"]) & tokens) >= 3]
    if len(matches) != 1:
        raise ValueError(f"Farmacia no identificada inequívocamente en {locality}: {text}")
    return matches[0]


def duty(label, city, period, target, source, directory):
    row = resolve_label(label, city, directory)
    record = {**row, "guardia": True, "guardia_franja": period, "guardia_franjas": [period],
            "fecha_guardia": target.isoformat(), "fuente": source, "fuentes": [source],
            "direccion_cartel": clean(label), "localidades_atendidas": [city.title()]}
    address = ADDRESS.search(label)
    if address and saved_address_signature(label[address.start():], row["localidad"]) != saved_address_signature(row["direccion"], row["localidad"]):
        record["nota_ubicacion"] = f"El cartel indica «{label[address.start():]}»; el directorio oficial identifica a este titular en «{row['direccion']}». Confirma la dirección antes de desplazarte."
    return record


def grouped_lines(page):
    groups = []
    for line in sorted(page["lines"], key=lambda v: (v["y"], v["x"])):
        if not groups or abs(groups[-1][0]["y"] - line["y"]) > 3:
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def parse_capital(pages, target, source, directory):
    records = []
    for page in pages:
        text = " ".join(v["text"] for v in page["lines"])
        if not re.search(rf"JA[ÉE]N\s*[–-]\s*{next(k.upper() for k, v in MONTHS.items() if v == target.month and len(k) > 3)}\s+{target.year}", text):
            continue
        day_heading = next((v for v in page["lines"] if "DIURNA (9.30" in v["text"]), None)
        night_heading = next((v for v in page["lines"] if "NOCTURNA (22:00" in v["text"]), None)
        if not day_heading or not night_heading:
            continue
        stamps = []
        for group in grouped_lines(page):
            first = next((v for v in group if v["x"] < day_heading["x"]-15 and re.fullmatch(r"\d{1,2}", v["text"])), None)
            weekday = next((v for v in group if re.fullmatch(r"Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo", v["text"])), None)
            if first and weekday:
                stamps.append((int(first["text"]), first["y"]))
        for i, (day, y) in enumerate(stamps):
            if day != target.day:
                continue
            low = (stamps[i-1][1]+y)/2 if i else day_heading["y"]+10
            high = (y+stamps[i+1][1])/2 if i+1 < len(stamps) else y+30
            boundary = (day_heading["right"]+night_heading["x"])/2
            for period, left, right in [("Día (9:30-22:00)", day_heading["x"]-20, boundary),
                                       ("Noche (22:00-9:30 del día siguiente)", boundary, page["width"])]:
                labels = [v["text"] for v in sorted(page["lines"], key=lambda v: (v["y"], v["x"]))
                          if low <= v["y"] < high and left <= v["x"] < right]
                for label in labels:
                    if not re.fullmatch(r"\d+", label):
                        records.append(duty(label, "Jaén", period, target, source, directory))
    return records


def parse_dated_lists(pages, target, city, source, directory):
    records = []
    stamp = target.strftime("%d/%m/%Y")
    for page in pages:
        groups = grouped_lines(page)
        for group in groups:
            joined = clean(" ".join(v["text"] for v in group))
            if stamp not in joined:
                continue
            day_heading = next((v for v in page["lines"] if "DIURNA (9.30" in v["text"]), None)
            night_heading = next((v for v in page["lines"] if "NOCTURNA (22:00" in v["text"]), None)
            columns = [(0, page["width"], "Guardia de la fecha; horario no especificado en el cartel")]
            if day_heading and night_heading:
                columns = [(0, night_heading["x"]-20, "Día (9:30-22:00)"),
                           (night_heading["x"]-20, page["width"], "Noche (22:00-9:30 del día siguiente)")]
            for left, right, period in columns:
                label = clean(" ".join(v["text"] for v in group if left <= v["x"] < right).replace(stamp, " "))
                label = re.sub(r"^(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s*", "", label, flags=re.I)
                if label:
                    records.append(duty(label, city, period, target, source, directory))
    return records


def parse_week_grid(pages, target, city, source, directory):
    records = []
    current_monday = None
    if "guardia de 24 horas" not in " ".join(v["text"].lower() for p in pages for v in p["lines"]):
        return records
    for page in pages:
        for group in grouped_lines(page):
            joined = clean(" ".join(v["text"] for v in sorted(group, key=lambda v: v["x"])))
            header = re.match(r"([a-z]+)-(\d{2})\b", joined, re.I)
            if header:
                name, short_year = header.groups()
                name = name.lower()
                if name in MONTHS:
                    month, year = MONTHS[name], 2000+int(short_year)
                    first = date(year, month, 1)
                    current_monday = first-timedelta(days=first.weekday())
                joined = joined[header.end():].strip()
            sequence = re.match(r"((?:\d{1,2}\s+){6}\d{1,2})\s+(.+)", joined)
            if not sequence or not current_monday:
                continue
            actual = [int(v) for v in sequence[1].split()]
            expected = [(current_monday+timedelta(days=i)).day for i in range(7)]
            if actual != expected:
                # Some months omit the first week when it belongs to the preceding month.
                next_week = current_monday+timedelta(days=7)
                if actual == [(next_week+timedelta(days=i)).day for i in range(7)]:
                    current_monday = next_week
                else:
                    raise ValueError("Días de la tabla no coinciden con el calendario.")
            if current_monday <= target < current_monday+timedelta(days=7):
                label = sequence[2]
                if re.match(r"^\d+\s", label):
                    raise ValueError("La semana está codificada con colores/celdas combinadas, sin farmacia legible.")
                records.append(duty(label, city, "Guardia de 24 horas; semana del " + current_monday.isoformat(),
                                    target, source, directory))
                return records
            current_monday += timedelta(days=7)
    return records


def parse_month_rows(pages, target, city, source, directory):
    records = []
    month_name = next(k for k, v in MONTHS.items() if v == target.month and len(k)>3)
    for page in pages:
        text = " ".join(v["text"] for v in page["lines"])
        if not re.search(rf"MES DE {month_name} DE {target.year}\b", text, re.I) or "ANDÚJAR" not in text:
            continue
        for group in grouped_lines(page):
            day = next((v for v in group if re.fullmatch(str(target.day), v["text"]) and v["x"]<100), None)
            weekday = next((v for v in group if re.fullmatch(r"Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo", v["text"])), None)
            if not day or not weekday:
                continue
            label = " ".join(v["text"] for v in group if v["x"] > weekday["right"]+5)
            if not label:
                continue
            period = "24 horas (9:30-9:30 del día siguiente)" if "COMIENZA A LAS 9:30" in text else "Guardia de la fecha; horario no especificado en el cartel"
            records.append(duty(label, city, period, target, source, directory))
    return records


def parse_month_cells(pages, target, city, source, directory):
    month_name = next(k for k, v in MONTHS.items() if v == target.month and len(k)>3)
    records = []
    for page in pages:
        lines = page["lines"]
        top = " ".join(v["text"] for v in lines if v["y"]<90)
        if not re.search(rf"\b{month_name}\b", top, re.I) or str(target.year) not in top:
            continue
        if not any(re.search(r"LUNES|^Lu$", v["text"]) for v in lines):
            continue
        numbers = [v for v in lines if re.fullmatch(r"\d{1,2}", v["text"])
                   and 0<int(v["text"])<=31 and v["y"]>60]
        target_cells = [v for v in numbers if int(v["text"])==target.day]
        if len(target_cells)!=1:
            continue
        cell = target_cells[0]
        centers = []
        for v in sorted(numbers, key=lambda v:v["x"]):
            if not centers or v["x"]-centers[-1]>25:
                centers.append(v["x"])
        if len(centers)!=7:
            continue
        col = min(range(7), key=lambda i:abs(centers[i]-cell["x"]))
        if col!=target.weekday():
            raise ValueError("La casilla del calendario no coincide con el día de la semana.")
        next_rows = [v["y"] for v in numbers if v["y"]>cell["y"]+8]
        high = min(next_rows) if next_rows else cell["y"]+100
        spacing = (centers[-1]-centers[0])/6
        # Dates are right-aligned in these monthly tables; names fill their column.
        left, right = centers[col]-spacing+15, centers[col]+15
        label = clean(" ".join(v["text"] for v in sorted(lines,key=lambda v:(v["y"],v["x"]))
                              if cell["y"]+3<v["y"]<high and left<=v["x"]<right))
        if not label:
            raise ValueError("Calendario por colores sin nombre/dirección legible en la casilla.")
        records.append(duty(label, city, "Guardia según casilla mensual; consulta el horario del cartel",
                            target, source, directory))
    return records


def parse_document(pages, target, city, source, directory):
    for parser in [lambda: parse_capital(pages, target, source, directory),
                   lambda: parse_dated_lists(pages, target, city, source, directory),
                   lambda: parse_month_rows(pages, target, city, source, directory),
                   lambda: parse_month_cells(pages, target, city, source, directory),
                   lambda: parse_week_grid(pages, target, city, source, directory)]:
        records = parser()
        if records:
            return records
    raise ValueError("PDF sin guardias interpretables para la fecha: calendario gráfico, otro mes o formato pendiente.")


def merge(rows):
    result = {}
    for row in rows:
        if row["id"] not in result:
            result[row["id"]] = row
            continue
        prior = result[row["id"]]
        for field in ("guardia_franjas", "fuentes", "localidades_atendidas"):
            prior[field] = list(dict.fromkeys(prior[field]+row[field]))
        prior["guardia_franja"] = "; ".join(prior["guardia_franjas"])
    return list(result.values())


def valid_coordinates(row):
    return (isinstance(row.get("lat"), (int, float)) and not isinstance(row["lat"], bool)
            and isinstance(row.get("lng"), (int, float)) and not isinstance(row["lng"], bool)
            and 37.2 < row["lat"] < 38.7 and -4.3 < row["lng"] < -2.3)


def geocode(row):
    street = street_query(row["direccion"])
    params = {"q": f"Farmacia, {street}, {row['localidad']}, Jaén, España",
              "format": "jsonv2", "addressdetails": 1, "countrycodes": "es", "limit": 5}
    content = request(urllib.request.build_opener(),
                      "https://nominatim.openstreetmap.org/search?"+urllib.parse.urlencode(params))
    key = saved_address_signature(street, row["localidad"])
    found = []
    for item in json.loads(content):
        address = item.get("address", {})
        city = next((address[k] for k in ("city", "town", "village", "municipality", "suburb") if address.get(k)), "")
        road = f"{address.get('road', '')} {address.get('house_number', '')}"
        if not key or item.get("type")!="pharmacy" or saved_address_signature(road, city)!=key:
            continue
        location = {"lat": float(item["lat"]), "lng": float(item["lon"]),
                    "precision_ubicacion": "farmacia",
                    "fuente_coordenadas": f"https://www.openstreetmap.org/{item['osm_type']}/{item['osm_id']}"}
        if valid_coordinates(location):
            found.append(location)
    return found[0] if len(found)==1 else None


def locate(directory, rows, use_geocoder):
    path = OUT_DIR / "farmacias-jaen.json"
    old = {r["id"]: r for r in json.loads(path.read_text())} if path.exists() else {}
    osm_path = OUT_DIR / "farmacias-osm-espana.json"
    if not osm_path.exists():
        raise FileNotFoundError("Falta el catálogo OSM necesario para contrastar coordenadas.")
    osm = [r for r in json.loads(osm_path.read_text()) if valid_coordinates(r)]
    fields = ("lat", "lng", "precision_ubicacion", "fuente_coordenadas")
    for row in directory:
        prior = old.get(row["id"])
        if prior and prior["direccion"]==row["direccion"] and prior.get("telefono")==row["telefono"] and valid_coordinates(prior):
            row.update({f:prior.get(f) for f in fields})
            continue
        key = saved_address_signature(row["direccion"], row["localidad"])
        matches = [r for r in osm if (
            row["telefono"] and re.sub(r"\D", "", str(r.get("telefono") or "")).removeprefix("34")==row["telefono"]
        ) or (key and saved_address_signature(r.get("direccion", ""), r.get("localidad", ""))==key)]
        if len(matches)==1:
            row.update(lat=matches[0]["lat"], lng=matches[0]["lng"], precision_ubicacion="farmacia",
                       fuente_coordenadas="https://www.openstreetmap.org/"+matches[0]["id"].replace("osm-", "node/"))
    by_id = {r["id"]:r for r in directory}
    errors = []
    for row in rows:
        reference = by_id[row["id"]]
        if not valid_coordinates(reference) and use_geocoder:
            try:
                position = geocode(reference)
                if position:
                    reference.update(position)
                print(f"Ubicación {reference['localidad']} {reference['direccion']}: {'verificada' if position else 'pendiente; sin coincidencia fiable'}", flush=True)
            except (OSError, ValueError) as error:
                errors.append(f"{reference['id']}: {error}")
                print(f"ERROR geocodificación {reference['id']}: {error}", flush=True)
            time.sleep(1.1)
        row.update({f:reference.get(f) for f in fields})
    write_json(path, directory)
    return errors


def publish(target, rows, reports, coordinate_errors):
    complete = bool(reports) and all(r["estado"]=="disponible" for r in reports)
    path = OUT_DIR / f"guardias-jaen-{target.isoformat()}.json"
    preserved = path.exists() and not rows
    published = bool(rows) and (complete or not path.exists())
    if published:
        write_json(path, rows)
    elif rows and path.exists():
        # Update confirmed municipalities, preserving records for unconfirmed queries.
        saved = json.loads(path.read_text())
        confirmed = {r["nombre"].title() for r in reports if r["estado"]=="disponible"}
        retained = []
        for row in saved:
            towns = [c for c in row.get("localidades_atendidas", []) if c not in confirmed]
            if towns:
                retained.append({**row, "localidades_atendidas": towns})
        preserved = bool(retained)
        write_json(path, merge(rows+retained))
        published = True
    visible = json.loads(path.read_text()) if path.exists() else []
    report = {"fecha": target.isoformat(), "provincia": "Jaén", "fuente": SOURCE,
              "consultado": datetime.now(timezone.utc).isoformat(), "completa": complete,
              "consultas": reports, "farmacias": len(visible), "farmacias_confirmadas": len(rows),
              "con_coordenadas": sum(valid_coordinates(r) for r in visible),
              "calendario_actualizado": published, "errores_coordenadas": coordinate_errors,
              "conserva_guardias_no_reconfirmadas": not complete and preserved}
    write_json(OUT_DIR / f"cobertura-jaen-{target.isoformat()}.json", report)
    print(f"Jaén: {len(rows)} confirmadas; {len(visible)} publicadas, {report['con_coordenadas']} ubicadas; cobertura {'completa' if complete else 'parcial'}.", flush=True)
    return complete


def run(target, cache, offline=False, use_geocoder=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        index = json.loads((cache/"indice.json").read_text()) if offline else collect(target, cache)
        if index["fecha"]!=target.isoformat():
            raise ValueError("La caché no corresponde a la fecha solicitada.")
        directory = json.loads((cache/"directorio.json").read_text())
        if not directory:
            raise ValueError("Directorio oficial vacío.")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        publish(target, [], [{"nombre": "Índice/directorio provincial", "estado": "error", "error":str(error)}], [])
        return False
    rows, reports = [], []
    for query in index["consultas"]:
        found, errors = [], []
        if query.get("error"):
            errors.append(query["error"])
        if not query.get("documentos") and not errors:
            errors.append("Sin documento mensual/anual vigente publicado para esta población.")
        for item in query.get("documentos", []):
            try:
                document = index["documentos"][item["url"]]
                if document.get("error"):
                    raise ValueError(document["error"])
                pages = json.loads((cache/document["convertido"]).read_text())["pages"]
                found.extend(parse_document(pages, target, query["nombre"], item["url"], directory))
            except (OSError, ValueError, KeyError) as error:
                errors.append(str(error))
        state = "parcial" if found and errors else "pendiente_pdf" if errors else "disponible"
        rows.extend(found)
        reports.append({"nombre":query["nombre"], "codigo":query["codigo"], "estado":state,
                        "farmacias":len({r["id"] for r in found}),
                        "documentos":[v["url"] for v in query.get("documentos", [])], "errores":errors})
        print(f"{query['nombre']}: {state}, {len(found)} guardias.", flush=True)
    rows = merge(rows)
    try:
        errors = locate(directory, rows, use_geocoder)
    except (OSError, ValueError) as error:
        reports.append({"nombre":"Coordenadas/catálogo provincial", "estado":"error", "error":str(error)})
        errors = [str(error)]
        print(f"ERROR publicación del catálogo: {error}", flush=True)
    return publish(target, rows, reports, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home()/".local/state/farmacia/jaen")
    parser.add_argument("--sin-red", action="store_true", help="Validar/publicar desde la caché de la misma fecha.")
    parser.add_argument("--geocode", action="store_true", help="Contrastar guardias sin coordenadas con POI exactos.")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite --geocode.")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red, args.geocode) else 1)
