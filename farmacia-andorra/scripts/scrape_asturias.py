#!/usr/bin/env python3
"""Import the dated official duty listing of every municipality in Asturias (COF Asturias)."""
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from localizacion_cartociudad import LOCATION_FIELDS, locate
from merge_espana import coordinates
from provincial_catalog import publish
from proximidad import Geocoder
from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://www.farmasturias.org/GESCOF/cms/Guardias/FarmaciaBuscar.asp?IdMenu=111"
ENDPOINT = SOURCE + "&intPagina=1"
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
SHIFT = re.compile(r'<h5 class="HorarioGuardias">\s*<a name=[\'"]([^\'"]+)[\'"]>(.*?)</a>\s*</h5>', re.S)
CARD = re.compile(r'<h6 class="LocalidadGuardias">(.*?)</h6>\s*<ul class="ListadoResultados">(.*?)</ul>', re.S)
RANGE = re.compile(r"(\d\d):(\d\d) - (\d\d):(\d\d)")
NAMES = {"S.M.R.A.": "San Martín del Rey Aurelio"}
SMALL = {"de", "del", "la", "las", "los", "el", "y"}


def fetch(target, code=""):
    """Official listing for one date; an empty municipality code returns the whole province."""
    params = {"busqueda": "1", "Fecha": target.strftime("%d/%m/%Y"),
              "txtMunicipio": code, "txtLocalidad": ""}
    request = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode(params).encode(),
                                     headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8")


def text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def place_name(value):
    words = NAMES.get(value, value).lower().split()
    return " ".join(word if i and word in SMALL else word[:1].upper() + word[1:] for i, word in enumerate(words))


def span(hours, day):
    """Official «HH:MM - HH:MM» range; an end not after the start finishes the next day."""
    match = RANGE.fullmatch(hours)
    if not match:
        raise ValueError(f"Horario oficial no reconocido: {hours!r}.")
    h1, m1, h2, m2 = map(int, match.groups())
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
        raise ValueError(f"Horario oficial inválido: {hours!r}.")
    begin = datetime.combine(day, time(h1, m1))
    finish = datetime.combine(day, time(h2, m2))
    return begin, finish if finish > begin else finish + timedelta(days=1)


def kind(begin, finish):
    if finish - begin >= timedelta(hours=24):
        return "24 horas"
    base = datetime.combine(begin.date(), time.min)
    return "nocturna" if begin < base + timedelta(hours=6) or finish > base + timedelta(hours=22) else "diurna"


def parse_page(content, day):
    """Every duty shift published for «day», as flat entries with their original span."""
    header = re.search(r'<h3 class="FechaGuardias">\s*<span>(.*?)</span>', content, re.S)
    if not header:
        raise ValueError("No aparece la fecha oficial.")
    if f"{day.day:02} de {MONTHS[day.month - 1]} de {day.year}" not in text(header[1]).lower():
        raise ValueError("La fecha oficial no coincide con la solicitada.")
    parts = re.split(r'<h4\s+class="MunicipioGuardias">(.*?)</h4>', content, flags=re.S)
    if len(parts) < 3 or "TituloResultado" in parts[0]:
        raise ValueError("La respuesta no contiene municipios reconocibles.")
    entries = []
    for name, body in zip(parts[1::2], parts[2::2]):
        municipio = place_name(text(name))
        shifts = list(SHIFT.finditer(body))
        if not shifts or "TituloResultado" in body[:shifts[0].start()]:
            raise ValueError(f"{municipio}: no se reconocen turnos oficiales.")
        for i, shift in enumerate(shifts):
            begin, finish = span(text(shift[1]), day)
            label = text(shift[2])
            segment = body[shift.end():shifts[i + 1].start() if i + 1 < len(shifts) else len(body)]
            cards = CARD.findall(segment)
            if not cards or len(cards) != segment.count('class="TituloResultado"') or not label:
                raise ValueError(f"{municipio}: la sección contiene farmacias no reconocidas.")
            for town, card in cards:
                fields = {}
                for field in ("TituloResultado", "ico-localizacion", "ico-telefono"):
                    match = re.search(r'<span class="' + field + r'">(.*?)</span>', card, re.S)
                    if not match:
                        raise ValueError(f"{municipio}: ficha sin {field}.")
                    fields[field] = text(match[1])
                address = re.sub(r"-\s*\d{5}$", "", fields["ico-localizacion"].removeprefix("Dirección:").strip())
                phone = re.sub(r"\D", "", fields["ico-telefono"])
                ident = re.search(r"VerMapa\(.*?,\s*'(\d+)'\s*,\s*'(\d+)'\s*\)", card, re.S)
                town = text(town)
                if not address or len(phone) != 9 or not ident or not fields["TituloResultado"] or not town:
                    raise ValueError(f"{municipio}: ficha sin identificación, dirección o teléfono válidos.")
                entries.append({"id": ident[2], "nombre": fields["TituloResultado"], "direccion": address,
                                "telefono": phone, "municipio": municipio,
                                "localidad": municipio if slugify(town) == slugify(municipio) else place_name(town),
                                "inicio": begin, "fin": finish, "turno": label})
    if not entries:
        raise ValueError("No hay guardias confirmadas en la respuesta.")
    return entries


