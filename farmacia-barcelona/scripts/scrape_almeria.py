#!/usr/bin/env python3
"""Import complete dated public Almería finder responses, including overnight duties."""
import argparse
import http.cookiejar
import json
import math
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from scrape_mes import OUT_DIR, write_json
from scrape_sevilla import saved_address_signature, street_query

SOURCE = "https://www.cofalmeria.com/buscador-de-farmacias/?activo_guardias=on"
AJAX = "https://www.cofalmeria.com/wp-admin/admin-ajax.php"


def request(opener, url, params=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode() if params else None,
                                 headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with opener.open(req, timeout=60) as response:
        return response.read()


def fetch_day(opener, config, target):
    response = request(opener, AJAX, {
        "action": "bearer_authentication_with_params", "nonce": config["nonce"],
        "vbf_req_endpoint": "/farmacias-abiertas", "vbf_req_fecha": target.isoformat(),
        "vbf_req_es_listado_geo": "false", "vbf_req_solo_guardias": "true",
        "vbf_req_aplica_filtro_fecha": "true", "vbf_req_lang": "es_ES",
    })
    return json.loads(response)


def response_rows(response, requested, diagnostics=None):
    if not isinstance(response, dict) or response.get("success") is not True:
        raise ValueError("El buscador de Almería no confirma una respuesta válida.")
    data = response["data"]["data"]
    groups = data["informacion"]
    if not isinstance(groups, list):
        raise ValueError("Respuesta provincial sin lista de guardias.")
    rows = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Grupo de guardias con estructura no reconocible.")
        if not isinstance(group.get("contenido"), list):
            raise ValueError("Grupo de guardias sin contenido reconocible.")
        rows.extend(group["contenido"])
    pagination = data["metadatos"]["paginacion"]
    if (int(pagination["totalPaginas"]) != 1 or int(pagination["paginaActual"]) != 1
            or int(pagination["totalElementos"]) != len(rows)):
        raise ValueError("Respuesta provincial incompleta/paginada; no se publica una lista truncada.")
    valid_rows = []
    omitted = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Registro de farmacia con estructura no reconocible.")
        if not isinstance(row.get("guardias"), list) or not row["guardias"]:
            raise ValueError("Farmacia sin intervalos de guardia confirmados.")
        for duty in row["guardias"]:
            if not isinstance(duty, dict) or not all(
                    isinstance(duty.get(field), str) and duty[field].strip()
                    for field in ("tipo_guardia", "guardia_horario_fecha_inicio", "guardia_horario_fecha_fin")):
                raise ValueError("Intervalo de guardia con estructura no reconocible.")
            start = datetime.fromisoformat(duty["guardia_horario_fecha_inicio"])
            end = datetime.fromisoformat(duty["guardia_horario_fecha_fin"])
            if start.tzinfo or end.tzinfo:
                raise ValueError(f"Intervalo de guardia inválido: {row.get('uuid', 'sin UUID')}")
            if start.date() != requested:
                raise ValueError("El buscador no respeta la fecha solicitada; no se reutilizan guardias de hoy.")
        if not all(isinstance(row.get(field), str) and row[field].strip()
                   for field in ("uuid", "direccion", "municipio")):
            uuid = row.get("uuid")
            omitted.append(uuid.strip() if isinstance(uuid, str) and uuid.strip() else None)
            continue
        valid_rows.append(row)
    if omitted:
        uuids = [uuid for uuid in omitted if uuid]
        detail = f"UUID omitidos: {', '.join(uuids)}." if uuids else "No se pudo identificar con UUID alguno de los registros omitidos."
        usable = f"{len(valid_rows)} registro utilizable" if len(valid_rows) == 1 else f"{len(valid_rows)} registros utilizables"
        diagnostic = (
            f"{requested}: cobertura parcial; {len(omitted)} de {len(rows)} registros omitidos "
            f"por identidad, dirección o municipio incompletos; {usable}. {detail}"
        )
        if diagnostics is not None:
            diagnostics.append(diagnostic)
        print(f"AVISO {diagnostic}", flush=True)
    return valid_rows


def parse_responses(responses, target, errors=None, unconfirmed=None):
    start_day = datetime.combine(target, datetime.min.time())
    end_day = start_day + timedelta(days=1)
    result = {}
    for requested, response in responses:
        for pharmacy in response_rows(response, requested, errors):
            for duty in pharmacy["guardias"]:
                start = datetime.fromisoformat(duty["guardia_horario_fecha_inicio"])
                end = datetime.fromisoformat(duty["guardia_horario_fecha_fin"])
                invalid = end <= start
                if invalid:
                    error = f"{pharmacy['municipio']}, {pharmacy['direccion']}: intervalo oficial no válido ({start}–{end}); no se supone una guardia de 24 horas."
                    if errors is not None and error not in errors:
                        errors.append(error)
                    print(f"AVISO {error}", flush=True)
                    if requested != target:
                        if unconfirmed is not None:
                            unconfirmed.add(f"alm-{pharmacy['uuid']}")
                        continue
                if not invalid and (start >= end_day or end <= start_day):
                    continue
                identifier = f"alm-{pharmacy['uuid']}"
                if identifier not in result:
                    result[identifier] = {
                        "id": identifier, "nombre": pharmacy["nombre"], "direccion": pharmacy["direccion"],
                        "localidad": pharmacy["municipio"], "provincia": "Almería",
                        "telefono": pharmacy.get("telefono"),
                        "telefono_guardia": pharmacy.get("guardias_telefono"),
                        "guardia": True, "fecha_guardia": target.isoformat(),
                        "guardia_intervalos": [], "guardia_franjas": [],
                        "lat": None, "lng": None, "fuente": SOURCE,
                    }
                    if pharmacy.get("nota_localizacion"):
                        result[identifier]["nota_ubicacion"] = pharmacy["nota_localizacion"]
                row = result[identifier]
                if invalid:
                    note = "Guardia publicada para la fecha; horario oficial inválido, confirmar por teléfono"
                    if note not in row["guardia_franjas"]:
                        row["guardia_franjas"].append(note)
                    row["nota_horario"] = error
                    row["guardia_franja"] = " · ".join(row["guardia_franjas"])
                    continue
                clipped_start, clipped_end = max(start, start_day), min(end, end_day)
                interval = {"inicio": clipped_start.isoformat(), "fin": clipped_end.isoformat(),
                            "tipo": duty["tipo_guardia"]}
                if interval not in row["guardia_intervalos"]:
                    row["guardia_intervalos"].append(interval)
                    row["guardia_franjas"].append(f"{duty['tipo_guardia']}: {clipped_start:%d/%m %H:%M}–{clipped_end:%d/%m %H:%M}")
                    row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(result.values())


def valid_position(row):
    lat, lng = row.get("lat"), row.get("lng")
    return (isinstance(lat, (int, float)) and not isinstance(lat, bool)
            and isinstance(lng, (int, float)) and not isinstance(lng, bool)
            and math.isfinite(lat) and math.isfinite(lng)
            and 36.5 < lat < 37.95 and -3.25 < lng < -1.5)


def geocode(row):
    street = street_query(row["direccion"])
    key = saved_address_signature(street, row["localidad"])
    params = {"q": f"{street}, {row['localidad']}, Almería, España",
              "format": "jsonv2", "addressdetails": 1, "countrycodes": "es", "limit": 5}
    candidates = json.loads(request(urllib.request.build_opener(),
                           "https://nominatim.openstreetmap.org/search?"+urllib.parse.urlencode(params)))
    matches = []
    for candidate in candidates:
        address = candidate.get("address", {})
        cities = [address[k] for k in ("city", "town", "village", "municipality", "suburb", "city_district")
                  if address.get(k)]
        road = f"{address.get('road', '')} {address.get('house_number', '')}"
        if (candidate.get("type") != "pharmacy" or not key
                or not any(saved_address_signature(road, city) == key for city in cities)):
            continue
        position = {"lat": float(candidate["lat"]), "lng": float(candidate["lon"]),
                    "precision_ubicacion": "farmacia",
                    "fuente_coordenadas": f"https://www.openstreetmap.org/{candidate['osm_type']}/{candidate['osm_id']}"}
        if valid_position(position):
            matches.append(position)
    return matches[0] if len(matches) == 1 else None


def locate(rows, use_geocoder=False):
    path = OUT_DIR / "farmacias-almeria.json"
    old = {r["id"]:r for r in json.loads(path.read_text())} if path.exists() else {}
    osm = [r for r in json.loads((OUT_DIR / "farmacias-osm-espana.json").read_text()) if valid_position(r)]
    errors = []
    for row in rows:
        prior = old.get(row["id"])
        fields = ("lat", "lng", "precision_ubicacion", "fuente_coordenadas")
        if prior and prior["direccion"] == row["direccion"] and prior.get("telefono") == row["telefono"] and valid_position(prior):
            row.update({field:prior.get(field) for field in fields})
            continue
        phone = re.sub(r"\D", "", str(row["telefono"] or "")).removeprefix("34")
        key = saved_address_signature(row["direccion"], row["localidad"])
        matches = [r for r in osm if (phone and re.sub(r"\D", "", str(r.get("telefono") or "")).removeprefix("34") == phone)
                   or (key and saved_address_signature(r.get("direccion", ""), r.get("localidad", "")) == key)]
        if len(matches) == 1:
            point = matches[0]
            row.update(lat=point["lat"], lng=point["lng"], precision_ubicacion="farmacia",
                       fuente_coordenadas="https://www.openstreetmap.org/"+point["id"].replace("osm-", "node/"))
        elif use_geocoder and not matches:
            try:
                position = geocode(row)
                if position:
                    row.update(position)
                print(f"Ubicación {row['localidad']} {row['direccion']}: {'verificada' if position else 'pendiente'}", flush=True)
            except (OSError, ValueError) as error:
                errors.append(f"{row['id']}: {error}")
                print(f"ERROR geocodificación: {row['id']}: {error}", flush=True)
            time.sleep(1.1)
        if not valid_position(row):
            print(f"AVISO {row['id']}: ubicación no confirmada; no se dibuja marcador.", flush=True)
    for row in rows:
        old[row["id"]] = {**row, "guardia": False}
    write_json(path, list(old.values()))
    return errors


def retain_unconfirmed(rows, unconfirmed, target):
    path = OUT_DIR / f"guardias-almeria-{target}.json"
    if not unconfirmed or not path.exists():
        return []
    known = {row["id"] for row in rows}
    retained = []
    for previous in json.loads(path.read_text()):
        if previous["id"] in unconfirmed and previous["id"] not in known:
            row = dict(previous)
            row["guardia_reconfirmada"] = False
            row["guardia_franja"] = f"{row.get('guardia_franja', '')} · Guardia anterior conservada; madrugada no reconfirmada, confirmar por teléfono"
            retained.append(row)
    return retained


def run(target, use_geocoder=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        html = request(opener, SOURCE).decode("utf-8")
        match = re.search(r"var vbf_vars = (\{.*?\});", html)
        if not match:
            raise ValueError("El buscador oficial no publica su configuración.")
        config = json.loads(match[1])
        if config.get("ajax_url") != AJAX or not config.get("nonce"):
            raise ValueError("Configuración pública del buscador no reconocible.")
        responses = [(day, fetch_day(opener, config, day))
                     for day in (target-timedelta(days=1), target)]
        schedule_errors = []
        unconfirmed = set()
        rows = parse_responses(responses, target, schedule_errors, unconfirmed)
        if not rows:
            raise ValueError("Sin guardias confirmadas: se conserva el calendario anterior.")
        errors = locate(rows, use_geocoder)
        retained = retain_unconfirmed(rows, unconfirmed, target)
        rows.extend(retained)
    except (OSError, ValueError, KeyError, TypeError) as error:
        write_json(OUT_DIR / f"cobertura-almeria-{target}.json", {
            "fecha":target.isoformat(), "provincia":"Almería", "fuente":SOURCE, "completa":False,
            "consultas":[{"nombre":"Buscador provincial", "estado":"error", "error":str(error)}],
            "calendario_actualizado":False,
        })
        raise
    write_json(OUT_DIR / f"guardias-almeria-{target}.json", rows)
    located = sum(valid_position(r) for r in rows)
    write_json(OUT_DIR / f"cobertura-almeria-{target}.json", {
        "fecha":target.isoformat(), "provincia":"Almería", "fuente":SOURCE, "completa":not schedule_errors,
        "consultado":datetime.now(timezone.utc).isoformat(),
        "consultas":[{"nombre":"Buscador provincial: fecha y madrugada anterior, sin filtro de municipio",
                     "estado":"parcial" if schedule_errors else "disponible",
                     "farmacias":len(rows), "errores":schedule_errors}],
        "farmacias":len(rows), "con_coordenadas":located, "calendario_actualizado":True,
        "guardias_conservadas_no_reconfirmadas":len(retained),
        "errores_coordenadas":errors,
    })
    print(f"Almería {target}: {len(rows)} guardias confirmadas, {located} ubicadas.", flush=True)
    return not errors and not schedule_errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    parser.add_argument("--geocode", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if run(args.fecha, args.geocode) else 1)
