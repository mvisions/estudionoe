#!/usr/bin/env python3
"""Verify and permanently save locations for guard pharmacies without coordinates."""
import argparse
import json
import math
import os
from datetime import date
from pathlib import Path
import re

from merge_espana import coordinates, identity_keys
from proximidad import RADIO_M, Geocoder, PharmacyIndex, propose, resolve, split_address
from scrape_mes import OUT_DIR, slugify, write_json

LOCATION_FIELDS = (
    "lat", "lng", "precision_ubicacion", "fuente_coordenadas", "nota_ubicacion",
    "osm_id", "ajuste_ubicacion_m",
)
LEDGER = "farmacias-coordenadas-verificadas.json"


def location_key(row, province=None):
    return (
        str(row.get("id") or ""),
        slugify(row.get("provincia") or province or ""),
        " ".join((row.get("localidad") or "").casefold().split()),
        " ".join((row.get("direccion") or "").casefold().split()),
    )


def apply_location(row, location):
    if row.get("ubicacion_pendiente_verificacion") is not True and not coordinates(row):
        row.update({field: location[field] for field in LOCATION_FIELDS if field in location})
    return row


def verified_within_radius(row):
    distance = row.get("ajuste_ubicacion_m")
    return (
        coordinates(row)
        and isinstance(distance, (int, float))
        and math.isfinite(distance)
        and 0 <= distance <= RADIO_M
    )


def clear_location(row):
    for field in LOCATION_FIELDS:
        row.pop(field, None)


def _read_rows(path):
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"El archivo debe contener una lista: {path}")
    return rows


def _guard_date(path):
    match = re.search(r"-(\d{4}-\d{2}-\d{2})\.json$", path.name)
    return match[1] if match else ""


def _ordered_guard_files(output):
    files = list(output.glob("guardias-*.json"))
    today = date.today().isoformat()
    current = sorted(path for path in files if _guard_date(path) == today)
    remaining = sorted(
        (path for path in files if _guard_date(path) != today),
        key=_guard_date,
        reverse=True,
    )
    return current + remaining


