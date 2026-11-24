#!/usr/bin/env python3
"""Import official duty calendars for Segovia capital, Cuéllar, and El Espinar."""
import argparse
from datetime import date, datetime, time, timedelta
import hashlib
import html
import json
import re
import subprocess
import time as time_module
from pathlib import Path
import unicodedata
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import fetch, slugify
from scrape_palencia import consolidate

SOURCE = "https://cofsegovia.com/farmacias-de-guardia/"
REGISTRY = (
    "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/"
    "registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/exports/json?"
    + urllib.parse.urlencode({"where": 'provincia="SEGOVIA"'})
)
MAELLO_REGISTRY = (
    "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/"
    "registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/exports/json?"
    + urllib.parse.urlencode({"where": 'provincia="AVILA" AND localidad="MAELLO"'})
)
TZ = ZoneInfo("Europe/Madrid")
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTH_NUMBERS = {
    **MONTHS,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTH_NUMBERS, key=len, reverse=True))
DATE_TOKEN = re.compile(rf"\b(\d{{1,2}})-({MONTH_PATTERN})\b", re.I)
SPECIAL_DAY = re.compile(
    r"\b(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{1,2})\b",
    re.I,
)
SPECIAL_MONTH = re.compile(rf"\b({MONTH_PATTERN})\b", re.I)
WEEKDAY_NUMBERS = {
    "LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3,
    "VIERNES": 4, "SABADO": 5, "DOMINGO": 6,
}
LOCAL_CALENDARS = {
    "Cuéllar": {
        "municipio": "CUÉLLAR",
        "filename": "GUARDIAS-CUELLAR",
        "assignments": {
            "STA MARINA": "40-E1-00009",
            "AV C J CELA": "40-E1-00082",
            "CTRA BAHABON": "40-E1-00093",
            "C RESINA": "40-E1-00008",
        },
    },
    "El Espinar": {
        "municipio": "ESPINAR, EL",
        "filename": "GUARDIAS-EL-ESPINAR",
        "assignments": {
            "SAN RAFAEL": "40-E1-00100",
            "AV HONTANILLA 18": "40-E1-00096",
            "C MARQUES PERALES": "40-E1-00017",
        },
    },
}
RURAL_COLUMN_BOUNDS = (300.0, 377.5, 477.0, 548.0, 606.0, 676.5, 745.5, 900.0)
RURAL_COLUMN_HOURS = ((10, 22), (10, 22), (10, 20), (10, 20), (10, 20), (10, 20), (10, 20))
RURAL_ADDRESS_BAND = (375.0, 420.0)
CANTALEJO_ADDRESS_BAND = (130.0, 160.0)
RURAL_LABEL_ALIASES = {
    "FUENTESAUCO": "FUENTESAUCO DE FUENTIDUEÑA",
    "LA GRANJA": "SAN ILDEFONSO O LA GRANJA",
    "MAELLO AVILA": "MAELLO",
    "ESCALONA": "ESCALONA DEL PRADO",
    "ESCARABAJOSA": "ESCARABAJOSA DE CABEZAS",
    "CARBONERO M": "CARBONERO EL MAYOR",
    "NAVAS DE SA": "NAVAS DE SAN ANTONIO",
    "SANTIUSTE": "SANTIUSTE DE SAN JUAN BAUTISTA",
    "TORREVAL": "TORRE VAL DE SAN PEDRO",
    "ZARZUELA PINAR": "ZARZUELA DEL PINAR",
}
RURAL_STREET_STOPWORDS = {
    "AV", "AVDA", "AVENIDA", "C", "CALLE", "CAMINO", "CARRETERA", "CL", "CTRA",
    "DE", "DEL", "EL", "LA", "LAS", "LOS", "PL", "PLAZA", "PZA", "TRAVESIA", "TRVA",
}
RURAL_DATE = re.compile(
    r"\b(\d{1,2})-([a-záéíóú]+)-(\d{2,4})\b", re.I
)
RURAL_PAGE = re.compile(r'<page\b([^>]*)>(.*?)</page>', re.S)
RURAL_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
    re.S,
)
ADDRESS_NUMBER_OVERRIDES = {"40-E1-00096": "18"}
DAY_START = time(10, 15)
DAY_END = time(22, 0)
NIGHT_END = time(10, 15)


