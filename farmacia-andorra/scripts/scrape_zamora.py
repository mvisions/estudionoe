#!/usr/bin/env python3
"""Import the COF Zamora monthly rota for the explicitly selected zone."""
import argparse
from datetime import date, datetime
import html
import json
import re
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import fetch

SOURCE = "https://cofzamora.es/admin/config/media/ver_mes_completo"
REGISTRY = (
    "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/"
    "registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/exports/json"
)
TZ = ZoneInfo("Europe/Madrid")
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
STREET_WORDS = {
    "avenida", "av", "calle", "c", "cl", "carretera", "cr", "plaza", "pza",
    "paseo", "de", "del", "la", "las", "los", "el",
}


def normalize(value):
    plain = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(character for character in plain if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def phone_numbers(value):
    matches = re.findall(r"(?<!\d)(?:\d[\s.-]?){8}\d(?!\d)", value or "")
    return list(dict.fromkeys(
        re.sub(r"\D", "", match) for match in matches
        if len(re.sub(r"\D", "", match)) == 9
    ))


class ZamoraPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_form = False
        self.current_select = None
        self.current_option = None
        self.selected = {}
        self.table_depth = 0
        self.cell_parts = None
        self.cells = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "vista-mes-completo-settings":
            self.in_form = True
        elif self.in_form and tag == "select":
            self.current_select = attrs.get("name")
        elif self.in_form and tag == "option":
            self.current_option = {
                "value": attrs.get("value", ""),
                "selected": "selected" in attrs,
                "text": [],
            }
        if tag == "table":
            self.table_depth += 1
        elif tag == "td" and self.table_depth == 1:
            self.cell_parts = []

    def handle_data(self, data):
        if self.current_option is not None:
            self.current_option["text"].append(data)
        if self.cell_parts is not None:
            self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.current_option is not None:
            if self.current_option["selected"] and self.current_select:
                self.selected[self.current_select] = (
                    self.current_option["value"],
                    " ".join(" ".join(self.current_option["text"]).split()),
                )
            self.current_option = None
        elif tag == "select":
            self.current_select = None
        elif tag == "td" and self.cell_parts is not None:
            text = " ".join(" ".join(self.cell_parts).split())
            if text:
                self.cells.append(text)
            self.cell_parts = None
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1
        elif tag == "form" and self.in_form:
            self.in_form = False


def address_matches(source_address, official):
    source = re.match(r"^(.*?)[,\s]+([0-9]+[a-z]?)$", normalize(source_address))
    official_number = normalize(official.get("numero"))
    if source is None or not official_number or source[2] != official_number:
        return False
    source_street = {word for word in source[1].split() if word not in STREET_WORDS}
    official_street = {
        word for word in normalize(official.get("calle")).split() if word not in STREET_WORDS
    }
    return bool(source_street & official_street)


def registry_match(assignment, registry):
    zamora = [row for row in registry
              if row.get("provincia") == "ZAMORA" and row.get("num_reg")]
    assignment_phones = set(assignment["telefonos"])
    phone_matches = [
        row for row in zamora
        if re.sub(r"\D", "", str(row.get("telefono") or "")) in assignment_phones
    ]
    name = normalize(assignment["nombre"])
    name_matches = [row for row in zamora if normalize(row.get("nombre_comercial")) == name]
    candidates = phone_matches if phone_matches else name_matches
    candidates = [
        row for row in candidates
        if (normalize(row.get("nombre_comercial")) == name
            or address_matches(assignment["direccion"], row))
    ]
    if len(candidates) != 1:
        raise ValueError(
            "No se identifica de forma única en el registro oficial JCyL: "
            f"{assignment['nombre']} · {assignment['direccion']}"
        )
    return candidates[0]


def parse_assignments(cell, target, registry):
    day = re.match(r"^\s*(\d{1,2})\b", cell)
    if day is None or int(day[1]) != target.day:
        return []
    labels = list(re.finditer(r"\b(Diurna|Nocturna)\b", cell, re.I))
    if not labels:
        return []
    assignments = []
    for index, label in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(cell)
        details = cell[label.end():end]
        address = re.search(r"Direcci[oó]n:\s*(.+?)(?=\s+Nombre:)", details, re.I)
        name = re.search(r"Nombre:\s*(.+?)(?=\s+Tel[eé]fono:)", details, re.I)
        phone = re.search(r"Tel[eé]fono:\s*(.+)$", details, re.I)
        if address is None or name is None or phone is None:
            raise ValueError(f"El turno {label[1]} del día {target.day} está incompleto.")
        assignment = {
            "tipo": label[1].capitalize(),
            "direccion": address[1].strip(),
            "nombre": name[1].strip(),
            "telefonos": phone_numbers(phone[1]),
        }
        official = registry_match(assignment, registry)
        registration = str(official["num_reg"])
        locality = str(official["localidad"]).title()
        official_address = ", ".join(
            str(part).strip() for part in (official.get("calle"), official.get("numero")) if part
        )
        phone_value = (
            assignment["telefonos"][0] if assignment["telefonos"]
            else str(official.get("telefono") or "") or None
        )
        label_text = (
            f"Guardia {assignment['tipo'].lower()} COF Zamora; horario exacto pendiente, "
            "confirmar por teléfono."
        )
        assignments.append({
            "id": f"jcyl-{registration.lower()}",
            "nombre": assignment["nombre"],
            "direccion": official_address or assignment["direccion"],
            "localidad": locality,
            "provincia": "Zamora",
            "telefono": phone_value,
            "fuente": SOURCE,
            "guardia": True,
            "fecha_guardia": target.isoformat(),
            "localidades_atendidas": [locality],
            "guardia_franja": label_text,
            "guardia_franjas": [label_text],
            "guardia_intervalos": [],
            "guardia_apertura": "desconocida",
            "lat": None,
            "lng": None,
            "ubicacion_requiere_verificacion": True,
        })
    return assignments


def parse_calendar(content, target, registry):
    page = ZamoraPageParser()
    page.feed(content)
    selected_zone = page.selected.get("zonasGuardia", ("", ""))[1]
    selected_month = page.selected.get("listaMeses", ("", ""))[0]
    selected_year = page.selected.get("listaAnios", ("", ""))[0]
    if selected_zone != "Zamora Capital":
        raise ValueError(f"La página no confirma la zona Zamora Capital: {selected_zone or 'vacía'}.")
    try:
        month = int(selected_month or MONTHS[normalize(page.selected.get("listaMeses", ("", ""))[1])])
        year = int(selected_year)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("La página oficial no identifica el mes y año del calendario.") from error
    if (year, month) != (target.year, target.month):
        raise ValueError(
            f"El calendario seleccionado es {year:04d}-{month:02d}, no {target:%Y-%m}."
        )

    target_cells = []
    for cell in page.cells:
        day = re.match(r"^\s*(\d{1,2})\b", cell)
        if day and int(day[1]) == target.day:
            target_cells.append(cell)
    rows = []
    found_types = set()
    for cell in target_cells:
        found_types.update(
            match.group(1).casefold()
            for match in re.finditer(r"\b(Diurna|Nocturna)\b", cell, re.I)
        )
        rows.extend(parse_assignments(cell, target, registry))
    if not rows or not {"diurna", "nocturna"}.issubset(found_types):
        raise ValueError(f"El calendario no confirma los turnos diurno y nocturno del día {target.day}.")
    return merge_rows(rows)


def cached_text(url, path, offline=False, resume=False):
    if (offline or resume) and path.exists():
        return path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
    content = fetch(url)
    path.write_text(content, encoding="utf-8")
    return content


def cached_registry(path, offline=False, resume=False):
    if (offline or resume) and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        if offline:
            raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
        data = json.loads(fetch(REGISTRY))
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        time.sleep(1.1)
    if not isinstance(data, list) or not data:
        raise ValueError("El registro oficial JCyL de Castilla y León está vacío o no es una lista.")
    return data


def run(target, cache, offline=False, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    rows, reports = [], []
    try:
        page = cached_text(SOURCE, cache / f"calendario-{target}.html", offline, resume)
        registry = cached_registry(cache / "registro-jcyl-castilla-y-leon.json", offline, resume)
        rows = parse_calendar(page, target, registry)
        locate_and_catalogue(rows, "Zamora")
        reports.append({
            "nombre": "Zamora Capital",
            "estado": "parcial",
            "farmacias": len(rows),
            "error": (
                "El calendario mensual confirma los turnos de Zamora Capital, pero no publica "
                "horarios exactos ni confirma las otras zonas de la provincia."
            ),
        })
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Zamora: {error}", flush=True)
        reports.append({"nombre": "Calendario COF Zamora", "estado": "error", "error": str(error)})
    publish(target, "Zamora", SOURCE, rows, reports)
    print(
        f"Zamora {target}: {len(rows)} guardias confirmadas; "
        f"{sum(row.get('lat') is not None for row in rows)} ubicadas; cobertura parcial.",
        flush=True,
    )
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/zamora")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
