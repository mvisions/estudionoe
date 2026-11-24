#!/usr/bin/env python3
"""Download regional pharmacy POIs without filtering by country."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from scrape_mes import write_json

OUT = Path(__file__).resolve().parent.parent / "public/data/farmacias-osm-espana.json"
REGIONS = {
    "sur": (36.0, -9.5, 38.5, -1.0),
    "norte": (42.0, -9.5, 44.0, 4.5),
    "este": (38.5, -1.0, 42.0, 4.5),
    "oeste": (38.5, -9.5, 42.0, -1.0),
    "centro": (39.5, -5.0, 42.0, -1.0),
    "canarias": (27.5, -18.5, 29.5, -13.0),
    "ceuta": (35.8, -5.5, 36.0, -5.2),
    "melilla": (35.2, -3.1, 35.4, -2.8),
}
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def query_for(region):
    bounds = ",".join(str(v) for v in REGIONS[region])
    return (
        '[out:json][timeout:180];'
        f'node["amenity"="pharmacy"]({bounds});out body;'
    )


def parse_response(data, region):
    if data.get("remark"):
        raise ValueError(f"Overpass no completó {region}: {data['remark']}")
    elements = data.get("elements")
    if not isinstance(elements, list) or not elements:
        raise ValueError(f"Overpass devolvió una región vacía o inválida: {region}.")
    rows = []
    south, west, north, east = REGIONS[region]
    for element in elements:
        tags = element.get("tags", {})
        if (element.get("type") != "node" or tags.get("amenity") != "pharmacy"
                or not isinstance(element.get("id"), int)):
            raise ValueError(f"Elemento inesperado en {region}.")
        lat, lng = element.get("lat"), element.get("lon")
        if (not isinstance(lat, (int, float)) or isinstance(lat, bool)
                or not isinstance(lng, (int, float)) or isinstance(lng, bool)
                or not south <= lat <= north or not west <= lng <= east):
            raise ValueError(f"Coordenadas inválidas en {region}: {element['id']}.")
        rows.append({
            "id": f"osm-{element['id']}", "cofm_id": None,
            "nombre": tags.get("name", "Farmacia"),
            "direccion": (tags.get("addr:street", "")+" "+tags.get("addr:housenumber", "")).strip(),
            "localidad": tags.get("addr:city", tags.get("addr:town", tags.get("addr:village", ""))),
            "zona": "", "provincia": tags.get("addr:province", ""),
            "telefono": tags.get("phone", tags.get("contact:phone")),
            "horario": tags.get("opening_hours"), "guardia": False, "guardia_franja": None,
            "lat": lat, "lng": lng,
        })
    return rows


def download(region):
    errors = []
    for endpoint in ENDPOINTS:
        req = urllib.request.Request(
            endpoint, data=urllib.parse.urlencode({"data": query_for(region)}).encode(),
            headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=240) as response:
                return parse_response(json.load(response), region)
        except (OSError, ValueError) as error:
            errors.append(f"{endpoint}: {error}")
            print(f"ERROR {region}: {error}", flush=True)
    raise RuntimeError(f"No se pudo descargar {region}. "+"; ".join(errors))


def refresh(regions, output=OUT):
    old = json.loads(output.read_text()) if output.exists() else []
    batches = {}
    for region in regions:
        print(f"Descargando región {region} sin filtro de país...", flush=True)
        batches[region] = download(region)
        print(f"{region}: {len(batches[region])} farmacias.", flush=True)
        if len(regions)>1:
            time.sleep(5)
    if set(regions)==set(REGIONS):
        rows = []
    else:
        def replaced(row):
            lat, lng = row.get("lat"), row.get("lng")
            if lat is None or lng is None:
                return False
            return any(south <= lat <= north and west <= lng <= east
                       for south, west, north, east in (REGIONS[r] for r in regions))
        rows = [r for r in old if not replaced(r)]
    merged = {r["id"]:r for r in rows}
    for batch in batches.values():
        merged.update({r["id"]:r for r in batch})
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, list(merged.values()))
    print(f"Catálogo publicado: {len(merged)} farmacias; todas las regiones solicitadas verificadas.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", action="append", choices=REGIONS,
                        help="Actualizar solo estas regiones conservando las demás; por defecto todas.")
    args = parser.parse_args()
    try:
        refresh(list(dict.fromkeys(args.region or REGIONS)))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}. El catálogo anterior no se reemplaza.", flush=True)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