def calendar_pdf_url(content, year):
    found = set()
    for href in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', content, re.I):
        url = urllib.parse.urljoin(SOURCE, href)
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "cofsegovia.com"
                and f"CALENDARIO-GUARDIAS-SEGOVIA-CAPITAL-{year}.pdf" in parsed.path):
            found.add(url)
    if len(found) != 1:
        raise ValueError(f"No se encontró un único calendario oficial de Segovia capital para {year}.")
    return found.pop()


def municipal_pdf_url(content, municipality, year):
    schedule = LOCAL_CALENDARS[municipality]
    filename = re.compile(
        rf"{re.escape(schedule['filename'])}_{year}\.pdf$", re.I
    )
    found = set()
    for href in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', content, re.I):
        url = urllib.parse.urljoin(SOURCE, href)
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "cofsegovia.com"
                and filename.fullmatch(Path(parsed.path).name)):
            found.add(url)
    if len(found) != 1:
        raise ValueError(f"No se encontró un único calendario oficial de {municipality} para {year}.")
    return found.pop()


def rural_pdf_url(content, year):
    filename = re.compile(rf"SERVICIOS-DE-URGENCIA-RURALES-{year}\.pdf$", re.I)
    found = set()
    for href in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', content, re.I):
        url = urllib.parse.urljoin(SOURCE, href)
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "cofsegovia.com"
                and filename.fullmatch(Path(parsed.path).name)):
            found.add(url)
    if len(found) != 1:
        raise ValueError(f"No se encontró un único calendario rural oficial de Segovia para {year}.")
    return found.pop()


def normalize_words(value):
    decomposed = unicodedata.normalize("NFKD", value or "")
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^A-Z0-9]+", " ", plain.upper()).strip()


def schedule_dates(day_months, target, weekdays=None, weekly=False):
    valid = []
    invalid_target = False
    for first_year in (target.year - 1, target.year, target.year + 1):
        dates = []
        year = first_year
        previous_month = day_months[0][1]
        for index, (day, month) in enumerate(day_months):
            if index and month < previous_month:
                year += 1
            previous_month = month
            try:
                dates.append(date(year, month, day))
            except ValueError:
                dates = []
                break
        if target not in dates:
            continue
        consecutive = all(
            current == previous + timedelta(days=1)
            for previous, current in zip(dates, dates[1:])
        )
        matches_weekdays = not weekdays or all(
            current.weekday() == weekday for current, weekday in zip(dates, weekdays)
        )
        starts_monday = not weekly or dates[0].weekday() == 0
        if consecutive and matches_weekdays and starts_monday:
            valid.append(dates)
        else:
            invalid_target = True
    if invalid_target:
        raise ValueError(f"El calendario semanal contiene fechas inconsistentes para {target}.")
    return valid


def _special_dates(line, events, target):
    day_months = []
    weekdays = []
    previous_month = None
    for index, event in enumerate(events):
        end = events[index + 1].start() if index + 1 < len(events) else len(line)
        month_match = SPECIAL_MONTH.search(line, event.end(), end)
        if month_match is None:
            month_match = SPECIAL_MONTH.search(line, event.end())
        month = MONTH_NUMBERS.get(month_match.group(1).casefold()) if month_match else previous_month
        if month is None:
            return [], False
        previous_month = month
        day_months.append((int(event.group(2)), month))
        weekdays.append(WEEKDAY_NUMBERS[normalize_words(event.group(1))])
    return schedule_dates(day_months, target, weekdays), True


def _schedule_label(line, end, special=False):
    if special:
        columns = split_columns(line)
        label = columns[-1] if len(columns) > 1 else ""
    else:
        label = line[end:].strip()
    label = re.sub(r"^\s*EL\s+ESPINAR\.?\s*", "", label, flags=re.I)
    return label.strip()


