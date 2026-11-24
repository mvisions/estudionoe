#!/usr/bin/env python3
"""Import the Valladolid College's public, explicitly dated duty grids."""
import argparse
import html
import json
import re
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import OUT_DIR, write_json
from scrape_sevilla import clean, saved_address_signature

HOST = "https://ciudadanos.farmaceuticosdevalladolid.es/"
SOURCE = HOST + "FarmaciasGuardia.aspx"
CATALOG = HOST + "FarmaciasProvincia.aspx"
TZ = ZoneInfo("Europe/Madrid")


def fetch(url):
    time.sleep(1.1)
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8")


def text(value):
    return clean(html.unescape(re.sub(r"<[^>]*>", " ", value)))


def grid_rows(content, grid):
    pattern = r'<tr id="' + re.escape(grid) + r'_DXDataRow\d+"[^>]*>(.*?)</tr>'
    rows = re.findall(pattern, content, re.S)
    if not rows:
        raise ValueError(f"Cuadrícula oficial vacía/no reconocible: {grid}.")
    return [(row, [text(cell) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)])
            for row in rows]


def markers(content):
    section = re.search(r"var markers\s*=\s*\[(.*?)\];", content, re.S)
    if not section:
        raise ValueError("Mapa oficial sin lista de posiciones reconocible.")
    points = []
    for entry in re.findall(r"\{([^{}]*)\}", section[1]):
        fields = {}
        for name in ("lat", "lng", "description"):
            field = re.search(r'"' + name + r'":\s*\'(.*?)\'\s*,?\s*$', entry, re.M)
            if not field:
                raise ValueError(f"Posición oficial sin campo {name}.")
            fields[name] = field[1]
        parts = re.split(r"<br\s*/?>", html.unescape(fields["description"]), flags=re.I)
        if len(parts) < 3:
            print("AVISO Valladolid: posición oficial sin identidad/dirección; se omite.", flush=True)
            continue
        address, separator, city = text(parts[1]).rpartition(",")
        try:
            a, b = float(fields["lat"]), float(fields["lng"])
        except ValueError:
            print("AVISO Valladolid: posición oficial no numérica; no se dibuja.", flush=True)
            continue
        if not separator or not 40.8 < a < 42.4 or not -5.7 < b < -3.8:
            print("AVISO Valladolid: posición oficial inválida; no se dibuja.", flush=True)
            continue
        phone = re.search(r"\b(?:\+34\s*)?(\d{9})\b", text(parts[2]))
        points.append({"direccion": address.strip(), "localidad": city.strip(),
                       "lat": a, "lng": b, "telefono": phone[1] if phone else None,
                       "precision_ubicacion": "farmacia", "fuente_coordenadas": SOURCE})
    return points


