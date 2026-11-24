#!/usr/bin/env python3
"""Publish daily schedules, preserving zone/population routes and source coverage."""
import argparse
import calendar
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://farmaciasguardia.farmaceuticos.com/web_guardias"
OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "data"


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def normalize_locality(locality):
    aliases = {
        "arroyo-de-la-miel": "Benalmádena",
        "cartama-estacion": "Cártama",
        "torre-del-mar": "Vélez-Málaga",
        "torrox-torrox-costa": "Torrox",
        "torre-de-benagalbon": "Rincón de la Victoria",
        "benagalbon": "Rincón de la Victoria",
        "la-cala-del-moral": "Rincón de la Victoria",
        "chilches": "Vélez-Málaga",
    }
    return aliases.get(slugify(locality), locality)


def pharmacy_sector(address, locality, sector=""):
    if slugify(locality) == "rincon-de-la-victoria" and re.search(
        r"\b(?:T\.\s*|TORRE\s+DE\s+)BENAGALB[OÓ]N\b", address, re.IGNORECASE
    ):
        return "Torre de Benagalbón"
    return sector


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "farmacia-guardia-mvp/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
        charset = response.headers.get_content_charset()
    if charset:
        return content.decode(charset)
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252")


def parse_selectors(content, province_id):
    selectors = []
    seen = set()
    for parameter, body in re.findall(
        r'<select[^>]*name=["\']?(vzona|vpoblacion)["\']?[^>]*>(.*?)</select>',
        content, re.IGNORECASE | re.DOTALL
    ):
        for code, name in re.findall(
            r'<option[^>]*value=["\']?(\d+)["\']?[^>]*>(.*?)</option>',
            body, re.IGNORECASE | re.DOTALL
        ):
            key = (parameter.lower(), code)
            if not code.startswith(province_id) or key in seen:
                continue
            seen.add(key)
            selectors.append({
                "parametro": parameter.lower(),
                "codigo": code,
                "nombre": html.unescape(re.sub(r"<[^>]+>", "", name)).strip(),
            })
    if not selectors:
        raise ValueError("La fuente no contiene selectores de zonas ni poblaciones.")
    return selectors


def parse_schedule(content, selector, province_id, province_name, date):
    content = html.unescape(content)
    if re.search(r"Datos\s+no\s+disponibles", content, re.IGNORECASE):
        return None
    displayed_dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", content)
    if displayed_dates and datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y") not in displayed_dates:
        raise ValueError("La fecha impresa del calendario no coincide con la solicitada.")
    headings = list(re.finditer(
        r"GUARDIAS\s+(?:DE\s+)?(TODO EL D[IÍ]A|D[IÍ]A|NOCHE)", content, re.IGNORECASE
    ))
    matches = list(re.finditer(
        r'abbre\(\d+,\s*(\d+),\s*0\)\s*>\s*(.*?)</a>',
        content, re.IGNORECASE | re.DOTALL
    ))
    if not headings and not matches:
        raise ValueError("Respuesta sin calendario reconocible.")
    pharmacies = []
    for match in matches:
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        combined_suffix = re.search(r"\s+-\s+(Torrox\s+-\s+Torrox Costa)\s*$", text, re.IGNORECASE)
        if combined_suffix:
            address, separator, locality = text[:combined_suffix.start()], " - ", combined_suffix.group(1)
        else:
            address, separator, locality = text.rpartition(" - ")
        if not separator:
            address, locality = text, selector["nombre"]
        section = next(
            (item.group(1).upper() for item in reversed(headings) if item.start() < match.start()),
            "",
        )
        periods = {
            "NOCHE": "noche (22:00-9:30)",
            "DÍA": "dia (9:30-22:00)",
            "DIA": "dia (9:30-22:00)",
            "TODO EL DÍA": "todo el dia (9:30-9:30)",
            "TODO EL DIA": "todo el dia (9:30-9:30)",
        }
        area = locality.strip()
        city = "Málaga" if (
            slugify(selector["nombre"]) == "malaga-capital" or area.upper().startswith("SECTOR ")
            or area.upper().startswith("BARRIADA CHURRIANA")
        ) else area
        city = normalize_locality(city)
        pharmacies.append({
            "id": f"{province_id}-{match.group(1)}",
            "cofm_id": match.group(1),
            "direccion": address.strip(),
            "localidad": city,
            "sector": pharmacy_sector(address, city, area if city != area else ""),
            "zona": selector["nombre"],
            "provincia": province_name,
            "guardia": True,
            "guardia_franja": periods.get(section, "desconocida"),
            "fecha_guardia": date,
            "fuente": BASE,
            "lat": None,
            "lng": None,
        })
    return pharmacies