def parse_weekly_calendar(text, target, municipality, source, registry):
    schedule = LOCAL_CALENDARS[municipality]
    header = normalize_words(text)
    required_header = (
        f"TURNOS DE GUARDIAS PARA LAS FARMACIAS DEL MUNICIPIO DE "
        f"{'EL ESPINAR' if municipality == 'El Espinar' else 'CUELLAR'} PARA EL ANO {target.year}"
        if municipality == "El Espinar"
        else f"SERVICIOS DE URGENCIA DE LAS FARMACIAS DEL MUNICIPIO DE CUELLAR PARA EL ANO {target.year}"
    )
    if required_header not in header:
        raise ValueError(f"El PDF no confirma el calendario anual oficial de {municipality} para {target.year}.")

    matches = []
    for line in text.splitlines():
        date_tokens = list(DATE_TOKEN.finditer(line))
        special_events = list(SPECIAL_DAY.finditer(line))
        if len(date_tokens) >= 6:
            day_months = [
                (int(match.group(1)), MONTH_NUMBERS[match.group(2).casefold()])
                for match in date_tokens
            ]
            dates = schedule_dates(day_months, target, weekly=True)
            if dates:
                matches.append((_schedule_label(line, date_tokens[-1].end()), dates[0]))
        elif len(special_events) >= 2:
            dates, parsed = _special_dates(line, special_events, target)
            if parsed and dates:
                matches.append((_schedule_label(line, special_events[-1].end(), special=True), dates[0]))

    if len(matches) != 1:
        raise ValueError(
            f"El calendario de {municipality} no contiene una única semana válida para {target}."
        )
    label, week = matches[0]
    normalized_label = normalize_words(label)
    if municipality == "El Espinar" and normalized_label.startswith("EL ESPINAR "):
        normalized_label = normalized_label.removeprefix("EL ESPINAR ")
    registration_number = schedule["assignments"].get(normalized_label)
    if registration_number is None:
        raise ValueError(f"Etiqueta de turno no reconocida en {municipality}: {label.strip()!r}")

    records = [
        row for row in registry
        if row.get("num_reg") == registration_number
        and row.get("municipio") == schedule["municipio"]
        and row.get("provincia") == "SEGOVIA"
    ]
    if len(records) != 1:
        raise ValueError(
            f"El registro JCyL {registration_number} no es único para {municipality}."
        )
    registration = records[0]
    street_parts = re.sub(r"\s+", " ", str(registration.get("calle") or "")).strip().split(" ", 1)
    street_types = {"AVDA": "Avenida", "CTRA": "Carretera", "CALLE": "Calle", "TRVA": "Travesía"}
    street_type = street_types.get(street_parts[0].rstrip(".").upper()) if street_parts else None
    number = str(ADDRESS_NUMBER_OVERRIDES.get(registration_number, registration.get("numero") or "")).strip()
    if not street_type or len(street_parts) != 2 or not re.fullmatch(r"\d+[A-Za-z]?", number):
        raise ValueError(f"Dirección incompleta en el registro JCyL {registration_number}.")
    address = f"{street_type} {street_parts[1].strip()} {number}"
    note = None
    official_number = str(registration.get("numero") or "").strip()
    if number != official_number:
        note = (
            f"El registro de la Junta indica el número {official_number}; "
            f"el calendario COF Segovia publica el número {number}."
        )
    locality = "Cuéllar" if municipality == "Cuéllar" else (
        "San Rafael" if normalize_words(registration.get("localidad")) == "SAN RAFAEL" else "El Espinar"
    )
    start, finish = week[0], week[-1]
    label_text = (
        f"Turno semanal COF Segovia del {start:%d/%m} al {finish:%d/%m}; "
        "sin horario publicado"
    )
    row = {
        "id": f"jcyl-{registration_number.lower()}",
        "nombre": registration["nombre_comercial"],
        "direccion": address,
        "localidad": locality,
        "provincia": "Segovia",
        "telefono": str(registration["telefono"]) if registration.get("telefono") else None,
        "fuente": source,
        "guardia": True,
        "fecha_guardia": str(target),
        "localidades_atendidas": [municipality],
        "guardia_franja": label_text,
        "guardia_franjas": [label_text],
        "lat": None,
        "lng": None,
    }
    if note:
        row["nota_direccion"] = note
    report = {
        "nombre": municipality,
        "estado": "parcial",
        "farmacias": 1,
        "error": "El turno semanal no publica la hora del relevo; no se asigna un intervalo horario.",
    }
    return [row], report


