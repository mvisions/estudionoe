#!/usr/bin/env python3
"""Import COFM's public full catalogue and explicitly dated duty intervals."""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://www.cofm.es/es/buscador-de-farmacias/"
HOST = "https://www.cofm.es"
TZ = ZoneInfo("Europe/Madrid")
ALIASES = {"las-rozas": "rozas-de-madrid-las",
           "san-agustin-de-guadalix": "san-agustin-del-guadalix"}


def municipality(value):
    key = slugify(value)
    return ALIASES.get(key, key)


def request(url):
    time.sleep(1.1)
    req = urllib.request.Request(url, headers={
        "User-Agent": "FarmaciasDeGuardiaTracker/1.0",
        "Accept": "application/json,text/html,*/*"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8")


def discover():
    content = request(SOURCE)
    scripts = re.findall(r'<script[^>]*src="([^"]*pharmacy\.js[^"]*)"', content)
    if len(scripts) != 1:
        raise ValueError("Configuración pública COFM no reconocible; no se usa un token guardado.")
    url = urllib.parse.urljoin(SOURCE, scripts[0])
    if urllib.parse.urlparse(url).netloc != "www.cofm.es":
        raise ValueError("Aplicación del buscador fuera del dominio oficial.")
    script = request(url)
    if '"/rest/farmacias/"' not in script or '"/rest/poblaciones/"' not in script:
        raise ValueError("La aplicación oficial ha cambiado sus recursos públicos.")
    return {"catalogo": HOST + "/rest/farmacias/es?direccion=",
            "municipios": HOST + "/rest/poblaciones/"}


def catalogue(data):
    if not isinstance(data, list) or not data:
        raise ValueError("Catálogo COFM vacío o sin lista reconocible.")
    result = []
    seen = set()
    for info in data:
        identifier = str(info["identificador"])
        if not identifier or identifier in seen or not info.get("direccion") or not info.get("poblacion"):
            raise ValueError("Catálogo COFM con identidad duplicada o dirección/municipio ausente.")
        seen.add(identifier)
        address = re.sub(r"\s+", " ", info["direccion"]).strip()
        prefixes = {"CL": "Calle", "PZ": "Plaza", "AV": "Avenida", "PS": "Paseo",
                    "GL": "Glorieta", "CT": "Carretera", "CM": "Camino", "UR": "Urbanización"}
        address = re.sub(r"^([A-Z]{2})\s+", lambda m: prefixes.get(m[1], m[1]) + " ", address)
        row = {"id": f"cof-madrid-{identifier}", "nombre": info.get("nombre", ""),
               "direccion": address, "localidad": info["poblacion"].title(), "provincia": "Madrid",
               "telefono": info.get("telefono"), "codigo_postal": info.get("codigoPostal"),
               "guardia": False, "lat": None, "lng": None, "fuente": SOURCE,
               "horario_habitual": info.get("horarioDesc"), "servicio_24h": info.get("servicio24h", False)}
        try:
            a, b = float(info["latitud"]), float(info["longitud"])
            if coordinates({"lat": a, "lng": b}) and 39.8 < a < 41.3 and -4.7 < b < -3.0:
                row.update(lat=a, lng=b, precision_ubicacion="farmacia",
                           fuente_coordenadas=HOST + "/rest/farmacias/es")
        except (KeyError, TypeError, ValueError):
            pass
        result.append(row)
    return result


def intervals(value, target):
    start_day = datetime.combine(target, clock.min)
    end_day = start_day + timedelta(days=1)
    result = []
    for part in value.split(";"):
        match = re.fullmatch(
            r"\s*(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2})\s*-\s*"
            r"(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2})\s*", part)
        if not match:
            raise ValueError(f"Horario de guardia COFM no reconocible: {value}")
        start, end = (datetime.strptime(v, "%Y-%m-%d %H:%M") for v in match.groups())
        if end <= start:
            # The official client explicitly treats equal/reversed end times as overnight.
            end += timedelta(days=1)
        if end <= start:
            raise ValueError(f"Intervalo de guardia COFM no válido: {value}")
        if start < end_day and end > start_day:
            result.append({"inicio": max(start, start_day).isoformat(),
                           "fin": min(end, end_day).isoformat(), "tipo": "Guardia COFM",
                           "inicio_original": start.isoformat(), "fin_original": end.isoformat()})
    return result


def parse(data, towns, target):
    points = catalogue(data)
    if not isinstance(towns, list) or not towns or any(not t.get("nombre") for t in towns):
        raise ValueError("Censo municipal COFM vacío o no reconocible.")
    groups = {}
    for town in towns:
        groups.setdefault(municipality(town["nombre"]), []).append(town["nombre"])
    if len(groups) != 179 or "madrid" not in groups:
        raise ValueError(f"Censo COFM no contrastado: {len(groups)} municipios únicos, esperados 179.")
    extra = {municipality(row["localidad"]) for row in points} - set(groups)
    if extra:
        raise ValueError(f"Municipios del catálogo sin correspondencia en el selector: {sorted(extra)}")
    rows, errors = [], {}
    for info, point in zip(data, points):
        value = info.get("horarioGuardia")
        if not value:
            continue
        try:
            periods = intervals(value, target)
            if periods:
                row = {**point, "guardia": True, "fecha_guardia": target.isoformat(),
                       "localidades_atendidas": [groups[municipality(point["localidad"])][0]],
                       "guardia_intervalos": periods, "horario_guardia_original": value,
                       "guardia_descripcion_oficial": info.get("horarioGuardiaDesc", ""),
                       "guardia_franjas": [
                           f"Guardia COFM: {p['inicio'].replace('T', ' ')}–{p['fin'].replace('T', ' ')}"
                           for p in periods]}
                rows.append(row)
        except ValueError as error:
            errors.setdefault(municipality(point["localidad"]), []).append(str(error))
    reports = []
    for key, names in groups.items():
        confirmed = [r for r in rows if municipality(r["localidad"]) == key]
        known = [r for r in points if municipality(r["localidad"]) == key]
        dated = [r for r in data if municipality(r["poblacion"]) == key and r.get("horarioGuardia")]
        report = {"nombre": names[0], "opciones_selector": names,
                  "metodo": "Evaluación municipal del catálogo provincial completo; sin filtro por distancia",
                  "recurso_consultado": HOST + "/rest/farmacias/es?direccion=",
                  "fecha_evaluada": target.isoformat(),
                  "farmacias_catalogo": len(known), "farmacias": len(confirmed),
                  "registros_con_horario_guardia": len(dated),
                  "consulta_provincial_correcta": True,
                  "derivacion_oficial_confirmada": False,
                  "estado": "disponible" if confirmed else "sin_datos"}
        if key in errors:
            report.update(estado="parcial" if confirmed else "error", error=" · ".join(errors[key]))
        elif not confirmed:
            report["motivo_sin_datos"] = (
                "sin_registros_en_catalogo" if not known else
                "sin_horario_guardia_publicado" if not dated else "intervalos_fuera_de_fecha")
            report["error"] = "Sin intervalo propio confirmado para la fecha; derivaciones comarcales no publicadas por esta API."
        reports.append(report)
    return points, rows, reports


def run(target, cache, offline=False, use_geocoder=False, allow_address=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if offline:
            manifest = json.loads((cache / "indice.json").read_text())
            if date.fromisoformat(manifest["fecha_consulta"]) != target:
                raise ValueError("La API publica hoy, no acepta fecha: la captura debe corresponder al día solicitado.")
            data = json.loads((cache / "farmacias.json").read_text())
            towns = json.loads((cache / "poblaciones.json").read_text())
        else:
            acquired = datetime.now(TZ)
            if target != acquired.date():
                raise ValueError("La API COFM no admite fechas históricas/futuras; use una captura de ese día.")
            config = discover()
            towns = json.loads(request(config["municipios"]))
            data = json.loads(request(config["catalogo"]))
            if datetime.now(TZ).date() != acquired.date():
                raise ValueError("Consulta atravesó medianoche: repetir para la fecha correcta.")
            # Validate before replacing reusable snapshots.
            parse(data, towns, target)
            write_json(cache / "farmacias.json", data)
            write_json(cache / "poblaciones.json", towns)
            manifest = {"fecha_consulta": acquired.date().isoformat(),
                        "consultado": acquired.isoformat(), "recursos_publicos": config}
            write_json(cache / "indice.json", manifest)
        points, rows, reports = parse(data, towns, target)
        locate_and_catalogue(points, "Madrid", use_geocoder=use_geocoder, allow_address=allow_address)
        positions = {r["id"]: r for r in points}
        for row in rows:
            row.update({k: v for k, v in positions[row["id"]].items()
                        if k in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas", "nota_ubicacion")})
        complete = publish(target, "Madrid", SOURCE, rows, reports)
        path = OUT_DIR / f"cobertura-madrid-{target}.json"
        coverage = json.loads(path.read_text())
        coverage.update(consultado=manifest["consultado"], captura_sin_red=offline,
                        opciones_selector=len(towns), municipios_censados=len(reports),
                        farmacias_catalogo=len(points),
                        municipios_con_guardia=sum(r["farmacias"] > 0 for r in reports),
                        municipios_sin_registros_catalogo=sum(r["farmacias_catalogo"] == 0 for r in reports),
                        municipios_sin_horario_publicado=sum(
                            r.get("motivo_sin_datos") == "sin_horario_guardia_publicado" for r in reports),
                        municipios_intervalos_fuera_fecha=sum(
                            r.get("motivo_sin_datos") == "intervalos_fuera_de_fecha" for r in reports),
                        limitacion="API de hoy; sin derivaciones comarcales ni consulta por fecha. Cero resultados no certifica ausencia de servicio.")
        write_json(path, coverage)
        return complete
    except (OSError, ValueError, KeyError, TypeError) as error:
        reports = [{"nombre": "API provincial COFM", "estado": "error", "error": str(error)}]
        census = cache / "poblaciones.json"
        if census.exists():
            try:
                groups = {}
                for town in json.loads(census.read_text()):
                    groups.setdefault(municipality(town["nombre"]), town["nombre"])
                reports.extend({"nombre": name, "estado": "error", "error": str(error)} for name in groups.values())
            except (OSError, ValueError, KeyError, TypeError) as cache_error:
                reports[0]["error"] += f" · Censo guardado no legible: {cache_error}"
        publish(target, "Madrid", SOURCE, [], reports)
        print(f"ERROR Madrid: {error}", flush=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path("data/madrid-cache"))
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite --geocode")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red,
                             args.geocode, args.permitir_direccion_exacta) else 1)
