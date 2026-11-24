#!/usr/bin/env python3
"""Scraper de farmacias de guardia de Las Palmas (Canarias) via API del COF Las Palmas."""
import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from scrape_mes import OUT_DIR, slugify, write_json

BASE = "https://www.coflaspalmas.es"
AJAX = "https://www.coflaspalmas.es/wp-admin/admin-ajax.php"
NONCE = "bc4daa5b6f"
PROVINCIA = "Las Palmas"


def request_municipios():
    body = urllib.parse.urlencode({
        "action": "bearer_authentication_with_params",
        "nonce": NONCE,
        "vbf_req_endpoint": "/municipios",
        "vbf_req_aplica_filtro_fecha": 0,
        "vbf_req_lang": "es",
    }).encode()
    req = urllib.request.Request(AJAX, data=body,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    return [m["municipio"] for m in data["data"]["data"]["informacion"]]


def request_guardias(municipio, fecha):
    body = urllib.parse.urlencode({
        "action": "bearer_authentication_with_params",
        "nonce": NONCE,
        "vbf_req_endpoint": "/farmacias-abiertas",
        "vbf_req_fecha": fecha.isoformat(),
        "vbf_req_municipio": municipio,
        "vbf_req_es_listado_geo": "false",
        "vbf_req_solo_guardias": "true",
        "vbf_req_aplica_filtro_fecha": 1,
        "vbf_req_lang": "es",
    }).encode()
    req = urllib.request.Request(AJAX, data=body,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    return data["data"]["data"]["informacion"]


def parse_guardias(municipio, fecha, groups):
    rows = []
    for group in groups or []:
        for item in group.get("contenido", []):
            nombre = item.get("nombre", "")
            direccion = item.get("direccion", "")
            telefono = item.get("telefono")
            municipio_real = item.get("municipio", municipio)
            lat = item.get("coordenadas", [None, None])[0]
            lng = item.get("coordenadas", [None, None])[1]
            for g in item.get("guardias", []):
                inicio = g.get("guardia_horario_fecha_inicio")
                fin = g.get("guardia_horario_fecha_fin")
                franja = f"{g.get('guardia_hora_inicio','')} - {g.get('guardia_hora_fin','')}"
                rows.append({
                    "id": f"cof-laspalmas-{item.get('uuid','')}",
                    "nombre": nombre,
                    "direccion": direccion,
                    "localidad": municipio_real,
                    "provincia": "Las Palmas",
                    "telefono": telefono,
                    "lat": lat,
                    "lng": lng,
                    "guardia": True,
                    "guardia_franja": franja,
                    "guardia_franjas": [franja],
                    "fecha_guardia": fecha.isoformat(),
                    "fuente": BASE,
                    "fuentes": [BASE],
                    "hora_inicio": inicio,
                    "hora_fin": fin,
                })
    return rows


def run(fecha, offline=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    municipios = request_municipios()
    print(f"Municipios: {len(municipios)}", flush=True)
    rows = []
    reports = []
    for i, m in enumerate(municipios, 1):
        try:
            groups = request_guardias(m, fecha)
            found = parse_guardias(m, fecha, groups)
            rows.extend(found)
            reports.append({"nombre": m, "estado": "disponible", "farmacias": len({r["id"] for r in found})})
            print(f"{i}/{len(municipios)} {m}: {len(found)} guardias", flush=True)
        except Exception as e:
            reports.append({"nombre": m, "estado": "error", "error": str(e)})
            print(f"{i}/{len(municipios)} {m}: ERROR {e}", flush=True)
        time.sleep(0.3)
    # publish
    path = OUT_DIR / f"guardias-laspalmas-{fecha.isoformat()}.json"
    write_json(path, rows)
    report = {"fecha": fecha.isoformat(), "provincia": "Las Palmas", "fuente": BASE,
              "consultas": reports, "farmacias": len(rows),
              "farmacias_confirmadas": len(rows)}
    write_json(OUT_DIR / f"cobertura-laspalmas-{fecha.isoformat()}.json", report)
    print(f"Las Palmas: {len(rows)} guardias publicadas.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    run(args.fecha)