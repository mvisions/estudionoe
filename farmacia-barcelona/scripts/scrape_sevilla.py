#!/usr/bin/env python3
"""Import dated official Sevilla posters, including the complete municipal index."""
import argparse
import hashlib
import http.cookiejar
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from complete_malaga import address_key, normalize_street

from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://www.farmaceuticosdesevilla.es/ciudadanos/utilidades/localizador-de-farmacias/"
HOST = "servicios.farmaceuticosdesevilla.es"
MONTHS = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "septiembre": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
}
DATE_RE = r"(\d{1,2})[\s-]+(?:DE\s+)?([a-zá]+)[\s-]+(?:DE\s+)?(\d{4})"
PHONE_RE = re.compile(r"\(?([69](?:[\s.-]*\d){8})\)?")
NS = {"h": "http://www.w3.org/1999/xhtml"}
REVIEWED_COORDINATES = Path(__file__).resolve().parent.parent / "data/coordenadas-sevilla-revisadas.json"
LOCATION_FIELDS = ("lat", "lng", "precision_ubicacion", "fuente_coordenadas",
                   "direccion_coordenadas", "nota_ubicacion")


class MunicipalIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.frames = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "iframe":
            self.frames.append(attrs.get("src", "").strip())
        elif tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = {"texto": "", "urls": []}
        elif tag == "a" and self.cell is not None:
            href = attrs.get("href", "")
            if "/images/farmaciasguardia/" in href:
                self.cell["urls"].append(href)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["texto"] += data

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if len(self.row) >= 6:
                self.rows.append({
                    "municipio": self.row[0]["texto"].strip(),
                    "agrupacion": self.row[1]["texto"].strip(),
                    "trimestres": [cell["urls"] for cell in self.row[2:6]],
                })
            self.row = None


def public_request(opener, url):
    request = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with opener.open(request, timeout=60) as response:
        return response.read()


def load_index(opener):
    parent = MunicipalIndex()
    parent.feed(public_request(opener, SOURCE).decode("utf-8"))
    iframe = next((url for url in parent.frames if urllib.parse.urlparse(url).hostname == HOST), None)
    if not iframe:
        raise ValueError("No se encontró el iframe público de carteles de Sevilla.")
    separator = "&" if "?" in iframe else "?"
    content = public_request(opener, iframe + separator + "limit=0").decode("utf-8")
    parser = MunicipalIndex()
    parser.feed(content)
    count = re.search(r"\bof\s+(\d+)\b", content)
    if not parser.rows or (count and len(parser.rows) != int(count.group(1))):
        raise ValueError("El índice municipal está vacío o la paginación está incompleta.")
    return parser.rows


def pdf_pages(content, include_words=False):
    result = subprocess.run(
        ["pdftotext", "-bbox-layout", "-", "-"], input=content, capture_output=True, check=True,
    )
    xml = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", result.stdout)
    root = ET.fromstring(xml)
    pages = []
    for page in root.findall(".//h:page", NS):
        lines = []
        for line in page.findall(".//h:line", NS):
            words = line.findall("h:word", NS)
            lines.append({
                "x": float(line.attrib["xMin"]), "y": float(line.attrib["yMin"]),
                "right": float(line.attrib["xMax"]),
                "text": " ".join(word.text or "" for word in words),
            })
        parsed = {"width": float(page.attrib["width"]), "lines": lines}
        if include_words:
            parsed["words"] = [{
                "x": float(word.attrib["xMin"]), "y": float(word.attrib["yMin"]),
                "right": float(word.attrib["xMax"]), "text": word.text or "",
            } for word in page.findall(".//h:word", NS)]
        pages.append(parsed)
    return pages


def parse_date(match):
    return date(int(match[2]), MONTHS[slugify(match[1])], int(match[0]))


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" \x03Ŀ»")


