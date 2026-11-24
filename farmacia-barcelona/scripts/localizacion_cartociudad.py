"""Verify an OSM pharmacy against a nearby official CartoCiudad address portal."""
import urllib.parse

from merge_espana import coordinates
from proximidad import distance_m, latlng, phone_digits, same_locality, same_number, similar_street, split_address

REVERSE = "https://www.cartociudad.es/geocoder/api/geocoder/reverseGeocode"
LOCATION_FIELDS = ("lat", "lng", "precision_ubicacion", "fuente_coordenadas",
                   "nota_ubicacion", "osm_id", "ajuste_ubicacion_m", "referencia_ubicacion")


def locate(rows, known, geocoder, province):
    phones = {}
    for pharmacy in known:
        phone = phone_digits(pharmacy)
        if (pharmacy.get("provincia") == province and len(phone) == 9
                and latlng(pharmacy) and str(pharmacy.get("id", "")).startswith("osm-")
                and str(pharmacy["id"])[4:].isdigit()):
            phones.setdefault(phone, []).append(pharmacy)
    for row in rows:
        if coordinates(row):
            continue
        candidates = phones.get(phone_digits(row), [])
        address = split_address(row["direccion"])
        if len(candidates) != 1 or not address:
            continue
        pharmacy = candidates[0]
        lat, lng = latlng(pharmacy)
        url = REVERSE + "?" + urllib.parse.urlencode({"lon": lng, "lat": lat})
        reference = geocoder.lookup(f"R|{lat},{lng}", url, lambda value: value)
        if not isinstance(reference, dict):
            continue
        if (reference.get("type") != "portal" or reference.get("noNumber") is not False
                or not same_locality(row["localidad"], reference.get("muni"))
                or not similar_street(address[0], reference.get("address"))
                or not same_number(address[1], str(reference.get("portalNumber") or ""))):
            continue
        point = reference.get("lat"), reference.get("lng")
        if not coordinates({"lat": point[0], "lng": point[1]}):
            continue
        distance = distance_m((lat, lng), point)
        if distance <= 15:
            row.update(lat=lat, lng=lng, precision_ubicacion="farmacia",
                       fuente_coordenadas=f"https://www.openstreetmap.org/node/{pharmacy['id'][4:]}",
                       referencia_ubicacion=url, ajuste_ubicacion_m=round(distance, 1),
                       nota_ubicacion=f"Teléfono, dirección y portal CartoCiudad coinciden a {distance:.1f} m.")
    geocoder.save()
