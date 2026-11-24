#!/usr/bin/env python3
"""Import verified cells from the COF Palencia's dated PDF calendars."""
import argparse
import hashlib
import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import slugify
from scrape_sevilla import MONTHS, PHONE_RE, pdf_pages, saved_address_signature

SOURCE = "https://www.cofpalencia.org/PUBLICO/CALENDARIOS%20DE%20GUARDIA/menu_calendarios_guardia.htm"
CATALOGUE = "https://www.cofpalencia.org/PUBLICO/FARMACIA/capital.htm"
WEEKDAYS = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
DATE_RE = re.compile(r"(\d{1,2})\s+(?:DE\s+)?(SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)", re.I)


def text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()


def record(name, address, locality, source):
    if not address or not locality:
        raise ValueError("Farmacia sin dirección o municipio; no se inventa una ubicación.")
    key = saved_address_signature(address, locality)
    identifier = hashlib.sha256(json.dumps(key or slugify(address + locality)).encode()).hexdigest()[:16]
    return {"id": "cof-palencia-" + identifier, "nombre": name, "direccion": address,
            "localidad": locality, "provincia": "Palencia", "fuente": source,
            "lat": None, "lng": None, "guardia": False}


def catalogue(content):
    rows = []
    for block in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content, re.S | re.I):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", block, re.S | re.I)
        if len(cells) != 4:
            continue
        contact = re.split(r"\bTELEFONO\b", text(cells[2]), flags=re.I)
        if len(contact) != 2:
            raise ValueError("Fila del directorio capitalino sin contacto verificable.")
        row = record(text(cells[0]), contact[0].strip(), "Palencia", CATALOGUE)
        phone = re.sub(r"\D", "", contact[1])
        if len(phone) != 9:
            raise ValueError("Teléfono del directorio capitalino con longitud inválida.")
        row["telefono"] = phone
        rows.append(row)
    if not rows:
        raise ValueError("Directorio oficial de Palencia vacío.")
    return rows


def links(content):
    result = []
    for href, label in re.findall(r'<a\b[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>',
                                  content, re.I | re.S):
        url = urllib.parse.urljoin(SOURCE, urllib.parse.quote(html.unescape(href), safe="/%:"))
        if urllib.parse.urlparse(url).hostname != "www.cofpalencia.org":
            raise ValueError("El enlace PDF no pertenece al colegio oficial.")
        result.append({"url": url, "nombre": text(label)})
    if not result:
        raise ValueError("Índice oficial sin calendarios PDF.")
    return result


def get_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def cached(url, cache, offline, resume):
    path = cache / (hashlib.sha256(url.encode()).hexdigest()[:20] +
                    (".pdf" if url.endswith(".pdf") else ".html"))
    if offline or (resume and path.exists()):
        return path.read_bytes()
    content = get_bytes(url)
    path.write_bytes(content)
    return content


def cell(lines, start, end, left, right):
    selected = sorted((line for line in lines if start <= line["y"] < end and
                       left <= (line["x"] + line["right"]) / 2 < right),
                      key=lambda line: (round(line["y"] / 3), line["x"]))
    return [line["text"] for line in selected]


def pharmacy_from_cell(values, source, locality=None):
    combined = " ".join(values)
    match = re.search(r"\(?\s*((?:C\s*/|Calle\b|Mayor Principal\b|Plaza\b|PZ\b|AV(?:DA)?\.?\b|Paseo\b|Crta\.?\b).*)",
                      combined, re.I)
    if not match:
        raise ValueError(f"Celda sin dirección verificable: {combined}")
    name = combined[:match.start()].strip()
    address = match[1]
    if locality is None:
        town = re.search(r"\b(CARRI[ÓO]N DE LOS CONDES|SALDA[ÑN]A|SAHAG[ÚU]N|VILLADA|CISNEROS)\b",
                         address, re.I)
        if not town:
            raise ValueError(f"Celda sin municipio verificable: {combined}")
        locality = text(town[0]).title()
        address = address[:town.start()].strip(" ()-*")
    else:
        address = address.split("(")[0].strip(" )*")
    row = record(name, address, locality, source)
    # Referrals to León are published as such, not relabelled as Palencia pharmacies.
    if slugify(locality) == "sahagun":
        row["provincia"] = "León"
    return row