def locate_guardias(output=OUT_DIR, cache=None, network=True, max_requests=120, geocoder=None,
                    province=None, excluded_provinces=(), catalog_candidates=()):
    """Locate guard rows and, after them, rows of the named catalogs (e.g. the JCyL registry)."""
    output = Path(output)
    guard_files = _ordered_guard_files(output)
    province_slug = slugify(province) if province else None
    if province_slug:
        guard_files = [
            path for path in guard_files
            if path.stem.removeprefix("guardias-").rsplit("-", 3)[0] == province_slug
        ]
    excluded = {slugify(name) for name in excluded_provinces}
    guard_files = [
        path for path in guard_files
        if path.stem.removeprefix("guardias-").rsplit("-", 3)[0] not in excluded
    ]
    catalog_files = [
        path for path in sorted(output.glob("farmacias-*.json"))
        if path.name not in {
            "farmacias-espana-hoy.json", "farmacias-osm-espana.json",
            "farmacias-todas.json", LEDGER,
        }
    ]
    catalogs = {path: _read_rows(path) for path in catalog_files}
    guard_data = {path: _read_rows(path) for path in guard_files}
    changed_catalogs = set()
    changed_guards = set()
    for path, rows in catalogs.items():
        for row in rows:
            if (row.get("ubicacion_requiere_verificacion") is True and coordinates(row)
                    and not verified_within_radius(row)):
                clear_location(row)
                changed_catalogs.add(path)
    for path, rows in guard_data.items():
        for row in rows:
            if (row.get("ubicacion_requiere_verificacion") is True and coordinates(row)
                    and not verified_within_radius(row)):
                clear_location(row)
                changed_guards.add(path)

    osm = _read_rows(output / "farmacias-osm-espana.json")
    national = _read_rows(output / "farmacias-espana-hoy.json")
    known = {}
    for row in (*osm, *(row for rows in catalogs.values() for row in rows), *national):
        if row.get("id") and coordinates(row):
            previous = known.get(row["id"])
            if previous is None or not coordinates(previous):
                known[row["id"]] = row
    index = PharmacyIndex(known.values())

    ledger_path = output / LEDGER
    ledger_rows = _read_rows(ledger_path)
    valid_ledger_rows = [row for row in ledger_rows if verified_within_radius(row)]
    ledger = {location_key(row): row for row in valid_ledger_rows}
    ledger_changed = len(valid_ledger_rows) != len(ledger_rows)
    for path, rows in catalogs.items():
        province = path.stem.removeprefix("farmacias-")
        for row in rows:
            if row.get("ubicacion_pendiente_verificacion") is True:
                continue
            saved = ledger.get(location_key(row, province))
            if saved:
                was_unlocated = not coordinates(row)
                apply_location(row, saved)
                if was_unlocated:
                    changed_catalogs.add(path)

    for path, rows in guard_data.items():
        province = path.stem.removeprefix("guardias-").rsplit("-", 3)[0]
        for row in rows:
            if row.get("ubicacion_pendiente_verificacion") is True:
                continue
            saved = ledger.get(location_key(row))
            if saved:
                was_unlocated = not coordinates(row)
                apply_location(row, saved)
                if was_unlocated:
                    changed_guards.add(path)
            if coordinates(row):
                continue
            province_catalogs = [
                catalog_rows for catalog_path, catalog_rows in catalogs.items()
                if catalog_path.stem.removeprefix("farmacias-") == slugify(province)
            ]
            exact = {
                candidate["id"]: candidate
                for catalog_rows in province_catalogs
                for candidate in catalog_rows
                if candidate.get("id") == row.get("id") and coordinates(candidate)
            }
            if len(exact) == 1:
                apply_location(row, next(iter(exact.values())))
                changed_guards.add(path)
                continue
            keys = set(identity_keys({**row, "provincia": row.get("provincia") or province}))
            matches = {
                candidate["id"]: candidate
                for catalog_rows in province_catalogs
                for candidate in catalog_rows
                if candidate.get("id") and coordinates(candidate)
                and keys.intersection(identity_keys({
                    **candidate, "provincia": candidate.get("provincia") or province
                }))
            }
            if len(matches) == 1:
                location = matches.popitem()[1]
                apply_location(row, location)
                changed_guards.add(path)

    candidates = {}
    for path in guard_files:
        for row in guard_data[path]:
            if row.get("ubicacion_pendiente_verificacion") is True:
                continue
            key = location_key(row)
            if coordinates(row) or key in ledger or key in candidates:
                continue
            if split_address(row.get("direccion")) and row.get("localidad") and row.get("provincia"):
                candidates[key] = row

    wanted = set(catalog_candidates)
    unknown = wanted - {path.name for path in catalogs}
    if unknown:
        raise FileNotFoundError(f"Catálogo para ubicar no encontrado: {', '.join(sorted(unknown))}")
    for path, rows in catalogs.items():
        if path.name not in wanted:
            continue
        for row in rows:
            row_province = slugify(row.get("provincia") or "")
            if (row.get("ubicacion_pendiente_verificacion") is True or coordinates(row)
                    or (province_slug and row_province != province_slug) or row_province in excluded
                    or coordinates(known.get(row.get("id")) or {})):
                continue
            key = location_key(row)
            if key in ledger or key in candidates:
                continue
            if split_address(row.get("direccion")) and row.get("localidad") and row.get("provincia"):
                candidates[key] = row

    if geocoder is None:
        geocoder = Geocoder(cache=cache, network=network, ttl_days=365)
    proposals = {}
    processed = 0
    for key, row in candidates.items():
        references = geocoder.references(row)
        if references is not None:
            proposals[key] = propose(row, references, index)
        else:
            proposals[key] = {"estado": "sin_referencia"}
        processed += 1
        if geocoder.errors:
            break
        if max_requests and geocoder.requests >= max_requests:
            break

    placements, pending = resolve(proposals)
    for key, location in placements.items():
        source = candidates[key]
        saved = {**{field: source.get(field) for field in
                    ("id", "provincia", "localidad", "direccion")},
                 **location}
        ledger[key] = saved
        for path, rows in catalogs.items():
            province = path.stem.removeprefix("farmacias-")
            for row in rows:
                if location_key(row, province) == key:
                    if not coordinates(row):
                        changed_catalogs.add(path)
                    apply_location(row, location)
        for path, rows in guard_data.items():
            for row in rows:
                if location_key(row) == key:
                    if not coordinates(row):
                        changed_guards.add(path)
                    apply_location(row, location)

    if changed_catalogs or changed_guards:
        for path in changed_catalogs:
            rows = catalogs[path]
            write_json(path, rows)
        for path in changed_guards:
            rows = guard_data[path]
            write_json(path, rows)
            coverage_path = output / path.name.replace("guardias-", "cobertura-", 1)
            if coverage_path.exists():
                coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
                coverage["con_coordenadas"] = sum(bool(coordinates(row)) for row in rows)
                write_json(coverage_path, coverage)
    if placements or ledger_changed:
        write_json(ledger_path, sorted(ledger.values(), key=lambda row: location_key(row)))

    unresolved = sum(not coordinates(row) for rows in guard_data.values() for row in rows)
    print(
        f"Geolocalización de guardias: {len(placements)} ubicaciones verificadas y guardadas; "
        f"{unresolved} registros siguen sin coordenadas; "
        f"{len(candidates) - processed} pendientes de próximas ejecuciones; "
        f"{geocoder.requests} consultas externas."
    )
    if pending:
        print(f"Sin confirmación a 15 m: {len(pending)}; no se asignaron coordenadas.")
    geocoder.save()
    if geocoder.errors:
        raise RuntimeError(f"El geocodificador notificó {geocoder.errors} errores; revisa los avisos anteriores.")
    return placements, pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    parser.add_argument(
        "--cache", type=Path,
        default=default_state / "farmacia" / "geocache-guardias.json",
        help="Caché persistente de las consultas de geocodificación.",
    )
    parser.add_argument("--sin-red", action="store_true", help="Usar solo la caché local.")
    parser.add_argument("--provincia", help="Limitar las guardias procesadas a una provincia.")
    parser.add_argument("--excluir-provincia", action="append", default=[],
                        help="Omitir guardias de una provincia; se puede repetir.")
    parser.add_argument(
        "--max-consultas", type=int, default=120,
        help="Límite de peticiones de red por ejecución; 0 procesa todas las guardias guardadas.",
    )
    parser.add_argument(
        "--catalogo", action="append", default=[],
        help="Ubicar también, después de las guardias, las filas sin coordenadas de este catálogo "
             "(p. ej. farmacias-registro-jcyl.json); se puede repetir.",
    )
    args = parser.parse_args()
    if args.max_consultas < 0:
        parser.error("--max-consultas no puede ser negativo.")
    locate_guardias(cache=args.cache, network=not args.sin_red, max_requests=args.max_consultas,
                    province=args.provincia, excluded_provinces=args.excluir_provincia,
                    catalog_candidates=args.catalogo)


if __name__ == "__main__":
    main()
