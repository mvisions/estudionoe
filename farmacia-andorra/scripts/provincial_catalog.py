"""Shared catalogue and partial-publication handling for dated provincial imports."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from merge_espana import coordinates, identity_keys
from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import saved_address_signature, street_query


def geocode_exact(row, allow_address=False):
    street = street_query(row["direccion"])
    key = saved_address_signature(street, row["localidad"])
    params = {"q":f"{street}, {row['localidad']}, {row['provincia']}, España",
              "format":"jsonv2", "addressdetails":1, "countrycodes":"es", "limit":5}
    request = urllib.request.Request("https://nominatim.openstreetmap.org/search?"+
                                    urllib.parse.urlencode(params),
                                    headers={"User-Agent":"FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(request,timeout=45) as response:
        candidates = json.load(response)
    matches = []
    address_matches = []
    for candidate in candidates:
        address = candidate.get("address", {})
        cities = [address[k] for k in ("city","town","village","municipality","suburb","city_district")
                  if address.get(k)]
        road = f"{address.get('road','')} {address.get('house_number','')}"
        if (key and re.search(r"\d",street)
                and any(saved_address_signature(road,city)==key for city in cities)):
            position = {"lat":float(candidate["lat"]), "lng":float(candidate["lon"]),
                        "precision_ubicacion":"farmacia",
                        "fuente_coordenadas":f"https://www.openstreetmap.org/{candidate['osm_type']}/{candidate['osm_id']}"}
            if coordinates(position):
                if candidate.get("type")=="pharmacy":
                    matches.append(position)
                elif allow_address and candidate.get("type") in ("house","building","yes","apartments","residential") and address.get("house_number"):
                    address_matches.append({**position,"precision_ubicacion":"direccion",
                                            "nota_ubicacion":"Ubicación por dirección exacta; pendiente de verificar como farmacia."})
    if matches:
        return matches[0] if len(matches)==1 else None
    return address_matches[0] if len(address_matches)==1 else None


def merge_rows(rows):
    result = {}
    for row in rows:
        key = row["id"]
        if key not in result:
            result[key] = dict(row)
            result[key]["localidades_atendidas"] = list(row.get("localidades_atendidas", []))
            result[key]["guardia_franjas"] = list(row.get("guardia_franjas", []))
        else:
            for field in ("localidades_atendidas", "guardia_franjas"):
                result[key][field] = list(dict.fromkeys(result[key][field]+row.get(field, [])))
        result[key]["guardia_franja"] = " · ".join(result[key]["guardia_franjas"])
    return list(result.values())


def locate_and_catalogue(rows, province, output=OUT_DIR, use_geocoder=False, official_points=None, allow_address=False):
    slug = slugify(province)
    path = output / f"farmacias-{slug}.json"
    old = json.loads(path.read_text()) if path.exists() else []
    national = json.loads((output / "farmacias-espana-hoy.json").read_text())
    points = [row for row in national if row.get("provincia") == province and coordinates(row)]
    saved = {row["id"]: row for row in old}
    for point in official_points or []:
        saved[point["id"]] = {**point,"guardia":False}
    for row in rows:
        requires_location_verification = row.get("ubicacion_requiere_verificacion") is True
        if official_points:
            keys = set(identity_keys(row))
            matches = [point for point in official_points if keys.intersection(identity_keys(point))]
            if len(matches)==1 and not requires_location_verification:
                point=matches[0]
                row.update(lat=point["lat"],lng=point["lng"],
                           precision_ubicacion=point.get("precision_ubicacion", "farmacia"),
                           fuente_coordenadas=point["fuente_coordenadas"])
                if point.get("nota_ubicacion"):
                    row["nota_ubicacion"] = point["nota_ubicacion"]
        prior = saved.get(row["id"])
        if (not requires_location_verification and not coordinates(row) and prior
                and prior.get("direccion") == row["direccion"]
                and prior.get("localidad") == row["localidad"] and coordinates(prior)):
            row.update({field:prior.get(field) for field in
                        ("lat", "lng", "precision_ubicacion", "fuente_coordenadas", "nota_ubicacion")})
        if not requires_location_verification and not coordinates(row):
            keys = set(identity_keys(row))
            matches = [point for point in points if keys.intersection(identity_keys(point))]
            if len(matches) == 1:
                point = matches[0]
                row.update(lat=point["lat"], lng=point["lng"],
                           precision_ubicacion=point.get("precision_ubicacion", "farmacia"),
                           fuente_coordenadas=point.get("fuente_coordenadas", "https://www.openstreetmap.org"))
                if point.get("nota_ubicacion"):
                    row["nota_ubicacion"] = point["nota_ubicacion"]
        if not coordinates(row) and not requires_location_verification:
            if use_geocoder:
                try:
                    position = geocode_exact(row,allow_address)
                    if position:
                        row.update(position)
                except urllib.error.HTTPError as error:
                    if error.code != 429:
                        print(f"ERROR ubicación {row['id']}: {error}",flush=True)
                        raise
                    print("AVISO geocodificador limitado (HTTP 429); se continúa sin geocodificar.",flush=True)
                    use_geocoder = False
                except (OSError, ValueError, KeyError) as error:
                    print(f"ERROR ubicación {row['id']}: {error}",flush=True)
                    raise
                time.sleep(1.1)
        if not coordinates(row):
            print(f"AVISO {row['id']}: ubicación pendiente; no se dibuja marcador.", flush=True)
        saved[row["id"]] = {**row, "guardia":False}
    write_json(path, list(saved.values()))


def publish(target, province, source, rows, reports, output=OUT_DIR, authoritative_sources=None):
    slug = slugify(province)
    rows = merge_rows(rows)
    complete = bool(reports) and all(report["estado"] == "disponible" for report in reports)
    path = output / f"guardias-{slug}-{target}.json"
    retained = []
    if path.exists() and not complete:
        confirmed = {slugify(r["nombre"]) for r in reports if r["estado"] == "disponible"}
        known = {row["id"] for row in rows}
        for old in json.loads(path.read_text()):
            towns = [town for town in old.get("localidades_atendidas", [old["localidad"]])
                     if slugify(town) not in confirmed]
            if towns and old["id"] not in known and old.get("fuente") not in (authoritative_sources or set()):
                retained.append({**old, "localidades_atendidas":towns, "guardia_reconfirmada":False,
                                 "guardia_franjas":[*old.get("guardia_franjas", []),
                                                   "Guardia anterior no reconfirmada; confirmar por teléfono"]})
    visible = merge_rows(rows+retained)
    if visible:
        write_json(path, visible)
    write_json(output / f"cobertura-{slug}-{target}.json", {
        "fecha":target.isoformat(), "provincia":province, "fuente":source,
        "completa":complete, "consultas":reports, "farmacias":len(visible),
        "farmacias_confirmadas":len(rows), "con_coordenadas":sum(bool(coordinates(r)) for r in visible),
        "calendario_actualizado":bool(visible), "guardias_conservadas_no_reconfirmadas":len(retained),
    })
    print(f"{province} {target}: {len(rows)} confirmadas; {sum(bool(coordinates(r)) for r in visible)} ubicadas; cobertura {'completa' if complete else 'parcial'}.", flush=True)
    return complete
