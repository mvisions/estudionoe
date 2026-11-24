#!/usr/bin/env python3
"""Geocode Málaga capital pharmacies from the saved monthly duty calendars."""
import glob
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
CALENDAR_PATTERN = os.path.join(ROOT, "data", "calendarios", "calendario-malaga-capital-*.json")
COORDS_FILE = os.path.join(ROOT, "public", "data", "coordenadas-malaga-capital.json")
CITY_BOUNDS = (36.58, 36.87, -4.60, -4.25)


def valid_coordinates(value):
    if not isinstance(value, dict):
        return False
    try:
        lat, lng = float(value["lat"]), float(value["lng"])
    except (KeyError, TypeError, ValueError):
        return False
    south, north, west, east = CITY_BOUNDS
    return south <= lat <= north and west <= lng <= east


def geocode(address):
    street = re.split(r"\s+-\s+(?:SECTOR|BARRIADA)\b", address, maxsplit=1, flags=re.IGNORECASE)[0]
    street = re.sub(r"\([^)]*\)", " ", street)
    street = unicodedata.normalize("NFC", street)
    replacements = [
        (r"\bC\s*/\.?\s*", "Calle "),
        (r"\bC\.\s*", "Calle "),
        (r"\bAVDA\.?(?=\s|[A-Z])\s*", "Avenida "),
        (r"\bAV\.(?=\s|[A-Z])\s*", "Avenida "),
        (r"\bAV(?=\s)\s*", "Avenida "),
        (r"\b(?:CRTA|CTRA)\.?\s*", "Carretera "),
        (r"\bPJE\.?\s*", "Pasaje "),
        (r"\bPZA\.?\s*", "Plaza "),
        (r"\bP\.\s*MAR[IÍ]TIMO\b", "Paseo Marítimo"),
        (r"\bP\.?\s+MART\.?\s*", "Paseo Marítimo "),
        (r"\bABOG\.?\s*", "Abogado "),
        (r"\bNUM\.?\s*", ""),
        (r"\b(?:N[º°]|N[ÚU]M\.?)(?=\s*\d)\s*", ""),
    ]
    for pattern, replacement in replacements:
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)
    street = re.sub(r",\s*(?=\d)", " ", street)
    street = re.sub(r"\s+", " ", street).strip(" ,.")

    queries = [f"{street}, Málaga, Andalucía, España"]
    if "LOCAL" not in street.upper():
        number = re.search(r"\s+(\d+(?:-\d+)?[A-Za-z]?)\b", street)
        if number:
            road = street[:number.start()].strip(" ,.")
            queries.append(f"{number.group(1)}, {road}, Málaga, Andalucía, España")
    street_without_number = re.sub(r"\s+S/N\b.*$", "", street, flags=re.IGNORECASE)
    street_without_number = re.sub(r"\s+\d+\b.*$", "", street_without_number).strip(" ,.")
    if street_without_number and street_without_number != street:
        queries.append(f"{street_without_number}, Málaga, Andalucía, España")

    for query in queries:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "es",
            "viewbox": "-4.60,36.87,-4.25,36.58",
            "bounded": 1,
        })
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0 (public pharmacy map)"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            results = json.load(response)
        if results:
            coordinates = {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
            if valid_coordinates(coordinates):
                return coordinates
        if query != queries[-1]:
            time.sleep(1.1)
    return None


def main():
    calendars = sorted(glob.glob(CALENDAR_PATTERN))
    if not calendars:
        raise FileNotFoundError(f"No se encontraron calendarios: {CALENDAR_PATTERN}")

    pharmacies = {}
    for path in calendars:
        with open(path, encoding="utf-8") as source:
            calendar = json.load(source)
        for day in calendar.get("dias", {}).values():
            for pharmacy in day:
                pharmacy_id = str(pharmacy.get("id", ""))
                if pharmacy_id and pharmacy_id not in pharmacies:
                    pharmacies[pharmacy_id] = html.unescape(pharmacy.get("direccion", "")).strip()

    if os.path.exists(COORDS_FILE):
        with open(COORDS_FILE, encoding="utf-8") as source:
            saved_coordinates = json.load(source)
        coordinates = {
            pharmacy_id: value
            for pharmacy_id, value in saved_coordinates.items()
            if valid_coordinates(value)
        }
    else:
        coordinates = {}

    pending = [
        (pharmacy_id, address)
        for pharmacy_id, address in pharmacies.items()
        if not valid_coordinates(coordinates.get(pharmacy_id))
    ]
    print(f"{len(pharmacies)} farmacias únicas; {len(pending)} necesitan coordenadas.")
    for index, (pharmacy_id, address) in enumerate(pending, start=1):
        try:
            result = geocode(address)
        except Exception as error:
            raise RuntimeError(f"No se pudo geocodificar {pharmacy_id} ({address}): {error}") from error

        if result:
            coordinates[pharmacy_id] = result
            print(f"[{index}/{len(pending)}] {pharmacy_id}: {result['lat']}, {result['lng']}")
        else:
            print(f"[{index}/{len(pending)}] Sin coincidencia fiable: {pharmacy_id} ({address})")

        with open(COORDS_FILE, "w", encoding="utf-8") as output:
            json.dump(coordinates, output, ensure_ascii=False, indent=2)
            output.write("\n")
        if index < len(pending):
            time.sleep(1.1)

    print(f"Guardadas {len(coordinates)} coordenadas en {COORDS_FILE}.")


if __name__ == "__main__":
    main()