def make_pharmacy(text, locality, period, target, source, sector="", allow_missing_phone=False):
    text = clean(text)
    phones = list(PHONE_RE.finditer(text))
    phone = phones[0] if phones else None
    if not phone and not allow_missing_phone:
        raise ValueError(f"Registro sin teléfono reconocible: {locality}: {text}")
    number = re.sub(r"\D", "", phone.group(1)) if phone else None
    address = text[:phone.start()].rstrip(" ( -") if phone else re.split(r"\bT\s*:", text)[0].strip(" .-")
    name = text[phones[-1].end():].strip(" ).-") if phone else ""
    address = re.sub(r"\s*(?:-\s*)?T\s*:\s*(?:Tlfno\.)?\s*$", "", address, flags=re.IGNORECASE)
    if not address:
        raise ValueError(f"Registro sin dirección: {text}")
    override = re.match(r"^(El Viso del Alcor|Mairena del Alcor|La Rinconada|Tocina|Los Rosales)\s*-\s*(.*)", address, re.IGNORECASE)
    if override:
        locality, address = override.group(1).title(), override.group(2)
    special = re.search(r"\([^)]*(?:De|Hasta|A partir)[^)]*\)", address, re.IGNORECASE)
    if special:
        period = f"{period}; {special.group(0)}"
    identifier = hashlib.sha256(f"{slugify(locality)}:{number or slugify(address)}".encode()).hexdigest()[:16]
    return {
        "id": f"cof-sevilla-{identifier}", "cofm_id": None,
        "nombre": name, "direccion": address, "localidad": locality, "provincia": "Sevilla",
        "sector": sector, "telefono": number,
        "telefonos": list(dict.fromkeys(re.sub(r"\D", "", match.group(1)) for match in phones)),
        "guardia": True, "guardia_franja": period,
        "guardia_franjas": [period], "fecha_guardia": target.isoformat(), "fuente": source,
        "lat": None, "lng": None,
    }


def ordered(lines):
    return sorted(lines, key=lambda line: (round(line["y"], 1), line["x"]))


def parse_single(page, target, source):
    lines = ordered(page["lines"])
    header = next((line["text"] for line in lines if "desde" in line["text"] and "hasta" in line["text"]), "")
    dates = re.findall(DATE_RE, header, re.IGNORECASE)
    locality = re.search(r"Farmacias de Guardia de (.*?) desde", header, re.IGNORECASE)
    if len(dates) != 2 or not locality:
        raise ValueError("Cabecera municipal sin fechas completas.")
    start, end = map(parse_date, dates)
    if not start <= target <= end:
        return []
    city = clean(locality.group(1)).title()
    current = None
    period = ""
    records = []
    pending = ""

    def flush():
        nonlocal pending
        if pending and current == target:
            records.append(make_pharmacy(pending, city, period, target, source))
        pending = ""

    for line in lines:
        text = line["text"]
        day = re.fullmatch(r"(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{1,2})", text)
        if day:
            flush()
            current = next((start + timedelta(days=i) for i in range((end-start).days+1)
                            if (start + timedelta(days=i)).day == int(day.group(1))), None)
            period = ""
        elif re.search(r"(?:Día|Noche)\s*\(de|24 horas", text, re.IGNORECASE):
            flush()
            period = clean(text)
        elif "Ŀ" in text or "»" in text:
            flush()
            pending = clean(text)
        elif pending and current == target and line["x"] > 40 and line["y"] < 770:
            pending += " " + clean(text)
    flush()
    return records


def merge_records(records):
    merged = {}
    addresses = {}
    for record in records:
        if record["telefono"]:
            addresses[(slugify(record["localidad"]), slugify(record["direccion"]))] = record
    for record in records:
        if not record["telefono"]:
            known = addresses.get((slugify(record["localidad"]), slugify(record["direccion"])))
            if known:
                record["telefono"], record["id"] = known["telefono"], known["id"]
                record["telefonos"] = known["telefonos"]
    for record in records:
        key = record["id"]
        if key not in merged:
            merged[key] = {**record, "fuentes": [record["fuente"]], "guardia_franjas": list(record["guardia_franjas"])}
        else:
            if record["fuente"] not in merged[key]["fuentes"]:
                merged[key]["fuentes"].append(record["fuente"])
            for period in record["guardia_franjas"]:
                if period not in merged[key]["guardia_franjas"]:
                    merged[key]["guardia_franjas"].append(period)
            merged[key]["guardia_franja"] = " · ".join(merged[key]["guardia_franjas"])
    return list(merged.values())


