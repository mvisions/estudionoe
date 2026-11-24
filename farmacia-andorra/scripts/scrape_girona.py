#!/usr/bin/env python3
"""Import the dated public duty table of the College of Girona."""
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates, identity_keys
from provincial_catalog import publish
from proximidad import PharmacyIndex
from scrape_mes import OUT_DIR, write_json

SOURCE = "https://www.cofgi.org/farmacies/farmacies-de-guardia"
DETAIL = "https://www.cofgi.org/farmacies/detall-guardia/"
RANGE = re.compile(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})(\s*\(dia seg\.\))?")
MARKER = re.compile(r"position:\s*new google\.maps\.LatLng\(\s*['\"](-?\d+\.\d+)['\"]\s*,\s*['\"](-?\d+\.\d+)['\"]\s*\)")


class DutyPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.in_title = False
        self.row = None
        self.cell = None
        self.rows = []

    def finish_cell(self):
        if self.cell is not None:
            self.row["cells"].append(" ".join("".join(self.cell).split()))
            self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div" and "pharmacies-of-guard-title" in classes:
            self.in_title = True
        elif tag == "tr" and "pharmacy-detail" in classes:
            if self.row is not None:
                raise ValueError("Filas de guardia anidadas.")
            self.row = {"href": attrs.get("href", ""), "cells": [], "located": False}
        elif tag == "td" and self.row is not None:
            self.finish_cell()
            self.cell = []
        elif tag == "img" and self.cell is not None:
            alt = attrs.get("alt", "")
            if "no presencial" not in alt.lower():
                raise ValueError("Indicador de guardia desconocido.")
            self.row["located"] = True

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self.in_title:
            self.in_title = False
        elif tag == "td" and self.cell is not None:
            self.finish_cell()
        elif tag == "tr" and self.row is not None:
            self.finish_cell()
            self.rows.append(self.row)
            self.row = None


def parse(html, target):
    page = DutyPage()
    page.feed(html)
    title = " ".join("".join(page.title).split())
    if title != f"TOTES LES FARMÀCIES DE GUÀRDIA DEL DIA {target:%d/%m/%Y}":
        raise ValueError(f"La página no confirma la fecha y el ámbito provincial: {title!r}")
    if page.row is not None or not page.rows:
        raise ValueError("Tabla de guardias incompleta o vacía.")
    rows = []
    seen = set()
    for item in page.rows:
        match = re.fullmatch(r"/farmacies/detall-guardia/(\d+)", item["href"])
        if not match or len(item["cells"]) != 7:
            raise ValueError("Ficha de guardia con formato inesperado.")
        ident = match.group(1)
        name, town, schedule, _, address, phone, _ = item["cells"]
        if ident in seen or not all((name, town, schedule, address, phone)):
            raise ValueError(f"Ficha duplicada o incompleta: {ident}.")
        seen.add(ident)
        parts = list(RANGE.finditer(schedule))
        if not parts or RANGE.sub("", schedule).strip():
            raise ValueError(f"Horario desconocido en {ident}: {schedule!r}")
        franjas = []
        for part in parts:
            start, end, next_day = part.groups()
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
            if (end <= start) != bool(next_day):
                raise ValueError(f"Cruce de día ambiguo en {ident}: {part.group()!r}")
            text = f"{start} - {end}" + (" (día siguiente)" if next_day else "")
            if item["located"]:
                text += "; guardia no presencial, llamar antes"
            franjas.append(text)
        rows.append({
            "id": f"cof-girona-{ident}", "nombre": name, "direccion": address,
            "localidad": town, "provincia": "Girona", "telefono": phone,
            "lat": None, "lng": None, "ubicacion_pendiente_verificacion": True,
            "guardia": True, "guardia_franja": " · ".join(franjas),
            "guardia_franjas": franjas, "fecha_guardia": target.isoformat(),
            "localidades_atendidas": [town], "fuente": SOURCE,
            "fuentes": [SOURCE, DETAIL + ident],
        })
    return rows


def request(url, data=None):
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def locate(row, html, index):
    ident = row["id"].removeprefix("cof-girona-")
    marker = MARKER.search(html)
    if not marker or not re.search(r"\bid:\s*" + re.escape(ident) + r"\s*[,}]", html):
        raise ValueError("Ficha sin marcador correspondiente a la farmacia.")
    lat, lng = map(float, marker.groups())
    if not (41.3 < lat < 43.0 and 1.5 < lng < 3.5):
        raise ValueError("Marcador fuera del ámbito de Girona.")
    keys = set(identity_keys(row))
    matches = [(distance, ref) for distance, ref in index.near((lat, lng))
               if keys.intersection(identity_keys(ref))]
    if len(matches) != 1:
        return
    distance, ref = matches[0]
    row.update(lat=lat, lng=lng, ubicacion_pendiente_verificacion=False,
               precision_ubicacion="farmacia", fuente_coordenadas=DETAIL + ident,
               ajuste_ubicacion_m=round(distance, 1),
               referencia_ubicacion=f"https://www.openstreetmap.org/node/{ref['id'].removeprefix('osm-')}",
               nota_ubicacion=f"Marcador del Colegio contrastado con farmacia OSM a {distance:.1f} m.")


def run(target, output=OUT_DIR):
    data = urllib.parse.urlencode({"city-group": 0, "city": 0, "date": target.isoformat()}).encode()
    rows = parse(request(SOURCE, data), target)
    national = json.loads((output / "farmacias-espana-hoy.json").read_text())
    index = PharmacyIndex(row for row in national
                          if row.get("provincia") == "Girona"
                          and re.fullmatch(r"osm-\d+", str(row.get("id", ""))))
    for row in rows:
        try:
            locate(row, request(DETAIL + row["id"].removeprefix("cof-girona-")), index)
        except (OSError, ValueError, UnicodeError) as error:
            print(f"AVISO Girona {row['id']}: no se pudo contrastar la ubicación: {error}", flush=True)
        if not coordinates(row):
            print(f"AVISO Girona {row['id']}: ubicación pendiente; no se dibuja marcador.", flush=True)
        time.sleep(0.2)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "farmacias-girona.json"
    saved = {row["id"]: row for row in json.loads(path.read_text())} if path.exists() else {}
    for row in rows:
        saved[row["id"]] = {**row, "guardia": False}
    write_json(path, list(saved.values()))
    reports = [{"nombre": "Provincia de Girona", "estado": "parcial", "farmacias": len(rows),
                "error": "La tabla no acredita cobertura de todos los municipios; confirmar por teléfono."}]
    return publish(target, "Girona", SOURCE, rows, reports, output=output,
                   authoritative_sources={SOURCE})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Madrid")).date())
    parser.add_argument("--salida", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    try:
        return 0 if run(args.fecha, args.salida) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Girona: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