def apply_positions(rows, points):
    for row in rows:
        key = saved_address_signature(row["direccion"], row["localidad"])
        matches = [p for p in points if key and
                   saved_address_signature(p["direccion"], p["localidad"]) == key]
        positions = {(p["lat"], p["lng"]) for p in matches}
        if len(positions) == 1:
            point = matches[0]
            row.update({k: point[k] for k in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas")})
            if not row.get("telefono"):
                row["telefono"] = point["telefono"]


def parse_catalogue(content):
    result = []
    for raw, cells in grid_rows(content, "GridFarmacias"):
        identifier = re.search(r"FarmaciaFicha\.aspx\?Id=(\d+)", raw)
        if len(cells) != 7 or not identifier or not cells[1]:
            raise ValueError("Ficha del catálogo sin identidad/dirección/municipio.")
        if not cells[4]:
            print(f"AVISO Valladolid catálogo {identifier[1]}: sin dirección oficial; "
                  "no se inventa una farmacia.", flush=True)
            continue
        address = re.sub(r"\s+\d{5}$", "", cells[4])
        result.append({"id": f"cof-valladolid-catalogo-{identifier[1]}", "nombre": cells[3],
                       "localidad": cells[1], "sector": cells[2], "direccion": address,
                       "telefono": re.sub(r"\D", "", cells[5]) or None, "provincia": "Valladolid",
                       "guardia": False, "lat": None, "lng": None, "fuente": CATALOG})
    apply_positions(result, markers(content))
    return result


def parse_schedule(content, target):
    dates = re.findall(r"Fecha:\s*(\d{2}/\d{2}/\d{4})", text(content))
    if len(dates) != 3 or any(day != target.strftime("%d/%m/%Y") for day in dates):
        raise ValueError("Los tres cuadros no confirman la fecha solicitada.")
    result = []
    for grid, label in (("PageContent_GridFarmacias", "Diurna capital: laborables 09:30–22:00; "
                        "sábados, domingos y festivos 10:00–22:00"),
                        ("PageContent_GridFarmaciasDiurnas", "Nocturna capital: 22:00–09:30; "
                         "sábados, domingos y festivos hasta 10:00 del día siguiente"),
                        ("PageContent_GridFarmaciasProvincia", "")):
        for raw, cells in grid_rows(content, grid):
            link = re.search(r"FarmaciaFichaGuardia\.aspx\?Id=(\d+)&(?:amp;)?Base=(\d+)", raw)
            provincial = grid.endswith("Provincia")
            if not link or len(cells) != (6 if provincial else 3):
                raise ValueError("Fila de guardia sin identidad/celdas reconocibles.")
            city, address = (cells[0], cells[2]) if provincial else ("Valladolid", cells[0])
            sector = re.search(r"\s*\(Zona:\s*(.*?)\)$", address)
            address = re.sub(r"\s*\(Zona:.*?\)$", "", address)
            period = label
            if provincial:
                if "ico_sol_peq.png" in raw:
                    period = "Diurna provincial: hasta las 22:00; confirmar hora de inicio."
                elif "sol_luna_peq.png" in raw:
                    period = "Día y noche: 24 horas según el cuadro provincial."
                else:
                    period = "Guardia provincial: horario pendiente de confirmar por teléfono."
                if "telephone-call.png" in raw:
                    period += " Guardia localizada/no presencial; llamar antes de acudir."
            phone = re.search(r'href="tel:(\d{9})"', raw)
            result.append({"id": f"cof-valladolid-guardia-{link[1]}", "nombre": "",
                           "direccion": address, "localidad": city, "sector": sector[1] if sector else "",
                           "provincia": "Valladolid", "telefono": phone[1] if phone else None,
                           "guardia": True, "fecha_guardia": str(target), "guardia_franjas": [period],
                           "localidades_atendidas": [city], "lat": None, "lng": None, "fuente": SOURCE})
    apply_positions(result, markers(content))
    return result


def run(target, cache, offline=False, geocode=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports, rows = [], []
    try:
        guard_path, catalog_path = cache / f"{target}.html", cache / "catalogo.html"
        guard = guard_path.read_text() if offline else fetch(SOURCE)
        rows = parse_schedule(guard, target)
        if not offline:
            guard_path.write_text(guard)
        catalog = catalog_path.read_text() if offline else fetch(CATALOG)
        points = parse_catalogue(catalog)
        if not offline:
            catalog_path.write_text(catalog)
        locate_and_catalogue(points, "Valladolid")
        locate_and_catalogue(rows, "Valladolid", use_geocoder=geocode, official_points=points)
        reports = [{"nombre": town, "estado": "parcial",
                    "farmacias": sum(r["localidad"] == town for r in rows),
                    "error": "Cuadros oficiales del día confirmados; madrugada anterior y cobertura "
                             "de todos los municipios no certificadas. El directorio puede contener "
                             "fichas sin dirección, que se omiten con aviso. No se infieren derivaciones."}
                   for town in sorted({row["localidad"] for row in rows})]
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Valladolid: {error}", flush=True)
        reports.append({"nombre": "Fuente provincial", "estado": "error", "error": str(error)})
    return publish(target, "Valladolid", SOURCE, rows, reports)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/valladolid")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red, args.geocode) else 1)
