#!/usr/bin/env python3
"""Regla de proximidad de 15 m para ubicar farmacias de guardia sin inventar puntos.

Una ubicación solo se confirma si los datos coinciden a 15 m o menos: la referencia
de una dirección con una farmacia conocida o con una segunda fuente independiente.
"""
import itertools
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple, Optional

from merge_espana import coordinates
from scrape_mes import write_json
from scrape_sevilla import street_query

RADIO_M = 15.0
USER_AGENT = "FarmaciasDeGuardiaTracker/1.0 (public pharmacy map)"
STREET_TYPES = {
    "calle", "c", "cl", "carrer", "avenida", "avda", "avd", "av", "avinguda", "plaza", "pza", "pl",
    "placa", "paseo", "po", "pso", "passeig", "carretera", "ctra", "crta", "camino", "cami", "ronda",
    "travesia", "trv", "urbanizacion", "urb", "glorieta", "pasaje", "pje", "pasatge", "barrio", "bo",
    "poligono", "pol", "rua", "praza", "via", "vial", "callejon", "bulevar", "rambla", "cuesta",
}
ARTICLES = {
    "de", "del", "la", "las", "los", "el", "d", "l", "en", "na", "al", "a", "y", "e", "els", "les",
    "lo", "dels", "des", "do", "da", "das", "dos", "o", "os", "as",
}
ROAD_KEYS = ("road", "pedestrian", "footway", "path", "residential")
TOWN_KEYS = ("city", "town", "village", "municipality", "suburb", "city_district", "hamlet", "borough", "quarter")
NOMINATIM_FIELDS = ("lat", "lon", "type", "osm_type", "osm_id")
NOMINATIM_ADDRESS = (*ROAD_KEYS, *TOWN_KEYS, "house_number")
CARTOCIUDAD_FIELDS = ("type", "address", "muni", "poblacion", "portalNumber", "noNumber", "lat", "lng")
SOURCE_NAMES = {
    "osm": "OpenStreetMap",
    "cartociudad": "CartoCiudad (IGN)",
    "oficial": "el mapa oficial de la fuente de guardias",
}


class Reference(NamedTuple):
    point: tuple
    source: str
    kind: str
    url: str
    osm_id: Optional[str] = None


def latlng(row):
    point = coordinates(row)
    return (point[1], point[0]) if point else None


def distance_m(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    half = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lng2-lng1)/2)**2
    return 2*6371008.8*math.asin(math.sqrt(half))


def cluster(items, radius=RADIO_M, point=lambda item: item):
    """Group items so that every pair inside a group is at most radius metres apart."""
    groups = []
    for item in items:
        for group in groups:
            if all(distance_m(point(item), point(other)) <= radius for other in group):
                group.append(item)
                break
        else:
            groups.append([item])
    return groups


def central(items, point=lambda item: item):
    return min(items, key=lambda item: sum(distance_m(point(item), point(other)) for other in items))


def agreement(points, radius=RADIO_M):
    """Single point representing candidates that all lie within radius metres, or None."""
    groups = cluster(points, radius)
    return central(groups[0]) if len(groups) == 1 else None


class PharmacyIndex:
    CELL = 0.0005

    def __init__(self, rows):
        self.cells = defaultdict(list)
        for row in rows:
            point = latlng(row)
            if point:
                self.cells[self.cell(point)].append((point, row))

    @classmethod
    def cell(cls, point):
        return math.floor(point[0]/cls.CELL), math.floor(point[1]/cls.CELL)

    def near(self, point, radius=RADIO_M):
        x, y = self.cell(point)
        found = []
        for dx, dy in itertools.product((-1, 0, 1), repeat=2):
            for other, row in self.cells.get((x+dx, y+dy), ()):
                distance = distance_m(point, other)
                if distance <= radius:
                    found.append((distance, row))
        return sorted(found, key=lambda item: (item[0], item[1]["id"]))


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def split_address(address):
    """Street and house number of a postal address, or None when it has no number."""
    match = re.fullmatch(r"(.+?)[,\s]+(\d+(?:-\d+)?[A-Za-z]?)", street_query(address or "").strip())
    return (match[1].strip(" ,"), match[2]) if match else None


def street_core(street):
    return " ".join(token for token in fold(street).split() if token not in STREET_TYPES and token not in ARTICLES)


def edit_distance(a, b):
    previous = list(range(len(b)+1))
    for i, char in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            current.append(min(previous[j]+1, current[j-1]+1, previous[j-1]+(char != other)))
        previous = current
    return previous[-1]


