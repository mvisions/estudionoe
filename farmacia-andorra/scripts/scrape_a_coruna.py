#!/usr/bin/env python3
"""Import dated duty pharmacies from the official COF A Coruña locator."""
import argparse
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import publish
from proximidad import PharmacyIndex, phone_digits
from scrape_mes import OUT_DIR, write_json

SOURCE = "https://www.cofc.es/farmacia/index"
HEADERS = {"User-Agent": "FarmaciasDeGuardiaTracker/1.0"}
TOKEN = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')
RANGE = re.compile(r"^(\d\d):(\d\d) - (\d\d):(\d\d)( \(día posterior\))?$")


def fetch(target):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(urllib.request.Request(SOURCE, headers=HEADERS), timeout=45) as response:
        page = response.read().decode("utf-8")
    token = TOKEN.search(page)
    if not token:
        raise ValueError("El buscador del Colegio no ofrece el token del formulario.")
    body = urllib.parse.urlencode({"FechaBusqueda": target.strftime("%d/%m/%Y"), "IdPoblacionFiltro": "0",
                                   "LatitudFiltro": "", "LongitudFiltro": "",
                                   "__RequestVerificationToken": token.group(1)}).encode()
    request = urllib.request.Request(SOURCE, data=body, headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"})
    with opener.open(request, timeout=45) as response:
        return json.load(response)


def intervals(schedule, target):
    """Official opening hours for the day; «(día posterior)» ends the next morning."""
    text = re.sub(r"\s*\(Ahora (abierta|cerrada)\)\s*$", "", schedule or "").strip()
    start_day = datetime.combine(target, time.min)
    end_day = start_day + timedelta(days=1)
    if text == "24 Horas":
        return [(start_day, end_day)]
    result = []
    for part in text.split(";"):
        match = RANGE.match(part.strip())
        if not match:
            raise ValueError(f"Horario oficial no reconocido: {schedule!r}")
        h1, m1, h2, m2, next_day = match.groups()
        begin = start_day + timedelta(hours=int(h1), minutes=int(m1))
        finish = start_day + timedelta(hours=int(h2), minutes=int(m2), days=1 if next_day else 0)
        if finish <= begin:
            raise ValueError(f"Horario oficial inválido: {schedule!r}")
        result.append((begin, finish))
    return result


def parse(data, target, known):
    form = data.get("formulario") or ""
    if f'value="{target.strftime("%d/%m/%Y")}"' not in form:
        raise ValueError("La respuesta no confirma la fecha solicitada.")
    records = data.get("listadoTodas")
    if not isinstance(records, list) or not records:
        raise ValueError("Respuesta sin guardias; no se publica.")
    end_day = datetime.combine(target, time.min) + timedelta(days=1)
    index = PharmacyIndex(row for row in known if row.get("provincia") == "A Coruña")
    rows = {}
    for item in records:
        ident = item.get("codigoSanidad") or ""
        if not re.fullmatch(r"C-\d+-F", ident) or not all(item.get(k) for k in ("nombre", "direccion", "nombrePoblacion")):
            raise ValueError("Ficha sin código sanitario, nombre o dirección.")
        turn = item.get("nombreGuardiaTipoTurno") or "Guardia"
        spans = [(begin, min(finish, end_day), finish) for begin, finish in intervals(item.get("horario"), target)]
        row = {"id": f"cof-a-coruna-{ident}", "cofm_id": None, "nombre": item["nombre"],
               "direccion": item["direccion"], "localidad": item["nombrePoblacion"],
               "provincia": "A Coruña", "telefono": item.get("telefono") or "", "guardia": True,
               "fecha_guardia": target.isoformat(), "fuente": SOURCE,
               "localidades_atendidas": [item["nombrePoblacion"]], "lat": None, "lng": None,
               "guardia_intervalos": [{"inicio": b.isoformat(), "fin": f.isoformat(),
                                       "inicio_original": b.isoformat(), "fin_original": o.isoformat(),
                                       "tipo": turn} for b, f, o in spans],
               "guardia_franjas": [f"{turn}: {item['horario'].split(' (Ahora')[0]}"]}
        row["guardia_franja"] = row["guardia_franjas"][0]
        lat, lng = item.get("latitud"), item.get("longitud")
        if coordinates({"lat": lat, "lng": lng}) and 42.6 < lat < 43.9 and -9.4 < lng < -7.6:
            phone = phone_digits(row)
            matches = [(distance, pharmacy) for distance, pharmacy in index.near((lat, lng))
                       if str(pharmacy.get("id", "")).startswith("osm-")
                       and (not phone_digits(pharmacy) or phone_digits(pharmacy) == phone)]
            if len(matches) == 1:
                distance, pharmacy = matches[0]
                row.update(lat=lat, lng=lng, precision_ubicacion="farmacia",
                           fuente_coordenadas=SOURCE, ajuste_ubicacion_m=round(distance, 1),
                           referencia_ubicacion=f"https://www.openstreetmap.org/node/{pharmacy['id'].removeprefix('osm-')}",
                           nota_ubicacion=f"Coordenada del Colegio contrastada con farmacia OSM a {distance:.1f} m.")
        if not coordinates(row):
            print(f"AVISO A Coruña {ident}: ubicación sin contraste inequívoco a 15 m; no se dibuja.", flush=True)
        if ident in rows:
            raise ValueError(f"Farmacia {ident} repetida en el listado oficial.")
        rows[ident] = row
    return list(rows.values())


def run(target, output=OUT_DIR):
    data = fetch(target)
    known = json.loads((output / "farmacias-espana-hoy.json").read_text())
    rows = parse(data, target, known)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "farmacias-a-coruna.json"
    saved = {row["id"]: row for row in json.loads(path.read_text())} if path.exists() else {}
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(path, list(saved.values()))
    report = [{"nombre": "Provincia de A Coruña", "estado": "parcial", "farmacias": len(rows),
               "error": "Listado provincial del Colegio; confirmar por teléfono antes de acudir."}]
    return publish(target, "A Coruña", SOURCE, rows, report, output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.salida) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR A Coruña: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
