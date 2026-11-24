#!/usr/bin/env python3
"""Import the COF León dated pharmacy rota and resolve municipalities conservatively."""
import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
from datetime import date, datetime, time as wall_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import OUT_DIR, fetch, slugify

SOURCE = "https://www.cofleon.es/index.php/farmacias-de-guardia/"
REGISTRY = (
    "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/"
    "registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/exports/json"
)
TZ = ZoneInfo("Europe/Madrid")


def normalize(value):
    plain = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(character for character in plain if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()


def phone_numbers(value):
    matches = re.findall(r"(?<!\d)(?:\d[\s.-]?){8}\d(?!\d)", value or "")
    return list(dict.fromkeys(re.sub(r"\D", "", match) for match in matches
                              if len(re.sub(r"\D", "", match)) == 9))


def split_locality(address, localities):
    normalized_address = normalize(address)
    for key, locality in sorted(localities.items(), key=lambda entry: len(entry[0]), reverse=True):
        if not normalized_address.endswith(key):
            continue
        for start in range(len(address)):
            if normalize(address[start:]) == key:
                street = address[:start].strip(" ,/")
                if street:
                    return street, locality
    words = address.split()
    for count in range(1, len(words) + 1):
        suffix = normalize(" ".join(words[-count:]))
        locality = localities.get(suffix)
        if locality:
            street = " ".join(words[:-count]).strip(" ,")
            if street:
                return street, locality
    raise ValueError(f"No se identifica el municipio oficial en la dirección: {address}")


def registry_indexes(registry):
    if not isinstance(registry, list) or not registry:
        raise ValueError("El registro oficial JCyL de León está vacío o no es una lista.")
    localities = {}
    municipalities = {}
    phones = {}
    for row in registry:
        if row.get("provincia") == "LEON" and row.get("localidad"):
            locality = str(row["localidad"])
            localities.setdefault(normalize(locality), locality)
            municipality = normalize(row.get("municipio"))
            if municipality:
                municipalities.setdefault(municipality, set()).add(locality)
        number = re.sub(r"\D", "", str(row.get("telefono") or ""))
        if len(number) == 9:
            phones.setdefault(number, []).append(row)
    for municipality, names in municipalities.items():
        if len(names) == 1 and municipality not in localities:
            localities[municipality] = next(iter(names))
    if not localities:
        raise ValueError("El registro oficial JCyL no contiene localidades de León.")
    return localities, phones


def registered_outside_leon(phones, registry_phones):
    if len(phones) != 1:
        return False
    matches = registry_phones.get(phones[0], [])
    return len(matches) == 1 and matches[0].get("provincia") != "LEON"


def registered_outside_leon_by_address(name, address, registry):
    """Identify registry rows without phone by locality, holder name and street number."""
    normalized_address = normalize(address)
    address_words = set(normalized_address.split())
    name_words = set(normalize(name).split())
    if not name_words:
        return False
    matches = [
        row for row in registry
        if row.get("provincia") != "LEON"
        and normalize(row.get("localidad"))
        and normalized_address.endswith(" " + normalize(row.get("localidad")))
        and name_words <= set(normalize(row.get("nombre_comercial")).split())
        and normalize(row.get("numero")) in address_words
    ]
    return len(matches) == 1


def pharmacy_identity(name, address, locality, phones, registry_phones):
    matches = []
    for phone in phones:
        matches.extend(registry_phones.get(phone, []))
    matches = [row for row in matches
               if normalize(row.get("localidad")) == normalize(locality)]
    if len(matches) == 1:
        official = matches[0]
        registration = str(official.get("num_reg") or "")
        address_parts = [official.get("calle"), official.get("numero")]
        official_address = ", ".join(str(part).strip() for part in address_parts if part)
        identifier = f"jcyl-{slugify(registration)}" if registration else ""
        if identifier:
            return identifier, official_address or address, phones[0] if phones else None
    signature = "|".join((normalize(name), normalize(address), normalize(locality),
                          phones[0] if phones else ""))
    identifier = "cof-leon-" + hashlib.sha256(signature.encode()).hexdigest()[:16]
    return identifier, address, phones[0] if phones else None


def combine_assignments(rows):
    combined = {}
    for row in rows:
        previous = combined.get(row["id"])
        if previous is None:
            combined[row["id"]] = {
                **row,
                "guardia_intervalos": list(row.get("guardia_intervalos", [])),
                "guardia_franjas": list(row.get("guardia_franjas", [])),
                "localidades_atendidas": list(row.get("localidades_atendidas", [])),
            }
            continue
        intervals = previous["guardia_intervalos"]
        for interval in row.get("guardia_intervalos", []):
            if interval not in intervals:
                intervals.append(interval)
        for field in ("guardia_franjas", "localidades_atendidas"):
            previous[field] = list(dict.fromkeys(previous[field] + row.get(field, [])))
        previous["guardia_desde_ayer"] = (
            previous.get("guardia_desde_ayer") is True
            or row.get("guardia_desde_ayer") is True
        )
        if row.get("guardia_apertura") == "desconocida":
            previous["guardia_apertura"] = "desconocida"
        previous["guardia_franja"] = " · ".join(previous["guardia_franjas"])
    return list(combined.values())


def parse_calendar(content, target, registry):
    table = re.search(
        r"<table\b(?=[^>]*\bid=['\"]farmaciasList['\"])[^>]*>(.*?)</table>",
        content, re.I | re.S,
    )
    if table is None:
        raise ValueError("La página oficial no contiene la tabla farmaciasList.")

    localities, registry_phones = registry_indexes(registry)
    parsed_rows = []
    for attributes, body in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", table.group(1), re.I | re.S):
        index = re.search(r"\bdata-index=['\"](\d+)['\"]", attributes, re.I)
        if index is None:
            continue
        spans = {}
        for span_attributes, value in re.findall(r"<span\b([^>]*)>(.*?)</span>", body, re.I | re.S):
            classes = re.search(r"\bclass=['\"]([^'\"]*)['\"]", span_attributes, re.I)
            if classes:
                for class_name in classes.group(1).split():
                    spans[class_name] = clean(value)
        for required in ("farmacia-nombre", "farmacia-direccion", "farmacia-telefono"):
            if not spans.get(required):
                raise ValueError(f"Fila {index[1]} sin campo oficial {required}.")
        parsed_rows.append((int(index[1]), attributes, spans))

    parsed_rows.sort(key=lambda entry: entry[0])
    if not parsed_rows or [row[0] for row in parsed_rows] != list(range(len(parsed_rows))):
        raise ValueError("La tabla oficial está vacía o tiene índices incompletos.")

    previous_date = target - timedelta(days=1)
    next_date = target + timedelta(days=1)
    expected_nights = {
        (previous_date.strftime("%d/%m"), target.strftime("%d/%m")): "previous",
        (target.strftime("%d/%m"), next_date.strftime("%d/%m")): "current",
    }
    found_nights = set()
    daytime_count = 0
    rows = []

    for _, attributes, spans in parsed_rows:
        night_flag = re.search(r"\bdata-nocturna=['\"](true|false)['\"]", attributes, re.I)
        if night_flag is None:
            raise ValueError("Fila oficial sin tipo de turno reconocible.")
        nocturnal = night_flag[1].casefold() == "true"
        phones = phone_numbers(spans["farmacia-telefono"])
        try:
            address, locality = split_locality(spans["farmacia-direccion"], localities)
        except ValueError:
            if (registered_outside_leon(phones, registry_phones)
                    or registered_outside_leon_by_address(
                        spans["farmacia-nombre"], spans["farmacia-direccion"], registry)):
                continue
            raise
        identifier, canonical_address, phone = pharmacy_identity(
            spans["farmacia-nombre"], address, locality, phones, registry_phones
        )
        row = {
            "id": identifier,
            "nombre": "",
            "direccion": canonical_address,
            "localidad": locality.title(),
            "provincia": "León",
            "telefono": phone,
            "guardia": True,
            "fecha_guardia": target.isoformat(),
            "localidades_atendidas": [locality.title()],
            "guardia_intervalos": [],
            "guardia_franjas": [],
            "lat": None,
            "lng": None,
            "fuente": SOURCE,
            "ubicacion_requiere_verificacion": True,
        }

        if not nocturnal:
            daytime_count += 1
            row["guardia_apertura"] = "desconocida"
            row["guardia_franjas"] = [
                "Guardia diurna COF León; horario exacto pendiente, confirmar por teléfono."
            ]
        else:
            schedule = spans.get("farmacia-horario", "")
            match = re.search(
                r"desde\s+las\s+(\d{1,2}:\d{2})\s+del\s+d[ií]a\s+(\d{1,2}/\d{1,2})"
                r"\s+hasta\s+las\s+(\d{1,2}:\d{2})\s+del\s+d[ií]a\s+(\d{1,2}/\d{1,2})",
                schedule, re.I,
            )
            if match is None:
                raise ValueError("Turno nocturno sin fechas y horas oficiales reconocibles.")
            start_label, end_label = match[2], match[4]
            period = expected_nights.get((start_label, end_label))
            if period is None:
                raise ValueError(
                    f"El turno nocturno ({start_label}–{end_label}) no coincide con {target}."
                )
            start_time = datetime.strptime(match[1], "%H:%M").time()
            end_time = datetime.strptime(match[3], "%H:%M").time()
            start_date = previous_date if period == "previous" else target
            end_date = target if period == "previous" else next_date
            start = datetime.combine(start_date, start_time).replace(tzinfo=TZ)
            end = datetime.combine(end_date, end_time).replace(tzinfo=TZ)
            if end <= start:
                raise ValueError("El intervalo nocturno oficial no avanza en el tiempo.")
            if period == "previous":
                start = datetime.combine(target, wall_time.min).replace(tzinfo=TZ)
                row["guardia_desde_ayer"] = True
                label = f"Madrugada de guardia nocturna anterior · 00:00–{end_time:%H:%M}"
            else:
                label = f"Guardia nocturna COF León · {start_time:%H:%M}–{end_time:%H:%M}"
            row["guardia_intervalos"] = [{"inicio": start.isoformat(), "fin": end.isoformat()}]
            row["guardia_franjas"] = [label]
            found_nights.add(period)

        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
        rows.append(row)

    if found_nights != {"previous", "current"} or daytime_count == 0:
        raise ValueError("El calendario no confirma madrugada anterior, día y noche para la fecha.")
    return combine_assignments(rows)


def cached_text(url, path, offline=False, resume=False):
    if (offline or resume) and path.exists():
        return path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
    content = fetch(url)
    path.write_text(content, encoding="utf-8")
    time.sleep(1.1)
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
    if not isinstance(data, list):
        raise ValueError("La respuesta del registro oficial JCyL no es una lista.")
    return data


def run(target, cache, offline=False, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, reports = [], []
    try:
        page = cached_text(SOURCE, cache / f"{target}.html", offline, resume)
        registry = cached_registry(cache / "registro-jcyl-castilla-y-leon.json", offline, resume)
        rows = parse_calendar(page, target, registry)
        locate_and_catalogue(rows, "León")
        reports.append({
            "nombre": "Calendario COF León",
            "estado": "parcial",
            "farmacias": len(rows),
            "error": (
                "Turnos publicados por el Colegio para la fecha; el horario diurno exacto "
                "y la cobertura de todas las derivaciones no están acreditados. Confirmar por teléfono."
            ),
        })
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR León: {error}", flush=True)
        reports.append({"nombre": "Calendario COF León", "estado": "error", "error": str(error)})
    publish(target, "León", SOURCE, rows, reports)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/leon")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