def similar_street(a, b):
    """Same street name allowing language variants such as Joan Carles / Juan Carlos."""
    core_a, core_b = street_core(a), street_core(b)
    if not core_a or not core_b:
        return False
    longest = max(len(core_a), len(core_b))
    return edit_distance(core_a, core_b) <= (1 if longest <= 7 else 2 if longest <= 16 else 3)


def number_parts(number):
    return {int(digits) for digits in re.findall(r"\d+", number or "")}, re.sub(r"[\d\s-]", "", number or "").upper()


def same_number(a, b):
    digits_a, suffix_a = number_parts(a)
    digits_b, suffix_b = number_parts(b)
    return bool(digits_a & digits_b) and (not suffix_a or not suffix_b or suffix_a == suffix_b)


def locality_names(value):
    names = set()
    for part in (value or "").split("/"):
        core = " ".join(token for token in fold(re.sub(r"\([^)]*\)", " ", part)).split() if token not in ARTICLES)
        if core:
            names.add(core)
    return names


def same_locality(a, b):
    return bool(locality_names(a) & locality_names(b))


def query_locality(value):
    """First name of a bilingual locality, with the INE trailing article moved to the front."""
    first = (value or "").split("/")[0].strip()
    match = re.fullmatch(r"(.*?)\s*\((el|la|los|las|l'|els|les|lo)\)", first, re.IGNORECASE)
    if not match:
        return first
    return f"{match[2]}{match[1]}" if match[2].endswith("'") else f"{match[2]} {match[1]}"


def phone_digits(row):
    return re.sub(r"\D", "", str(row.get("telefono") or "")).removeprefix("34")


def contradicts(row, pharmacy):
    """True when both records show a different phone or a different number on the same street."""
    phones = phone_digits(row), phone_digits(pharmacy)
    if len(phones[0]) == 9 and len(phones[1]) == 9 and phones[0] != phones[1]:
        return True
    ours, theirs = split_address(row.get("direccion")), split_address(pharmacy.get("direccion"))
    return bool(ours and theirs and similar_street(ours[0], theirs[0]) and not same_number(ours[1], theirs[1]))


def nominatim_references(row, results):
    parsed = split_address(row.get("direccion"))
    if not parsed:
        return []
    street, number = parsed
    found = []
    for item in results or []:
        details = item.get("address") or {}
        roads = [details[key] for key in ROAD_KEYS if details.get(key)]
        towns = [details[key] for key in TOWN_KEYS if details.get(key)]
        if not (same_number(number, details.get("house_number"))
                and any(similar_street(street, road) for road in roads)
                and any(same_locality(row.get("localidad"), town) for town in towns)):
            continue
        try:
            point = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not coordinates({"lat": point[0], "lng": point[1]}):
            continue
        osm_type, osm_id = item.get("osm_type"), item.get("osm_id")
        found.append(Reference(point, "osm", "pharmacy" if item.get("type") == "pharmacy" else "address",
                               f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                               f"osm-{osm_id}" if osm_type == "node" else None))
    return found


def cartociudad_references(row, results):
    parsed = split_address(row.get("direccion"))
    if not parsed:
        return []
    street, number = parsed
    found = []
    for item in results or []:
        text = (item.get("address") or "").rsplit(",", 1)[0]
        name = re.fullmatch(r"(.+?)\s+\d+\S*", text)
        if (item.get("type") != "portal" or item.get("noNumber") or not name
                or not same_number(number, str(item.get("portalNumber") or ""))
                or not similar_street(street, name[1])
                or not any(same_locality(row.get("localidad"), town) for town in (item.get("muni"), item.get("poblacion")))):
            continue
        point = (item.get("lat"), item.get("lng"))
        if coordinates({"lat": point[0], "lng": point[1]}):
            found.append(Reference((float(point[0]), float(point[1])), "cartociudad", "address",
                                   "https://www.cartociudad.es/"))
    return found


def official_references(row):
    """Point published by the duty source itself; it only counts when another source agrees."""
    official = row.get("referencia_ubicacion")
    if not isinstance(official, dict) or not coordinates(official):
        return []
    return [Reference((float(official["lat"]), float(official["lng"])), "oficial", "address",
                      official.get("fuente") or "")]


def sources_text(sources):
    names = [SOURCE_NAMES[source] for source in SOURCE_NAMES if source in sources]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} y {names[-1]}"