def _rural_date_from_word(value):
    match = RURAL_DATE.fullmatch(value.strip())
    if not match:
        return None
    month = MONTH_NUMBERS.get(match.group(2).casefold())
    if month is None:
        raise ValueError(f"Mes no reconocido en el calendario rural de Segovia: {value}")
    year = int(match.group(3))
    if year < 100:
        year += 2000
    try:
        return date(year, month, int(match.group(1)))
    except ValueError as error:
        raise ValueError(f"Fecha no válida en el calendario rural de Segovia: {value}") from error


def _rural_bbox_pages(text):
    pages = []
    for page_match in RURAL_PAGE.finditer(text):
        height_match = re.search(r'\bheight="([\d.]+)"', page_match.group(1))
        if not height_match:
            raise ValueError("El PDF rural no informa la altura de página.")
        words = [
            (*map(float, match.group(1, 2, 3, 4)), html.unescape(match.group(5)))
            for match in RURAL_WORD.finditer(page_match.group(2))
        ]
        pages.append({"height": float(height_match.group(1)), "words": words})
    if not pages:
        raise ValueError("No se pudieron leer las posiciones de la tabla rural.")
    return pages


def _rural_center(word):
    return (word[1] + word[3]) / 2


def _rural_week_y_bounds(page, target):
    dated_words = [
        (row_date, word) for word in page["words"]
        if (row_date := _rural_date_from_word(word[4])) is not None
    ]
    mondays_before = [
        (row_date, word) for row_date, word in dated_words
        if row_date <= target and row_date.weekday() == 0
    ]
    if not mondays_before:
        raise ValueError(f"No se encontró el inicio semanal rural de {target}.")
    start = max(mondays_before, key=lambda item: item[0])[1]
    mondays_after = [
        (row_date, word) for row_date, word in dated_words
        if row_date > target and row_date.weekday() == 0
    ]
    end_y = _rural_center(min(mondays_after, key=lambda item: item[0])[1]) if mondays_after \
        else page["height"]
    return _rural_center(start), end_y


def _rural_column_text(page, band, y_start, y_end):
    left, right = band
    return " ".join(
        word[4] for word in page["words"]
        if word[0] < right and word[2] > left
        and y_start <= _rural_center(word) <= y_end
    )


def _rural_candidates(label, registry):
    normalized = normalize_words(label)
    identity = normalize_words(RURAL_LABEL_ALIASES.get(normalized, normalized))
    return [
        row for row in registry
        if row.get("provincia") in {"SEGOVIA", "AVILA"}
        and identity in {
            normalize_words(row.get("municipio")),
            normalize_words(row.get("localidad")),
        }
    ]


def _rural_street_tokens(value):
    return {
        token for token in normalize_words(value).split()
        if token not in RURAL_STREET_STOPWORDS and not token.isdigit()
    }


def _resolve_rural_candidate(label, registry, week_text):
    candidates = _rural_candidates(label, registry)
    if len(candidates) > 1:
        block_tokens = set(normalize_words(week_text).split())
        candidates = [
            row for row in candidates
            if _rural_street_tokens(row.get("calle"))
            and _rural_street_tokens(row.get("calle")).issubset(block_tokens)
        ]
    return candidates[0] if len(candidates) == 1 else None


def _rural_address(registration):
    street_parts = str(registration.get("calle") or "").split(" ", 1)
    number = str(registration.get("numero") or "").strip()
    street_types = {
        "AVDA": "Avenida", "CALLE": "Calle", "CTRA": "Carretera",
        "PLAZA": "Plaza", "TRVA": "Travesía",
    }
    if len(street_parts) != 2 or not number:
        return None
    street_type = street_types.get(street_parts[0].upper())
    if not street_type:
        return None
    return f"{street_type} {street_parts[1].title()} {number}"


