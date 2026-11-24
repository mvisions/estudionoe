#!/usr/bin/env python3
"""Build a catalogue from observed schedules and geocode missing provincial addresses."""
import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request

from scrape_mes import OUT_DIR, normalize_locality, pharmacy_sector, slugify, write_json


def normalize_street(street):
    for pattern, replacement in [
        (r"\b(?:AVDA\.?|AV\.)(?=\s)", "Avenida"),
        (r"\b(?:CRTA|CTRA)\.?(?=\s)", "Carretera"),
        (r"\bC\s*/", "Calle "),
        (r"\bPZA\.?(?=\s)", "Plaza"),
        (r"\bPZ\.?(?=\s)", "Plaza"),
        (r"\bPJE\.?(?=\s)", "Pasaje"),
        (r"\b(?:N[ÚU]M\.?|N[º°])(?=\s*\d)\s*", ""),
        (r"^\s*ESQUINA\s+", ""),
    ]:
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", street).strip(" ,")


def geocode(address, locality):
    address = html.unescape(address)
    aliases = [
        normalize_street(value)
        for value in re.findall(r"\(([^()]*\d[^()]*)\)", address)
    ]
    street = normalize_street(re.sub(r"\([^)]*\)", "", address))
    queries = [street, *aliases]
    without_de = re.sub(r"\b(Avenida|Calle|Plaza)\s+DE\s+", r"\1 ", street, flags=re.IGNORECASE)
    if without_de != street:
        queries.append(without_de)
    alternate = re.sub(r",?\s+\d+\b.*$", "", street).strip(" ,")
    if alternate and alternate != street:
        queries.append(alternate)
    queries = list(dict.fromkeys(queries))
    approximate = None
    for index, query in enumerate(queries):
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": f"{query}, {locality}, Málaga, España",
            "format": "jsonv2", "limit": 5, "countrycodes": "es", "addressdetails": 1,
            "viewbox": "-5.65,37.35,-3.7,36.25", "bounded": 1,
        })
        request = urllib.request.Request(url, headers={
            "User-Agent": "FarmaciasDeGuardiaTracker/1.0 (public pharmacy map)",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            results = json.load(response)
        results.sort(key=lambda item: item.get("type") != "pharmacy")
        for item in results:
            lat, lng = float(item["lat"]), float(item["lon"])
            if not (36.25 <= lat <= 37.35 and -5.65 <= lng <= -3.7):
                continue
            details = item.get("address", {})
            names = [details.get(key, "") for key in (
                "city", "town", "village", "municipality", "suburb", "city_district",
            )]
            if slugify(locality) not in [slugify(name) for name in names]:
                continue
            if item.get("type") in {"administrative", "village", "town", "city", "municipality"}:
                continue
            number = re.search(r"\b(\d+)\b", query)
            exact = (
                item.get("type") == "pharmacy" and number is not None
                and details.get("house_number") == number.group(1)
            )
            position = {
                "lat": lat, "lng": lng,
                "precision_ubicacion": "farmacia" if exact else "aproximada",
                "fuente_coordenadas": "https://www.openstreetmap.org",
            }
            if exact:
                return position
            if approximate is None:
                approximate = position
        if index + 1 < len(queries):
            time.sleep(1.1)
    return approximate


def address_key(address, locality):
    street = normalize_street(re.sub(r"\([^)]*\)", "", html.unescape(address)))
    tokens = slugify(street).split("-")
    if not any(token.isdigit() for token in tokens):
        return None
    return (
        slugify(normalize_locality(locality)),
        tuple(token for token in tokens if token not in {"de", "del", "la", "el", "los", "las"}),
    )


def match_saved_osm(entries):
    path = OUT_DIR / "farmacias-osm-espana.json"
    if not path.exists():
        return
    index = {}
    for pharmacy in json.loads(path.read_text(encoding="utf-8")):
        key = address_key(pharmacy.get("direccion", ""), pharmacy.get("localidad", ""))
        lat, lng = pharmacy.get("lat"), pharmacy.get("lng")
        if key and lat is not None and lng is not None and 36.25 <= lat <= 37.35 and -5.65 <= lng <= -3.7:
            index.setdefault(key, []).append(pharmacy)
    for pharmacy in entries.values():
        if pharmacy.get("lat") is not None and pharmacy.get("lng") is not None:
            continue
        key = address_key(pharmacy["direccion"], pharmacy["localidad"])
        matches = index.get(key, [])
        if len(matches) == 1:
            match = matches[0]
            pharmacy.update({
                "lat": match["lat"], "lng": match["lng"],
                "precision_ubicacion": "farmacia",
                "fuente_coordenadas": "https://www.openstreetmap.org",
                "osm_id": match["id"],
            })


def catalogue():
    entries = {}
    for path in sorted(OUT_DIR.glob("guardias-malaga-*.json")):
        for original in json.loads(path.read_text(encoding="utf-8")):
            pharmacy = {**original}
            pharmacy_id = str(pharmacy.get("cofm_id") or "")
            if not pharmacy_id:
                continue
            for field in ("direccion", "localidad", "zona"):
                pharmacy[field] = html.unescape(pharmacy.get(field, "")).strip()
            locality = pharmacy["localidad"]
            if locality.upper().startswith(("SECTOR ", "BARRIADA CHURRIANA")):
                pharmacy["sector"] = locality
                pharmacy["localidad"] = "Málaga"
            if slugify(pharmacy["zona"]) == "malaga-capital":
                pharmacy["localidad"] = "Málaga"
            city = normalize_locality(pharmacy["localidad"])
            if city != pharmacy["localidad"]:
                pharmacy["sector"] = pharmacy["localidad"]
                pharmacy["localidad"] = city
            if slugify(pharmacy["localidad"]) == "torrox":
                pharmacy["direccion"] = re.sub(
                    r"\s+-\s+Torrox(?:\s+-\s+Torrox Costa)?\s*$",
                    "", pharmacy["direccion"], flags=re.IGNORECASE,
                )
            pharmacy["sector"] = pharmacy_sector(
                pharmacy["direccion"], pharmacy["localidad"], pharmacy.get("sector", ""),
            )
            pharmacy["provincia"] = "Málaga"
            pharmacy["id"] = f"29-{pharmacy_id}"
            pharmacy["guardia"] = False
            for field in ("guardia_franja", "guardia_franjas", "fecha_guardia"):
                pharmacy.pop(field, None)
            entries[pharmacy_id] = pharmacy
    saved = OUT_DIR / "farmacias-malaga.json"
    if saved.exists():
        for pharmacy in json.loads(saved.read_text(encoding="utf-8")):
            key = str(pharmacy["cofm_id"])
            if key not in entries:
                entries[key] = pharmacy
            elif pharmacy.get("lat") is not None and pharmacy.get("lng") is not None:
                for field in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas"):
                    if field in pharmacy:
                        entries[key][field] = pharmacy[field]
    sidecar = OUT_DIR / "coordenadas-malaga-capital.json"
    if sidecar.exists():
        for key, position in json.loads(sidecar.read_text(encoding="utf-8")).items():
            if key in entries and entries[key].get("lat") is None:
                entries[key].update(position)
                entries[key]["precision_ubicacion"] = "aproximada"
    match_saved_osm(entries)
    return entries


def enrich_calendar(date, entries):
    path = OUT_DIR / f"guardias-malaga-{date}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for pharmacy in rows:
        entry = entries.get(str(pharmacy.get("cofm_id", "")))
        if entry:
            for field in ("lat", "lng", "direccion", "localidad", "sector", "precision_ubicacion", "fuente_coordenadas"):
                if field in entry and (field not in ("lat", "lng") or entry[field] is not None):
                    pharmacy[field] = entry[field]
    write_json(path, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--fecha", help="Geocodificar solo farmacias de este calendario (YYYY-MM-DD).")
    args = parser.parse_args()
    entries = catalogue()
    output = OUT_DIR / "farmacias-malaga.json"
    write_json(output, list(entries.values()))
    pending = [item for item in entries.values() if (
        item.get("lat") is None or item.get("lng") is None
    ) and slugify(item["localidad"]) != "malaga"]
    if args.fecha:
        date_path = OUT_DIR / f"guardias-malaga-{args.fecha}.json"
        day_ids = {str(item["cofm_id"]) for item in json.loads(date_path.read_text(encoding="utf-8"))}
        pending = [item for item in pending if item["cofm_id"] in day_ids]
    priority = {"antequera", "alora", "san-pedro-alcantara", "san-pedro-de-alcantara"}
    pending.sort(key=lambda item: (slugify(item["localidad"]) not in priority, item["localidad"], item["cofm_id"]))
    print(f"Catálogo: {len(entries)} farmacias observadas; {len(pending)} ubicaciones provinciales pendientes.", flush=True)
    if not args.geocode:
        if args.fecha:
            enrich_calendar(args.fecha, entries)
        return
    for index, item in enumerate(pending, 1):
        try:
            position = geocode(item["direccion"], item["localidad"])
        except (OSError, ValueError) as error:
            raise RuntimeError(f"Error geocodificando {item['cofm_id']}: {error}") from error
        if position:
            item.update(position)
            write_json(output, list(entries.values()))
        print(f"[{index}/{len(pending)}] {item['localidad']} {item['cofm_id']}: {position or 'sin coincidencia fiable'}", flush=True)
        time.sleep(1.1)
    if args.fecha:
        enrich_calendar(args.fecha, entries)


if __name__ == "__main__":
    main()
