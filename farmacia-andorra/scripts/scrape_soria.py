#!/usr/bin/env python3
"""Import the COF Soria daily duty list for the capital and the province."""
import argparse
from datetime import date, datetime, time as wall_time, timedelta
import html
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from proximidad import fold, same_number, similar_street, split_address, street_core
from scrape_mes import fetch
from scrape_zamora import cached_registry

SOURCE = "https://www.cofsoria.es/ciudadanos/farmacias-de-guardia/"
TZ = ZoneInfo("Europe/Madrid")
CAPITAL = "Soria Capital"
PROVINCE = "Provincia de Soria"
SHEET_MAX_AGE = 30 * 86400
LOCALIZED = (
    "Puede ser guardia localizada (Orden de 2/3/1998, BOCYL 10/3/1998): si está cerrada, "
    "llamar al teléfono expuesto en la fachada."
)
LOWER_WORDS = {"de", "del", "la", "las", "los", "el", "y", "e"}
FIELD_CLASSES = {
    "farmacia-municipio", "farmacia-direccion", "farmacia-horario", "farmacia-ficha",
    "aviso-localizado", "ficha-municipio", "ficha-direccion", "ficha-titular",
    "ficha-dato-label", "ficha-dato-valor",
}
MARKER = re.compile(
    r"L\.marker\(\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\)"
    r"(?:(?!L\.marker).){0,400}?\?farmacia=(\d+)",
    re.S,
)
NOTE = re.compile(
    r"desde las (\d{1,2})[:.](\d{2})\s*h?\.?\s+del d[ií]a indicado\s+"
    r"hasta las (\d{1,2})[:.](\d{2})\s*h?\.?\s+del d[ií]a siguiente",
    re.I,
)


def clean(value):
    return " ".join(html.unescape(value or "").split())


def display(value):
    words = []
    for index, word in enumerate(clean(value).lower().split()):
        if index == 0 or word not in LOWER_WORDS:
            word = re.sub(r"[^\W\d_]", lambda letter: letter[0].upper(), word, count=1)
        words.append(word)
    return " ".join(words)


def phone_number(value):
    digits = re.sub(r"\D", "", str(value or ""))
    digits = digits[2:] if len(digits) == 11 and digits.startswith("34") else digits
    return digits if len(digits) == 9 else None


class SoriaParser(HTMLParser):
    """Collect the selected date, duty blocks, pharmacy items and sheet fields of a COF page."""

    def __init__(self):
        super().__init__()
        self.select = None
        self.selected = {}
        self.blocks = []
        self.item = None
        self.field = None
        self.in_title = False
        self.in_note = False
        self.notice = []
        self.sheet = {"labels": [], "values": [], "telefonos": []}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "select":
            self.select = attrs.get("name")
        elif tag == "option" and self.select and "selected" in attrs:
            self.selected[self.select] = attrs.get("value", "")
        elif tag == "div" and "bloque-tipo-farmacia" in classes:
            self.blocks.append({"nombre": [], "nota": [], "items": []})
            self.item = None
        elif tag == "div" and "farmacia-item" in classes and self.blocks:
            self.item = {"municipio": [], "direccion": [], "iconos": set(), "ficha": None}
            self.blocks[-1]["items"].append(self.item)
        elif tag == "div" and classes & FIELD_CLASSES:
            self.field = next(iter(classes & FIELD_CLASSES))
            if self.field in ("ficha-dato-label", "ficha-dato-valor"):
                self.sheet["labels" if self.field.endswith("label") else "values"].append([])
        elif tag == "h3" and self.blocks and not self.blocks[-1]["nombre"] and not self.blocks[-1]["items"]:
            self.in_title = True
        elif tag == "span" and "nota-servicio" in classes and self.blocks:
            self.in_note = True
        elif tag == "span" and self.item is not None and self.field == "farmacia-horario":
            self.item["iconos"].update(name.removeprefix("icon-") for name in classes if name.startswith("icon-"))
        elif tag == "a" and self.item is not None and self.field == "farmacia-ficha":
            match = re.fullmatch(r"\?farmacia=(\d+)", attrs.get("href") or "")
            self.item["ficha"] = match[1] if match else None
        elif tag == "a" and self.field == "ficha-dato-valor" and (attrs.get("href") or "").startswith("tel:"):
            self.sheet["telefonos"].append(attrs["href"][4:])

    def handle_data(self, data):
        if self.in_title:
            self.blocks[-1]["nombre"].append(data)
        elif self.in_note:
            self.blocks[-1]["nota"].append(data)
        elif self.field in ("farmacia-municipio", "farmacia-direccion") and self.item is not None:
            self.item[self.field.removeprefix("farmacia-")].append(data)
        elif self.field == "aviso-localizado":
            self.notice.append(data)
        elif self.field in ("ficha-municipio", "ficha-direccion", "ficha-titular"):
            self.sheet.setdefault(self.field.removeprefix("ficha-"), []).append(data)
        elif self.field in ("ficha-dato-label", "ficha-dato-valor"):
            self.sheet["labels" if self.field.endswith("label") else "values"][-1].append(data)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        elif tag == "h3":
            self.in_title = False
        elif tag == "span":
            self.in_note = False
        elif tag == "div":
            self.field = None


