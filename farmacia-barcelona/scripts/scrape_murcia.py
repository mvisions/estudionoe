#!/usr/bin/env python3
"""Collect the COFRM public catalogue and explicitly dated on-call calendars."""
import argparse
import json
import math
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import write_json
from scrape_palencia import consolidate

SOURCE = "https://guardias.cofrm.com"
TZ = ZoneInfo("Europe/Madrid")


def request(path):
    req = urllib.request.Request(SOURCE + path, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def cached(path, name, cache, offline, resume):
    file = cache / name
    if offline or (resume and file.exists()):
        return json.loads(file.read_text())
    result = request(path)
    write_json(file, result)
    time.sleep(1.1)
    return result


def utm_coordinates(easting, northing):
    if (isinstance(easting, bool) or isinstance(northing, bool)
            or not isinstance(easting, (int, float)) or not isinstance(northing, (int, float))
            or not math.isfinite(easting) or not math.isfinite(northing)
            or not 100000 < easting < 1000000 or not 0 < northing < 10000000):
        raise ValueError("Coordenadas UTM oficiales inválidas.")
    # The linked COFRM map uses WGS84, UTM zone 30 north (not a town centroid).
    a, eccentricity, scale = 6378137, 0.00669438, 0.9996
    mu = northing / scale / (a * (1 - eccentricity / 4 - 3 * eccentricity ** 2 / 64
                                  - 5 * eccentricity ** 3 / 256))
    e1 = (1 - math.sqrt(1 - eccentricity)) / (1 + math.sqrt(1 - eccentricity))
    phi = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
           + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
           + 151 * e1 ** 3 / 96 * math.sin(6 * mu) + 1097 * e1 ** 4 / 512 * math.sin(8 * mu))
    ep = eccentricity / (1 - eccentricity)
    n = a / math.sqrt(1 - eccentricity * math.sin(phi) ** 2)
    t, c = math.tan(phi) ** 2, ep * math.cos(phi) ** 2
    r = a * (1 - eccentricity) / (1 - eccentricity * math.sin(phi) ** 2) ** 1.5
    d = (easting - 500000) / (n * scale)
    latitude = phi - n * math.tan(phi) / r * (
        d ** 2 / 2 - (5 + 3 * t + 10 * c - 4 * c ** 2 - 9 * ep) * d ** 4 / 24
        + (61 + 90 * t + 298 * c + 45 * t ** 2 - 252 * ep - 3 * c ** 2) * d ** 6 / 720)
    longitude = -3 + math.degrees((d - (1 + 2 * t + c) * d ** 3 / 6
                                   + (5 - 2 * c + 28 * t - 3 * c ** 2 + 8 * ep + 24 * t ** 2)
                                   * d ** 5 / 120) / math.cos(phi))
    latitude = math.degrees(latitude)
    if not 37.2 < latitude < 39.0 or not -2.5 < longitude < -0.5:
        raise ValueError("Coordenadas oficiales fuera de la Región de Murcia; no se publica marcador.")
    return latitude, longitude


def catalogue(data, municipalities):
    if (not isinstance(municipalities, list) or len(municipalities) != 45
            or any(item.get("locationType") != "MUNICIPALITY" for item in municipalities)):
        raise ValueError("El índice oficial no acredita los 45 municipios de Murcia.")
    names = {item["name"] for item in municipalities}
    if len(names) != 45 or not isinstance(data, list) or not data:
        raise ValueError("Directorio o índice municipal vacío/repetido.")
    rows, seen = [], set()
    for item in data:
        identifier = item.get("id")
        if (not isinstance(identifier, int) or isinstance(identifier, bool) or identifier in seen
                or not item.get("address") or not item.get("town") or item.get("municipality") not in names):
            raise ValueError("Ficha oficial sin identidad, dirección o municipio válido.")
        seen.add(identifier)
        row = {"id": f"cof-murcia-{identifier}", "cofrm_id": identifier, "nombre": item.get("name", ""),
               "direccion": item["address"], "localidad": item["town"], "provincia": "Murcia",
               "municipio": item["municipality"].split(" - ", 1)[-1], "guardia": False,
               "telefono": item.get("phone", ""), "codigo_postal": item.get("postalCode", ""),
               "fuente": SOURCE + f"/api/pharmacies/{identifier}", "lat": None, "lng": None}
        try:
            lat, lng = utm_coordinates(item.get("coordinateX"), item.get("coordinateY"))
            row.update(lat=lat, lng=lng, precision_ubicacion="farmacia",
                       fuente_coordenadas=row["fuente"])
        except ValueError as error:
            print(f"AVISO Murcia {row['id']}: {error}", flush=True)
            row["nota_ubicacion"] = str(error)
        rows.append(row)
    if {item["municipality"] for item in data} != names:
        raise ValueError("El directorio no incluye todos los municipios del índice.")
    return rows


