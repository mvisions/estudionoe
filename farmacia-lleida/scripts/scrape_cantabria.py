#!/usr/bin/env python3
"""Import COF Cantabria's public dated zone schedules and institutional positions."""
import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import OUT_DIR, slugify, write_json

HOST = "https://cofcantabria.org"
SOURCE = HOST + "/cofguardiasclient/"
SCHEDULE = SOURCE + "data/guardias.json"
PHONES = SOURCE + "data/telefonos.json"
GEO = "https://geoservicios.cantabria.es/inspire/rest/services/Sanidad/MapServer/1/query"
TZ = ZoneInfo("Europe/Madrid")


def fetch(url):
    time.sleep(1.1)
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0",
                                              "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def master_positions(cache, offline):
    path = cache / "posiciones-cof.json"
    if offline:
        if not path.exists():
            print("AVISO Cantabria: caché sin posiciones del maestro COF; se usa cartografía institucional.",
                  flush=True)
            return []
        return json.loads(path.read_text())

    def get_text(url):
        time.sleep(1.1)
        req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
        with urllib.request.urlopen(req, timeout=45) as response:
            return response.read().decode("utf-8")

    page = get_text(SOURCE)
    links = re.findall(r'<script[^>]+src="(/cofguardiasclient/assets/index-[^"]+\.js)"', page)
    if len(links) != 1:
        raise ValueError("La aplicación COF no publica un recurso de coordenadas reconocible.")
    content = get_text(HOST + links[0])
    entries = re.findall(
        r'\[\w+\("((?:[^"\\]|\\.)*)","((?:[^"\\]|\\.)*)"\)\]:'
        r'\{latitude:([-\d.]+),longitude:([-\d.]+),'
        r'source:"Listado Maestro de Farmacias del COF \(2026\)"\}', content)
    if not entries:
        raise ValueError("Maestro de posiciones COF no reconocible; no se ejecuta JavaScript externo.")
    result = []
    for name, address, lat, lng in entries:
        a, b = float(lat), float(lng)
        if coordinates({"lat": a, "lng": b}) and 42.7 < a < 43.7 and -4.9 < b < -3:
            result.append({"name": json.loads('"' + name + '"'),
                           "address": json.loads('"' + address + '"'), "lat": a, "lng": b})
        else:
            print("AVISO Cantabria: posición del maestro COF inválida; se omite.", flush=True)
    write_json(path, result)
    return result


def identity(info):
    return slugify(info["name"]), slugify(info["address"])


def pharmacy(info):
    locality = re.match(r"^\(([^)]+)\)\s*(.+)$", info["address"])
    if not locality or not info["name"].strip():
        raise ValueError("Farmacia sin nombre, dirección o localidad oficial.")
    town, address = locality.groups()
    prefixes = {"CL": "Calle", "AV": "Avenida", "PZ": "Plaza", "PS": "Paseo",
                "CR": "Carretera", "BO": "Barrio"}
    address = re.sub(r"^([A-Z]{2})\.\s*", lambda m: prefixes.get(m[1], m[1]) + " ", address)
    key = hashlib.sha256("|".join(identity(info)).encode()).hexdigest()[:16]
    return {"id": f"cof-cantabria-{key}", "nombre": info["name"], "direccion": address,
            "localidad": town.title(), "provincia": "Cantabria", "fuente": SOURCE,
            "telefono": info.get("phone"), "guardia": False, "lat": None, "lng": None}


def coordinate_index(data):
    if (not isinstance(data, dict) or not isinstance(data.get("features"), list)
            or data.get("exceededTransferLimit") or data.get("error")):
        raise ValueError("Cartografía de Cantabria incompleta o no reconocible.")
    result = {}
    for feature in data["features"]:
        phone = re.sub(r"\D", "", feature.get("properties", {}).get("TELEFONO_1") or "")
        point = feature.get("geometry") or {}
        values = point.get("coordinates", [])
        if len(phone) != 9 or point.get("type") != "Point" or len(values) != 2:
            continue
        lng, lat = values
        if coordinates({"lat": lat, "lng": lng}) and 42.7 < lat < 43.7 and -4.9 < lng < -3:
            result.setdefault(phone, set()).add((lat, lng))
        else:
            print(f"AVISO Cantabria: coordenadas inválidas para teléfono {phone}; no se dibujan.", flush=True)
    return result


def interval(info, service_day, target):
    match = re.fullmatch(r"(\d{2}:\d{2})\s*[—-]\s*(\d{2}:\d{2})", info["hours"])
    if not match or not isinstance(info.get("overnight"), bool):
        raise ValueError("Horario oficial o indicador nocturno no reconocible.")
    start_hour, end_hour = (clock.fromisoformat(value) for value in match.groups())
    start, end = (datetime.combine(service_day, value) for value in (start_hour, end_hour))
    if end <= start:
        # The official client treats equal hours as 24h and reversed hours as overnight.
        if not info["overnight"]:
            raise ValueError("Horario invertido/igual sin indicador nocturno oficial.")
        end += timedelta(days=1)
    day_start = datetime.combine(target, clock.min)
    day_end = day_start + timedelta(days=1)
    if start >= day_end or end <= day_start:
        return None
    return {"inicio": max(start, day_start).isoformat(), "fin": min(end, day_end).isoformat(),
            "inicio_original": start.isoformat(), "fin_original": end.isoformat()}