def build_rows(entries, previous, target):
    """Rows for «target»; the night shift started the day before covers the early morning,
    unless the municipality already publishes its own early-morning shift for «target»."""
    day_start = datetime.combine(target, time.min)
    day_end = day_start + timedelta(days=1)
    own_dawn = {e["municipio"] for e in entries if e["inicio"] == day_start and e["fin"] < day_end}
    pieces = [(e, max(e["inicio"], day_start), min(e["fin"], day_end), False) for e in entries]
    pieces += [(e, day_start, min(e["fin"], day_end), True) for e in previous
               if e["fin"] > day_start and e["municipio"] not in own_dawn]
    rows = {}
    for entry, begin, finish, carried in pieces:
        if finish <= begin:
            continue
        row = rows.get(entry["id"])
        if row is None:
            row = rows[entry["id"]] = {
                "id": f"cof-asturias-{entry['id']}", "cofm_id": None, "nombre": entry["nombre"],
                "direccion": entry["direccion"], "localidad": entry["localidad"], "municipio": entry["municipio"],
                "provincia": "Asturias", "telefono": entry["telefono"], "guardia": True,
                "fecha_guardia": target.isoformat(), "fuente": SOURCE,
                "localidades_atendidas": list(dict.fromkeys([entry["localidad"], entry["municipio"]])),
                "lat": None, "lng": None, "guardia_intervalos": [], "guardia_franjas": []}
        elif any(row[key] != entry[key] for key in ("direccion", "telefono", "municipio")):
            raise ValueError("Datos contradictorios para una misma farmacia.")
        interval = {"inicio": begin.isoformat(), "fin": finish.isoformat(), "tipo": kind(entry["inicio"], entry["fin"])}
        if interval in row["guardia_intervalos"]:
            continue
        label = (f"Continúa el turno del {entry['inicio']:%d/%m} ({entry['turno']})" if carried else entry["turno"])
        if "no presencial" in entry["turno"].lower():
            label += "; llamar antes de acudir"
        row["guardia_intervalos"].append(interval)
        row["guardia_franjas"].append(f"{label}: {interval['inicio']}–{interval['fin']}")
    for row in rows.values():
        order = sorted(range(len(row["guardia_intervalos"])), key=lambda i: row["guardia_intervalos"][i]["inicio"])
        row["guardia_intervalos"] = [row["guardia_intervalos"][i] for i in order]
        row["guardia_franjas"] = [row["guardia_franjas"][i] for i in order]
        row["guardia_franja"] = " · ".join(row["guardia_franjas"])
    return list(rows.values())


def run(target, cache, output=OUT_DIR, geocode=False):
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    content = fetch(target)
    (cache / f"{target}-todos.html").write_text(content, encoding="utf-8")
    entries = parse_page(content, target)
    reports = []
    previous_day = target - timedelta(days=1)
    try:
        content = fetch(previous_day)
        (cache / f"{previous_day}-todos.html").write_text(content, encoding="utf-8")
        previous = parse_page(content, previous_day)
    except (OSError, ValueError, UnicodeError) as error:
        previous = []
        reports.append({"nombre": "Madrugada (turnos iniciados el día anterior)", "estado": "error",
                        "farmacias": 0, "error": str(error)})
        print(f"ERROR Asturias madrugada: {error}", flush=True)
    rows = build_rows(entries, previous, target)
    for municipio in sorted({row["municipio"] for row in rows}):
        reports.append({"nombre": municipio, "estado": "disponible",
                        "farmacias": sum(row["municipio"] == municipio for row in rows)})
    path = output / "farmacias-asturias.json"
    saved = {item["id"]: item for item in json.loads(path.read_text())} if path.exists() else {}
    for row in rows:
        previous_row = saved.get(row["id"])
        if (previous_row and previous_row.get("direccion") == row["direccion"]
                and previous_row.get("localidad") == row["localidad"] and coordinates(previous_row)):
            row.update({field: previous_row[field] for field in LOCATION_FIELDS if field in previous_row})
    if geocode and rows:
        known = json.loads((output / "farmacias-espana-hoy.json").read_text())
        geocoder = Geocoder(cache=cache / "posiciones.json", ttl_days=365)
        # CartoCiudad identifica el municipio, no el núcleo (Lugones, El Berrón…).
        proxies = [{**row, "localidad": row["municipio"]} for row in rows]
        locate(proxies, known, geocoder, "Asturias")
        for row, proxy in zip(rows, proxies):
            if coordinates(proxy) and not coordinates(row):
                row.update({field: proxy[field] for field in LOCATION_FIELDS if field in proxy})
        if geocoder.errors:
            reports.append({"nombre": "CartoCiudad", "estado": "error",
                            "error": "No se pudieron contrastar todas las ubicaciones."})
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(path, list(saved.values()))
    print(f"Asturias: {len(rows)} farmacias de guardia en {len({r['municipio'] for r in rows})} municipios.", flush=True)
    return publish(target, "Asturias", SOURCE, rows, reports, output=output, authoritative_sources={SOURCE})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/asturias")
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    parser.add_argument("--geocode", action="store_true")
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.cache_documentos, args.salida, args.geocode) else 1
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
        print(f"ERROR Asturias: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