def duty(row, day, target, section, zone, hours=None):
    prior = day < target
    if prior and section == "diurna":
        return None
    row = {**row, "guardia": True, "fecha_guardia": str(target),
           "localidades_atendidas": [zone], "provincias_atendidas": ["Palencia"],
           "guardia_intervalos": []}
    label = ("Madrugada del día anterior" if prior else "Guardia " + section) + f" · {zone}"
    if hours:
        start, end = hours
        begin = datetime.combine(day, datetime.strptime(start, "%H:%M").time())
        finish = datetime.combine(day, datetime.strptime(end, "%H:%M").time())
        if finish <= begin:
            finish += timedelta(days=1)
        if prior:
            begin = datetime.combine(target, datetime.min.time())
        tz = ZoneInfo("Europe/Madrid")
        row["guardia_intervalos"] = [{"inicio": begin.replace(tzinfo=tz).isoformat(),
                                      "fin": finish.replace(tzinfo=tz).isoformat()}]
        label += f" · {'00:00' if prior else start}–{end}"
    else:
        label += " · Horario exacto pendiente; confirmar por teléfono"
    row["guardia_franjas"] = [label]
    row["guardia_franja"] = label
    return row


def parse_weekly(page, year, zone, target, source, weekend_layout=None):
    lines = page.get("words", page["lines"])
    starts = sorted(line["y"] for line in lines if line["text"] == "SEMANA")
    if not starts:
        raise ValueError("No se reconocen las filas semanales del cartel.")
    nocturnal = next((line for line in lines if line["text"] == "NOCTURNA"), None)
    diurnal = next((line for line in lines if line["text"] == "DIURNA"), None)
    if not nocturnal or not diurnal:
        raise ValueError("Columnas diurna/nocturna no verificadas.")
    centers = [(line["x"] + line["right"]) / 2 for line in (diurnal, nocturnal)]
    boundary = sum(centers) / 2
    first_column = page["width"] * 0.29
    footer = min((line["y"] for line in page["lines"] if line["y"] > starts[-1] and
                  ("ESTA INFORMACION" in line["text"] or line["text"].startswith("(*)"))),
                 default=starts[-1] + 95)
    rows = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else footer
        dates = list(DATE_RE.finditer(" ".join(cell(lines, start, end, 0, first_column))))
        if len(dates) != 2:
            raise ValueError("Rango semanal sin dos fechas verificables.")
        first, last = [date(year, MONTHS[slugify(match[2])], int(match[1])) for match in dates]
        if last < first:
            raise ValueError("Rango semanal invertido.")
        for day in (target, target - timedelta(days=1)):
            if not first <= day <= last:
                continue
            columns = [("diurna", first_column, boundary, ("10:00", "22:00"), None),
                       ("nocturna", boundary, page["width"], ("22:00", "10:00"), None)]
            if weekend_layout:
                if day.weekday() < 5:
                    raise ValueError("Calendario especial entre semana: festivos y subturnos pendientes de verificar.")
                if weekend_layout == "villada":
                    columns = [("24 horas", page["width"] * 0.75, page["width"], None, None)]
                elif weekend_layout == "venta":
                    columns = [("diurna", page["width"] * 0.29, page["width"] * 0.53,
                                ("09:30", "20:00"), "Venta de Baños"),
                               ("diurna", page["width"] * 0.53, page["width"] * 0.76,
                                ("20:00", "22:00"), "Venta de Baños"),
                               ("nocturna", page["width"] * 0.76, page["width"],
                                ("22:00", "09:30"), "Venta de Baños")]
                else:
                    raise ValueError("Plantilla semanal especial no reconocida.")
            for section, left, right, hours, locality in columns:
                if day < target and section == "diurna":
                    continue
                row = pharmacy_from_cell(cell(lines, start - 2, end, left, right), source, locality)
                item = duty(row, day, target, section, zone, hours)
                rows.append(item)
    return rows


