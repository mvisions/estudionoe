"""Collect the public COFCAM dated provincial duty lists without an hourly filter."""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path

from merge_espana import coordinates
from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import street_query

SOURCE = "https://farmaciasdeguardia.cofcam.es/"
IDENTIFIERS = {"Toledo": r"TO-\d+-F", "Guadalajara": r"GU-\d+-F",
               "Albacete": r"AB-\d+-F", "Cuenca": r"CU-\d+-F", "Ciudad Real": r"\d+"}


def request(params):
    time.sleep(1.1)
    url = SOURCE + "api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0",
                                              "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def parse_response(data, target, province):
    if (not isinstance(data, dict) or data.get("success") is not True or data.get("fecha") != target.isoformat()
            or data.get("filtro_hora") is not None or not isinstance(data.get("data"), list)
            or data.get("total") != len(data["data"])):
        raise ValueError("COFCAM no confirma fecha, listado íntegro y ausencia de filtro horario.")
    if not data["data"]:
        raise ValueError("COFCAM no devuelve guardias; no se supone que no existan.")
    rows, errors = [], []
    day_start = datetime.combine(target, clock.min)
    day_end = day_start + timedelta(days=1)
    for info in data["data"]:
        try:
            identifier = str(info["numero_farmacia"])
            if info["provincia"] != province or not re.fullmatch(IDENTIFIERS[province], identifier):
                raise ValueError("Provincia/identificador no corresponde a la consulta.")
            address, city = info["domicilio"].strip(), info["localidad"].strip()
            if not address or not city:
                raise ValueError("Farmacia sin domicilio o localidad oficial.")
            start = datetime.fromisoformat(f"{info['fecha_inicio']}T{info['hora_inicio']}")
            end = datetime.fromisoformat(f"{info['fecha_fin']}T{info['hora_fin']}")
            if end <= start:
                raise ValueError("Intervalo oficial inválido; no se inventa una duración de 24 horas.")
            if start >= day_end or end <= day_start:
                continue
            sector = ""
            if province == "Toledo" and re.fullmatch(r"TOLEDO\s*\(.+\)", city, re.I):
                sector, city = city, "Toledo"
            row = {"id": f"cof-{slugify(province)}-{identifier}", "nombre": info.get("nombre", ""),
                   "direccion": street_query(address), "localidad": city.title(), "sector": sector,
                   "provincia": province, "telefono": info.get("telefono"),
                   "telefonos_adicionales": [info["telefono2"]] if info.get("telefono2") else [],
                   "zona": info.get("zona", ""), "localidades_atendidas": [city.title()],
                   "guardia": True, "fecha_guardia": target.isoformat(), "fuente": SOURCE,
                   "guardia_localizada": info.get("guardia_localizada", False),
                   "guardia_intervalos": [{"inicio": max(start, day_start).isoformat(),
                                          "fin": min(end, day_end).isoformat(),
                                          "inicio_original": start.isoformat(), "fin_original": end.isoformat()}],
                   "guardia_franjas": [f"{start:%d/%m/%Y %H:%M}–{end:%d/%m/%Y %H:%M}"],
                   "lat": None, "lng": None}
            if row["guardia_localizada"]:
                row["guardia_franjas"].append("Guardia localizada; llamar antes de acudir.")
            try:
                if isinstance(info.get("lat"), bool) or isinstance(info.get("lng"), bool):
                    raise ValueError("Coordenadas booleanas no válidas.")
                a, b = float(info["lat"]), float(info["lng"])
                position = {"lat": a, "lng": b}
                if coordinates(position) and 38 < a < 42 and -6 < b < -1 and (a, b) != (39.4, -3.0):
                    row.update(position, precision_ubicacion="farmacia", fuente_coordenadas=SOURCE)
                else:
                    raise ValueError("Coordenadas oficiales inválidas o centro genérico.")
            except (KeyError, TypeError, ValueError) as error:
                print(f"AVISO COFCAM {identifier}: {error}; ubicación pendiente.", flush=True)
            rows.append(row)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"Registro {info.get('id', '?')}: {error}")
            print(f"ERROR COFCAM {province}: {errors[-1]}", flush=True)
    if not rows:
        raise ValueError("No hay intervalos válidos que solapen la fecha solicitada.")
    merged = merge_rows(rows)
    for row in merged:
        row["guardia_intervalos"] = list({json.dumps(interval, sort_keys=True): interval
                                         for raw in rows if raw["id"] == row["id"]
                                         for interval in raw["guardia_intervalos"]}.values())
    return merged, errors


def run(target, province, cache, offline=False, use_geocoder=False, allow_address=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = cache / f"{target}.json"
    rows, reports = [], []
    try:
        if offline:
            data = json.loads(path.read_text())
        else:
            data = request({"action": "list", "fecha": target.isoformat(), "provincia": province})
        rows, errors = parse_response(data, target, province)
        if not offline:
            write_json(path, data)
        for town in sorted({row["localidad"] for row in rows}):
            reports.append({"nombre": town, "estado": "parcial" if errors else "disponible",
                            "farmacias": sum(row["localidad"] == town for row in rows),
                            "error": " · ".join(errors) if errors else ""})
        reports.append({"nombre": "Cobertura municipal provincial", "estado": "parcial",
                        "error": "Listado provincial completo consultado sin filtro horario; "
                                 "no es un censo de todos los municipios ni confirma derivaciones. "
                                 "El catálogo azul conserva las farmacias OSM y las observadas en guardias."})
        locate_and_catalogue(rows, province, use_geocoder=use_geocoder, allow_address=allow_address)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR COFCAM {province}: {error}", flush=True)
        reports.append({"nombre": province, "estado": "error", "error": str(error)})
    return publish(target, province, SOURCE, rows, reports)


def main(province):
    parser = argparse.ArgumentParser(description=f"Guardias oficiales COFCAM: {province}.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / f".local/state/farmacia/{slugify(province)}")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    return 0 if run(args.fecha, province, args.cache_documentos, args.sin_red,
                    args.geocode, args.permitir_direccion_exacta) else 1
