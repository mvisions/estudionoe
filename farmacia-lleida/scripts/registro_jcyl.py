#!/usr/bin/env python3
"""Catálogo base de Castilla y León con todas las farmacias del registro oficial de la Junta.

El registro de datos abiertos (CC BY 4.0) contiene más farmacias que OpenStreetMap en la región,
pero no publica coordenadas. Las filas se publican sin marcador salvo que el localizador haya
contrastado la posición a 15 m o menos (registro de coordenadas verificadas) o que el catálogo
nacional enlace la farmacia con un punto de OpenStreetMap por teléfono o dirección exacta.
"""
import argparse
import json
import re
from pathlib import Path

from locate_guardias import LEDGER, apply_location, location_key, verified_within_radius
from proximidad import ARTICLES, STREET_TYPES, fold
from scrape_mes import OUT_DIR, write_json
from scrape_soria import display, phone_number
from scrape_zamora import cached_registry

FILE = "farmacias-registro-jcyl.json"
SOURCE = ("https://analisis.datosabiertos.jcyl.es/explore/dataset/"
          "registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/")
PROVINCES = {
    "05": "Ávila", "09": "Burgos", "24": "León", "34": "Palencia", "37": "Salamanca",
    "40": "Segovia", "42": "Soria", "47": "Valladolid", "49": "Zamora",
}
MIN_KEPT = 0.9


def street_name(value):
    """Registry street with the INE trailing articles moved forward: «PLAZA DOLORES (DE) (LOS)» → «Plaza de los Dolores»."""
    street = display(value)
    articles = []
    while (match := re.fullmatch(r"(.+?)\s*\(([^()]+)\)", street)) and set(fold(match[2]).split()) <= ARTICLES:
        street, articles = match[1], [match[2].lower(), *articles]
    if not articles:
        return street
    words = street.split()
    if len(words) > 1 and fold(words[0]) in STREET_TYPES:
        return " ".join([words[0], *articles, *words[1:]])
    return " ".join([articles[0].capitalize(), *articles[1:], *words])


def build_row(item):
    registration = str(item["num_reg"]).strip()
    code = registration.split("-", 1)[0]
    if code not in PROVINCES or fold(item.get("provincia")) != fold(PROVINCES[code]):
        raise ValueError(f"Provincia no reconocible en el registro: {registration}")
    municipality = str(item.get("municipio") or "")
    locality = str(item.get("localidad") or municipality)
    street = street_name(item.get("calle"))
    number = str(item.get("numero") or "").strip()
    if not street:
        raise ValueError(f"Registro sin calle: {registration}")
    has_number = number and fold(number) not in ("s n", "sn", "0")
    return {
        "id": f"jcyl-{registration.lower()}",
        "num_reg": registration,
        "nombre": f"Farmacia {display(item.get('nombre_comercial'))}",
        "direccion": f"{street}, {number if has_number else 's/n'}",
        "localidad": display(municipality if fold(locality) == fold(municipality) else locality),
        "provincia": PROVINCES[code],
        "codigo_postal": str(item.get("codigo_postal") or "").strip() or None,
        "telefono": phone_number(item.get("telefono")),
        "fuente": SOURCE,
        "guardia": False,
        "guardia_franja": None,
        "lat": None,
        "lng": None,
    }


def build_catalog(registry, ledger_rows=(), previous_count=0):
    rows = [build_row(item) for item in registry]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("El registro repite números de registro.")
    missing = set(PROVINCES.values()) - {row["provincia"] for row in rows}
    if missing:
        raise ValueError(f"El registro no incluye: {', '.join(sorted(missing))}.")
    if previous_count and len(rows) < MIN_KEPT*previous_count:
        raise ValueError(f"El registro bajó de {previous_count} a {len(rows)} farmacias; se conserva el anterior.")
    ledger = {location_key(row): row for row in ledger_rows if verified_within_radius(row)}
    for row in rows:
        saved = ledger.get(location_key(row))
        if saved:
            apply_location(row, saved)
    return sorted(rows, key=lambda row: row["id"])


def run(cache, output=OUT_DIR, offline=False, resume=False):
    output = Path(output)
    cache.mkdir(parents=True, exist_ok=True)
    path = output / FILE
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    ledger_path = output / LEDGER
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else []
    try:
        registry = cached_registry(cache / "registro-jcyl-castilla-y-leon.json", offline, resume)
        rows = build_catalog(registry, ledger, len(previous))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR registro JCyL: {error}", flush=True)
        return False
    write_json(path, rows)
    located = sum(row["lat"] is not None for row in rows)
    print(f"Registro JCyL: {len(rows)} farmacias de Castilla y León; {located} con ubicación verificada.",
          flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/registro-jcyl")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.cache_documentos, offline=args.sin_red, resume=args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
