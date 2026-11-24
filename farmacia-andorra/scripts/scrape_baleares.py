#!/usr/bin/env python3
"""Import dated duty lists and official pharmacy coordinates from COFIB."""
import argparse
from datetime import date, datetime, time, timedelta
import hashlib
from html.parser import HTMLParser
import re
import time as time_module
from pathlib import Path
import urllib.parse
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import OUT_DIR, fetch, slugify
from scrape_palencia import consolidate

SOURCE = "https://www.cofib.es/es/llistat_guardies.aspx"
TZ = ZoneInfo("Europe/Madrid")
SELECTORS = ("ddlMallorca", "ddlMenorca", "ddlPitiuses")


class CofibPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.zones = []
        self.hidden = {}
        self.rows = []
        self.in_listing = False
        self.listing_seen = False
        self.selectors_seen = set()
        self.current_row = None
        self.active_field = None
        self.active_option = None
        self.active_selector = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        identifier = attrs.get("id", "")
        if tag == "input" and (identifier.endswith("hdnData") or identifier.endswith("hdnZona")):
            self.hidden[identifier.rsplit("_", 1)[-1]] = attrs.get("value", "")
        if tag == "select":
            self.active_selector = any(identifier.endswith(selector) for selector in SELECTORS)
            if self.active_selector:
                self.selectors_seen.update(selector for selector in SELECTORS if identifier.endswith(selector))
        elif tag == "option" and self.active_selector:
            self.active_option = {"value": attrs.get("value", ""), "text": []}
        elif tag == "table" and identifier == "tblLlistatGuardies":
            self.in_listing = True
            self.listing_seen = True
        elif tag == "tr" and self.in_listing:
            self.current_row = {"title": [], "name": [], "address": [], "official_id": ""}
        elif self.current_row is not None:
            if tag == "p" and "lstgtitol" in classes:
                self.active_field = "title"
            elif tag == "span" and "lstgnom" in classes:
                self.active_field = "name"
            elif tag == "span" and "lstgdir" in classes:
                self.active_field = "address"
            elif tag == "a" and "lstgmapa" in classes:
                match = re.search(r"mostrarmapa\(\s*['\"][^'\"]+['\"]\s*,\s*['\"](\d+)['\"]",
                                  attrs.get("onclick", ""), re.I)
                if match:
                    self.current_row["official_id"] = match.group(1)

    def handle_data(self, data):
        if self.active_option is not None:
            self.active_option["text"].append(data)
        if self.active_field is not None and self.current_row is not None:
            self.current_row[self.active_field].append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.active_option is not None:
            text = " ".join("".join(self.active_option["text"]).split())
            if self.active_option["value"] != "sin" and text and text != "------":
                self.zones.append(text)
            self.active_option = None
        elif tag == "select":
            self.active_selector = False
        elif tag in ("p", "span"):
            self.active_field = None
        elif tag == "tr" and self.current_row is not None:
            row = {key: " ".join(value).strip() if isinstance(value, list) else value
                   for key, value in self.current_row.items()}
            if any(row[key] for key in ("title", "name", "address", "official_id")):
                self.rows.append(row)
            self.current_row = None
            self.active_field = None
        elif tag == "table" and self.in_listing:
            self.in_listing = False


def parse_index(content):
    parser = CofibPage()
    parser.feed(content)
    if (parser.selectors_seen != set(SELECTORS) or not parser.zones
            or len(parser.zones) != len(set(parser.zones))):
        raise ValueError("No se encontró una lista única y válida de municipios COFIB.")
    return parser.zones