def parse(data, phones, geo, target, official_positions=None):
    zones = data.get("zones") if isinstance(data, dict) else None
    if not isinstance(zones, list) or not zones:
        raise ValueError("Calendario provincial sin zonas.")
    if not isinstance(phones, list):
        raise ValueError("Directorio telefónico no reconocible.")
    positions = coordinate_index(geo)
    phone_index = {}
    for info in phones:
        phone_index.setdefault(identity(info), set()).add(info["phone"])
    master = {}
    for info in official_positions or []:
        if coordinates(info) and 42.7 < info["lat"] < 43.7 and -4.9 < info["lng"] < -3:
            master.setdefault(identity(info), set()).add((info["lat"], info["lng"]))
    catalog = {}
    for zone in zones:
        if not isinstance(zone.get("schedule"), dict) or not zone.get("name") or not zone.get("id"):
            raise ValueError("Zona sin identidad o calendario.")
        for day, infos in zone["schedule"].items():
            date.fromisoformat(day)
            for info in infos:
                row = pharmacy(info)
                candidates = phone_index.get(identity(info), set())
                if not row["telefono"] and len(candidates) == 1:
                    row["telefono"] = next(iter(candidates))
                digits = re.sub(r"\D", "", row["telefono"] or "")
                matches = positions.get(digits, set())
                if len(matches) == 1:
                    lat, lng = next(iter(matches))
                    row.update(lat=lat, lng=lng, precision_ubicacion="farmacia", fuente_coordenadas=GEO)
                exact = master.get(identity(info), set())
                if len(exact) == 1:
                    lat, lng = next(iter(exact))
                    row.update(lat=lat, lng=lng, precision_ubicacion="farmacia", fuente_coordenadas=SOURCE)
                catalog[row["id"]] = row
    duties, reports = [], []
    prior_day = target - timedelta(days=1)
    for zone in zones:
        report = {"nombre": zone["name"], "codigo": zone["id"], "estado": "disponible", "farmacias": 0}
        if target.isoformat() not in zone["schedule"]:
            report.update(estado="error", error="No hay calendario para la fecha; no se usa el día más próximo.")
        if prior_day.isoformat() not in zone["schedule"] and report["estado"] == "disponible":
            report.update(estado="parcial", error="Madrugada anterior no confirmada.")
        for service_day in (prior_day, target):
            for info in zone["schedule"].get(service_day.isoformat(), []):
                try:
                    hours = interval(info, service_day, target)
                    if not hours:
                        continue
                    row = {**catalog[pharmacy(info)["id"]], "guardia": True, "fecha_guardia": str(target),
                           "guardia_franjas": [f"{service_day:%d/%m/%Y}: {info['hours']} · Zona {zone['name']}"],
                           "guardia_intervalos": [hours], "zonas_atendidas": [zone["name"]],
                           "localidades_atendidas": [catalog[pharmacy(info)["id"]]["localidad"]]}
                    duties.append(row)
                    report["farmacias"] += 1
                except (KeyError, TypeError, ValueError) as error:
                    report.update(estado="parcial", error=str(error))
                    print(f"ERROR Cantabria {zone['name']}: {error}", flush=True)
        reports.append(report)
    merged = merge_rows(duties)
    for row in merged:
        raw = [info for info in duties if info["id"] == row["id"]]
        row["guardia_intervalos"] = list({json.dumps(hours, sort_keys=True): hours for info in raw
                                         for hours in info["guardia_intervalos"]}.values())
        row["zonas_atendidas"] = list(dict.fromkeys(zone for info in raw for zone in info["zonas_atendidas"]))
    reports.append({"nombre": "Censo municipal provincial", "estado": "parcial",
                    "error": "Se consultan todas las zonas publicadas; no acreditan un censo de los "
                             "102 municipios ni derivaciones municipio a municipio. "
                             "El catálogo contiene farmacias observadas en calendarios, no todas las oficinas."})
    return list(catalog.values()), merged, reports


def run(target, cache, offline=False, geocode=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports, rows = [], []
    try:
        payload = []
        geo_url = GEO + "?" + urllib.parse.urlencode({"where": "1=1", "outFields": "TELEFONO_1",
                                                     "returnGeometry": "true", "outSR": "4326", "f": "geojson"})
        for filename, url in ((f"calendario-{target}.json", SCHEDULE),
                              ("telefonos.json", PHONES)):
            path = cache / filename
            data = json.loads(path.read_text()) if offline else fetch(url)
            payload.append(data)
            if not offline:
                write_json(path, data)
        try:
            path = cache / "coordenadas.json"
            geo = json.loads(path.read_text()) if offline else fetch(geo_url)
            coordinate_index(geo)
            if not offline:
                write_json(path, geo)
        except (OSError, ValueError, KeyError, TypeError) as error:
            reports.append({"nombre": "Cartografía institucional", "estado": "error", "error": str(error)})
            print(f"ERROR Cantabria cartografía institucional: {error}", flush=True)
            geo = {"features": []}
        payload.append(geo)
        try:
            official = master_positions(cache, offline)
        except (OSError, ValueError, KeyError, TypeError) as error:
            official = []
            reports.append({"nombre": "Maestro de posiciones COF", "estado": "error", "error": str(error)})
            print(f"ERROR Cantabria posiciones COF: {error}", flush=True)
        points, rows, schedule_reports = parse(*payload, target, official)
        reports.extend(schedule_reports)
        locate_and_catalogue(points, "Cantabria")
        locate_and_catalogue(rows, "Cantabria", official_points=[p for p in points if coordinates(p)],
                             use_geocoder=geocode)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Cantabria: {error}", flush=True)
        reports.append({"nombre": "Fuente provincial", "estado": "error", "error": str(error)})
    return publish(target, "Cantabria", SOURCE, rows, reports)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/cantabria")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red, args.geocode) else 1)