def parse_rural_calendar(text, target, source, registry):
    pages = _rural_bbox_pages(text)
    all_words = [word[4] for page in pages for word in page["words"]]
    normalized = normalize_words(" ".join(all_words))
    title = "CALENDARIO DE SERVICIOS DE URGENCIA EN LA PROVINCIA DE SEGOVIA"
    headings = (
        "GUARDIA DE 24 H", "GUARDIA DE 10 H A 22 H", "GUARDIA DE 10 H A 20 H",
        "ZBS RIAZA SEPULVEDA", "ZBS LA GRANJA", "FUENTIDUENA SACRAMENIA",
        "ZBS CARBONERO", "ZBS NAVA DE LA A", "ZBA VILLACASTIN",
    )
    year_label = f"2 {target.year % 1000:03d}"
    if title not in normalized or year_label not in normalized:
        raise ValueError(f"El PDF no confirma el calendario rural de Segovia para {target.year}.")
    if any(heading not in normalized for heading in headings):
        raise ValueError("El PDF no confirma las zonas y horarios rurales esperados.")

    matches = [
        (page, word) for page in pages for word in page["words"]
        if _rural_date_from_word(word[4]) == target
    ]
    if len(matches) != 1:
        raise ValueError(f"El calendario rural no contiene una única fecha para {target}.")
    page, target_word = matches[0]
    target_y = _rural_center(target_word)
    row_words = [
        word for word in page["words"]
        if abs(_rural_center(word) - target_y) <= 1.5
    ]
    weekdays = {
        WEEKDAY_NUMBERS[normalize_words(word[4])]
        for word in row_words if normalize_words(word[4]) in WEEKDAY_NUMBERS
    }
    if weekdays != {target.weekday()}:
        raise ValueError(f"El día de la semana no coincide con la fecha: {target}.")

    grouped_words = []
    for word in sorted((word for word in row_words if word[0] >= RURAL_COLUMN_BOUNDS[0]),
                       key=lambda item: item[0]):
        if grouped_words and word[0] - grouped_words[-1][-1][2] <= 8:
            grouped_words[-1].append(word)
        else:
            grouped_words.append([word])
    cells = [""] * len(RURAL_COLUMN_HOURS)
    for group in grouped_words:
        if RURAL_ADDRESS_BAND[0] <= group[0][0] < RURAL_ADDRESS_BAND[1]:
            continue
        column = next(
            (index for index in range(len(RURAL_COLUMN_HOURS))
             if RURAL_COLUMN_BOUNDS[index] <= group[0][0] < RURAL_COLUMN_BOUNDS[index + 1]),
            None,
        )
        if column is None or cells[column]:
            raise ValueError(f"No se reconoce una única asignación rural para {target}.")
        cells[column] = " ".join(word[4] for word in group)
    if not any(cells):
        raise ValueError(f"El calendario rural no contiene servicios legibles para {target}.")

    week_start_y, week_end_y = _rural_week_y_bounds(page, target)
    week_address_text = _rural_column_text(page, RURAL_ADDRESS_BAND, week_start_y, week_end_y)
    rows = []
    unresolved = []
    for label, (start_hour, end_hour) in zip(cells, RURAL_COLUMN_HOURS):
        if not label:
            continue
        registration = _resolve_rural_candidate(label, registry, week_address_text)
        address = _rural_address(registration) if registration else None
        if not registration or not address:
            unresolved.append(label)
            continue
        start = datetime.combine(target, time(start_hour), TZ)
        finish = datetime.combine(target, time(end_hour), TZ)
        registration_province = registration["provincia"]
        province = {"SEGOVIA": "Segovia", "AVILA": "Ávila"}[registration_province]
        locality = (registration["localidad"].title()
                    if registration_province == "AVILA" else label.title())
        rows.append({
            "id": f"jcyl-{registration['num_reg'].lower()}",
            "nombre": registration["nombre_comercial"],
            "direccion": address,
            "localidad": locality,
            "provincia": province,
            "telefono": str(registration["telefono"]) if registration.get("telefono") else None,
            "fuente": source,
            "guardia": True,
            "fecha_guardia": str(target),
            "localidades_atendidas": [locality],
            "guardia_franja": f"Guardia rural COF Segovia · {start:%H:%M}–{finish:%H:%M}",
            "guardia_franjas": [f"Guardia rural COF Segovia · {start:%H:%M}–{finish:%H:%M}"],
            "guardia_intervalos": [{"inicio": start.isoformat(), "fin": finish.isoformat()}],
            "lat": None,
            "lng": None,
        })

    unresolved_services = []
    cantalejo_text = _rural_column_text(page, CANTALEJO_ADDRESS_BAND, week_start_y, week_end_y)
    if "CANTALEJO" in normalize_words(cantalejo_text):
        cantalejo = _resolve_rural_candidate("CANTALEJO", registry, cantalejo_text)
        if cantalejo is None:
            count = len(_rural_candidates("CANTALEJO", registry))
            if count > 1:
                unresolved_services.append(
                    f"La guardia de 24 h de Cantalejo no identifica cuál de sus {count} farmacias está asignada."
                )
            else:
                unresolved_services.append("La farmacia de guardia de 24 h de Cantalejo no se pudo identificar.")
    if unresolved:
        unresolved_services.append(
            "No se pudo identificar de forma única: " + ", ".join(dict.fromkeys(unresolved)) + "."
        )
    if not unresolved_services:
        unresolved_services.append(
            "Los turnos rurales de 24 h no cubiertos por otros calendarios aún requieren integración."
        )
    report = {
        "nombre": "Servicios rurales de Segovia",
        "estado": "parcial",
        "farmacias": sum(row["provincia"] == "Segovia" for row in rows),
        "error": " ".join(unresolved_services),
    }
    return rows, report