def parse_clock(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as error:
        raise ValueError(f"Hora oficial COFIB no válida: {value}") from error


def parse_interval(day, title):
    match = re.search(r"(\d{2}:\d{2})\s*(?:a|-)\s*(\d{2}:\d{2})", title, re.I)
    if not match:
        raise ValueError(f"Horario oficial COFIB no reconocido: {title}")
    start = datetime.combine(day, parse_clock(match.group(1)), TZ)
    finish = datetime.combine(day, parse_clock(match.group(2)), TZ)
    if finish <= start:
        finish += timedelta(days=1)
    return start, finish


def split_pharmacy_name(value):
    normalized = " ".join(value.replace("\xa0", " ").split())
    phone_match = re.search(r"(?<!\d)([6789](?:[\s.-]*\d){8})(?!\d)", normalized)
    if phone_match:
        phone = re.sub(r"\D", "", phone_match.group(1))
        name = (normalized[:phone_match.start()] + normalized[phone_match.end():]).strip(" \t-;,")
    else:
        phone, name = "", normalized
    if not name:
        raise ValueError("Ficha COFIB sin nombre verificable.")
    return name, phone


def pharmacy_locality(address, zone_names, fallback):
    normalized = slugify(address)
    for zone in sorted(zone_names, key=len, reverse=True):
        candidate = slugify(zone)
        if normalized.endswith("-" + candidate) or normalized == candidate:
            return zone
    return fallback


def pharmacy_identifier(official_id, phone, name, address, locality):
    if official_id:
        return f"cof-baleares-{official_id}"
    if phone:
        return f"cof-baleares-tel-{phone}"
    identity = f"{slugify(name)}|{slugify(address)}|{slugify(locality)}"
    return f"cof-baleares-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def parse_listing(content, requested, target, zone, source, zone_names):
    parser = CofibPage()
    parser.feed(content)
    try:
        returned_date = datetime.strptime(parser.hidden["hdnData"], "%d/%m/%Y").date()
    except (KeyError, ValueError) as error:
        raise ValueError("La respuesta COFIB no confirma una fecha reconocible.") from error
    if returned_date != requested or parser.hidden.get("hdnZona") != zone:
        raise ValueError("La respuesta COFIB no corresponde a la fecha y municipio solicitados.")
    if not parser.listing_seen:
        raise ValueError("La respuesta COFIB no contiene la tabla oficial de guardias.")

    day_start = datetime.combine(target, time.min, TZ)
    day_end = day_start + timedelta(days=1)
    current_title = ""
    rows = []
    for record in parser.rows:
        if record["title"]:
            current_title = record["title"]
            continue
        if not record["name"] and not record["address"]:
            continue
        if not current_title or not all((record["name"], record["address"])):
            raise ValueError(f"Registro COFIB incompleto en {zone}.")
        name, phone = split_pharmacy_name(record["name"])
        start, finish = parse_interval(requested, current_title)
        if start >= day_end or finish <= day_start:
            continue
        start, finish = max(start, day_start), min(finish, day_end)
        address = record["address"]
        locality = pharmacy_locality(address, zone_names, zone)
        official_id = record["official_id"]
        pharmacy = {
            "id": pharmacy_identifier(official_id, phone, name, address, locality),
            "cofa_id": official_id,
            "nombre": name,
            "direccion": address,
            "localidad": locality,
            "provincia": "Baleares",
            "telefono": phone,
            "fuente": source,
            "lat": None,
            "lng": None,
        }
        label = f"Guardia COFIB · {start:%d/%m %H:%M}–{finish:%d/%m %H:%M}"
        rows.append({**pharmacy, "guardia": True, "fecha_guardia": str(target),
                     "localidades_atendidas": [zone], "guardia_franja": label,
                     "guardia_franjas": [label], "guardia_intervalos": [
                         {"inicio": start.isoformat(), "fin": finish.isoformat()}]})
    return rows


def parse_coordinates(content):
    match = re.search(r"\blatit\s*=\s*(-?\d+(?:\.\d+)?)\s*,\s*longt\s*=\s*(-?\d+(?:\.\d+)?)",
                      content, re.I)
    if not match:
        raise ValueError("El mapa oficial COFIB no incluye coordenadas.")
    lat, lng = map(float, match.groups())
    if not (38.5 <= lat <= 40.5 and 1.0 <= lng <= 4.7):
        raise ValueError("Las coordenadas oficiales COFIB quedan fuera de Baleares.")
    return lat, lng


def cached_page(url, path, offline=False, resume=False, static=False):
    if path.exists() and (offline or resume or static):
        return path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(f"Falta caché para consulta sin red: {path.name}")
    content = fetch(url)
    path.write_text(content, encoding="utf-8")
    time_module.sleep(1.1)
    return content


def map_url(official_id):
    return SOURCE.rsplit("/", 1)[0] + f"/mapes.aspx?sede=0&numfact={official_id}"


def run(target, cache, offline=False, resume=False):
    cache.mkdir(parents=True, exist_ok=True)
    reports, rows = [], []
    try:
        index_path = cache / "indice.html"
        index = cached_page(SOURCE, index_path, offline, resume)
        zones = parse_index(index)
        for zone in zones:
            zone_reports = []
            for requested in (target - timedelta(days=1), target):
                url = SOURCE + "?" + urllib.parse.urlencode(
                    {"z": zone, "data": requested.strftime("%d/%m/%Y")})
                path = cache / f"{requested.isoformat()}-{slugify(zone)}.html"
                try:
                    content = cached_page(url, path, offline, resume)
                    batch = parse_listing(content, requested, target, zone, url, zones)
                    rows.extend(batch)
                    zone_reports.append({"estado": "parcial", "farmacias": len(batch)})
                except (OSError, ValueError, KeyError) as error:
                    zone_reports.append({"estado": "error", "error": str(error)})
                    print(f"AVISO COFIB {zone} {requested}: {error}", flush=True)
            failures = [item["error"] for item in zone_reports if "error" in item]
            reports.append({
                "nombre": zone,
                "estado": "error" if failures else "parcial",
                "farmacias": sum(item.get("farmacias", 0) for item in zone_reports),
                "error": ("; ".join(failures) if failures else
                          "Consulta oficial por municipio; no acredita cobertura de todas las derivaciones.")
            })

        confirmed = consolidate(rows)
        directory = {row["id"]: dict(row) for row in confirmed}
        for row in directory.values():
            if not row["cofa_id"]:
                continue
            path = cache / f"mapa-{row['cofa_id']}.html"
            url = map_url(row["cofa_id"])
            try:
                content = cached_page(url, path, offline, resume, static=True)
                row["lat"], row["lng"] = parse_coordinates(content)
                row["precision_ubicacion"] = "farmacia"
                row["fuente_coordenadas"] = url
            except (OSError, ValueError) as error:
                print(f"AVISO COFIB mapa {row['cofa_id']}: {error}", flush=True)
                row["lat"], row["lng"] = None, None
        points = list(directory.values())
        locate_and_catalogue(points, "Baleares")
        for row in confirmed:
            point = directory[row["id"]]
            for field in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas"):
                if field in point:
                    row[field] = point[field]
        locate_and_catalogue(confirmed, "Baleares")
        publish(target, "Baleares", SOURCE, confirmed, reports)
        located = sum(row.get("lat") is not None for row in confirmed)
        print(f"Baleares {target}: {len(confirmed)} guardias confirmadas; "
              f"{located} ubicadas; {len(zones)} municipios consultados; cobertura parcial.", flush=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR Baleares: {error}", flush=True)
        publish(target, "Baleares", SOURCE, rows,
                reports + [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
    return False


def main():
    parser = argparse.ArgumentParser(description="Calendario oficial de guardias del COFIB.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path,
                        default=Path.home() / ".local/state/farmacia/baleares")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
