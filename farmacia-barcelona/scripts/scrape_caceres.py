#!/usr/bin/env python3
"""Import Cáceres pharmacies returned as open now, without inferring duty hours."""
import argparse
from datetime import date, datetime
from html.parser import HTMLParser
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import slugify
from scrape_palencia import consolidate

SOURCE = "https://farmacias.cofcaceres.es/"
SEARCH = urllib.parse.urljoin(SOURCE, "buscar-farmacias-por-municipios")
TZ = ZoneInfo("Europe/Madrid")
OPEN_NOW_NOTE = (
    "COFCáceres marca esta farmacia «En Servicio de Urgencias» al consultar, pero no publica "
    "un calendario fechado ni su intervalo horario; se asigna al día actual."
)


class CaceresPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.token = ""
        self.municipalities = []
        self.selected_municipality = None
        self.in_municipality_select = False
        self.current_option = None
        self.results_seen = False
        self.current_card = None
        self.card_depth = 0
        self.active_field = None
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "input" and attrs.get("name") == "_token":
            self.token = attrs.get("value", "")
        elif tag == "a" and attrs.get("id") == "resultados":
            self.results_seen = True
        elif tag == "select":
            self.in_municipality_select = attrs.get("name") == "municipio_id"
        elif tag == "option" and self.in_municipality_select:
            self.current_option = {
                "value": attrs.get("value", ""),
                "text": [],
                "selected": "selected" in attrs,
            }

        if tag == "div" and self.current_card is None and "row-item-listado-farmacia" in classes:
            self.current_card = {"name": [], "status": [], "address": [], "phone": [], "map_url": ""}
            self.card_depth = 1
        elif tag == "div" and self.current_card is not None:
            self.card_depth += 1

        if self.current_card is not None:
            if tag == "strong":
                self.active_field = "name"
            elif tag == "span" and "badge" in classes:
                self.active_field = "status"
            elif tag == "span" and "mt-2" in classes and "d-block" in classes:
                self.active_field = "phone"
            elif tag == "span" and "d-block" in classes and "texto-rojizo" in classes:
                self.active_field = "address"
            elif tag == "a":
                href = attrs.get("href", "")
                if "google." in href and "/maps/dir/" in href:
                    self.current_card["map_url"] = href

    def handle_data(self, data):
        if self.current_option is not None:
            self.current_option["text"].append(data)
        if self.active_field is not None and self.current_card is not None:
            self.current_card[self.active_field].append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.current_option is not None:
            option = self.current_option
            value = option["value"]
            label = " ".join("".join(option["text"]).split())
            if option["selected"] and value:
                self.selected_municipality = value
            if value and label:
                self.municipalities.append((value, label))
            self.current_option = None
        elif tag == "select":
            self.in_municipality_select = False
        elif tag in ("strong", "span"):
            self.active_field = None
        elif tag == "div" and self.current_card is not None:
            self.card_depth -= 1
            if self.card_depth == 0:
                card = {key: " ".join(value).strip() if isinstance(value, list) else value
                        for key, value in self.current_card.items()}
                self.cards.append(card)
                self.current_card = None
                self.active_field = None


def parse_municipalities(content):
    parser = CaceresPage()
    parser.feed(content)
    if not parser.token:
        raise ValueError("El buscador de Cáceres no incluye el token de sesión.")
    if not parser.municipalities or len({value for value, _ in parser.municipalities}) != len(parser.municipalities):
        raise ValueError("No se encontró una lista única de municipios de Cáceres.")
    return parser.token, parser.municipalities


def first_phone(value):
    match = re.search(r"(?<!\d)([6789](?:[\s./-]*\d){8})(?!\d)", value)
    return re.sub(r"\D", "", match.group(1)) if match else ""