def parse_capital(page, year, target, source):
    lines = page.get("words", page["lines"])
    starts = sorted((line for line in lines if line["x"] < page["width"] * 0.17 and
                     slugify(line["text"]).upper() in WEEKDAYS), key=lambda line: line["y"])
    if not starts:
        raise ValueError("Cartel capitalino sin días de semana verificables.")
    rows = []
    for index, heading in enumerate(starts):
        start = heading["y"] - 2
        end = starts[index + 1]["y"] - 2 if index + 1 < len(starts) else start + 95
        date_text = " ".join(cell(lines, start, end, 0, page["width"] * 0.17))
        match = DATE_RE.search(date_text)
        if not match:
            raise ValueError("Fila capitalina sin fecha verificable.")
        day = date(year, MONTHS[slugify(match[2])], int(match[1]))
        if WEEKDAYS[day.weekday()] != slugify(heading["text"]).upper():
            raise ValueError("El día de semana no coincide con el año del PDF.")
        if day not in (target, target - timedelta(days=1)):
            continue
        for section, left, right in (("diurna", 0.17, 0.405), ("diurna", 0.405, 0.694),
                                     ("nocturna", 0.694, 1)):
            if day < target and section == "diurna":
                continue
            row = pharmacy_from_cell(cell(lines, start, end, page["width"] * left,
                                           page["width"] * right), source, "Palencia")
            hours = ("22:00", "10:00") if section == "nocturna" else None
            rows.append(duty(row, day, target, section, "Palencia", hours))
    return rows


def raster(content):
    result = subprocess.run(["pdftoppm", "-r", "72", "-singlefile", "-"],
                            input=content, capture_output=True, check=True)
    header = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", result.stdout)
    if not header:
        raise ValueError("Imagen PPM del calendario no reconocida.")
    width, height = map(int, header.groups())
    pixels = result.stdout[header.end():]
    if len(pixels) != width * height * 3:
        raise ValueError("Imagen del calendario incompleta.")
    return width, height, pixels


def pixel(image, x, y):
    width, height, pixels = image
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError("Muestra de color fuera del calendario.")
    index = (y * width + x) * 3
    return tuple(pixels[index:index + 3])


def background(image, left, top, right, bottom):
    colors = Counter(pixel(image, x, y) for y in range(round(top), round(bottom))
                     for x in range(round(left), round(right)))
    if not colors:
        raise ValueError("Celda de color vacía.")
    color, count = colors.most_common(1)[0]
    if count / colors.total() < 0.4 or color in ((255, 255, 255), (0, 0, 0)):
        raise ValueError("Color de celda sin correspondencia inequívoca.")
    return color


def matching_color(color, palette):
    matches = [key for key in palette if max(abs(a - b) for a, b in zip(color, key)) <= 40]
    if len(matches) != 1:
        raise ValueError("Color del día ausente o ambiguo en la leyenda de farmacias.")
    return matches[0]


def color_pharmacy(values, source, locality):
    combined = " ".join(values)
    phones = list(PHONE_RE.finditer(combined))
    if not phones:
        raise ValueError(f"Leyenda sin teléfono reconocible: {combined}")
    address_start = re.search(r"\(|\bC\s*/|\bConstituci[oó]n\b", combined, re.I)
    if not address_start:
        raise ValueError(f"Leyenda sin dirección reconocible: {combined}")
    name = combined[:address_start.start()].strip()
    address = combined[address_start.start():phones[0].start()].strip()
    address = re.split(r"\b(?:TFNO|TLFN|TLFO|TLF)(?:N?[º°])?|\bTel[eé]fono\b", address, flags=re.I)[0]
    if "barruelo-de-santullan" in slugify(address):
        locality = "Barruelo de Santullán"
        address = re.split(r"\(\s*BARRUELO", address, flags=re.I)[0]
    row = record(name, address.strip(" ()*:.-"), locality, source)
    row["telefono"] = re.sub(r"\D", "", phones[0][1])
    return row


