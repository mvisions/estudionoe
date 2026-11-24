#!/usr/bin/env python3
"""Merge all known pharmacies without dropping incomplete provincial areas."""
import json
import math
import re
from pathlib import Path

from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import saved_address_signature

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def coordinates(row):
    if row.get("ubicacion_pendiente_verificacion") is True:
        return None
    lat, lng = row.get("lat"), row.get("lng")
    if (not isinstance(lat, (int, float)) or isinstance(lat, bool)
            or not isinstance(lng, (int, float)) or isinstance(lng, bool)
            or not math.isfinite(lat) or not math.isfinite(lng)
            or not -90 <= lat <= 90 or not -180 <= lng <= 180 or (lat == 0 and lng == 0)):
        return None
    return lng, lat


def in_ring(point, ring):
    x, y = point
    inside = False
    for a, b in zip(ring, [*ring[1:], ring[0]]):
        ax, ay = a[:2]
        bx, by = b[:2]
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def province_polygons(geojson, provinces):
    names = {province["codigo"]: province["nombre"] for province in provinces}
    geometry_codes = {feature["properties"]["cod_prov"] for feature in geojson["features"]}
    missing = geometry_codes - set(names)
    if missing:
        raise ValueError(f"Faltan provincias en el catálogo: {', '.join(sorted(missing))}.")
    polygons = []
    for feature in geojson["features"]:
        code = feature["properties"]["cod_prov"]
        name = names[code]
        geometry = feature["geometry"]
        if geometry["type"] not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Geometría provincial no reconocible: {name}")
        parts = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for rings in parts:
            outer = rings[0]
            xs, ys = zip(*(p[:2] for p in outer))
            polygons.append((name, (min(xs), min(ys), max(xs), max(ys)), rings))
    return polygons


def assign_province(row, polygons):
    point = coordinates(row)
    if not point or row.get("provincia"):
        return dict(row)
    x, y = point
    for name, (west, south, east, north), rings in polygons:
        if (west <= x <= east and south <= y <= north
                and in_ring(point, rings[0]) and not any(in_ring(point, hole) for hole in rings[1:])):
            return {**row, "provincia": name}
    return dict(row)


def identity_keys(row):
    province = slugify(row.get("provincia", ""))
    if not province:
        return []
    keys = []
    phone = re.sub(r"\D", "", str(row.get("telefono") or "")).removeprefix("34")
    if len(phone) == 9:
        keys.append(("phone", province, phone))
    address = row.get("direccion", "")
    signature = saved_address_signature(address, row.get("localidad", ""))
    if signature and row.get("localidad") and re.search(r"\d", address):
        keys.append(("address", province, signature))
    return keys


def different_phone(a, b):
    phones = [re.sub(r"\D", "", str(row.get("telefono") or "")).removeprefix("34") for row in (a, b)]
    return all(len(phone) == 9 for phone in phones) and phones[0] != phones[1]


def merge_catalogs(osm, catalogs, polygons):
    """One row per pharmacy: later catalogs replace earlier rows with the same id, the OSM node
    linked by the 15 m locator (osm_id) or a unique phone/exact-address identity."""
    result = {}
    index = {}
    row_keys = {}
    replaced = {}

    def current(identifier):
        seen = set()
        while identifier in replaced and identifier not in seen:
            seen.add(identifier)
            identifier = replaced[identifier]
        return identifier if identifier in result else None

    for source in (osm, *catalogs):
        for original in source:
            row = assign_province(original, polygons)
            row.update(guardia=False, guardia_franja=None)
            keys = identity_keys(row)
            matches = set().union(*(index.get(key, set()) for key in keys)) if keys else set()
            identifier = row["id"]
            previous_ids = []
            if not identifier.startswith("osm-"):
                linked = current(row.get("osm_id")) if row.get("osm_id") else None
                if linked and linked != identifier and not different_phone(row, result[linked]):
                    previous_ids.append(linked)
                if len(matches) == 1:
                    previous_ids.append(next(iter(matches)))
            if identifier in result:
                previous_ids.append(identifier)
            for previous_id in dict.fromkeys(previous_ids):
                previous = result.pop(previous_id)
                if (row.get("ubicacion_pendiente_verificacion") is not True
                        and row.get("ubicacion_requiere_verificacion") is not True
                        and not coordinates(row) and coordinates(previous)):
                    row.update(lat=previous["lat"], lng=previous["lng"],
                               precision_ubicacion=previous.get("precision_ubicacion", "farmacia"),
                               fuente_coordenadas=previous.get("fuente_coordenadas", "https://www.openstreetmap.org"))
                    if previous.get("nota_ubicacion"):
                        row["nota_ubicacion"] = previous["nota_ubicacion"]
                    node = previous_id if previous_id.startswith("osm-") else previous.get("osm_id")
                    if node and not row.get("osm_id"):
                        row["osm_id"] = node
                previous_keys = row_keys.pop(previous_id, None) or identity_keys(previous)
                for key in previous_keys:
                    index.get(key, set()).discard(previous_id)
                keys = list(set(keys) | set(previous_keys))
                if previous_id != identifier:
                    replaced[previous_id] = identifier
            result[identifier] = row
            row_keys[identifier] = keys
            for key in keys:
                index.setdefault(key, set()).add(identifier)
    return list(result.values())


BASE_CATALOGS = ("farmacias-registro-jcyl.json",)


def catalog_paths(output_dir):
    """Base catalogs (official registries) right after OSM, then provincial catalogs that refine them."""
    paths = [path for path in sorted(output_dir.glob("farmacias-*.json"))
             if path.name not in {"farmacias-osm-espana.json", "farmacias-espana-hoy.json",
                                  "farmacias-todas.json", "farmacias-coordenadas-verificadas.json"}]
    return sorted(paths, key=lambda path: path.name not in BASE_CATALOGS)


def run(output_dir=OUT_DIR, data_dir=DATA_DIR):
    osm = json.loads((output_dir / "farmacias-osm-espana.json").read_text())
    provinces = json.loads((data_dir / "provincias.json").read_text())
    geometry = json.loads((data_dir / "limites-provincias.geojson").read_text())
    polygons = province_polygons(geometry, provinces)
    catalogs = [json.loads(path.read_text()) for path in catalog_paths(output_dir)]
    rows = merge_catalogs(osm, catalogs, polygons)
    write_json(output_dir / "farmacias-espana-hoy.json", rows)
    print(f"Catálogo nacional: {len(rows)} farmacias; sin exclusiones por rectángulos provinciales.")
    return rows


if __name__ == "__main__":
    run()