def map_coordinates(url):
    match = re.search(r"/maps/dir//(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if not match:
        return None
    lat, lng = map(float, match.groups())
    if not (27 <= lat <= 44 and -19 <= lng <= 5):
        raise ValueError("El enlace oficial de mapas contiene coordenadas fuera de España.")
    return lat, lng


def pharmacy_locality(address, requested, municipalities):
    postcode = re.search(r"\b\d{5}\b", address)
    if postcode:
        suffix = address[postcode.end():].strip(" ,.-").split(",", 1)[0].strip()
        match = next((name for _, name in municipalities if slugify(name) == slugify(suffix)), None)
        if match:
            return match
    normalized = slugify(address)
    match = next((name for _, name in sorted(municipalities, key=lambda item: len(item[1]), reverse=True)
                  if normalized.endswith("-" + slugify(name))), None)
    return match or requested


def pharmacy_identifier(phone, name, address, locality):
    if phone:
        return f"cof-caceres-tel-{phone}"
    identity = "|".join(map(slugify, (name, address, locality)))
    return "cof-caceres-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def parse_open_results(content, municipality_id, municipality, target, municipalities, province_by_code):
    parser = CaceresPage()
    parser.feed(content)
    if parser.selected_municipality != municipality_id:
        raise ValueError("La respuesta no confirma el municipio solicitado.")
    if not parser.results_seen:
        raise ValueError("La respuesta no contiene el listado de resultados de COFCáceres.")
    rows = []
    for card in parser.cards:
        if not card["name"] or not card["address"]:
            raise ValueError(f"Ficha incompleta en la consulta de {municipality}.")
        status = card["status"].casefold()
        if status == "abierta":
            continue
        if status != "en servicio de urgencias":
            raise ValueError(f"COFCáceres devolvió un estado no reconocido en {municipality}: "
                             f"{card['status']}")

        phone = first_phone(card["phone"])
        locality = pharmacy_locality(card["address"], municipality, municipalities)
        postal = re.search(r"\b(\d{5})\b", card["address"])
        province = province_by_code.get(postal.group(1)[:2], "Cáceres") if postal else "Cáceres"
        point = map_coordinates(card["map_url"]) if card["map_url"] else None
        row = {
            "id": pharmacy_identifier(phone, card["name"], card["address"], locality),
            "nombre": card["name"],
            "direccion": card["address"],
            "localidad": locality,
            "provincia": province,
            "telefono": phone,
            "fuente": SOURCE,
            "guardia": True,
            "fecha_guardia": str(target),
            "localidades_atendidas": [municipality],
            "guardia_franja": "Guardia sin horario publicado",
            "guardia_franjas": ["Guardia sin horario publicado"],
            "lat": point[0] if point else None,
            "lng": point[1] if point else None,
            "nota_guardia": OPEN_NOW_NOTE,
        }
        if point:
            row["precision_ubicacion"] = "farmacia"
            row["fuente_coordenadas"] = card["map_url"]
        rows.append(row)
    return rows


def request(opener, url, data=None):
    headers = {"User-Agent": "FarmaciasDeGuardiaTracker/1.0"}
    if data is not None:
        headers.update({"Content-Type": "application/x-www-form-urlencoded",
                        "Referer": SOURCE})
    req = urllib.request.Request(url, data=data, headers=headers)
    with opener.open(req, timeout=45) as response:
        content = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return content.decode(charset, errors="replace")


def province_names():
    path = Path(__file__).resolve().parent.parent / "data" / "provincias.json"
    provinces = json.loads(path.read_text(encoding="utf-8"))
    if not provinces or any(not row.get("codigo") or not row.get("nombre") for row in provinces):
        raise ValueError("El catálogo de provincias no contiene códigos postales verificables.")
    return {row["codigo"]: row["nombre"] for row in provinces}


def run(target):
    reports, rows = [], []
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        token, municipalities = parse_municipalities(request(opener, SOURCE))
        codes = province_names()
        time.sleep(1.1)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Cáceres: {error}", flush=True)
        publish(target, "Cáceres", SOURCE, rows,
                [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
        return False

    for municipality_id, municipality in municipalities:
        payload = urllib.parse.urlencode({
            "_token": token,
            "municipio_id": municipality_id,
            "buscar_abiertas": "1",
        }).encode()
        try:
            content = request(opener, SEARCH, payload)
            batch = parse_open_results(content, municipality_id, municipality, target,
                                       municipalities, codes)
            rows.extend(batch)
            reports.append({
                "nombre": municipality,
                "estado": "parcial",
                "farmacias": len(batch),
                "error": OPEN_NOW_NOTE,
            })
        except (OSError, ValueError, KeyError, TypeError) as error:
            reports.append({"nombre": municipality, "estado": "error", "error": str(error)})
            print(f"AVISO COFCáceres {municipality}: {error}", flush=True)
        time.sleep(1.1)

    confirmed = consolidate(rows)
    for province in dict.fromkeys(row["provincia"] for row in confirmed):
        province_rows = [row for row in confirmed if row["provincia"] == province]
        locate_and_catalogue(province_rows, province)
    publish(target, "Cáceres", SOURCE, confirmed, reports)
    located = sum(row.get("lat") is not None for row in confirmed)
    print(f"Cáceres {target}: {len(confirmed)} farmacias en servicio de urgencias incorporadas como "
          f"guardias sin horario; {located} ubicadas; {len(municipalities)} consultas; "
          "cobertura parcial.", flush=True)
    return False


def main():
    today = datetime.now(TZ).date()
    parser = argparse.ArgumentParser(description="Consulta actual de farmacias abiertas en Cáceres.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=today)
    args = parser.parse_args()
    if args.fecha != today:
        parser.error("COFCáceres no permite elegir una fecha; sólo se puede importar el día actual.")
    return 0 if run(args.fecha) else 1


if __name__ == "__main__":
    raise SystemExit(main())