def parse_grid(page, target, source):
    headers = [(line, re.search(DATE_RE, line["text"], re.IGNORECASE)) for line in page["lines"]]
    headers = sorted([(line, match) for line, match in headers if match and slugify(match.group(2)) in MONTHS],
                     key=lambda pair: pair[0]["x"])
    if not headers:
        raise ValueError("Cuadrícula sin fechas.")
    records = []
    for index, (header, match) in enumerate(headers):
        if parse_date(match.groups()) != target:
            continue
        center = (header["x"] + header["right"]) / 2
        centers = [(item["x"] + item["right"]) / 2 for item, _ in headers]
        left = (centers[index-1] + center)/2 if index else 0
        right = (center + centers[index+1])/2 if index+1 < len(headers) else page["width"]
        lines = ordered([line for line in page["lines"] if left <= line["x"] < right and line["y"] > header["y"] + 8])
        origin = min((line["x"] for line in lines if re.match(r"(?:Día|Noche)", line["text"])), default=left)
        address_start = origin + 80
        period = ""
        pending = None
        queued_city = ""

        def flush():
            nonlocal pending
            if pending:
                records.append(make_pharmacy(pending["address"], clean(pending["city"]), period, target, source,
                                             allow_missing_phone=True))
                pending = None

        rows = []
        for line in lines:
            if rows and abs(rows[-1]["y"] - line["y"]) < 2:
                rows[-1]["lines"].append(line)
            else:
                rows.append({"y": line["y"], "lines": [line]})
        for row in rows:
            group = row["lines"]
            text = " ".join(line["text"] for line in group)
            if re.match(r"(?:Día|Noche)\s*\(", text):
                flush()
                period = clean(text)
                continue
            if not period or row["y"] > 810:
                continue
            city = " ".join(line["text"] for line in group if line["x"] < address_start)
            address = " ".join(line["text"] for line in group if line["x"] >= address_start)
            phone_only = bool(re.fullmatch(r"[\s()\d.-]+", address))
            if pending and not PHONE_RE.search(pending["address"]) and phone_only:
                pending["address"] += " " + address
                if city:
                    if re.search(r"\b(?:de la|de las|del)\s*$", pending["city"], re.IGNORECASE):
                        pending["city"] += " " + city
                    else:
                        queued_city = city
                continue
            if address and not city and queued_city:
                city, queued_city = queued_city, ""
            if city and address:
                flush()
                pending = {"city": city, "address": address}
            elif pending:
                pending["city"] += " " + city if city else ""
                pending["address"] += " " + address if address else ""
        flush()
    return records


def parse_capital(page, target, source):
    text = " ".join(line["text"] for line in page["lines"])
    interval = re.search(r"SEMANA DEL\s+" + DATE_RE + r"\s+AL\s+" + DATE_RE, text, re.IGNORECASE)
    if not interval:
        raise ValueError("Cartel de capital sin semana reconocible.")
    start, end = parse_date(interval.groups()[:3]), parse_date(interval.groups()[3:])
    if not start <= target <= end:
        return []
    records = []
    day_names = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = page["width"]
    bounds = [0, width*.245, width*.49, width*.73, width]
    night = next((line["y"] for line in page["lines"] if "URGENCIA DE NOCHE" in line["text"]), None)
    if night is None:
        raise ValueError("No se encontró el horario de noche de la capital.")
    for column in range(4):
        if target.weekday() == 6 and column < 3:
            selected = [line for line in page["lines"] if bounds[column] <= line["x"] < bounds[column+1] and line["y"] > night+15]
        elif target.weekday() != 6 and column == 3:
            continue
        else:
            selected = [line for line in page["lines"] if bounds[column] <= line["x"] < bounds[column+1] and line["y"] > 95]
        selected = ordered(selected)
        sector = ""
        pending = ""
        period = "Día (de 9:30 a 22:00)"

        def flush():
            nonlocal pending
            if pending:
                normalized = slugify(pending)
                only = re.search(r"solo-(lunes|martes|miercoles|jueves|viernes|sabado|domingo)", normalized)
                if only and only.group(1) != day_names[target.weekday()]:
                    pending = ""
                    return
                if "excepto-sabado" in normalized and target.weekday() == 5:
                    pending = ""
                    return
                value = re.sub(r"^(?:Sólo|Solo)\s+\w+\.\s*", "", pending, flags=re.IGNORECASE)
                locality = "Dos Hermanas" if "montequinto" in slugify(value) else "Sevilla"
                record = make_pharmacy(value, locality, period, target, source, sector, allow_missing_phone=True)
                records.append(record)
                pending = ""

        for line in selected:
            text = line["text"]
            next_period = "Noche (de 22:00 a 9:30)" if column < 3 and line["y"] > night else "Día (de 9:30 a 22:00)"
            if next_period != period:
                flush()
                period = next_period
            if text.startswith("ZONA "):
                flush()
                sector = text
            elif text.startswith("»"):
                flush()
                pending = clean(text)
            elif pending:
                pending += " " + clean(text)
        flush()
    return records