def split_columns(line):
    return [cell.strip() for cell in re.split(r"\s{2,}", line.strip()) if cell.strip()]


def date_in_line(line, target):
    match = re.match(
        r"^\s*(?:" + "|".join(WEEKDAYS) + r")\s*,?\s*(\d{1,2})\s+de\s+([a-záéíóú]+)\b",
        line.strip(), re.I)
    if not match:
        return None
    month = MONTHS.get(match.group(2).casefold())
    if month is None:
        raise ValueError(f"Mes no reconocido en el calendario COF Segovia: {match.group(2)}")
    day = int(match.group(1))
    year = target.year - 1 if target.month == 1 and month == 12 else target.year
    try:
        return date(year, month, day)
    except ValueError as error:
        raise ValueError(f"Fecha no válida en el calendario COF Segovia: {line.strip()}") from error


def phone_from_line(value):
    match = re.search(r"\bTfno\.?\s*:\s*([0-9][0-9 .-]*)", value, re.I)
    if not match:
        raise ValueError("El calendario de Segovia no incluye el teléfono de una guardia.")
    digits = re.sub(r"\D", "", match.group(1))
    if len(digits) != 9:
        raise ValueError(f"Teléfono oficial de Segovia no válido: {match.group(1).strip()}")
    return digits


def split_calendar_row(lines, index, day):
    if index == 0 or index + 1 >= len(lines):
        raise ValueError("Fila de guardia de Segovia incompleta.")
    names = split_columns(lines[index - 1])
    cells = split_columns(lines[index])
    details = split_columns(lines[index + 1])
    if len(names) != 2 or len(cells) != 3 or len(details) != 2:
        raise ValueError(f"No se reconocen las dos columnas de guardia: {lines[index].strip()}")
    if date_in_line(cells[0], day) != day:
        raise ValueError("La fecha de la fila no coincide con la consulta.")

    records = []
    for position, duty_type in enumerate(("diurna", "nocturna"), 1):
        detail = details[position - 1]
        phone = phone_from_line(detail)
        extra_address = re.split(r"\bTfno\.?\s*:", detail, maxsplit=1, flags=re.I)[0].strip()
        address = " ".join(part for part in (cells[position], extra_address) if part)
        if not names[position - 1] or not address:
            raise ValueError(f"Guardia de Segovia sin nombre o dirección: {lines[index].strip()}")
        records.append({"nombre": names[position - 1], "direccion": address,
                        "telefono": phone, "tipo": duty_type})
    return records


def pharmacy_id(phone, name, address):
    if phone:
        return f"cof-segovia-capital-tel-{phone}"
    identity = f"{name.casefold()}|{address.casefold()}"
    return "cof-segovia-capital-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def duty_row(record, duty_day, target, source):
    if record["tipo"] == "diurna":
        start = datetime.combine(duty_day, DAY_START, TZ)
        finish = datetime.combine(duty_day, DAY_END, TZ)
    else:
        start = datetime.combine(duty_day, DAY_END, TZ)
        finish = datetime.combine(duty_day + timedelta(days=1), NIGHT_END, TZ)
    label = (f"Guardia COF Segovia · {record['tipo']} "
             f"{start:%d/%m %H:%M}–{finish:%d/%m %H:%M}")
    return {
        "id": pharmacy_id(record["telefono"], record["nombre"], record["direccion"]),
        "nombre": record["nombre"],
        "direccion": record["direccion"],
        "localidad": "Segovia",
        "provincia": "Segovia",
        "telefono": record["telefono"],
        "fuente": source,
        "guardia": True,
        "fecha_guardia": str(target),
        "localidades_atendidas": ["Segovia"],
        "guardia_franja": label,
        "guardia_franjas": [label],
        "guardia_intervalos": [{"inicio": start.isoformat(), "fin": finish.isoformat()}],
        "lat": None,
        "lng": None,
    }


