#!/usr/bin/env python3
"""Import the official Andorran duty calendar published monthly by the Govern d'Andorra.

The official page links a monthly PDF with one day shift (9:30–22:00) and one
night shift (22:00–9:30).  The PDF is a calendar for the whole month, so the
previous day's night shift is available and is clipped to the requested day.
On the first day of a month the night shift started in the previous month's
PDF; that document is used when the same page links it (or it is already in
the cache), and otherwise the day is published without the early-morning part
and the gap is recorded in the coverage report.

The separate weekly Pas de la Casa table does not publish hours.  It is
imported with the official date text and an explicit "call before going"
warning, without inventing intervals, following the same unknown-schedule
convention as León.
"""
import argparse
import calendar
import hashlib
import html
import json
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as wall_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import publish
from scrape_mes import OUT_DIR, write_json

SOURCE = "https://www.govern.ad/ca/tematiques/salut/assistencia-sanitaria/farmacies-de-guardia"
OVERPASS = "https://overpass-api.de/api/interpreter"
TZ = ZoneInfo("Europe/Andorra")
HEADERS = {
    "User-Agent": "FarmaciasDeGuardiaTracker/1.0",
    "Accept-Encoding": "identity",
}

MONTHS = (
    "gener", "febrer", "marc", "abril", "maig", "juny",
    "juliol", "agost", "setembre", "octubre", "novembre", "desembre",
)
WEEKDAYS = {
    "dilluns": 0,
    "dimarts": 1,
    "dimecres": 2,
    "dijous": 3,
    "divendres": 4,
    "dissabte": 5,
    "diumenge": 6,
}
PAS_HEADING = "SERVEI DE GUÀRDIES I FESTIUS DEL PAS DE LA CASA"
STREET = (
    r"(?:C/|Carrer|Av\.|Avda\.|Avinguda|Plaça|Pl\.|Ctra\.|Carretera|"
    r"Passeig|Ronda|Baixada|Travessia|Camí)"
)
DAY_HEADING = re.compile(
    r"^\s*(Diumenge|Dilluns|Dimarts|Dimecres|Dijous|Divendres|Dissabte)"
    r"\s+(\d{1,2})\b(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
DAY_SHIFT = re.compile(r"DIA\s*/\s*DAY\s*9[’'′]\s*30\s*(?:→|->|–|-)\s*22", re.IGNORECASE)
NIGHT_SHIFT = re.compile(r"NIT\s*/\s*NIGHT\s*22\s*(?:→|->|–|-)\s*9[’'′]\s*30", re.IGNORECASE)
PAS_HEADER = re.compile(r"FARM[ÀA]CIA\s+CARRER\s+TEL[ÈE]FON", re.IGNORECASE)
PAS_ROW = re.compile(
    r"^(?P<period>Dia\s+(?P<day>\d{1,2})"
    r"|Del\s+(?P<first>\d{1,2})(?:\s+de\s+(?P<first_month>"
    + "|".join(MONTHS) + r"))?\s+al\s+(?P<last>\d{1,2}))"
    r"\s+de\s+(?P<month>" + "|".join(MONTHS) + r")"
    r"(?:\s+de\s+(?P<year>20\d{2}))?"
    r"\s+F\.\s*(?P<nombre>.+?)\s+"
    r"(?P<direccion>" + STREET + r"\s*.+?)\s+"
    r"(?P<telefono>[\d][\d\s.-]*\d)$",
    re.IGNORECASE,
)
PAS_WARNING = "horario no indicado en la fuente; llamar antes de acudir"
DOCUMENT_DATE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(20\d{2})\b",
    re.IGNORECASE,
)
RECORD = re.compile(
    r"^F\.\s*(?P<nombre>.+?)\s+"
    r"(?P<direccion>" + STREET + r"\s*.+?)\s+"
    r"(?P<localidad>Andorra(?: la Vella)?)\s+"
    r"Tel\.\s*(?P<telefono>[\d\s-]+)$",
    re.IGNORECASE,
)
RECORD_TEXT = re.compile(r"F\..*?Tel\.\s*[\d][\d\s-]*\d")
ANCHOR = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
ATTRIBUTE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
TAG = re.compile(r"<[^>]+>")
OVERPASS_QUERY = """[out:json][timeout:60];
area["ISO3166-1"="AD"][admin_level=2]->.a;
(
  node["amenity"="pharmacy"](area.a);
  way["amenity"="pharmacy"](area.a);
  relation["amenity"="pharmacy"](area.a);
);
out center tags;"""