def parse_document(content, target, source, pages=None):
    if not content.startswith(b"%PDF"):
        raise ValueError("El cartel no es un PDF.")
    pages = pdf_pages(content) if pages is None else pages
    if not any(page["lines"] for page in pages):
        if Path(source).name == "ModificacionesSevilla.pdf" and len(pages) == 1:
            image = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-scale-to", "128", "-gray", "-"],
                input=content, capture_output=True, check=True,
            ).stdout
            header = re.match(rb"P5\s+(\d+)\s+(\d+)\s+255\s", image)
            if header and image[header.end():] == b"\xff" * (int(header[1]) * int(header[2])):
                return []
        raise ValueError("PDF sin texto; necesita revisión visual/OCR.")
    records = []
    for page in pages:
        if not page["lines"]:
            continue
        text = " ".join(line["text"] for line in page["lines"])
        if "SEMANA DEL" in text:
            rows = parse_capital(page, target, source)
        elif "desde" in text and "hasta" in text:
            rows = parse_single(page, target, source)
        else:
            rows = parse_grid(page, target, source)
        records.extend(rows)
    return merge_records(records)


def reviewed_records(content, target, source):
    path = OUT_DIR.parent.parent / "data" / "sevilla-carteles-revisados.json"
    reviews = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(content).hexdigest()
    records = []
    for review in reviews:
        if review["documento"] == Path(source).name and review["fecha"] == target.isoformat():
            if review["sha256"] != digest:
                raise ValueError("El cartel revisado ha cambiado; requiere nueva revisión de la imagen.")
            for period in review["franjas"]:
                record = make_pharmacy(review["registro"], review["localidad"], period, target, source)
                record["revision"] = f"visual, página {review['pagina']}"
                records.append(record)
    return records


def street_query(address):
    street = normalize_street(address)
    street = re.sub(r"\([^)]*\)", "", street)
    street = re.sub(r"\b(?:N[.º°]+\s*|n\.\s*)(?=\d)", "", street, flags=re.IGNORECASE)
    street = re.sub(r"\b(?:AVD|AVDA)\.?(?=\s|del\b|de\b)", "Avenida ", street, flags=re.IGNORECASE)
    street = re.sub(r"\bPZA\.?(?=\s|de\b)", "Plaza ", street, flags=re.IGNORECASE)
    house = re.search(r",\s*(\d+(?:-\d+)?[A-Z]?)(?=\s|[.,;]|$)", street, re.IGNORECASE)
    if not house:
        house = re.search(r"\s+(\d+(?:-\d+)?[A-Z]?)(?!\d)(?=\s*(?:$|[.,;]|[-(]))", street, re.IGNORECASE)
    if house:
        return clean(street[:house.end()])
    return clean(re.split(r"\s+-\s+|\.\s+(?:Frente|Junto|Esq|Entre)", street, flags=re.IGNORECASE)[0])


def saved_address_signature(address, locality):
    key = address_key(street_query(address), locality)
    if not key:
        return None
    city, road = key
    if road and road[0] in {"calle", "avenida", "plaza", "carretera", "paseo"}:
        road = road[1:]
    return city, road