def parse_calendar(text, target, source):
    if ("FARMACIA EN SER. DE URGENCIA DIURNO" not in text
            or "FARMACIA EN SER. DE URGENCIA NOCTURNO" not in text
            or "De 10:15 h. a 22:00 h." not in text
            or "De 22:00 h.. a 10:15 h." not in text):
        raise ValueError("El PDF no confirma las columnas y horarios oficiales esperados.")

    required = {target, target - timedelta(days=1)}
    rows = []
    found = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        duty_day = date_in_line(line, target)
        if duty_day not in required:
            continue
        found.add(duty_day)
        records = split_calendar_row(lines, index, duty_day)
        for record in records:
            if duty_day == target - timedelta(days=1) and record["tipo"] != "nocturna":
                continue
            rows.append(duty_row(record, duty_day, target, source))
    if target not in found:
        raise ValueError(f"El calendario no confirma las guardias de Segovia capital del {target}.")

    reports = [{
        "nombre": "Segovia capital",
        "estado": "parcial",
        "farmacias": len(rows),
        "error": ("Calendario oficial de la capital interpretado; no cubre los calendarios "
                  "de otras localidades de Segovia."),
    }]
    if target - timedelta(days=1) not in found:
        reports.append({"nombre": "Madrugada anterior", "estado": "error",
                        "error": "El PDF no confirma la guardia nocturna de la víspera."})
    return consolidate(rows), reports


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()
    if not content.startswith(b"%PDF-"):
        raise ValueError("La fuente de Segovia no devolvió un PDF.")
    return content


def cached_file(url, path, offline=False, resume=False, binary=False):
    if path.exists() and (offline or resume):
        return path.read_bytes() if binary else path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
    content = download(url) if binary else fetch(url)
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    time_module.sleep(1.1)
    return content


def extract_text(document):
    result = subprocess.run(["pdftotext", "-layout", "-", "-"], input=document,
                            capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="replace")


def extract_rural_text(document):
    result = subprocess.run(["pdftotext", "-bbox", "-", "-"], input=document,
                            capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="replace")