NAME_STOPWORDS = {
    "f", "farmacia", "farm", "de", "del", "d", "el", "la", "les", "els", "l", "i",
}
ADDRESS_STOPWORDS = {
    "c", "carrer", "calle", "av", "avda", "avenida", "avinguda", "pl", "placa",
    "plaza", "ctra", "carretera", "passeig", "ronda", "baixada", "travessia",
    "cami", "de", "del", "d", "el", "la", "les", "els", "l", "i", "num", "n",
}


def normalize(value):
    """Accent-insensitive lowercase text with single spaces."""
    plain = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(character for character in plain if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


def fetch_text(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def cached_page(cache, offline=False):
    path = cache / "page.html"
    if offline:
        if not path.exists():
            raise FileNotFoundError(f"Falta la copia de la página oficial: {path}")
        return path.read_text(encoding="utf-8")
    try:
        content = fetch_text(SOURCE)
    except OSError as error:
        if not path.exists():
            raise
        print(f"AVISO Andorra: no se pudo descargar la página ({error}); se usa la copia local.", flush=True)
        return path.read_text(encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    return content


def cached_pdf(url, path, offline=False):
    if offline:
        if not path.exists():
            raise FileNotFoundError(f"Falta el PDF oficial en caché: {path}")
        data = path.read_bytes()
    else:
        try:
            data = fetch_bytes(url)
        except OSError as error:
            if not path.exists():
                raise
            print(f"AVISO Andorra: no se pudo descargar el PDF ({error}); se usa la copia local.", flush=True)
            data = path.read_bytes()
        else:
            path.write_bytes(data)
            time.sleep(0.5)
    if not data.startswith(b"%PDF"):
        raise ValueError("El documento descargado no es un PDF oficial.")
    return path


def cached_month_pdf(page, target, cache, offline=False):
    """Return the official PDF for a month, using the page link or an existing cache copy."""
    name = f"farmacies_guardia_{MONTHS[target.month - 1]}_{target.year}"
    try:
        url, data_name = find_pdf_link(page, target)
    except ValueError:
        path = cache / f"{name}.pdf"
        if not path.exists():
            raise
        if not path.read_bytes().startswith(b"%PDF"):
            raise ValueError(f"La copia local de {name} no es un PDF oficial.")
        return path, None
    path = cache / f"{data_name}.pdf"
    cached_pdf(url, path, offline)
    return path, url


def pdf_text(path):
    try:
        result = subprocess.run(
            ["pdftotext", "-raw", str(path), "-"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError as error:
        raise ValueError("No está disponible pdftotext para leer el PDF oficial.") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        raise ValueError(f"No se pudo extraer el texto del PDF oficial: {detail}") from error
    if not result.stdout.strip():
        raise ValueError("El PDF oficial no contiene texto legible.")
    return result.stdout


def find_pdf_link(page, target):
    """Pick the official monthly PDF linked for the requested month and year."""
    month = MONTHS[target.month - 1]
    candidates = []
    available = []
    for attributes, body in ANCHOR.findall(page):
        values = dict(ATTRIBUTE.findall(attributes))
        href = html.unescape(values.get("href", ""))
        data_name = values.get("data-name", "")
        text = " ".join(html.unescape(TAG.sub(" ", body)).split())
        haystack = normalize(" ".join((href, data_name, text)))
        if "farmaci" in haystack:
            available.append(text or data_name or href)
        if not href or "farmaci" not in haystack:
            continue
        if not re.search(rf"\b{re.escape(month)}\b", haystack):
            continue
        if not re.search(rf"\b{target.year}\b", haystack):
            continue
        is_pdf = (
            href.casefold().endswith(".pdf")
            or "download" in href.casefold()
            or values.get("data-type", "").casefold() == "pdf"
            or "pdf" in text.casefold()
        )
        if not is_pdf:
            continue
        candidates.append((urllib.parse.urljoin(SOURCE, href), data_name or Path(urllib.parse.urlparse(href).path).name))
    unique = {}
    for url, name in candidates:
        unique.setdefault(url, name)
    if not unique:
        seen = "; ".join(dict.fromkeys(available)) or "ninguno"
        raise ValueError(
            f"La página oficial no enlaza un PDF de {month} de {target.year}. "
            f"Enlaces de farmacias encontrados: {seen}."
        )
    if len(unique) > 1:
        raise ValueError("La página oficial enlaza más de un PDF para el mismo mes; no se elige uno al azar.")
    url, name = next(iter(unique.items()))
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._") or f"farmacies_guardia_{month}_{target.year}"
    return url, safe_name


def document_month(text):
    found = {
        (MONTHS.index(normalize(name)) + 1, int(year))
        for name, year in DOCUMENT_DATE.findall(text)
        if normalize(name) in MONTHS
    }
    if not found:
        raise ValueError("El PDF oficial no identifica el mes y el año del calendario.")
    if len(found) != 1:
        raise ValueError("El PDF oficial contiene varios meses o años distintos; no se publica.")
    return next(iter(found))


def parse_record(text):
    match = RECORD.match(text)
    if not match:
        raise ValueError(f"Fila oficial con formato desconocido: {text!r}")
    phone = re.sub(r"\D", "", match.group("telefono"))
    if not phone:
        raise ValueError(f"Fila oficial sin teléfono: {text!r}")
    nombre = " ".join(match.group("nombre").split())
    direccion = " ".join(match.group("direccion").split())
    localidad = " ".join(match.group("localidad").split())
    return {"nombre": f"F. {nombre}", "direccion": direccion,
            "localidad": localidad, "telefono": phone}


def month_number(name):
    key = normalize(name)
    if key not in MONTHS:
        raise ValueError(f"Mes oficial desconocido: {name!r}")
    return MONTHS.index(key) + 1


def resolve_pas_period(first, first_month, last, end_month_name, end_year_hint,
                       document_month_number, document_year):
    """Place a Pas de la Casa row on the calendar, including month-boundary weeks."""
    end_month = month_number(end_month_name)
    start_month = month_number(first_month) if first_month else end_month
    month_start = date(document_year, document_month_number, 1)
    month_end = date(
        document_year, document_month_number,
        calendar.monthrange(document_year, document_month_number)[1],
    )
    candidate_years = (
        [int(end_year_hint)] if end_year_hint
        else [document_year - 1, document_year, document_year + 1]
    )
    candidates = []
    for end_year in candidate_years:
        start_year = end_year if start_month <= end_month else end_year - 1
        try:
            start = date(start_year, start_month, first)
            end = date(end_year, end_month, last)
        except ValueError:
            continue
        if end < start:
            continue
        if start <= month_end and end >= month_start:
            candidates.append((start, end))
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise ValueError(
            "No se puede situar sin ambigüedad un periodo del Pas de la Casa "
            f"({first} {first_month or end_month_name}–{last} {end_month_name})."
        )
    return unique[0]


def parse_pas_table(text, target, document_url=None):
    """Return the Pas de la Casa duty row for ``target`` without inventing hours."""
    month, year = document_month(text)
    if (year, month) != (target.year, target.month):
        raise ValueError(
            f"El PDF oficial es de {month:02d}/{year}, no de {target.month:02d}/{target.year}."
        )
    if PAS_HEADING not in text:
        raise ValueError("El PDF oficial no contiene la sección del Pas de la Casa.")
    tail = text.split(PAS_HEADING, 1)[1]
    periods = []
    for raw_line in tail.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        folded = normalize(line)
        if (folded == "farmacia carrer telefon"
                or folded.startswith("la farmacia de guardia es un servei")
                or folded.startswith("servei de guardies i festius")
                or re.fullmatch(r"(?:" + "|".join(MONTHS) + r")\s+20\d{2}", folded)):
            continue
        if not (line.startswith("Dia ") or line.startswith("Del ")):
            raise ValueError(f"Texto no reconocido en la tabla del Pas de la Casa: {line!r}")
        match = PAS_ROW.match(line)
        if not match:
            raise ValueError(f"Fila del Pas de la Casa con formato desconocido: {line!r}")
        if normalize(match.group("month")) != MONTHS[month - 1]:
            raise ValueError(f"La fila del Pas de la Casa no es del mes del PDF: {line!r}")
        if match.group("year") and int(match.group("year")) != year:
            raise ValueError(f"La fila del Pas de la Casa no es del año del PDF: {line!r}")
        if match.group("day"):
            first = last = int(match.group("day"))
            first_month = None
        else:
            first = int(match.group("first"))
            last = int(match.group("last"))
            first_month = match.group("first_month")
        start, end = resolve_pas_period(
            first, first_month, last, match.group("month"), match.group("year"),
            month, year,
        )
        phone = re.sub(r"\D", "", match.group("telefono"))
        if not phone:
            raise ValueError(f"Fila del Pas de la Casa sin teléfono: {line!r}")
        period_text = " ".join(match.group("period").split()) + f" de {match.group('month')}"
        if match.group("year"):
            period_text += f" de {match.group('year')}"
        record = {
            "nombre": "F. " + " ".join(match.group("nombre").split()),
            "direccion": " ".join(match.group("direccion").split()),
            "localidad": "Pas de la Casa",
            "telefono": phone,
        }
        periods.append((start, end, record, period_text))

    expected = {
        day: date(year, month, day)
        for day in range(1, calendar.monthrange(year, month)[1] + 1)
    }
    by_day = {}
    for day, current in expected.items():
        matches = [period for period in periods if period[0] <= current <= period[1]]
        if len(matches) != 1:
            raise ValueError(
                "La tabla del Pas de la Casa no asigna una única farmacia "
                f"al {current.isoformat()}; no se importa."
            )
        by_day[day] = matches[0]

    if target.day not in by_day:
        raise ValueError("La tabla del Pas de la Casa no cubre la fecha solicitada.")
    _, _, record, period_text = by_day[target.day]
    label = f"{period_text} · {PAS_WARNING}"
    row = {
        "id": pharmacy_id(record),
        "cofm_id": None,
        "nombre": record["nombre"],
        "direccion": record["direccion"],
        "localidad": "Pas de la Casa",
        "provincia": "Andorra",
        "telefono": record["telefono"],
        "guardia": True,
        "fecha_guardia": target.isoformat(),
        "fuente": SOURCE,
        "localidades_atendidas": ["Pas de la Casa"],
        "lat": None,
        "lng": None,
        "ubicacion_pendiente_verificacion": True,
        "guardia_intervalos": [],
        "guardia_franjas": [label],
        "guardia_franja": label,
        "guardia_apertura": "desconocida",
    }
    if document_url:
        row["fuente_documento"] = document_url
    return [row]


def day_blocks(text):
    main = text.split(PAS_HEADING, 1)[0]
    if PAS_HEADING not in text:
        raise ValueError("El PDF oficial no contiene la sección separada del Pas de la Casa.")
    matches = list(DAY_HEADING.finditer(main))
    if not matches:
        raise ValueError("El PDF oficial no contiene filas de días reconocibles.")
    blocks = {}
    for index, match in enumerate(matches):
        day = int(match.group(2))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(main)
        body = " ".join(main[match.start(3):end].split())
        records = RECORD_TEXT.findall(body)
        if len(records) != 2:
            raise ValueError(
                f"El día {day} no tiene exactamente los turnos de día y noche: {body!r}"
            )
        remainder = body
        for record in records:
            remainder = remainder.replace(record, "", 1)
        if remainder.strip():
            raise ValueError(f"El día {day} contiene texto oficial no reconocido: {remainder!r}")
        if day in blocks:
            raise ValueError(f"El día {day} aparece repetido en el calendario oficial.")
        blocks[day] = [parse_record(record) for record in records]
    return blocks


def pharmacy_id(record):
    signature = "|".join((
        normalize(record["nombre"]), normalize(record["direccion"]), normalize(record["localidad"]),
    ))
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    return f"govern-andorra-{digest}"


def previous_month_night(text, target, document_url=None):
    """Extract the last night shift of the previous month for the first day of a month."""
    previous_day = target - timedelta(days=1)
    rows = parse_calendar(text, previous_day, document_url=document_url)
    expected_start = datetime.combine(previous_day, wall_time(22, 0)).isoformat()
    expected_finish = datetime.combine(target, wall_time(9, 30)).isoformat()
    matches = [
        row for row in rows
        if any(
            interval.get("inicio_original") == expected_start
            and interval.get("fin_original") == expected_finish
            for interval in row.get("guardia_intervalos", [])
        )
    ]
    if len(matches) != 1:
        raise ValueError(
            "El PDF del mes anterior no contiene una única guardia nocturna "
            f"que termine el {target.isoformat()} a las 9:30."
        )
    row = matches[0]
    return {
        "nombre": row["nombre"],
        "direccion": row["direccion"],
        "localidad": row["localidad"],
        "telefono": row["telefono"],
    }


def parse_calendar(text, target, document_url=None, previous_text=None, previous_document_url=None):
    """Return the duty rows for ``target`` after checking the whole official month."""
    month, year = document_month(text)
    if (year, month) != (target.year, target.month):
        raise ValueError(
            f"El PDF oficial es de {month:02d}/{year}, no de {target.month:02d}/{target.year}."
        )
    day_label = DAY_SHIFT.search(text)
    night_label = NIGHT_SHIFT.search(text)
    if not day_label or not night_label:
        raise ValueError("El PDF oficial no contiene los turnos DIA 9:30–22 y NIT 22–9:30.")
    day_label = " ".join(day_label.group(0).split())
    night_label = " ".join(night_label.group(0).split())
    blocks = day_blocks(text)
    expected = set(range(1, calendar.monthrange(target.year, target.month)[1] + 1))
    if set(blocks) != expected:
        missing = sorted(expected - set(blocks))
        extra = sorted(set(blocks) - expected)
        raise ValueError(f"Calendario oficial incompleto: faltan {missing}; sobran {extra}.")
    for day, records in blocks.items():
        weekday = datetime(target.year, target.month, day).weekday()
        label = next(
            (match.group(1) for match in DAY_HEADING.finditer(text)
             if int(match.group(2)) == day),
            "",
        )
        if WEEKDAYS.get(normalize(label)) != weekday:
            raise ValueError(f"El día {day} no coincide con su día de la semana oficial.")
        if len(records) != 2:
            raise ValueError(f"El día {day} no tiene dos turnos.")

    start_day = datetime.combine(target, wall_time.min)
    end_day = start_day + timedelta(days=1)
    rows = {}

    def add(record, begin, finish, clipped_begin, clipped_finish, label, inherited=False):
        if finish <= begin or clipped_finish <= clipped_begin:
            raise ValueError(f"Intervalo oficial inválido para {record['nombre']}.")
        identifier = pharmacy_id(record)
        row = rows.get(identifier)
        if row is None:
            row = {
                "id": identifier,
                "cofm_id": None,
                "nombre": record["nombre"],
                "direccion": record["direccion"],
                "localidad": record["localidad"],
                "provincia": "Andorra",
                "telefono": record["telefono"],
                "guardia": True,
                "fecha_guardia": target.isoformat(),
                "fuente": SOURCE,
                "localidades_atendidas": [record["localidad"]],
                "lat": None,
                "lng": None,
                "ubicacion_pendiente_verificacion": True,
                "guardia_intervalos": [],
                "guardia_franjas": [],
            }
            if document_url:
                row["fuente_documento"] = document_url
            rows[identifier] = row
        elif row["telefono"] != record["telefono"]:
            raise ValueError(f"La farmacia {record['nombre']} tiene teléfonos oficiales contradictorios.")
        if inherited:
            row["guardia_desde_ayer"] = True
        interval = {
            "inicio": clipped_begin.isoformat(),
            "fin": clipped_finish.isoformat(),
            "inicio_original": begin.isoformat(),
            "fin_original": finish.isoformat(),
            "tipo": label,
        }
        if interval not in row["guardia_intervalos"]:
            row["guardia_intervalos"].append(interval)
        if label not in row["guardia_franjas"]:
            row["guardia_franjas"].append(label)

    if target.day > 1:
        previous = target - timedelta(days=1)
        previous_night = blocks[target.day - 1][1]
        add(
            previous_night,
            datetime.combine(previous, wall_time(22, 0)),
            datetime.combine(target, wall_time(9, 30)),
            start_day,
            datetime.combine(target, wall_time(9, 30)),
            f"{night_label} · madrugada iniciada el {previous.isoformat()}",
            inherited=True,
        )
    elif previous_text is not None:
        previous = target - timedelta(days=1)
        previous_night = previous_month_night(
            previous_text, target, document_url=previous_document_url,
        )
        add(
            previous_night,
            datetime.combine(previous, wall_time(22, 0)),
            datetime.combine(target, wall_time(9, 30)),
            start_day,
            datetime.combine(target, wall_time(9, 30)),
            f"{night_label} · madrugada iniciada el {previous.isoformat()}",
            inherited=True,
        )
        if previous_document_url:
            rows[pharmacy_id(previous_night)]["fuente_documento_madrugada"] = previous_document_url

    daytime, night = blocks[target.day]
    add(
        daytime,
        datetime.combine(target, wall_time(9, 30)),
        datetime.combine(target, wall_time(22, 0)),
        datetime.combine(target, wall_time(9, 30)),
        datetime.combine(target, wall_time(22, 0)),
        day_label,
    )
    add(
        night,
        datetime.combine(target, wall_time(22, 0)),
        datetime.combine(target, wall_time(9, 30)) + timedelta(days=1),
        datetime.combine(target, wall_time(22, 0)),
        end_day,
        night_label,
    )

    for row in rows.values():
        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(rows.values())


def overpass_pharmacies(data):
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        raise ValueError("La respuesta de Overpass no contiene una lista de elementos.")
    pharmacies = []
    for element in elements:
        tags = element.get("tags") or {}
        if tags.get("amenity") != "pharmacy":
            continue
        point = element.get("center") or element
        lat, lng = point.get("lat"), point.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        if not (42.4 <= lat <= 42.7 and 1.4 <= lng <= 1.8):
            continue
        name = tags.get("name") or ""
        street = tags.get("addr:street") or tags.get("addr:place") or ""
        number = tags.get("addr:housenumber") or ""
        address = " ".join(part for part in (street, number) if part).strip()
        osm_type = element.get("type") or ""
        pharmacies.append({
            "id": f"osm-{element.get('id')}",
            "osm_type": osm_type,
            "nombre": name,
            "direccion": address,
            "lat": float(lat),
            "lng": float(lng),
            "url": f"https://www.openstreetmap.org/{osm_type}/{element.get('id')}",
        })
    return pharmacies


def cached_overpass(cache, offline=False):
    path = cache / "overpass.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if offline:
                raise
        else:
            if isinstance(data.get("elements"), list) and data["elements"]:
                return data
    if offline:
        raise FileNotFoundError(f"Falta la consulta de Overpass en caché: {path}")
    request = urllib.request.Request(
        OVERPASS,
        data=urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8"),
        headers=HEADERS,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    return data


def name_core(name):
    return " ".join(word for word in normalize(name).split() if word not in NAME_STOPWORDS)


def address_parts(address):
    text = normalize(address)
    words = {word for word in text.split() if word not in ADDRESS_STOPWORDS and not word.isdigit()}
    numbers = set(re.findall(r"\b\d+[a-z]?\b", text))
    return words, numbers


def locate(row, pharmacies):
    core = name_core(row.get("nombre"))
    words, numbers = address_parts(row.get("direccion"))
    if not core or not numbers:
        return False
    matches = []
    for pharmacy in pharmacies:
        if name_core(pharmacy["nombre"]) != core:
            continue
        osm_words, osm_numbers = address_parts(pharmacy["direccion"])
        if not (numbers & osm_numbers) or not (words & osm_words):
            continue
        matches.append(pharmacy)
    if len(matches) != 1:
        return False
    match = matches[0]
    row.update({
        "lat": match["lat"],
        "lng": match["lng"],
        "precision_ubicacion": "farmacia",
        "fuente_coordenadas": match["url"],
        "referencia_ubicacion": match["url"],
        "nota_ubicacion": (
            "Coordenada de OpenStreetMap; el nombre y la dirección coinciden de forma "
            "única con el PDF oficial."
        ),
        "ubicacion_pendiente_verificacion": False,
    })
    if match["osm_type"] == "node":
        row["osm_id"] = match["id"]
    return True


def prior_location(row, saved):
    previous = saved.get(row["id"])
    if not previous or previous.get("direccion") != row["direccion"]:
        return
    if previous.get("localidad") != row["localidad"] or not coordinates(previous):
        return
    for field in (
        "lat", "lng", "precision_ubicacion", "fuente_coordenadas",
        "referencia_ubicacion", "nota_ubicacion", "osm_id",
    ):
        if field in previous:
            row[field] = previous[field]
    row["ubicacion_pendiente_verificacion"] = False


def run(target, cache, output=OUT_DIR, offline=False):
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    page = cached_page(cache, offline)
    pdf_url, data_name = find_pdf_link(page, target)
    pdf_path = cache / f"{data_name}.pdf"
    cached_pdf(pdf_url, pdf_path, offline)
    text = pdf_text(pdf_path)

    previous_text = None
    previous_url = None
    previous_note = None
    if target.day == 1:
        previous_target = target - timedelta(days=1)
        try:
            previous_path, previous_url = cached_month_pdf(page, previous_target, cache, offline)
            previous_text = pdf_text(previous_path)
        except (OSError, ValueError) as error:
            previous_note = str(error)
            print(
                f"AVISO Andorra: sin madrugada heredada del {previous_target.isoformat()}: {error}",
                flush=True,
            )

    rows = parse_calendar(
        text, target, document_url=pdf_url,
        previous_text=previous_text, previous_document_url=previous_url,
    )
    pas_error = None
    try:
        rows.extend(parse_pas_table(text, target, document_url=pdf_url))
    except ValueError as error:
        pas_error = str(error)
        print(f"AVISO Andorra: no se importa la tabla del Pas de la Casa: {error}", flush=True)

    pharmacies = overpass_pharmacies(cached_overpass(cache, offline))

    catalog_path = output / "farmacias-andorra.json"
    saved = {row["id"]: row for row in json.loads(catalog_path.read_text(encoding="utf-8"))} \
        if catalog_path.exists() else {}
    for row in rows:
        if not locate(row, pharmacies):
            prior_location(row, saved)
        if not coordinates(row):
            row["ubicacion_pendiente_verificacion"] = True
        elif row.get("ubicacion_pendiente_verificacion") is True:
            row["ubicacion_pendiente_verificacion"] = False
        if not coordinates(row):
            print(f"AVISO Andorra {row['nombre']}: sin coincidencia única en OSM; no se dibuja.", flush=True)

    catalog = dict(saved)
    for row in rows:
        catalog[row["id"]] = {**row, "guardia": False}
    write_json(catalog_path, list(catalog.values()))

    error = (
        "PDF mensual oficial con turnos DIA 9:30–22 y NIT 22–9:30. Coordenadas solo "
        "con coincidencia única de nombre y dirección con una farmacia de OpenStreetMap."
    )
    if target.day == 1:
        if previous_text is None:
            error += (
                " La madrugada del 1 no se pudo acreditar: "
                + (previous_note or "no está disponible el PDF oficial del mes anterior")
                + "; se publica sin ella."
            )
        else:
            error += " La madrugada del 1 se tomó del PDF oficial del mes anterior."
    if pas_error:
        error += f" No se importó la tabla del Pas de la Casa: {pas_error}"
    else:
        error += (
            " La tabla semanal del Pas de la Casa no indica horas: se publica con "
            "«horario no indicado en la fuente; llamar antes de acudir» y sin intervalos inventados."
        )
    report = [{
        "nombre": "Govern d'Andorra - Farmàcies de guàrdia",
        "estado": "parcial",
        "farmacias": len(rows),
        "error": error,
    }]
    return publish(target, "Andorra", SOURCE, rows, report, output=output,
                   authoritative_sources={SOURCE})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/andorra")
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    parser.add_argument("--sin-red", action="store_true",
                        help="Usar solo la página, el PDF y Overpass guardados en caché.")
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.cache_documentos, args.salida, args.sin_red) else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"ERROR Andorra: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