def parse_colors(content, page, zone, target, source, catalogue_rows=None):
    cervera = slugify(zone) == "cervera-de-pisuerga"
    localities = {"cervera-de-pisuerga": "Cervera de Pisuerga",
                  "salinas-de-pisuerga": "Salinas de Pisuerga",
                  "san-salvador-de-cantamuda": "San Salvador de Cantamuda",
                  "castrejon-de-la-pena": "Castrejón de la Peña"}
    if cervera:
        services = [line for line in page["lines"] if slugify(line["text"]) in localities
                    and line["x"] < page["width"] * 0.4]
    else:
        services = [line for line in page["lines"] if line["text"] == "GUARDIA 24 HORAS"]
    services.sort(key=lambda line: line["y"])
    if cervera and (len(services) != 5 or sum(line["text"] == "GUARDIA 24H" for line in page["lines"]) != 4):
        raise ValueError("Leyenda rural de Cervera incompleta o modificada.")
    if not services:
        raise ValueError("Leyenda por colores sin turnos de 24 horas verificables.")
    image = raster(content)
    width = page["width"]
    palette = {}
    for service in services:
        y = round(service["y"] + 5)
        color = background(image, width * 0.4, y - 8, width * 0.85, y + 8)
        left = next((x for x in range(round(service["right"] + 2), round(width * 0.9))
                     if any(pixel(image, x, at) == color for at in range(y - 7, y + 8))), None)
        if left is None:
            raise ValueError("La leyenda no delimita una celda de farmacia coloreada.")
        def divider(at):
            samples = [pixel(image, x, at) for x in range(round(width * 0.35), round(width * 0.85))]
            return sum(max(value) < 100 for value in samples) / len(samples) > 0.85
        top = next((at for at in range(y - 1, max(0, y - 85), -1) if divider(at)), None)
        bottom = next((at for at in range(y + 1, min(image[1], y + 85)) if divider(at)), None)
        if top is None or bottom is None:
            raise ValueError("Bordes de la fila coloreada no verificables.")
        values = cell(page["words"], top - 5, bottom - 5, left, width)
        locality = localities[slugify(service["text"])] if cervera else zone
        palette.setdefault(color, []).append(color_pharmacy(values, source, locality))
    if catalogue_rows is not None:
        catalogue_rows.extend(row for pharmacies in palette.values() for row in pharmacies)
    months = sorted((word for word in page["words"] if word["text"].upper() in
                     ("OCTUBRE", "NOVIEMBRE", "DICIEMBRE") and word["y"] < services[0]["y"]),
                    key=lambda word: word["x"])
    if len(months) != 3:
        raise ValueError("El calendario por colores no contiene los tres meses esperados.")
    rows = []
    for day in (target, target - timedelta(days=1)):
        index = next((i for i, word in enumerate(months) if MONTHS[slugify(word["text"])] == day.month), None)
        if index is None:
            raise ValueError("El calendario por colores no incluye la madrugada del mes anterior.")
        centers = [(word["x"] + word["right"]) / 2 for word in months]
        left = (centers[index - 1] + centers[index]) / 2 if index else 0
        right = (centers[index] + centers[index + 1]) / 2 if index < 2 else width
        dates = [word for word in page["words"] if left <= word["x"] < right and
                 months[index]["y"] + 10 < word["y"] < services[0]["y"] - 25 and
                 re.fullmatch(r"\d{1,2}\*?", word["text"])]
        if sorted(int(word["text"].rstrip("*")) for word in dates) != list(range(1, monthrange(day.year, day.month)[1] + 1)):
            raise ValueError("Mes coloreado incompleto o con días repetidos.")
        word = next(word for word in dates if int(word["text"].rstrip("*")) == day.day)
        color = background(image, word["x"] - 2, word["y"] - 1, word["right"] + 2, word["y"] + 12)
        for row in palette[matching_color(color, palette)]:
            rows.append(duty(row, day, target, "24 horas", zone))
    return rows