def nearby_pharmacies(row, index, point):
    """Known pharmacies within the radius, counting once every record already linked to the same OSM node.

    A group is discarded when any of its records contradicts the row; the OSM node represents the group.
    """
    groups = defaultdict(list)
    for distance, pharmacy in index.near(point):
        identifier = str(pharmacy.get("id") or "")
        node = identifier if identifier.startswith("osm-") else pharmacy.get("osm_id") or identifier
        groups[node].append((distance, pharmacy))
    found = []
    for members in groups.values():
        if any(contradicts(row, pharmacy) for _, pharmacy in members):
            continue
        found.append(min(members, key=lambda item: (not str(item[1].get("id")).startswith("osm-"), item[0])))
    return sorted(found, key=lambda item: (item[0], item[1]["id"]))


def propose(row, references, index):
    """Evidence for one pharmacy: a pharmacy POI at its address, or an address point and the pharmacies near it."""
    pharmacies = [ref for ref in references if ref.kind == "pharmacy"]
    if pharmacies:
        groups = cluster(pharmacies, point=lambda ref: ref.point)
        if len(groups) != 1:
            return {"estado": "conflicto"}
        chosen = central(groups[0], point=lambda ref: ref.point)
        independent = [
            ref for ref in references
            if ref.kind == "address" and ref.source != chosen.source
            and distance_m(chosen.point, ref.point) <= RADIO_M
        ]
        if not independent:
            return {"estado": "sin_referencia"}
        return {
            "estado": "farmacia", "point": chosen.point, "url": chosen.url,
            "osm_id": chosen.osm_id,
            "ajuste_ubicacion_m": round(min(distance_m(chosen.point, ref.point)
                                            for ref in independent), 1),
        }
    addresses = [ref for ref in references if ref.kind == "address"]
    if not addresses:
        return {"estado": "sin_referencia"}
    groups = cluster(addresses, point=lambda ref: ref.point)
    if len(groups) != 1:
        return {"estado": "conflicto"}
    chosen = central(groups[0], point=lambda ref: ref.point)
    nearby = nearby_pharmacies(row, index, chosen.point)
    return {"estado": "direccion", "point": chosen.point, "url": chosen.url,
            "fuentes": sorted({ref.source for ref in groups[0]}), "cercanas": nearby,
            "ajuste_ubicacion_m": round(max(distance_m(chosen.point, ref.point)
                                            for ref in groups[0]), 1)}


def link_proposal(row, index):
    """Evidence from a point already stored for the pharmacy: pharmacies within the radius of it."""
    point = latlng(row)
    nearby = nearby_pharmacies(row, index, point)
    estado = "direccion" if row.get("precision_ubicacion") == "direccion" else "enlace"
    return {"estado": estado, "point": point, "fuentes": ["previa"], "cercanas": nearby}


def resolve(proposals, claimed=None):
    """Turn per-row evidence into placements, never assigning one known pharmacy to two records."""
    claimed = dict(claimed or {})
    claimants = defaultdict(set)
    for row_id, proposal in proposals.items():
        if proposal["estado"] in ("direccion", "enlace") and len(proposal["cercanas"]) == 1:
            claimants[proposal["cercanas"][0][1]["id"]].add(row_id)
    placements, pending = {}, {}
    for row_id, proposal in proposals.items():
        estado = proposal["estado"]
        if estado == "farmacia":
            lat, lng = proposal["point"]
            placements[row_id] = {"lat": lat, "lng": lng, "precision_ubicacion": "farmacia",
                                  "fuente_coordenadas": proposal["url"],
                                  "nota_ubicacion": (
                                      "Ubicación contrastada: una farmacia de OpenStreetMap y "
                                      "una fuente independiente coinciden a "
                                      f"{proposal['ajuste_ubicacion_m']:.1f} m."
                                  ),
                                  "ajuste_ubicacion_m": proposal["ajuste_ubicacion_m"],
                                  **({"osm_id": proposal["osm_id"]} if proposal.get("osm_id") else {})}
            continue
        if estado not in ("direccion", "enlace"):
            pending[row_id] = estado
            continue
        nearby = proposal["cercanas"]
        node = nearby[0][1] if len(nearby) == 1 else None
        free = node and claimed.get(node["id"], row_id) == row_id and claimants[node["id"]] == {row_id}
        if free:
            distance = nearby[0][0]
            link = {"osm_id": node["id"], "ajuste_ubicacion_m": round(distance, 1)}
            if estado == "enlace":
                placements[row_id] = link
            else:
                lat, lng = latlng(node)
                subject = SOURCE_NAMES["oficial"] if proposal["fuentes"] == ["oficial"] else "la dirección"
                placements[row_id] = {
                    "lat": lat, "lng": lng, "precision_ubicacion": "farmacia",
                    "fuente_coordenadas": node.get("fuente_coordenadas") or f"https://www.openstreetmap.org/node/{node['id'][4:]}",
                    "nota_ubicacion": f"Ubicación contrastada: {subject} y una farmacia de OpenStreetMap coinciden a {distance:.0f} m.",
                    **link}
        elif estado == "enlace":
            pending[row_id] = "enlace_ambiguo" if nearby else "sin_enlace"
        elif len(proposal["fuentes"]) >= 2:
            lat, lng = proposal["point"]
            placements[row_id] = {
                "lat": lat, "lng": lng, "precision_ubicacion": "direccion", "fuente_coordenadas": proposal["url"],
                "nota_ubicacion": f"{sources_text(proposal['fuentes'])} sitúan esta dirección a menos de 15 m entre sí.",
                "ajuste_ubicacion_m": proposal["ajuste_ubicacion_m"]}
        else:
            pending[row_id] = "farmacia_ambigua" if nearby else "una_sola_fuente"
    return placements, pending