def parse_day(content, target):
    """Duty items of one COF Soria day page, with the schedule each sun/moon icon set means."""
    page = SoriaParser()
    page.feed(content)
    selected = tuple(page.selected.get(name, "") for name in ("dia", "mes", "anio"))
    if selected != (str(target.day), str(target.month), str(target.year)):
        raise ValueError(f"La página oficial muestra {'/'.join(selected) or 'otra fecha'}, no {target:%d/%m/%Y}.")
    markers = {pharmacy: (float(lat), float(lng)) for lat, lng, pharmacy in MARKER.findall(content)}
    blocks = {clean(" ".join(block["nombre"])): block for block in page.blocks}
    if set(blocks) != {CAPITAL, PROVINCE}:
        raise ValueError(f"Bloques de guardia inesperados: {', '.join(sorted(blocks)) or 'ninguno'}.")
    items = []
    for name, block in blocks.items():
        if not block["items"]:
            raise ValueError(f"El bloque {name} no publica farmacias para {target:%d/%m/%Y}.")
        note = NOTE.search(clean(" ".join(block["nota"])))
        for item in block["items"]:
            municipality = clean(" ".join(item["municipio"]))
            address = clean(" ".join(item["direccion"]))
            if not municipality or not item["ficha"]:
                raise ValueError(f"Farmacia incompleta en {name}: {municipality or 'sin municipio'}.")
            if item["iconos"] == {"sol", "luna"}:
                duty = "24 horas"
            elif item["iconos"] == {"sol"}:
                duty = "hasta las 22:00"
            else:
                raise ValueError(f"Iconos de horario no reconocidos en {municipality}: {sorted(item['iconos'])}.")
            hours = None
            if name == CAPITAL and duty == "24 horas" and note:
                hours = tuple(wall_time(int(note[index]), int(note[index + 1])) for index in (1, 3))
            items.append({
                "bloque": name, "municipio": municipality, "direccion": address,
                "ficha": item["ficha"], "turno": duty, "horas": hours,
                "punto": markers.get(item["ficha"]),
            })
    notice = clean(" ".join(page.notice))
    return items, bool(re.search(r"localizada", fold(notice)))


def parse_sheet(content):
    page = SoriaParser()
    page.feed(content)
    sheet = page.sheet
    data = {
        fold(clean(" ".join(label))): clean(" ".join(value))
        for label, value in zip(sheet["labels"], sheet["values"])
    }
    phones = [phone for phone in map(phone_number, sheet["telefonos"]) if phone]
    return {
        "municipio": clean(" ".join(sheet.get("municipio", []))),
        "direccion": clean(" ".join(sheet.get("direccion", []))),
        "titular": clean(" ".join(sheet.get("titular", []))),
        "telefono": phones[0] if phones else phone_number(data.get("telefono")),
        "tipo": data.get("tipo de guardia", ""),
    }