def apply_reviewed_location(record, reviewed):
    review = reviewed.get(record["id"])
    if not review:
        return False
    if (record["direccion"] not in [review["direccion"], *review.get("direcciones_alternativas", [])]
            or review["telefono"] not in record.get("telefonos", [])):
        print(f"AVISO {record['id']}: dirección/teléfono cambiados; ubicación revisada no reutilizada.", flush=True)
        if record.get("direccion_coordenadas"):
            record["lat"] = record["lng"] = None
            for field in LOCATION_FIELDS[2:]:
                record.pop(field, None)
        return False
    lat, lng = review["lat"], review["lng"]
    if not (36.8 < lat < 38.3 and -6.6 < lng < -4.6):
        raise ValueError(f"Coordenadas revisadas fuera de rango: {record['id']}")
    record.update({"lat": lat, "lng": lng, "precision_ubicacion": "farmacia",
                   "fuente_coordenadas": review["fuente"],
                   "direccion_coordenadas": record["direccion"],
                   "nota_ubicacion": review.get("nota_ubicacion", "")})
    return True


def refresh_saved_coordinates():
    reviewed = {row["id"]: row for row in json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))}
    updated = 0
    counts = {}
    for path in [OUT_DIR / "farmacias-sevilla.json", *sorted(OUT_DIR.glob("guardias-sevilla-*.json"))]:
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        previous = json.dumps(rows, sort_keys=True)
        for row in rows:
            apply_reviewed_location(row, reviewed)
        if json.dumps(rows, sort_keys=True) != previous:
            write_json(path, rows)
            updated += 1
        if path.name.startswith("guardias-"):
            day = path.stem.removeprefix("guardias-sevilla-")
            counts[day] = sum(row.get("lat") is not None and row.get("lng") is not None for row in rows)
            report_path = OUT_DIR / f"cobertura-sevilla-{day}.json"
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if report.get("con_coordenadas") != counts[day]:
                    report["con_coordenadas"] = counts[day]
                    write_json(report_path, report)
    for path in OUT_DIR.glob("cobertura-sevilla-*-T*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for day in report["fechas"]:
            count = counts.get(day["fecha"])
            if count is not None and day.get("con_coordenadas") != count:
                day["con_coordenadas"] = count
                changed = True
        if changed:
            write_json(path, report)
    print(f"Ubicaciones revisadas aplicadas: {updated} catálogos/calendarios actualizados.", flush=True)
    return updated


def locate_saved(records):
    existing = OUT_DIR / "farmacias-sevilla.json"
    by_id = {}
    if existing.exists():
        by_id = {row["id"]: row for row in json.loads(existing.read_text(encoding="utf-8"))}
    osm_path = OUT_DIR / "farmacias-osm-espana.json"
    osm = json.loads(osm_path.read_text(encoding="utf-8")) if osm_path.exists() else []
    reviewed = {row["id"]: row for row in json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))}
    for record in records:
        review = reviewed.get(record["id"])
        if apply_reviewed_location(record, reviewed):
            continue
        old = by_id.get(record["id"])
        if (old and old.get("lat") is not None and old.get("lng") is not None
                and not review
                and old.get("direccion_coordenadas", record["direccion"]) == record["direccion"]):
            for field in LOCATION_FIELDS:
                if field in old:
                    record[field] = old[field]
            continue
        key = saved_address_signature(record["direccion"], record["localidad"])
        matches = [row for row in osm if (
            (re.sub(r"\D", "", str(row.get("telefono", ""))).removeprefix("34") in record["telefonos"])
            or (key and key == saved_address_signature(row.get("direccion", ""), row.get("localidad", ""))))
                   and row.get("lat") is not None and row.get("lng") is not None
                   and 36.8 < row["lat"] < 38.3 and -6.6 < row["lng"] < -4.6]
        if len(matches) == 1:
            record.update({"lat": matches[0]["lat"], "lng": matches[0]["lng"],
                           "precision_ubicacion": "farmacia", "fuente_coordenadas": "https://www.openstreetmap.org"})
    return by_id


def normalize_municipalities(records, municipalities):
    def signature(value):
        return "-".join(word for word in slugify(value).split("-") if word not in {"de", "del", "la", "el", "los", "las"})
    names = {signature(item["municipio"]): item["municipio"] for item in municipalities}
    for record in records:
        record["localidad"] = names.get(signature(record["localidad"]), record["localidad"])


