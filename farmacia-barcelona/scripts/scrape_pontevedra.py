#!/usr/bin/env python3
"""Import the COF Pontevedra monthly city listings without guessing hours."""
import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from localizacion_cartociudad import LOCATION_FIELDS, locate as locate_cartociudad
from provincial_catalog import merge_rows, publish
from proximidad import Geocoder
from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://farmacias.cofpo.org/public/guardias_listado_prensa.php"
ENDPOINT = "https://farmacias.cofpo.org/public/guardias_listado_prensa_ajax.php"
INDEX = "https://farmacias.cofpo.org/public/guardias_listado.php"
CITIES = {"Vigo", "Pontevedra"}
MONTHS = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
          "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")


def fetch(url, params=None):
    data = urllib.parse.urlencode(params).encode() if params is not None else None
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8")


def text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def selectors(content):
    match = re.search(r'<select\b[^>]*id="municipio"[^>]*>(.*?)</select>', content, re.S)
    if not match:
        raise ValueError("No se encuentra el selector oficial de municipios.")
    result = [(code, text(name)) for code, name in
              re.findall(r'<option\s+value="(\d+)"[^>]*>(.*?)</option>', match[1], re.S)]
    if not result or len({code for code, _ in result}) != len(result):
        raise ValueError("Selector municipal vacío o duplicado.")
    if not CITIES.issubset({name for _, name in result}):
        raise ValueError("El selector oficial no contiene las dos ciudades previstas.")
    return result


def parse(content, town, target):
    expected = f"{MONTHS[target.month - 1]} de {target.year}"
    if f">{expected}</span>" not in content or f">{html.escape(town)}</span>" not in content:
        raise ValueError("La respuesta no confirma el municipio y mes solicitados.")
    sections = re.findall(
        r"<div[^>]*class=['\"]titulo_tipo_horario['\"][^>]*>\s*"
        r"<span[^>]*>(.*?)</span>\s*</div>\s*<table\b[^>]*>(.*?)</table>",
        content, re.S,
    )
    if {text(name) for name, _ in sections} != {"Diurno", "Nocturno"} or len(sections) != 2:
        raise ValueError("No se reconocen ambos turnos oficiales.")
    rows = []
    for label, table in sections:
        shift = text(label)
        days = re.findall(r'<tr>\s*<td class="center">(\d+)</td>\s*<td>(.*?)</td>\s*</tr>', table, re.S)
        matches = [body for day, body in days if int(day) == target.day]
        if len(matches) != 1:
            raise ValueError(f"No hay una fila única para el día {target.day} ({shift}).")
        cards = re.findall(
            r'<div[^>]*class="ficha_farmacia"[^>]*>\s*<strong>(.*?)</strong>\s*'
            r'<ul[^>]*>\s*<li>(.*?)</li>\s*<li>(.*?)</li>\s*</ul>\s*</div>',
            matches[0], re.S,
        )
        if not cards or len(cards) != matches[0].count('class="ficha_farmacia"'):
            raise ValueError(f"Fichas incompletas o no reconocidas ({shift}).")
        for name, address, phone in cards:
            name, address, phone = text(name), text(address), re.sub(r"\D", "", text(phone))
            if not name or not address or len(phone) != 9:
                raise ValueError(f"Ficha sin nombre, dirección o teléfono válido ({shift}).")
            key = "|".join((slugify(town), slugify(address), phone))
            ident = hashlib.sha256(key.encode()).hexdigest()[:16]
            row = {
                "id": f"cof-pontevedra-{ident}", "cofm_id": None, "nombre": name,
                "direccion": address, "localidad": town, "provincia": "Pontevedra",
                "telefono": phone, "guardia": True, "fecha_guardia": target.isoformat(),
                "fuente": SOURCE, "localidades_atendidas": [town], "lat": None, "lng": None,
                "guardia_franjas": [f"{shift} según listado del Colegio; horario exacto no indicado, confirmar por teléfono."],
            }
            rows.append(row)
    return merge_rows(rows)


def locate(rows, known, geocoder):
    locate_cartociudad(rows, known, geocoder, "Pontevedra")


def run(target, cache, output=OUT_DIR, geocode=False):
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    source = fetch(INDEX)
    places = selectors(source)
    reports, rows = [], []
    for code, town in places:
        if town not in CITIES:
            reports.append({"nombre": town, "codigo": code, "estado": "pendiente",
                            "farmacias": 0, "error": "Municipio aún no consultado."})
            continue
        try:
            content = fetch(ENDPOINT, {"search_municipio": code, "municipio_nombre": town,
                                       "search_ano": target.year, "search_mes": target.month})
            (cache / f"{target.year}-{target.month:02}-{code}.html").write_text(content, encoding="utf-8")
            found = parse(content, town, target)
            rows.extend(found)
            reports.append({"nombre": town, "codigo": code, "estado": "parcial", "farmacias": len(found),
                            "error": "Horario exacto y posible madrugada anterior pendientes de confirmar."})
            print(f"{town}: {len(found)} farmacias del listado oficial.", flush=True)
        except (OSError, ValueError, UnicodeError) as error:
            reports.append({"nombre": town, "codigo": code, "estado": "error", "farmacias": 0,
                            "error": str(error)})
            print(f"ERROR {town}: {error}", flush=True)
        time.sleep(1.1)
    catalog_path = output / "farmacias-pontevedra.json"
    saved = {item["id"]: item for item in json.loads(catalog_path.read_text())} if catalog_path.exists() else {}
    for row in rows:
        previous = saved.get(row["id"])
        if (previous and previous.get("direccion") == row["direccion"]
                and previous.get("localidad") == row["localidad"] and coordinates(previous)):
            row.update({field: previous[field] for field in LOCATION_FIELDS if field in previous})
    if geocode and rows:
        known = json.loads((output / "farmacias-espana-hoy.json").read_text())
        geocoder = Geocoder(cache=cache / "posiciones.json", ttl_days=365)
        locate(rows, known, geocoder)
        if geocoder.errors:
            reports.append({"nombre": "CartoCiudad", "estado": "error",
                            "error": "No se pudieron contrastar todas las ubicaciones."})
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(catalog_path, list(saved.values()))
    return publish(target, "Pontevedra", SOURCE, rows, reports, output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/pontevedra")
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    parser.add_argument("--geocode", action="store_true", help="Contrastar teléfonos y portales a 15 m.")
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.cache_documentos, args.salida, args.geocode) else 1
    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR Pontevedra: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
