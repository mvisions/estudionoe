#!/usr/bin/env python3
"""Import daily city duties from the Government of Navarra's open data."""
import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from localizacion_cartociudad import LOCATION_FIELDS, locate
from merge_espana import coordinates
from provincial_catalog import publish
from proximidad import Geocoder
from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://datosabiertos.navarra.es/es/dataset/farmacias-de-guardia"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
API = "https://datosabiertos.navarra.es/api/3/action/datastore_search"
RESOURCE = "e309e89e-d62e-4222-b6fa-e81d0924a086"
LOCALITIES = {
    "pamplona-iruna": "Pamplona / Iruña",
    "tudela": "Tudela",
    "estella-lizarra": "Estella-Lizarra",
}


def fetch(target):
    params = {"resource_id": RESOURCE, "filters": json.dumps({"fecha": target.strftime("%d/%m/%Y")}),
              "limit": 1000}
    request = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def parse(data, target):
    if data.get("success") is not True:
        raise ValueError("La API no confirma una consulta correcta.")
    result = data["result"]
    records = result["records"]
    if not isinstance(records, list) or not records or int(result["total"]) != len(records):
        raise ValueError("Respuesta vacía o incompleta; no se supone ausencia de guardias.")
    rows = {}
    for item in records:
        if item.get("fecha") != target.strftime("%d/%m/%Y"):
            raise ValueError("La respuesta contiene una fecha distinta de la solicitada.")
        locality = LOCALITIES.get(slugify(item.get("localidad", "")))
        if not locality:
            continue
        ident, name, address = item.get("cod_Farmacia"), item.get("farmacia"), item.get("direccion")
        phone = re.sub(r"\D", "", item.get("telefono") or "")
        start, end = item.get("desde"), item.get("hasta")
        if (not ident or not re.fullmatch(r"F\d+", ident) or not name or not address
                or len(phone) != 9 or not re.fullmatch(r"\d{1,2}", start or "")
                or not re.fullmatch(r"\d{1,2}", end or "")
                or int(start) > 24 or int(end) > 24):
            raise ValueError(f"Ficha de {locality} incompleta o no reconocida.")
        row = rows.setdefault(ident, {
            "id": f"navarra-{ident.lower()}", "cofm_id": None, "nombre": name,
            "direccion": address, "localidad": locality, "provincia": "Navarra",
            "telefono": phone, "guardia": True, "fecha_guardia": target.isoformat(), "fuente": SOURCE,
            "fuente_licencia": LICENSE, "localidades_atendidas": [locality],
            "lat": None, "lng": None, "guardia_franjas": [], "horarios_fuente": [],
        })
        if (row["nombre"] != name or row["direccion"] != address
                or row["telefono"] != phone or row["localidad"] != locality):
            raise ValueError("Datos contradictorios para una misma farmacia.")
        row["horarios_fuente"].append({"desde": start, "hasta": end})
        row["guardia_franjas"].append(
            f"Fuente: desde {start}, hasta {end}; horario y cambio de fecha pendientes de confirmar.")
    if not rows:
        raise ValueError("El recurso no confirma guardias de las ciudades consultadas para la fecha solicitada.")
    for row in rows.values():
        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(rows.values())


def run(target, cache, output=OUT_DIR, geocode=False):
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    rows = parse(fetch(target), target)
    reports = [
        {"nombre": locality,
         "estado": "parcial" if count else "pendiente",
         "farmacias": count,
         "error": ("Horarios, cambio de fecha y madrugada anterior pendientes de interpretar."
                   if count else "La fuente no confirma guardias para esta ciudad y fecha.")}
        for locality in LOCALITIES.values()
        for count in [sum(row["localidad"] == locality for row in rows)]
    ] + [
        {"nombre": "Resto de Navarra", "estado": "pendiente", "farmacias": 0,
         "error": "Otros municipios y turnos semanales pendientes de interpretar."},
    ]
    path = output / "farmacias-navarra.json"
    saved = {item["id"]: item for item in json.loads(path.read_text())} if path.exists() else {}
    for row in rows:
        previous = saved.get(row["id"])
        if (previous and previous.get("direccion") == row["direccion"]
                and previous.get("localidad") == row["localidad"] and coordinates(previous)):
            row.update({field: previous[field] for field in LOCATION_FIELDS if field in previous})
    if geocode:
        known = json.loads((output / "farmacias-espana-hoy.json").read_text())
        geocoder = Geocoder(cache=cache / "posiciones.json", ttl_days=365)
        locate(rows, known, geocoder, "Navarra")
        if geocoder.errors:
            reports.append({"nombre": "CartoCiudad", "estado": "error",
                            "error": "No se pudieron contrastar todas las ubicaciones."})
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(path, list(saved.values()))
    return publish(target, "Navarra", SOURCE, rows, reports, output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/navarra")
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    parser.add_argument("--geocode", action="store_true")
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.cache_documentos, args.salida, args.geocode) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Navarra: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
