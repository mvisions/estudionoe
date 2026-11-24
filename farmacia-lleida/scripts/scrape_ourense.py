#!/usr/bin/env python3
"""Import dated duty intervals from the official COF Ourense locator."""
import argparse
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import publish
from proximidad import PharmacyIndex, phone_digits
from scrape_mes import OUT_DIR, write_json

SOURCE = "https://www.cofourense.es/buscador-de-farmacias-de-guardia/"
API = "https://www.cofourense.es/wp-json/vcomm/v1/farmacias/guardia"
PARAMS = {"estilo": "completo", "servicios": "", "tipo": "",
          "orden": "salida_dia_siguiente DESC,soe ASC",
          "uuid": "1fc2a951-9f87-4012-a76c-16eb39596a2e"}


def fetch(target):
    params = {**PARAMS, "fecha_inicio": target.isoformat(), "fecha_fin": target.isoformat(),
              "hora_inicio": "00:00:00", "hora_fin": "23:59:59"}
    request = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def parse(data, target, known):
    page = data["metadatos"]["paginacion"]
    records = data["informacion"]
    if not isinstance(records, list) or not records or int(page["totalPaginas"]) != 1:
        raise ValueError("Respuesta sin guardias o paginada; no se publica como completa.")
    start_day = datetime.combine(target, time.min)
    end_day = start_day + timedelta(days=1)
    index = PharmacyIndex(row for row in known if row.get("provincia") == "Ourense")
    rows = {}
    for item in records:
        service_day = date.fromisoformat(item["fecha"])
        if service_day not in (target, target - timedelta(days=1)):
            raise ValueError("La fuente devuelve una fecha inesperada.")
        contact = item["contactos_profesionales"]
        if len(contact) != 1:
            raise ValueError("La ficha no identifica una única dirección.")
        contact = contact[0]
        if contact["provincia"] != "Ourense" or not all(
                contact.get(key) for key in ("direccion", "municipio", "telefono")):
            raise ValueError("Ficha con dirección, municipio o teléfono incompletos.")
        ident = str(item["soe"])
        if not ident.isdigit() or not item.get("nombre") or not item.get("horarios"):
            raise ValueError("Ficha sin identificación o turnos.")
        intervals = []
        for duty in item["horarios"]:
            begin = datetime.combine(service_day, time.fromisoformat(duty["hora_apertura"]))
            finish = datetime.combine(service_day, time.fromisoformat(duty["hora_cierre"]))
            if not isinstance(duty["cierre_dia_siguiente"], bool):
                raise ValueError("Indicador de fin de guardia inválido.")
            if duty["cierre_dia_siguiente"]:
                finish += timedelta(days=1)
            if finish <= begin or not duty.get("tipo"):
                raise ValueError("Turno oficial inválido.")
            if begin < end_day and finish > start_day:
                intervals.append({"inicio": max(begin, start_day).isoformat(),
                                  "fin": min(finish, end_day).isoformat(),
                                  "inicio_original": begin.isoformat(), "fin_original": finish.isoformat(),
                                  "tipo": duty["tipo"]})
        if not intervals:
            continue
        row = {"id": f"cof-ourense-{ident}", "cofm_id": None, "nombre": item["nombre"],
               "direccion": contact["direccion"], "localidad": contact["municipio"],
               "provincia": "Ourense", "telefono": contact["telefono"], "guardia": True,
               "fecha_guardia": target.isoformat(), "fuente": SOURCE,
               "localidades_atendidas": [contact["municipio"]], "lat": None, "lng": None,
               "guardia_intervalos": intervals,
               "guardia_franjas": [f"{i['tipo']}: {i['inicio']}–{i['fin']}"
                                   + ("; llamar antes de acudir" if "localizada" in i["tipo"].lower() else "")
                                   for i in intervals]}
        try:
            lat, lng = json.loads(contact["coordenadas"])
        except (ValueError, TypeError, KeyError):
            lat, lng = None, None
        if coordinates({"lat": lat, "lng": lng}) and 41.7 < lat < 43.0 and -8.5 < lng < -6.5:
            phone = phone_digits(row)
            matches = [(distance, pharmacy) for distance, pharmacy in index.near((lat, lng))
                       if len(phone) == 9 and phone_digits(pharmacy) == phone
                       and str(pharmacy.get("id", "")).startswith("osm-")
                       and str(pharmacy["id"])[4:].isdigit()]
            if len(matches) == 1:
                distance, pharmacy = matches[0]
                row.update(lat=lat, lng=lng, precision_ubicacion="farmacia",
                           fuente_coordenadas=SOURCE, ajuste_ubicacion_m=round(distance, 1),
                           referencia_ubicacion=f"https://www.openstreetmap.org/node/{pharmacy['id'].removeprefix('osm-')}",
                           nota_ubicacion=f"Coordenada del Colegio contrastada con farmacia OSM a {distance:.1f} m.")
        if not coordinates(row):
            print(f"AVISO Ourense {ident}: ubicación sin contraste inequívoco a 15 m; no se dibuja.", flush=True)
        if ident in rows:
            existing = rows[ident]
            if any(existing[key] != row[key] for key in ("direccion", "localidad", "telefono")):
                raise ValueError("Una farmacia tiene fichas oficiales contradictorias.")
            existing["guardia_intervalos"].extend(intervals)
            existing["guardia_franjas"].extend(row["guardia_franjas"])
        else:
            rows[ident] = row
    if not rows:
        raise ValueError("No hay intervalos confirmados para la fecha.")
    for row in rows.values():
        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(rows.values())


def run(target, output=OUT_DIR):
    data = fetch(target)
    known = json.loads((output / "farmacias-espana-hoy.json").read_text())
    rows = parse(data, target, known)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "farmacias-ourense.json"
    saved = {row["id"]: row for row in json.loads(path.read_text())} if path.exists() else {}
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(path, list(saved.values()))
    report = [{"nombre": "Provincia de Ourense", "estado": "parcial", "farmacias": len(rows),
               "error": "La fuente no acredita cobertura de todos los municipios; confirmar por teléfono."}]
    return publish(target, "Ourense", SOURCE, rows, report, output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.salida) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Ourense: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