def parse_pdf(content, label, target, source, catalogue_rows=None):
    pages = pdf_pages(content, include_words=True)
    if len(pages) != 1:
        raise ValueError("Calendario con número de páginas no reconocido.")
    page = pages[0]
    month_y = min((line["y"] for line in page["lines"] if line["text"].upper()
                   in ("OCTUBRE", "NOVIEMBRE", "DICIEMBRE")), default=180)
    printed = " ".join(line["text"] for line in page["lines"] if line["y"] < month_y)
    years = set(re.findall(r"\b2\s?0\s?\d\s?\d\b", printed))
    years = {int(year.replace(" ", "")) for year in years}
    if slugify(label).startswith("palencia-"):
        info = subprocess.run(["pdfinfo", "-"], input=content, capture_output=True, check=True)
        match = re.search(rb"CreationDate:.*?\b(20\d{2})\b", info.stdout)
        if not match:
            raise ValueError("Cartel de capital sin año impreso ni fecha de creación verificable.")
        year = int(match[1])
        if year != target.year:
            raise ValueError("El año de creación del cartel capitalino no corresponde a la consulta.")
        return parse_capital(page, year, target, source)
    if years != {target.year}:
        raise ValueError("Año impreso del cartel provincial incorrecto o ambiguo.")
    zone = "Carrión de los Condes" if slugify(label).startswith("carrion-") else "Saldaña"
    if slugify(label).startswith(("carrion-", "saldana-")):
        return parse_weekly(page, target.year, zone, target, source)
    if slugify(label).startswith(("villada-", "venta-de-banos-")):
        layout = "villada" if slugify(label).startswith("villada-") else "venta"
        zone = "Villada" if layout == "villada" else "Venta de Baños"
        return parse_weekly(page, target.year, zone, target, source, layout)
    if slugify(label) in ("aguilar-de-campoo", "guardo", "cervera-de-pisuerga"):
        return parse_colors(content, page, text(label).title(), target, source, catalogue_rows)
    raise ValueError("Asignación por colores o columnas especiales pendiente de verificar; no se supone ausencia de guardia.")


def consolidate(rows):
    merged = merge_rows(rows)
    for row in merged:
        row["guardia_intervalos"] = []
        for original in rows:
            if original["id"] == row["id"]:
                for interval in original.get("guardia_intervalos", []):
                    if interval not in row["guardia_intervalos"]:
                        row["guardia_intervalos"].append(interval)
    return merged


def run(target, cache, offline=False, resume=False, geocode=False, allow_address=False):
    cache.mkdir(parents=True, exist_ok=True)
    rows, reports = [], []
    try:
        entries = links(cached(SOURCE, cache, offline, resume).decode("latin1"))
        directory = catalogue(cached(CATALOGUE, cache, offline, resume).decode("latin1"))
        locate_and_catalogue(directory, "Palencia")
        for entry in entries:
            report = {**entry, "estado": "parcial", "farmacias": 0}
            try:
                batch = parse_pdf(cached(entry["url"], cache, offline, resume),
                                  entry["nombre"], target, entry["url"], directory)
                rows.extend(batch)
                report["farmacias"] = len(batch)
                report["error"] = ("Turnos interpretados; cobertura municipal y otros carteles pendientes."
                                   if batch else "Este cartel no incluye la fecha ni su madrugada anterior.")
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                report.update(estado="error", error=str(error))
                print(f"AVISO Palencia {entry['nombre']}: {error}", flush=True)
            reports.append(report)
        confirmed = consolidate(rows)
        locate_and_catalogue(directory, "Palencia")
        contacts = {saved_address_signature(row["direccion"], row["localidad"]): row for row in directory}
        for row in confirmed:
            prior = contacts.get(saved_address_signature(row["direccion"], row["localidad"]))
            if prior:
                row["telefono"] = prior["telefono"]
        locate_and_catalogue(confirmed, "Palencia", use_geocoder=geocode, allow_address=allow_address)
        publish(target, "Palencia", SOURCE, confirmed, reports)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR Palencia: {error}", flush=True)
        publish(target, "Palencia", SOURCE, consolidate(rows),
                reports + [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
    return False


def main():
    parser = argparse.ArgumentParser(description="Carteles oficiales de guardia de Palencia.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/palencia")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar,
                    args.geocode, args.permitir_direccion_exacta) else 1


if __name__ == "__main__":
    raise SystemExit(main())