def geocode_sevilla(record):
    address = street_query(record["direccion"])
    locality = record["localidad"]
    if any(word in slugify(address) for word in ("servicios-localizables", "urgencias-diurnas", "urgencias-nocturnas")):
        return None
    query = f"{address}, {locality}, Sevilla, España"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "jsonv2", "limit": 5, "countrycodes": "es",
        "addressdetails": 1, "viewbox": "-6.6,38.3,-4.6,36.8", "bounded": 1,
    })
    request = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0 (public pharmacy map)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        candidates = json.load(response)
    candidates.sort(key=lambda candidate: candidate.get("type") != "pharmacy")
    for item in candidates:
        details = item.get("address", {})
        names = [details.get(key, "") for key in ("city", "town", "village", "municipality", "suburb", "city_district")]
        lat, lng = float(item["lat"]), float(item["lon"])
        if slugify(locality) not in [slugify(name) for name in names] or not (36.8 < lat < 38.3 and -6.6 < lng < -4.6):
            continue
        if item.get("type") in {"administrative", "city", "town", "village"}:
            continue
        number = re.search(r"\b(\d+)\b", address)
        exact = item.get("type") == "pharmacy" and number and details.get("house_number") == number.group(1)
        return {"lat": lat, "lng": lng, "precision_ubicacion": "farmacia" if exact else "aproximada",
                "fuente_coordenadas": "https://www.openstreetmap.org"}
    return None


def quarter_dates(year, quarter):
    start = date(year, (quarter-1)*3+1, 1)
    end = date(year+1, 1, 1) if quarter == 4 else date(year, quarter*3+1, 1)
    return [start + timedelta(days=index) for index in range((end-start).days)]


def collect_day(documents, target, municipalities):
    rows = []
    reports = []
    for url, document in documents.items():
        try:
            if "error" in document:
                raise ValueError(document["error"])
            content = document["content"]
            manual = reviewed_records(content, target, url)
            records = merge_records(parse_document(content, target, url, document["pages"]) + manual)
            rows.extend(records)
            state = "disponible" if records else (
                "sin_modificaciones" if Path(url).name == "ModificacionesSevilla.pdf" else "sin_fecha"
            )
            reports.append({"url": url, "estado": state, "farmacias": len(records),
                            "revision_visual": bool(manual)})
        except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
            reports.append({"url": url, "estado": "error", "error": str(error)})
    rows = merge_records(rows)
    normalize_municipalities(rows, municipalities)
    return rows, reports


def publish_day(target, rows, reports, municipalities):
    complete = bool(reports) and all(
        item["estado"] in {"disponible", "sin_modificaciones"} for item in reports
    )
    path = OUT_DIR / f"guardias-sevilla-{target.isoformat()}.json"
    published = bool(rows) and (complete or not path.exists())
    report = {
        "fecha": target.isoformat(), "provincia": "Sevilla", "fuente": SOURCE,
        "consultado": datetime.now(timezone.utc).isoformat(), "completa": complete,
        "municipios": municipalities, "consultas": reports,
        "farmacias": len(rows),
        "con_coordenadas": sum(row["lat"] is not None and row["lng"] is not None for row in rows),
        "calendario_actualizado": published,
    }
    write_json(OUT_DIR / f"cobertura-sevilla-{target.isoformat()}.json", report)
    if published:
        write_json(path, rows)
    return report


def prepare_document(opener, url, directory=None, cache=None):
    if directory:
        content = (directory / Path(urllib.parse.urlparse(url).path).name).read_bytes()
    else:
        content = public_request(opener, url)
    if not content.startswith(b"%PDF"):
        raise ValueError("El cartel no es un PDF.")
    if cache is None:
        return {"content": content, "pages": pdf_pages(content)}
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    digest = hashlib.sha256(content).hexdigest()
    converted = cache / f"{key}.json"
    if converted.exists():
        saved = json.loads(converted.read_text(encoding="utf-8"))
        if saved["sha256"] == digest:
            return {"content": content, "pages": saved["pages"]}
    pages = pdf_pages(content)
    write_json(converted, {"sha256": digest, "pages": pages})
    return {"content": content, "pages": pages}