def registry_evidence(item, sheet, official):
    evidence = set()
    phone = phone_number(official.get("telefono"))
    if sheet["telefono"] and phone == sheet["telefono"]:
        evidence.add("teléfono")
    surnames = fold(str(official.get("nombre_comercial") or "").split(",")[0]).split()
    if surnames and set(surnames) <= set(fold(sheet["titular"]).split()):
        evidence.add("titular")
    ours = split_address(item["direccion"])
    street = item["direccion"] if ours is None else ours[0]
    if street_core(street) and similar_street(street, official.get("calle")):
        if ours is None or same_number(ours[1], str(official.get("numero") or "")):
            evidence.add("dirección")
    return evidence


def registry_match(item, sheet, registry):
    town = fold(item["municipio"])
    candidates = [
        row for row in registry
        if row.get("provincia") == "SORIA" and row.get("num_reg")
        and town in (fold(row.get("municipio")), fold(row.get("localidad")))
    ]
    scored = [(registry_evidence(item, sheet, row), row) for row in candidates]
    confirmed = [(evidence, row) for evidence, row in scored if len(evidence) >= 2]
    if len(confirmed) != 1:
        raise ValueError(
            "No se identifica de forma única en el registro oficial JCyL: "
            f"{item['municipio']} · {item['direccion']} · {sheet['titular'] or 'sin titular'}"
        )
    return confirmed[0][1]


def build_row(item, sheet, official, target, fuente_ficha):
    registration = str(official["num_reg"])
    official_locality = str(official.get("localidad") or official.get("municipio") or "")
    locality = (item["municipio"] if fold(official_locality) == fold(item["municipio"])
                else display(official_locality))
    address = display(item["direccion"])
    if split_address(item["direccion"]) is None and similar_street(item["direccion"], official.get("calle")):
        address = ", ".join(display(str(part)) for part in (official.get("calle"), official.get("numero")) if part)
    intervals = []
    if item["horas"]:
        start, end = item["horas"]
        begin = datetime.combine(target, start).replace(tzinfo=TZ)
        finish = datetime.combine(target + timedelta(days=1), end).replace(tzinfo=TZ)
        intervals.append({"inicio": begin.isoformat(), "fin": finish.isoformat()})
        label = f"Guardia 24 horas COF Soria · {start:%H:%M}–{end:%H:%M} del día siguiente"
    elif item["turno"] == "24 horas":
        label = "Guardia 24 horas COF Soria; hora de inicio no publicada, confirmar por teléfono"
    else:
        label = "Guardia COF Soria hasta las 22:00; hora de inicio no publicada, confirmar por teléfono"
    row = {
        "id": f"jcyl-{registration.lower()}",
        "nombre": f"Farmacia {display(sheet['titular'] or official.get('nombre_comercial'))}",
        "direccion": address,
        "localidad": locality,
        "provincia": "Soria",
        "telefono": sheet["telefono"] or phone_number(official.get("telefono")),
        "fuente": SOURCE,
        "guardia": True,
        "fecha_guardia": target.isoformat(),
        "localidades_atendidas": [locality],
        "guardia_franja": "",
        "guardia_franjas": [label, LOCALIZED],
        "guardia_intervalos": intervals,
        "lat": None,
        "lng": None,
        "ubicacion_requiere_verificacion": True,
    }
    if not intervals:
        row["guardia_apertura"] = "desconocida"
    if item["punto"]:
        row["referencia_ubicacion"] = {"lat": item["punto"][0], "lng": item["punto"][1], "fuente": fuente_ficha}
    return row


def overnight_row(row, target):
    """Early-morning part of yesterday's capital duty, which officially ends on the target day."""
    interval = row["guardia_intervalos"][0]
    end = datetime.fromisoformat(interval["fin"])
    start = datetime.combine(target, wall_time.min).replace(tzinfo=TZ)
    label = f"Madrugada: guardia 24 horas de Soria Capital del día anterior · 00:00–{end:%H:%M}"
    return {
        **row,
        "fecha_guardia": target.isoformat(),
        "guardia_franjas": [label, LOCALIZED],
        "guardia_intervalos": [{"inicio": start.isoformat(), "fin": interval["fin"]}],
        "guardia_desde_ayer": True,
    }


