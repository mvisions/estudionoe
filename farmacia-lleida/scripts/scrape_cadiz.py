#!/usr/bin/env python3
"""Publish dated Cádiz API duty intervals, including overnight carry-over."""
import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone

from scrape_mes import OUT_DIR, write_json

SOURCE = "https://www.cofcadiz.es/wp-json/vcomm/v1/farmacias/guardia"


def parse_response(data, target):
    if not isinstance(data, dict) or not isinstance(data.get("informacion"), list):
        raise ValueError("La API de Cádiz no devuelve una lista de guardias.")
    start_day = datetime.combine(target, time.min)
    end_day = start_day + timedelta(days=1)
    rows = {}
    for info in data["informacion"]:
        service_day = date.fromisoformat(info["fecha"])
        for schedule in info["horarios"]:
            start = datetime.combine(service_day, time.fromisoformat(schedule["hora_apertura"]))
            end = datetime.combine(service_day, time.fromisoformat(schedule["hora_cierre"]))
            if schedule["cierre_dia_siguiente"] is True:
                end += timedelta(days=1)
            if end <= start:
                raise ValueError(f"Intervalo de guardia no válido: {info.get('soe')}")
            if not start < end_day or not end > start_day:
                continue
            clipped_start, clipped_end = max(start, start_day), min(end, end_day)
            period = f"{schedule['tipo']}: {clipped_start:%d/%m %H:%M}–{clipped_end:%d/%m %H:%M}"
            for contact in info["contactos_profesionales"]:
                identifier = str(contact.get("soe") or info.get("soe") or "")
                if not identifier or not contact.get("direccion") or not contact.get("municipio"):
                    raise ValueError("Registro de Cádiz sin identidad, dirección o municipio.")
                key = f"cad-{identifier}"
                if key not in rows:
                    lat = lng = None
                    precision = {}
                    coordinates = contact.get("coordenadas")
                    if coordinates:
                        point = json.loads(coordinates)
                        if (not isinstance(point, list) or len(point) != 2
                                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in point)):
                            raise ValueError(f"Coordenadas no numéricas: {key}")
                        a, b = point
                        if not (math.isfinite(a) and math.isfinite(b) and 35.7 < a < 37.2 and -6.6 < b < -5):
                            print(f"AVISO {key}: coordenadas oficiales no válidas ({a}, {b}); no se publica marcador.", flush=True)
                        else:
                            lat, lng = a, b
                            precision = {"precision_ubicacion": "farmacia", "fuente_coordenadas": SOURCE}
                    rows[key] = {
                        "id": key, "cofm_id": identifier, "nombre": info.get("nombre", ""),
                        "direccion": contact["direccion"], "localidad": contact["municipio"],
                        "provincia": "Cádiz", "zona": info.get("zona_guardia", ""),
                        "telefono": contact.get("telefono"), "guardia": True,
                        "fecha_guardia": target.isoformat(), "guardia_franjas": [],
                        "guardia_intervalos": [], "lat": lat, "lng": lng, "fuente": SOURCE,
                        **precision,
                    }
                row = rows[key]
                if period not in row["guardia_franjas"]:
                    row["guardia_franjas"].append(period)
                    row["guardia_intervalos"].append({"inicio": clipped_start.isoformat(),
                                                     "fin": clipped_end.isoformat(), "tipo": schedule["tipo"]})
                row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(rows.values())


def fetch_day(target):
    result = []
    page = 1
    while True:
        params = {
            "estilo": "completo", "servicios": "", "tipo": "", "orden": "",
            "uuid": "00000000-0000-0000-0000-000000000000",
            "fecha_inicio": target.isoformat(), "hora_inicio": "00:00:00",
            "fecha_fin": target.isoformat(), "hora_fin": "23:59:59",
            "zona": "", "b": "", "limit": 1000, "offset": (page-1)*1000,
        }
        request = urllib.request.Request(SOURCE + "?" + urllib.parse.urlencode(params),
                                        headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
        with urllib.request.urlopen(request, timeout=40) as response:
            data = json.load(response)
        if not isinstance(data.get("informacion"), list):
            raise ValueError("Respuesta de API sin lista de guardias.")
        pagination = data["metadatos"]["paginacion"]
        if int(pagination["paginaActual"]) != page:
            raise ValueError("La API no respeta la página solicitada.")
        total_pages = int(pagination["totalPaginas"])
        if total_pages < 1 or total_pages > 100:
            raise ValueError("Paginación de API no válida.")
        result.extend(data["informacion"])
        if page >= total_pages:
            break
        page += 1
    return {"informacion": result}


def run(target):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = fetch_day(target)
        rows = parse_response(data, target)
        if not rows:
            raise ValueError("La API devuelve cero guardias; no se sustituye el calendario.")
    except (OSError, ValueError, KeyError, TypeError) as error:
        write_json(OUT_DIR / f"cobertura-cadiz-{target}.json", {
            "fecha": target.isoformat(), "provincia": "Cádiz", "fuente": SOURCE, "completa": False,
            "consultas": [{"nombre": "API provincial", "estado": "error", "error": str(error)}],
            "calendario_actualizado": False,
        })
        raise
    catalogue_path = OUT_DIR / "farmacias-cadiz.json"
    catalogue = {r["id"]: r for r in json.loads(catalogue_path.read_text())} if catalogue_path.exists() else {}
    for row in rows:
        catalogue[row["id"]] = {**row, "guardia": False}
    write_json(catalogue_path, list(catalogue.values()))
    write_json(OUT_DIR / f"guardias-cadiz-{target}.json", rows)
    located = sum(r["lat"] is not None and r["lng"] is not None for r in rows)
    write_json(OUT_DIR / f"cobertura-cadiz-{target}.json", {
        "fecha": target.isoformat(), "provincia": "Cádiz", "fuente": SOURCE, "completa": True,
        "consultado": datetime.now(timezone.utc).isoformat(),
        "consultas": [{"nombre": "API provincial, todas sus páginas", "estado": "disponible", "farmacias": len(rows)}],
        "farmacias": len(rows), "con_coordenadas": located, "calendario_actualizado": True,
    })
    print(f"Cádiz {target}: {len(rows)} farmacias, {located} con coordenadas oficiales.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    run(parser.parse_args().fecha)