def parse_calendar(data, pharmacy, target):
    if not isinstance(data, list):
        raise ValueError("Calendario COFRM no reconocible.")
    beginning = datetime.combine(target, datetime.min.time()).replace(tzinfo=TZ)
    ending = beginning + timedelta(days=1)
    rows, year_observed = [], False
    for event in data:
        if not isinstance(event, dict) or not isinstance(event.get("title"), str):
            raise ValueError("Evento del calendario sin título verificable.")
        try:
            start, finish = [datetime.fromisoformat(event[key]) for key in ("start", "end")]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Evento del calendario sin fechas válidas.") from error
        if start.tzinfo is None:
            start = start.replace(tzinfo=TZ)
        if finish.tzinfo is None:
            finish = finish.replace(tzinfo=TZ)
        year_observed |= start.year == target.year
        if not event["title"].startswith("On-Call - "):
            continue
        if finish <= start:
            raise ValueError("Intervalo del calendario invertido; no se supone una guardia de 24 horas.")
        title = event["title"][len("On-Call - "):].strip()
        if title.endswith(" (Weekend)"):
            title = title[:-len(" (Weekend)")].strip()
        if title != pharmacy["nombre"].strip():
            raise ValueError("El titular del turno no coincide con la ficha consultada.")
        if start >= ending or finish <= beginning:
            continue
        start = max(start, beginning)
        label = f"Guardia COFRM · {start:%d/%m %H:%M}–{finish:%d/%m %H:%M}"
        rows.append({**pharmacy, "guardia": True, "fecha_guardia": str(target),
                     "localidades_atendidas": [pharmacy["localidad"]],
                     "guardia_franja": label, "guardia_franjas": [label],
                     "guardia_intervalos": [{"inicio": start.isoformat(), "fin": finish.isoformat()}],
                     "fuente": SOURCE + f"/api/pharmacies/{pharmacy['cofrm_id']}/calendar"})
    if not year_observed:
        raise ValueError("El calendario no publica eventos del año solicitado; no se supone ausencia de guardias.")
    return rows


def run(target, cache, offline=False, resume=False, limit=None):
    cache.mkdir(parents=True, exist_ok=True)
    rows, reports = [], []
    try:
        municipalities = cached("/api/locations?locationType=MUNICIPALITY", "municipios.json",
                                cache, offline, resume)
        data = cached("/api/pharmacies?general=GENERAL", "catalogo.json", cache, offline, resume)
        directory = catalogue(data, municipalities)
        locate_and_catalogue(directory, "Murcia")
        selection = directory[:limit] if limit else directory
        for pharmacy in selection:
            report = {"nombre": pharmacy["nombre"], "municipio": pharmacy["municipio"],
                      "localidad": pharmacy["localidad"], "estado": "parcial", "farmacias": 0,
                      "error": "Calendario por farmacia consultado; derivaciones y cobertura de todas las pedanías no certificadas."}
            try:
                events = cached(f"/api/pharmacies/{pharmacy['cofrm_id']}/calendar",
                                f"calendario-{target}-{pharmacy['cofrm_id']}.json", cache, offline, resume)
                batch = parse_calendar(events, pharmacy, target)
                rows.extend(batch)
                report["farmacias"] = len(batch)
            except (OSError, ValueError, TypeError, KeyError) as error:
                report.update(estado="error", error=str(error))
                print(f"AVISO Murcia {pharmacy['localidad']}: {error}", flush=True)
            reports.append(report)
            pending = [{"nombre": item["nombre"], "municipio": item["municipio"],
                        "localidad": item["localidad"], "estado": "error", "error": "Calendario aún no consultado."}
                       for item in directory[len(reports):]]
            publish(target, "Murcia", SOURCE, consolidate(rows), reports + pending)
            print(f"Murcia: {len(reports)}/{len(directory)} calendarios consultados.", flush=True)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"ERROR Murcia: {error}", flush=True)
        publish(target, "Murcia", SOURCE, consolidate(rows),
                reports + [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
    return False


def main():
    parser = argparse.ArgumentParser(description="Calendarios públicos COFRM, Murcia y sus pueblos.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/murcia")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    parser.add_argument("--limite", type=int)
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite debe ser positivo.")
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar, args.limite) else 1


if __name__ == "__main__":
    raise SystemExit(main())