def scrape_quarter(args, municipalities, opener):
    reviewed = {row["id"]: row for row in json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))}
    urls = sorted({url for municipality in municipalities for url in municipality["trimestres"][args.trimestre-1]})
    documents = {}
    for url in urls:
        if urllib.parse.urlparse(url).hostname != HOST:
            raise ValueError("El índice contiene un documento fuera del proveedor oficial.")
        try:
            documents[url] = prepare_document(opener, url, args.documentos, args.cache_documentos)
            print(f"Preparado {Path(url).name}", flush=True)
        except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
            documents[url] = {"error": str(error)}
            print(f"ERROR {Path(url).name}: {error}", flush=True)
    if not documents:
        raise ValueError("No hay documentos para el trimestre seleccionado.")
    days = {}
    unique = {}
    for target in quarter_dates(args.anio, args.trimestre):
        rows, reports = collect_day(documents, target, municipalities)
        days[target] = (rows, reports)
        for row in rows:
            unique.setdefault(row["id"], row)
        available = sum(report["estado"] == "disponible" for report in reports)
        print(f"{target}: {len(rows)} guardias; {available}/{len(documents)} documentos con fecha.", flush=True)
    catalogue = locate_saved(list(unique.values()))
    if args.geocode:
        for index, row in enumerate(unique.values(), 1):
            if row["lat"] is not None and row["lng"] is not None:
                continue
            try:
                position = geocode_sevilla(row)
            except (OSError, ValueError) as error:
                raise RuntimeError(f"No se pudo geocodificar {row['id']}: {error}") from error
            if position:
                row.update(position)
                catalogue[row["id"]] = {**row, "guardia": False}
                write_json(OUT_DIR / "farmacias-sevilla.json", list(catalogue.values()))
            print(f"Ubicación {index}/{len(unique)}: {row['localidad']}: {position or 'pendiente'}", flush=True)
            time.sleep(1.1)
    summary = []
    for target, (rows, reports) in days.items():
        for row in rows:
            location = unique[row["id"]]
            if location.get("direccion_coordenadas", row["direccion"]) == row["direccion"]:
                for field in LOCATION_FIELDS:
                    if field in location:
                        row[field] = location[field]
            apply_reviewed_location(row, reviewed)
        report = publish_day(target, rows, reports, municipalities)
        summary.append({key: report[key] for key in (
            "fecha", "completa", "farmacias", "con_coordenadas", "calendario_actualizado",
        )})
        if report["calendario_actualizado"]:
            for row in rows:
                catalogue[row["id"]] = {**row, "guardia": False}
    write_json(OUT_DIR / "farmacias-sevilla.json", list(catalogue.values()))
    write_json(OUT_DIR / f"cobertura-sevilla-{args.anio}-T{args.trimestre}.json", {
        "provincia": "Sevilla", "anio": args.anio, "trimestre": args.trimestre,
        "fuente": SOURCE, "municipios": len(municipalities), "documentos": len(documents),
        "fechas": summary, "completa": all(day["completa"] for day in summary),
    })
    print(f"Trimestre procesado: {len(summary)} fechas, {sum(day['completa'] for day in summary)} completas; "
          f"{len(unique)} farmacias/servicios diferentes.", flush=True)
    if not all(day["completa"] for day in summary):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    period = parser.add_mutually_exclusive_group()
    period.add_argument("--fecha", type=date.fromisoformat)
    period.add_argument("--trimestre", type=int, choices=range(1, 5), help="Generar todas las fechas del trimestre.")
    period.add_argument("--trimestre-actual", action="store_true", help="Consultar el trimestre y año actuales en cada ejecución.")
    parser.add_argument("--anio", type=int, default=date.today().year)
    parser.add_argument("--documentos", type=Path, help="Directorio de PDFs descargados; sin descargar de nuevo.")
    parser.add_argument("--geocode", action="store_true", help="Geocodificar ubicaciones pendientes con Nominatim.")
    parser.add_argument("--cache-documentos", type=Path, help="Reutilizar conversiones si los PDFs descargados no han cambiado.")
    parser.add_argument("--actualizar-coordenadas", action="store_true", help="Actualizar ubicaciones revisadas en los calendarios guardados, sin descargar carteles.")
    args = parser.parse_args()
    if not args.fecha:
        args.fecha = date.today()
    if args.trimestre_actual:
        args.trimestre = (args.fecha.month-1)//3+1
        args.anio = args.fecha.year
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    refresh_saved_coordinates()
    if args.actualizar_coordenadas:
        return
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    if args.documentos:
        index = MunicipalIndex()
        index.feed((args.documentos / "listado.html").read_text(encoding="utf-8"))
        municipalities = index.rows
    else:
        municipalities = load_index(opener)
    if not municipalities:
        raise ValueError("No hay municipios en el índice oficial.")
    if args.trimestre:
        scrape_quarter(args, municipalities, opener)
        return
    quarter = (args.fecha.month-1)//3
    urls = sorted({url for municipality in municipalities for url in municipality["trimestres"][quarter]})
    rows = []
    reports = []
    for url in urls:
        if urllib.parse.urlparse(url).hostname != HOST:
            raise ValueError("El índice contiene un documento fuera del proveedor oficial.")
        try:
            document = prepare_document(opener, url, args.documentos, args.cache_documentos)
            content = document["content"]
            manual = reviewed_records(content, args.fecha, url)
            records = merge_records(parse_document(content, args.fecha, url, document["pages"]) + manual)
            rows.extend(records)
            state = "disponible" if records else ("sin_modificaciones" if Path(url).name == "ModificacionesSevilla.pdf" else "sin_fecha")
            reports.append({"url": url, "estado": state, "farmacias": len(records),
                            "revision_visual": bool(manual)})
            print(f"{Path(url).name}: {len(records)} farmacias", flush=True)
        except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
            reports.append({"url": url, "estado": "error", "error": str(error)})
            print(f"ERROR {Path(url).name}: {error}", flush=True)
    rows = merge_records(rows)
    normalize_municipalities(rows, municipalities)
    complete = all(item["estado"] in {"disponible", "sin_modificaciones"} for item in reports)
    daily_path = OUT_DIR / f"guardias-sevilla-{args.fecha.isoformat()}.json"
    if not complete and daily_path.exists():
        write_json(OUT_DIR / f"cobertura-sevilla-{args.fecha.isoformat()}.json", {
            "fecha": args.fecha.isoformat(), "provincia": "Sevilla", "fuente": SOURCE,
            "consultado": datetime.now(timezone.utc).isoformat(), "completa": False,
            "municipios": municipalities, "consultas": reports,
        })
        raise RuntimeError("Cobertura incompleta: no se reemplaza el calendario anterior de Sevilla.")
    catalogue = locate_saved(rows)
    current_ids = {row["id"] for row in rows}
    catalogue = {key: row for key, row in catalogue.items()
                 if row.get("fecha_guardia") != args.fecha.isoformat() or key in current_ids}
    if args.geocode:
        for index, record in enumerate(rows, 1):
            if record.get("lat") is not None and record.get("lng") is not None:
                continue
            try:
                position = geocode_sevilla(record)
            except (OSError, ValueError) as error:
                raise RuntimeError(f"No se pudo geocodificar {record['id']}: {error}") from error
            if position:
                record.update(position)
                catalogue[record["id"]] = {**record, "guardia": False}
                write_json(OUT_DIR / "farmacias-sevilla.json", list(catalogue.values()))
            print(f"Ubicación {index}/{len(rows)} {record['localidad']}: {position or 'pendiente'}", flush=True)
            time.sleep(1.1)
    for row in rows:
        catalogue[row["id"]] = {**row, "guardia": False}
    date_string = args.fecha.isoformat()
    report = {
        "fecha": date_string, "provincia": "Sevilla", "fuente": SOURCE,
        "consultado": datetime.now(timezone.utc).isoformat(),
        "completa": complete,
        "municipios": municipalities, "consultas": reports,
        "farmacias": len(rows), "con_coordenadas": sum(row["lat"] is not None and row["lng"] is not None for row in rows),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_DIR / f"cobertura-sevilla-{date_string}.json", report)
    if rows:
        write_json(OUT_DIR / f"guardias-sevilla-{date_string}.json", rows)
        write_json(OUT_DIR / "farmacias-sevilla.json", list(catalogue.values()))
    print(f"Publicadas {len(rows)} guardias para {date_string}. Consultar cobertura para documentos no resueltos.")
    if not rows or not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
