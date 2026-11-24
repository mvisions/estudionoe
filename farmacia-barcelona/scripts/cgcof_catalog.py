#!/usr/bin/env python3
"""Collect dated CGCOF province routes with conservative partial publication."""
import argparse
import html
import json
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, merge_rows, publish
from scrape_mes import BASE, OUT_DIR, fetch, parse_schedule, parse_selectors, slugify, write_json

TZ = ZoneInfo("Europe/Madrid")


def parse(content, selector, target, prior=False, province_id="37", province="Salamanca"):
    rows = parse_schedule(content, selector, province_id, province, str(target))
    if rows is None:
        raise ValueError("Datos no disponibles; no se supone ausencia de guardias.")
    if not rows:
        raise ValueError("Calendario sin farmacias confirmadas.")
    for row in rows:
        if row["localidad"] == "Málaga":
            raise ValueError(f"La respuesta usa un sector sin municipio válido de {province}.")
        row["localidades_atendidas"] = [row["localidad"]]
        # Preserve printed hours instead of importing another province's default closing times.
        row["guardia_franjas"] = ["Guardia fechada según CGCOF; consultar horas del cartel y confirmar por teléfono."]
        row["guardia_franja"] = row["guardia_franjas"][0]
    if prior:
        source_rows = parse_schedule(content, selector, province_id, province, str(target))
        overnight_ids = {row["id"] for row in source_rows
                         if row["guardia_franja"].startswith(("noche", "todo el dia"))}
        rows = [row for row in rows if row["id"] in overnight_ids]
        for row in rows:
            row["fecha_guardia"] = str(target + timedelta(days=1))
            row["guardia_franjas"] = ["Madrugada: guardia nocturna/24h del día anterior; confirmar hora de cierre."]
            row["guardia_franja"] = row["guardia_franjas"][0]
    return rows


def enrich_contact(row, content):
    pairs = re.findall(r"<span><strong>(.*?)</strong></span>\s*<span>(.*?)</span>", content, re.S)
    fields = {slugify(html.unescape(key)): html.unescape(value).strip() for key, value in pairs}
    if (slugify(fields.get("direccion", "")) != slugify(row["direccion"])
            or slugify(fields.get("localidad", "")) != slugify(row["localidad"])):
        raise ValueError("Ficha CGCOF no confirma la dirección y localidad del calendario.")
    row["nombre"] = fields.get("titular", "")
    phone = re.sub(r"\D", "", fields.get("telefono", ""))
    if len(phone) == 9:
        row["telefono"] = phone
    elif phone:
        print(f"AVISO CGCOF {row['id']}: teléfono oficial con longitud inválida; no se corrige por conjetura.",
              flush=True)


def run(target, cache, offline=False, resume=False, geocode=False, limit=None, allow_address=False,
        province_id="37", province="Salamanca"):
    source = BASE + "/publico/Provincia_pNew.asp?id=" + province_id
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports, rows = [], []
    try:
        index = cache / "selectores.json"
        if offline or (resume and index.exists()):
            selectors = json.loads(index.read_text())
        else:
            selectors = parse_selectors(fetch(source), province_id)
            write_json(index, selectors)
        for selector in selectors[:limit] if limit else selectors:
            report = {**selector, "estado": "parcial", "farmacias": 0, "error":
                      "Horario exacto pendiente de interpretar; confirmar por teléfono. "
                      "La ruta oficial no acredita un censo municipal ni todas las derivaciones."}
            try:
                for day, prior in ((target, False), (target - timedelta(days=1), True)):
                    path = cache / f"{day}-{selector['parametro']}-{selector['codigo']}.html"
                    if offline or (resume and path.exists()):
                        content = path.read_text()
                    else:
                        params = {"date": f"{day.day}/{day.month}/{day.year}",
                                  selector["parametro"]: selector["codigo"], "vmenu": 1, "provincia": province_id}
                        content = fetch(BASE + "/GuardiasNew.asp?" + urllib.parse.urlencode(params))
                        path.write_text(content)
                        time.sleep(1.1)
                    batch = parse(content, selector, day, prior, province_id, province)
                    rows.extend(batch)
                    report["farmacias"] += len(batch)
            except (OSError, ValueError, KeyError, TypeError) as error:
                report.update(estado="error", error=str(error))
                print(f"AVISO {province} {selector['nombre']}: {error}", flush=True)
            reports.append(report)
            pending = [{**entry, "estado": "error", "error": "Ruta aún no consultada."}
                       for entry in selectors[len(reports):]]
            confirmed = merge_rows(rows)
            locate_and_catalogue(confirmed, province)
            publish(target, province, source, confirmed, reports + pending)
            print(f"{province}: {len(reports)}/{len(selectors)} rutas consultadas.", flush=True)
        confirmed = merge_rows(rows)
        for row in confirmed:
            try:
                path = cache / f"ficha-{row['cofm_id']}.html"
                if offline or path.exists():
                    detail = path.read_text()
                else:
                    detail = fetch(BASE + "/datosNew.asp?id=" + row["cofm_id"])
                    path.write_text(detail)
                    time.sleep(1.1)
                enrich_contact(row, detail)
            except (OSError, ValueError, KeyError, TypeError) as error:
                reports.append({"nombre": row["id"], "estado": "error", "error": str(error)})
                print(f"ERROR {province} ficha {row['id']}: {error}", flush=True)
        locate_and_catalogue(confirmed, province, use_geocoder=geocode, allow_address=allow_address)
        publish(target, province, source, confirmed, reports + pending)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR {province}: {error}", flush=True)
        publish(target, province, source, merge_rows(rows),
                reports + [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
    return False


def main(province_id, province):
    parser = argparse.ArgumentParser(description=f"Calendarios CGCOF de {province}.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / f".local/state/farmacia/{slugify(province)}")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    parser.add_argument("--limite", type=int)
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    if args.limite is not None and args.limite < 1:
        parser.error("--limite debe ser positivo.")
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red,
                    args.reanudar, args.geocode, args.limite, args.permitir_direccion_exacta,
                    province_id, province) else 1
