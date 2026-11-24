#!/usr/bin/env python3
"""Collect MICOF municipal catalogues and explicitly labelled emergency hours."""
import argparse
import html
import json
import re
import string
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import street_query

HOST = "https://www.micof.es"
SOURCE = HOST + "/ver/124/"
TZ = ZoneInfo("Europe/Madrid")
SNAPSHOTS = ("00:00", "12:00", "22:00")


def request(url):
    time.sleep(1.1)
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0",
                                              "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        print(f"AVISO MICOF: HTML con UTF-8 inválido en byte {error.start}; "
              "se validará por separado el listado de datos.", flush=True)
        return data.decode("utf-8", errors="surrogateescape")


def municipalities(cache, offline=False):
    path = cache / "municipios.json"
    if offline:
        return json.loads(path.read_text())
    names = set()
    for letter in string.ascii_lowercase:
        data = json.loads(request(HOST + "/MicofFarmacias/autocomplete_farmacias?query=" + letter))
        if data.get("query") != letter or not isinstance(data.get("suggestions"), list):
            raise ValueError("Autocompletado MICOF no confirma la consulta municipal.")
        for info in data["suggestions"]:
            if not info.get("desc") and info.get("value"):
                names.add(info["value"])
    if "Valencia" not in names or len(names) < 200:
        raise ValueError("Índice de localidades MICOF incompleto o no reconocible.")
    result = sorted(names)
    write_json(path, result)
    return result


def parse_page(content, target, requested_hour=None):
    if requested_hour:
        expected = f"{target:%d/%m/%Y} {requested_hour}"
        field = re.search(r'<input[^>]*id="buscarFecha"[^>]*value="([^"]*)"', content)
        if not field or html.unescape(field[1]) != expected:
            raise ValueError("MICOF no confirma la fecha y hora solicitadas.")
    match = re.search(r"\bvar distribuidores\s*=\s*", content)
    if not match:
        raise ValueError("MICOF no publica una lista de farmacias reconocible.")
    entries, _ = json.JSONDecoder().raw_decode(content[match.end():])
    if not isinstance(entries, list):
        raise ValueError("Listado MICOF inválido.")
    json.dumps(entries, ensure_ascii=False).encode("utf-8")
    catalog, duties = [], []
    for info in entries:
        if not isinstance(info, list) or len(info) != 11:
            raise ValueError("Ficha MICOF con formato inesperado.")
        identifier = re.search(r"/farmacia/ver/(\d+)", info[10])
        if not identifier or not info[3] or not info[4]:
            raise ValueError("Ficha MICOF sin identificador/domicilio/localidad.")
        city = info[4]
        sector = ""
        if city.startswith("Valencia (") and city.endswith(")"):
            sector, city = city, "Valencia"
        row = {"id": f"cof-valencia-{identifier[1]}", "nombre": info[0],
               "direccion": street_query(info[3]), "localidad": city, "sector": sector,
               "provincia": "Valencia", "codigo_postal": info[5], "telefono": info[6],
               "guardia": False, "lat": None, "lng": None, "fuente": SOURCE,
               "horario_publicado": info[9]}
        position = {"lat": info[1], "lng": info[2]}
        if coordinates(position) and 38 < info[1] < 41 and -2 < info[2] < 1:
            row.update(position, precision_ubicacion="farmacia", fuente_coordenadas=SOURCE)
        else:
            print(f"AVISO MICOF {row['id']}: ubicación oficial inválida; no se dibuja.", flush=True)
        catalog.append(row)
        # The finder mixes ordinary openings and emergencies: only its explicit label proves duty.
        if requested_hour and "incluye horario de urgencias" in info[9].lower():
            hours = re.findall(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", info[9])
            if not hours:
                raise ValueError("Guardia MICOF sin horas reconocibles.")
            intervals = []
            for start_hour, end_hour in hours:
                start = datetime.combine(target, clock.fromisoformat(start_hour))
                end = datetime.combine(target, clock.fromisoformat(end_hour))
                if end <= start:
                    raise ValueError("Horario MICOF ambiguo; no se supone un turno de 24 horas.")
                intervals.append({"inicio": start.isoformat(), "fin": end.isoformat()})
            duties.append({**row, "guardia": True, "fecha_guardia": str(target),
                           "guardia_franjas": [info[9] + " · Confirmar horario por teléfono"],
                           "guardia_intervalos": intervals,
                           "localidades_atendidas": [city]})
    return catalog, duties


def run(target, cache, offline=False, limit=None, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog, duties, reports = [], [], []
    towns = []
    try:
        towns = municipalities(cache, offline or (resume and (cache / "municipios.json").exists()))
        for town in towns[:limit] if limit else towns:
            report = {"nombre": town, "estado": "parcial", "farmacias": 0,
                      "error": "Consultas a las 00:00, 12:00 y 22:00; no certifican todos los turnos "
                               "ni que otras farmacias cercanas atiendan este municipio."}
            try:
                for hour in (None, *SNAPSHOTS):
                    key = f"{target}-{slugify(town)}-{hour.replace(':', '') if hour else 'catalogo'}.html"
                    path = cache / key
                    params = {"buscarLocalidadCp": town, "buscarGuardia": "1" if hour else "0"}
                    if hour:
                        params["buscarFecha"] = f"{target:%d/%m/%Y} {hour}"
                    content = (path.read_text(errors="surrogateescape") if offline or (resume and path.exists())
                               else request(SOURCE + "?" + urllib.parse.urlencode(params)))
                    points, rows = parse_page(content, target, hour)
                    if not offline:
                        path.write_text(content, errors="surrogateescape")
                    catalog.extend(points)
                    duties.extend(rows)
                    report["farmacias"] += len(rows)
            except (OSError, ValueError, KeyError, TypeError) as error:
                report.update(estado="error", error=str(error))
                print(f"ERROR MICOF {town}: {error}", flush=True)
            reports.append(report)
            # Persist each completed municipality so an interrupted run keeps useful evidence.
            points = list({point["id"]: point for point in catalog}.values())
            locate_and_catalogue(points, "Valencia")
            confirmed = merge_rows(duties)
            for row in confirmed:
                row["guardia_intervalos"] = list({json.dumps(i, sort_keys=True): i for raw in duties
                                                 if raw["id"] == row["id"]
                                                 for i in raw["guardia_intervalos"]}.values())
            pending = [{"nombre": name, "estado": "error", "error": "Localidad aún no consultada."}
                       for name in towns if name not in {r["nombre"] for r in reports}]
            publish(target, "Valencia", SOURCE, confirmed, reports + pending)
            print(f"MICOF {town}: {len(confirmed)} guardias acumuladas; {len(reports)}/{len(towns)} consultas.",
                  flush=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR MICOF Valencia: {error}", flush=True)
        publish(target, "Valencia", SOURCE, merge_rows(duties),
                reports + [{"nombre": "Índice provincial", "estado": "error", "error": str(error)}])
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/valencia")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true", help="Reutilizar páginas de la misma fecha ya consultadas.")
    parser.add_argument("--limite", type=int, help="Limitar localidades; el resto queda pendiente explícitamente.")
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite debe ser positivo.")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red,
                            args.limite, args.reanudar) else 1)