def compact_nominatim(results):
    return [{**{key: item.get(key) for key in NOMINATIM_FIELDS},
             "address": {key: (item.get("address") or {}).get(key) for key in NOMINATIM_ADDRESS
                         if (item.get("address") or {}).get(key)}} for item in results]


def compact_cartociudad(results):
    return [{key: item.get(key) for key in CARTOCIUDAD_FIELDS} for item in results]


class Geocoder:
    """Nominatim and CartoCiudad lookups with a persistent cache and one request per pause."""

    def __init__(self, cache=None, network=True, ttl_days=14, pause=1.1, opener=urllib.request.urlopen,
                 now=time.time, sleep=time.sleep):
        self.path = Path(cache) if cache else None
        self.network, self.ttl, self.pause = network, ttl_days*86400, pause
        self.opener, self.now, self.sleep = opener, now, sleep
        self.cache = json.loads(self.path.read_text()) if self.path and self.path.exists() else {}
        self.errors = self.requests = 0
        self.last = None
        self.unsaved = 0

    def lookup(self, key, url, compact):
        entry = self.cache.get(key)
        if entry and self.now()-entry["t"] < self.ttl:
            return entry["v"]
        if not self.network:
            return None
        for attempt in range(2):
            if self.last is not None:
                self.sleep(max(0, self.pause-(self.now()-self.last)))
            self.last = self.now()
            self.requests += 1
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with self.opener(request, timeout=45) as response:
                    text = response.read().decode()
                value = compact(json.loads(re.sub(r"^callback\(|\);?\s*$", "", text.strip())))
                break
            except (OSError, ValueError) as error:
                print(f"AVISO geocodificador ({key[:60]}): {error}", flush=True)
                self.sleep(5)
        else:
            self.errors += 1
            return None
        self.cache[key] = {"t": self.now(), "v": value}
        self.unsaved += 1
        if self.unsaved >= 25:
            self.save()
        return value

    def save(self):
        if self.path and self.unsaved:
            limit = self.now()-2*self.ttl
            write_json(self.path, {key: entry for key, entry in self.cache.items() if entry["t"] >= limit})
            self.unsaved = 0

    def references(self, row):
        parsed = split_address(row.get("direccion"))
        if not parsed:
            return None
        street = f"{parsed[0]}, {parsed[1]}"
        town, province = query_locality(row.get("localidad")), row.get("provincia", "")
        question = f"{street}, {town}, {province}, España"
        nominatim = self.lookup("N|"+question, "https://nominatim.openstreetmap.org/search?"+urllib.parse.urlencode({
            "q": question, "format": "jsonv2", "addressdetails": 1, "countrycodes": "es", "limit": 10,
            "accept-language": "es"}), compact_nominatim)
        question = f"{street}, {town}, {province}"
        carto = self.lookup("C|"+question, "https://www.cartociudad.es/geocoder/api/geocoder/candidates?"
                            + urllib.parse.urlencode({"q": question, "limit": 10, "countrycode": "es",
                                                      "no_process": "municipio,poblacion,toponimo"}),
                            compact_cartociudad)
        if nominatim is None and carto is None:
            return None
        return nominatim_references(row, nominatim)+cartociudad_references(row, carto)+official_references(row)