def combine(rows):
    result = {}
    for row in rows:
        previous = result.get(row["id"])
        if previous is None:
            result[row["id"]] = {**row, "guardia_franjas": list(row["guardia_franjas"]),
                                 "guardia_intervalos": list(row["guardia_intervalos"])}
            continue
        previous["guardia_franjas"] = list(dict.fromkeys(previous["guardia_franjas"] + row["guardia_franjas"]))
        previous["guardia_intervalos"] = sorted(
            previous["guardia_intervalos"] + row["guardia_intervalos"], key=lambda item: item["inicio"])
        previous.pop("guardia_desde_ayer", None)
        if previous["guardia_intervalos"]:
            previous.pop("guardia_apertura", None)
    for row in result.values():
        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(result.values())


def day_url(target):
    return f"{SOURCE}?{urlencode({'dia': target.day, 'mes': target.month, 'anio': target.year})}"


def cached_text(url, path, offline=False, resume=False, max_age=None):
    fresh = max_age is not None and path.exists() and time.time() - path.stat().st_mtime < max_age
    if path.exists() and (offline or resume or fresh):
        return path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
    content = fetch(url)
    path.write_text(content, encoding="utf-8")
    time.sleep(1.1)
    return content


def day_rows(target, cache, registry, offline=False, resume=False, capital_only=False):
    page = cached_text(day_url(target), cache / f"guardias-{target}.html", offline, resume)
    items, localized = parse_day(page, target)
    if not localized:
        raise ValueError("La página no muestra el aviso oficial de guardias localizadas.")
    rows = []
    for item in items:
        if capital_only and item["bloque"] != CAPITAL:
            continue
        url = f"{SOURCE}?farmacia={item['ficha']}"
        sheet = parse_sheet(cached_text(url, cache / f"ficha-{item['ficha']}.html", offline, resume,
                                        SHEET_MAX_AGE))
        if fold(sheet["municipio"]) != fold(item["municipio"]):
            raise ValueError(f"La ficha {item['ficha']} no corresponde a {item['municipio']}.")
        official = registry_match(item, sheet, registry)
        rows.append((item, build_row(item, sheet, official, target, url)))
    return rows


def run(target, cache, offline=False, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    rows, reports = [], []
    try:
        registry = cached_registry(cache / "registro-jcyl-castilla-y-leon.json", offline, resume)
        current = day_rows(target, cache, registry, offline, resume)
        capital = [row for item, row in current if item["bloque"] == CAPITAL]
        province = [row for item, row in current if item["bloque"] == PROVINCE]
        capital_error = None
        if any(not row["guardia_intervalos"] for row in capital):
            capital_error = "La capital no publica para todas sus guardias el horario de 9:00 a 9:00."
        overnight = []
        try:
            previous = day_rows(target - timedelta(days=1), cache, registry, offline, resume, capital_only=True)
            overnight = [overnight_row(row, target) for _, row in previous if row["guardia_intervalos"]]
            if len(overnight) != len(previous):
                capital_error = capital_error or "La guardia de la madrugada no publica horario exacto."
        except (OSError, ValueError, KeyError, TypeError) as error:
            capital_error = f"No se confirma la guardia de la madrugada (día anterior): {error}"
        rows = combine(overnight + capital + province)
        locate_and_catalogue(rows, "Soria")
        reports.append({
            "nombre": CAPITAL,
            "estado": "parcial" if capital_error else "disponible",
            "farmacias": len(capital) + len(overnight),
            **({"error": capital_error} if capital_error else {}),
        })
        reports.append({
            "nombre": PROVINCE,
            "estado": "parcial",
            "farmacias": len(province),
            "error": (
                "El COF publica las farmacias de guardia de la provincia («hasta las 22:00» o "
                "«24 horas»), pero no la hora de inicio; pueden ser guardias localizadas."
            ),
        })
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Soria: {error}", flush=True)
        reports.append({"nombre": "Guardias COF Soria", "estado": "error", "error": str(error)})
    return publish(target, "Soria", SOURCE, rows, reports, authoritative_sources={SOURCE})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/soria")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