def merge_schedule(pharmacies):
    unique = {}
    for pharmacy in pharmacies:
        key = pharmacy["id"]
        if key not in unique:
            unique[key] = {**pharmacy, "guardia_franjas": [pharmacy["guardia_franja"]]}
        else:
            periods = unique[key]["guardia_franjas"]
            if pharmacy["guardia_franja"] not in periods:
                periods.append(pharmacy["guardia_franja"])
        unique[key]["guardia_franja"] = " · ".join(unique[key]["guardia_franjas"])
    return list(unique.values())


def write_json(path, data):
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")
    os.replace(temporary, path)


def load_coordinates(province):
    coordinates = {}
    for filename in ["farmacias-espana-hoy.json", f"farmacias-{province}.json"]:
        path = OUT_DIR / filename
        if path.exists():
            for pharmacy in json.loads(path.read_text(encoding="utf-8")):
                if pharmacy.get("cofm_id") and pharmacy.get("lat") is not None and pharmacy.get("lng") is not None:
                    coordinates[str(pharmacy["cofm_id"])] = (pharmacy["lat"], pharmacy["lng"])
    if province == "malaga":
        path = OUT_DIR / "coordenadas-malaga-capital.json"
        if path.exists():
            for pharmacy_id, position in json.loads(path.read_text(encoding="utf-8")).items():
                coordinates[pharmacy_id] = (position["lat"], position["lng"])
    return coordinates


def scrape_day(selectors, province_id, province_name, date, coordinates):
    pharmacies = []
    coverage = []
    requested = datetime.strptime(date, "%Y-%m-%d")
    source_date = f"{requested.day}/{requested.month}/{requested.year}"
    for index, selector in enumerate(selectors, 1):
        url = f"{BASE}/GuardiasNew.asp?" + urllib.parse.urlencode({
            "date": source_date,
            selector["parametro"]: selector["codigo"],
            "vmenu": 1,
            "provincia": province_id,
        })
        try:
            rows = parse_schedule(fetch(url), selector, province_id, province_name, date)
            state = "sin_datos" if rows is None else "disponible"
            coverage.append({**selector, "estado": state, "farmacias": len(rows or []), "url": url})
            pharmacies.extend(rows or [])
            print(f"[{index}/{len(selectors)}] {selector['parametro']} {selector['nombre']}: {state}, {len(rows or [])}", flush=True)
        except (OSError, ValueError) as error:
            coverage.append({**selector, "estado": "error", "error": str(error), "url": url})
            print(f"ERROR {selector['nombre']}: {error}", flush=True)
        time.sleep(0.2)
    result = merge_schedule(pharmacies)
    for pharmacy in result:
        pharmacy["lat"], pharmacy["lng"] = coordinates.get(pharmacy["cofm_id"], (None, None))
    return result, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provincia_id")
    parser.add_argument("nombre")
    parser.add_argument("mes", type=int)
    parser.add_argument("anio", type=int)
    parser.add_argument("--dia", type=int, help="Consultar solo este día en vez del mes completo.")
    args = parser.parse_args()
    total_days = calendar.monthrange(args.anio, args.mes)[1]
    if args.dia is not None and not 1 <= args.dia <= total_days:
        parser.error("El día no pertenece al mes indicado.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    province = slugify(args.nombre)
    selectors = parse_selectors(fetch(f"{BASE}/publico/Provincia_pNew.asp?id={args.provincia_id}"), args.provincia_id)
    coordinates = load_coordinates(province)
    failed = False
    for day in [args.dia] if args.dia else range(1, total_days + 1):
        date = f"{args.anio:04d}-{args.mes:02d}-{day:02d}"
        rows, coverage = scrape_day(selectors, args.provincia_id, args.nombre, date, coordinates)
        errors = any(item["estado"] == "error" for item in coverage)
        available = any(item["estado"] == "disponible" for item in coverage)
        report = {
            "fecha": date,
            "provincia": args.nombre,
            "fuente": BASE,
            "consultado": datetime.now(timezone.utc).isoformat(),
            "completa": all(item["estado"] == "disponible" for item in coverage),
            "consultas": coverage,
        }
        write_json(OUT_DIR / f"cobertura-{province}-{date}.json", report)
        if available and not errors:
            write_json(OUT_DIR / f"guardias-{province}-{date}.json", rows)
            print(f"{date}: publicadas {len(rows)} farmacias.", flush=True)
        else:
            print(f"{date}: no se reemplaza el calendario; fuente no disponible o consultas fallidas.", flush=True)
        failed = failed or errors or not available
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