def run(target, cache, offline=False, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    reports = []
    cross_province_rows = []
    try:
        index_path = cache / f"indice-{target.year}.html"
        index = cached_file(SOURCE, index_path, offline, resume)
    except (OSError, ValueError, KeyError, TypeError) as error:
        index = None
        print(f"ERROR índice COF Segovia: {error}", flush=True)

    if index is None:
        reports.append({"nombre": "Segovia capital", "estado": "error",
                        "error": "No se pudo consultar el índice de calendarios COF Segovia."})
        for municipality in LOCAL_CALENDARS:
            reports.append({"nombre": municipality, "estado": "error",
                            "error": "No se pudo consultar el índice de calendarios COF Segovia."})
        reports.append({
            "nombre": "Servicios rurales de Segovia",
            "estado": "error",
            "farmacias": 0,
            "error": "No se pudo consultar el índice de calendarios COF Segovia.",
        })
    else:
        try:
            source = calendar_pdf_url(index, target.year)
            pdf_path = cache / f"calendario-capital-{target.year}.pdf"
            document = cached_file(source, pdf_path, offline, resume, binary=True)
            city_rows, city_reports = parse_calendar(extract_text(document), target, source)
            rows.extend(city_rows)
            reports.extend(city_reports)
        except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as error:
            print(f"ERROR Segovia capital: {error}", flush=True)
            reports.append({"nombre": "Segovia capital", "estado": "error", "error": str(error)})

        try:
            registry_path = cache / "registro-jcyl-segovia.json"
            registry = json.loads(cached_file(REGISTRY, registry_path, offline, resume))
            if not isinstance(registry, list) or not registry:
                raise ValueError("El registro oficial JCyL de Segovia está vacío o no es una lista.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"ERROR registro JCyL Segovia: {error}", flush=True)
            for municipality in LOCAL_CALENDARS:
                reports.append({"nombre": municipality, "estado": "error", "error": str(error)})
            reports.append({
                "nombre": "Servicios rurales de Segovia",
                "estado": "error",
                "farmacias": 0,
                "error": str(error),
            })
        else:
            rural_registry = registry
            rural_registry_error = None
            try:
                maello_path = cache / "registro-jcyl-maello-avila.json"
                maello_registry = json.loads(cached_file(
                    MAELLO_REGISTRY, maello_path, offline, resume))
                if not isinstance(maello_registry, list):
                    raise ValueError("El registro oficial de Maello (Ávila) no es una lista.")
                rural_registry = [
                    *registry,
                    *(row for row in maello_registry
                      if row.get("provincia") == "AVILA"
                      and normalize_words(row.get("localidad")) == "MAELLO"
                      and normalize_words(row.get("municipio")) == "MAELLO"),
                ]
            except (OSError, ValueError, KeyError, TypeError) as error:
                rural_registry_error = str(error)
                print(f"ERROR registro JCyL Maello (Ávila): {error}", flush=True)

            for municipality in LOCAL_CALENDARS:
                try:
                    source = municipal_pdf_url(index, municipality, target.year)
                    pdf_path = cache / f"calendario-{slugify(municipality)}-{target.year}.pdf"
                    document = cached_file(source, pdf_path, offline, resume, binary=True)
                    city_rows, report = parse_weekly_calendar(
                        extract_text(document), target, municipality, source, registry)
                    rows.extend(city_rows)
                    reports.append(report)
                except (OSError, ValueError, KeyError, TypeError, IndexError,
                        subprocess.SubprocessError) as error:
                    print(f"ERROR {municipality}: {error}", flush=True)
                    reports.append({"nombre": municipality, "estado": "error", "error": str(error)})

            try:
                rural_source = rural_pdf_url(index, target.year)
                rural_path = cache / f"calendario-rural-{target.year}.pdf"
                document = cached_file(rural_source, rural_path, offline, resume, binary=True)
                rural_rows, rural_report = parse_rural_calendar(
                    extract_rural_text(document), target, rural_source, rural_registry)
                rows.extend(row for row in rural_rows if row["provincia"] == "Segovia")
                cross_province_rows.extend(
                    row for row in rural_rows if row["provincia"] != "Segovia"
                )
                if rural_registry_error:
                    rural_report["error"] += (
                        f" No se pudo consultar el registro oficial de Ávila: {rural_registry_error}."
                    )
                reports.append(rural_report)
            except (OSError, ValueError, KeyError, TypeError, IndexError,
                    subprocess.SubprocessError) as error:
                print(f"ERROR servicios rurales: {error}", flush=True)
                reports.append({
                    "nombre": "Servicios rurales de Segovia",
                    "estado": "error",
                    "farmacias": 0,
                    "error": str(error),
                })
    if rows:
        try:
            locate_and_catalogue(rows, "Segovia")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"ERROR catálogo Segovia: {error}", flush=True)
            reports.append({"nombre": "Catálogo provincial", "estado": "error", "error": str(error)})
    publish(target, "Segovia", SOURCE, rows, reports)
    located = sum(row.get("lat") is not None for row in rows)
    print(f"Segovia {target}: {len(rows)} guardias confirmadas; "
          f"{located} ubicadas; cobertura provincial parcial.", flush=True)
    for province in sorted({row["provincia"] for row in cross_province_rows}):
        province_rows = [row for row in cross_province_rows if row["provincia"] == province]
        province_reports = [{
            "nombre": "Guardias rurales de Maello (COF Segovia)",
            "estado": "parcial",
            "farmacias": len(province_rows),
            "error": "El calendario COF Segovia confirma estas guardias de Maello, pero no cubre el resto de Ávila.",
        }]
        try:
            locate_and_catalogue(province_rows, province)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"ERROR catálogo {province}: {error}", flush=True)
            province_reports.append({
                "nombre": "Catálogo provincial",
                "estado": "error",
                "error": str(error),
            })
        publish(target, province, SOURCE, province_rows, province_reports)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Calendarios oficiales de Segovia capital, Cuéllar, El Espinar y zonas rurales."
    )
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/segovia")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
