#!/usr/bin/env python3
"""Read every locality in Granada's public dated duty form."""
import argparse
import hashlib
import html
import http.cookiejar
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from granada_verified_scans import VERIFIED_SCANS
from localizacion_cartociudad import locate as locate_cartociudad
from proximidad import Geocoder, PharmacyIndex, propose, resolve
from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import MONTHS, clean, pdf_pages, saved_address_signature, street_query

BASE = "https://www.cofgranada.com/"
SOURCE = BASE + "Paginas/Farmacias_Guardia.asp"
PHONE = re.compile(r"(?<!\d)[689](?:\s*\d){8}(?!\d)")


def locality_name(value):
    value = clean(value)
    if "," in value:
        noun, article = value.rsplit(",", 1)
        if slugify(article) in {"la", "las", "el", "los"}:
            return clean(article + " " + noun).title()
    return value.title()


def pharmacy(address, city, name, phone, period, target, source):
    phones = [re.sub(r"\D", "", m[0]) for m in PHONE.finditer(phone or "")]
    phone = phones[0] if phones else ""
    address = clean(address)
    city = locality_name(city)
    key = f"{slugify(city)}:{phone or slugify(address)}"
    return {
        "id": "cof-granada-" + hashlib.sha256(key.encode()).hexdigest()[:16],
        "cofm_id": None, "nombre": clean(name), "direccion": address,
        "localidad": city, "provincia": "Granada", "telefono": phone or None, "telefonos": phones,
        "guardia": True, "guardia_franja": period, "guardia_franjas": [period],
        "fecha_guardia": target.isoformat(), "fuente": source, "fuentes": [source],
        "lat": None, "lng": None,
    }


class Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.text = []
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "col-" in dict(attrs).get("class", ""):
                self.depth = 1
                self.text = []

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.cells.append(clean(" ".join(self.text)))

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


def parse_cards(content, requested, target):
    content = html.unescape(content)
    matches = list(re.finditer(r'id="Farmacia(\d+)"', content))
    markers = re.findall(r"L\.marker\(\[\s*([-\d.]+),\s*([-\d.]+)\]", content)
    rows = []
    for index, match in enumerate(matches):
        end = matches[index+1].start() if index+1 < len(matches) else content.find("<!--Mapa", match.start())
        parser = Cells()
        parser.feed("<div " + content[match.start():end if end >= 0 else len(content)])
        fields = {}
        for i, value in enumerate(parser.cells[:-1]):
            if value in {"Localidad", "Titular", "Dirección", "Teléfono"}:
                fields[value] = parser.cells[i+1]
        if not fields.get("Dirección") or not fields.get("Localidad"):
            raise ValueError("Ficha de farmacia sin dirección/localidad reconocible.")
        interval = re.search(r"Desde el día:\s*(\d{1,2}/\d{1,2}/\d{4})\s*hasta el día:\s*(\d{1,2}/\d{1,2}/\d{4})",
                             " ".join(parser.cells))
        if not interval:
            raise ValueError("Ficha sin intervalo fechado.")
        start, end_date = (datetime.strptime(v, "%d/%m/%Y").date() for v in interval.groups())
        if not start <= target <= end_date:
            raise ValueError("Ficha fuera de la fecha solicitada.")
        notes = next((v for v in parser.cells if v.startswith("Notas:")), "")
        period = f"Desde {start.isoformat()} hasta {end_date.isoformat()}; horario no especificado por la fuente"
        if notes.removeprefix("Notas:").strip():
            period += " · " + notes.removeprefix("Notas:").strip()
        row = pharmacy(fields["Dirección"], fields["Localidad"], fields.get("Titular", ""),
                       fields.get("Teléfono", ""), period, target, SOURCE)
        row["localidades_atendidas"] = [locality_name(requested)]
        if index < len(markers):
            lat, lng = map(float, markers[index])
            if not (36.5 < lat < 38.2 and -4.5 < lng < -2):
                row["nota_ubicacion"] = "La fuente publica coordenadas no válidas; ubicación pendiente."
                print(f"AVISO {fields['Localidad']}: coordenadas oficiales no válidas ({lat}, {lng}).", flush=True)
            else:
                row.update(lat=lat, lng=lng, precision_ubicacion="farmacia", fuente_coordenadas=SOURCE)
        rows.append(row)
    return rows


def parse_capital(pages, target, source):
    rows = []
    for page in pages:
        all_text = " ".join(line["text"] for line in page["lines"])
        stamp = re.search(r"(\d{1,2}) (?:DE )?([A-ZÁ]+) (\d{4})", all_text)
        if not stamp or date(int(stamp[3]), MONTHS[slugify(stamp[2])], int(stamp[1])) != target:
            continue
        if not (re.search(r"URGENCIA DIURNO:\s*DE 9[,.]30 H\. A 22[,.]00 H\.", all_text)
                and re.search(r"URGENCIA NOCTURNO:\s*DE 22[,.]00 H\. A 9[,.]30 H\. DEL DÍA SIGUIENTE", all_text)):
            raise ValueError("Horario de Granada capital no reconocido.")
        night = next((line["y"] for line in page["lines"] if "URGENCIA NOCTURNO" in line["text"]), float("inf"))
        for low, high, period in [(0, night, "Día (9:30-22:00)"),
                                  (night, float("inf"), "Noche (22:00-9:30 del día siguiente)")]:
            for right in (False, True):
                pending = []
                for line in sorted(page["lines"], key=lambda v: (v["y"], v["x"])):
                    text = line["text"]
                    if not low < line["y"] < high or (line["x"] >= page["width"]/2) != right:
                        continue
                    if ("SERVICIO DE" in text or re.search(r"\d{1,2} (?:DE )?[A-ZÁ]+ \d{4}", text)
                            or re.fullmatch(r"[-\s]+|\d+/\d+", text)):
                        pending = []
                        continue
                    if not pending and text.startswith("("):
                        continue
                    pending.append(text)
                    joined = clean(" ".join(pending))
                    phone = PHONE.search(joined)
                    if phone:
                        address = clean(re.split(r"\bTLF[.: ]*", joined, flags=re.I)[0])
                        rows.append(pharmacy(address, "Granada", "", phone[0], period, target, source))
                        pending = []
    return rows


def parse_loja(pages, target, source):
    rows = []
    for page in pages:
        lines = page["lines"]
        text = " ".join(line["text"] for line in lines)
        if "TURNOS ROTATORIOS DE GUARDIAS DIURNAS Y NOCTURNAS" not in text or "LOCALIDAD DE LOJA" not in text:
            continue
        year = re.search(r"\b(20\d{2})\b", text)
        month = re.search(r"MES DE\s+([A-ZÁÉÍÓÚÑ]+)\s+EN LA LOCALIDAD DE LOJA", text)
        if not year or not month or int(year[1]) != target.year or MONTHS.get(slugify(month[1])) != target.month:
            raise ValueError("El calendario de Loja no corresponde al mes solicitado.")
        daily = re.search(r"Farmacia\s+(Ldo\.\s+[^.]+)\.\s+(.+?)(?=\s+NOCTURNAS)", text, re.I)
        if not daily or not ("Lunes a viernes de 8,00 a 22,00 horas." in text
                             and "Sábados, domingos y festivos de 9,00 a 22,00." in text
                             and "NOCTURNAS de 22,00 a 8,00 laborables y de 22,00 a 9,00" in text):
            raise ValueError("Horario diurno o nocturno de Loja no reconocido.")
        entries = {}
        for heading in lines:
            match = re.fullmatch(r"(\d{1,2})\s+(LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO)", heading["text"], re.I)
            if not match:
                continue
            day = int(match[1])
            if day in entries:
                raise ValueError("Día duplicado en el calendario de Loja.")
            entry_date = date(target.year, target.month, day)
            weekdays = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
            if slugify(match[2]) != weekdays[entry_date.weekday()]:
                raise ValueError("Día de la semana contradictorio en el calendario de Loja.")
            near = [line for line in lines if abs(line["y"] - heading["y"]) <= 5]
            names = [line["text"] for line in near if 130 <= line["x"] < 300]
            addresses = [line["text"] for line in near if 300 <= line["x"] < page["width"]]
            if len(names) != 1 or len(addresses) != 1:
                raise ValueError("Fila de Loja incompleta o ambigua.")
            entries[day] = (names[0], addresses[0])
        if target.day not in entries:
            raise ValueError("El calendario de Loja no contiene el día solicitado.")

        def add(name, address, period):
            row = pharmacy(address, "Loja", name, "", period, target, source)
            row["id"] = "cof-granada-loja-" + hashlib.sha256(slugify(name).encode()).hexdigest()[:16]
            rows.append(row)

        add(daily[1], daily[2], "Guardia diurna; horario de festivo o laborable pendiente de confirmar.")
        name, address = entries[target.day]
        add(name, address, "Guardia nocturna; horario y relevo pendientes de confirmar.")
        if target.day > 1:
            if target.day - 1 not in entries:
                raise ValueError("Falta la guardia anterior de Loja para la madrugada.")
            name, address = entries[target.day - 1]
            add(name, address, "Guardia nocturna anterior; hora de cierre pendiente de confirmar.")
    return merge(rows)


def parse_weekly(pages, target, source):
    rows = []
    for page in pages:
        lines = sorted(page["lines"], key=lambda v: (v["y"], v["x"]))
        text = " ".join(v["text"] for v in lines)
        year = re.search(r"\b(20\d{2})\b", text)
        if not year:
            raise ValueError("Cartel sin año.")
        month = None
        intervals = []
        for line in lines:
            word = slugify(line["text"])
            if word in MONTHS:
                month = MONTHS[word]
            interval = re.fullmatch(r"(\d{1,2})(?:/(\d{1,2}))?\s+AL\s+(\d{1,2})(?:/(\d{1,2})(?:/(\d{2,4}))?)?", line["text"], re.I)
            if interval and month:
                a, am, b, bm, by = interval.groups()
                start = date(int(year[0]), int(am or month), int(a))
                end_year = int(by) + (2000 if len(by) == 2 else 0) if by else start.year
                end = date(end_year, int(bm or month), int(b))
                intervals.append((line, start, end))
        if not intervals:
            raise ValueError("Formato PDF pendiente de interpretación (no tabla semanal).")
        for i, (heading, start, end) in enumerate(intervals):
            night_only = "GUARDIA NOCTURNA 21:30H" in text
            if not start <= target < end + (timedelta(days=1) if night_only else timedelta()):
                continue
            low = heading["y"]-5
            high = intervals[i+1][0]["y"]-5 if i+1 < len(intervals) else heading["y"]+45
            cells = [v for v in lines if low <= v["y"] < high and v["x"] > heading["right"]+10
                     and not any(w in v["text"] for w in ("MÁS INFORMACIÓN", "*NOTA", "LOCALIDAD MÁS"))]
            names = [v for v in cells if re.match(r"Ld[ao]s?\.|LDA[S]?\.|LDO[S]?\.", v["text"], re.I)]
            if len(names) != 1:
                raise ValueError("Fila semanal sin un titular inequívoco.")
            name = names[0]
            phones = [m[0] for v in cells for m in PHONE.finditer(v["text"])]
            address = clean(" ".join(v["text"] for v in cells if v["x"] > name["right"]+10 and not PHONE.search(v["text"])))
            parts = re.split(r"\s+[-–]\s+", address)
            if len(parts) > 1:
                address, city = " - ".join(parts[:-1]), parts[-1]
            else:
                city_heading = next((v["text"].split()[0] for v in reversed(lines) if v["y"] < heading["y"]
                                     and re.fullmatch(r"HUÉSCAR|MARACENA(?: \d{4})?", v["text"])), None)
                if not city_heading:
                    raise ValueError("Fila semanal sin municipio de la farmacia.")
                city = city_heading
            if not address:
                raise ValueError("Fila semanal sin dirección.")
            period = ("Noche (21:30-8:30 del día siguiente)" if night_only else
                      f"Guardia del {start.isoformat()} 9:30 al {end.isoformat()} 9:30")
            rows.append(pharmacy(address, city, name["text"], phones[0] if phones else "", period, target, source))
    if not rows:
        raise ValueError("El cartel semanal no cubre toda la fecha solicitada.")
    return rows


def parse_weekly_blocks(pages, target, source):
    rows = []
    for page in pages:
        lines = sorted(page["lines"], key=lambda v: (v["y"], v["x"]))
        intervals = []
        for line in lines:
            match = re.fullmatch(r"LUNES (\d+) DE ([A-ZÁ]+) A LUNES (\d+) DE ([A-ZÁ]+) DE (\d{4})", line["text"])
            if match:
                a, am, b, bm, year = match.groups()
                intervals.append((line["y"], date(int(year), MONTHS[slugify(am)], int(a)),
                                  date(int(year), MONTHS[slugify(bm)], int(b))))
        if intervals:
            text = " ".join(line["text"] for line in lines)
            if not re.search(r"CAMBIOS DE GUARDIA SE REALIZAN TODOS LOS LUNES A LAS 9:30", text, re.I):
                raise ValueError("El cartel semanal no confirma la hora de cambio.")
            if "ATENCION LOCALIZADA" not in text.upper():
                raise ValueError("El cartel semanal no confirma atención localizada.")
        for i, (y, start, end) in enumerate(intervals):
            start_time = datetime.combine(start, datetime.min.time()).replace(hour=9, minute=30)
            end_time = datetime.combine(end, datetime.min.time()).replace(hour=9, minute=30)
            day_start = datetime.combine(target, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            if end_time <= start_time:
                raise ValueError("El cartel semanal contiene un intervalo no válido.")
            if start_time >= day_end or end_time <= day_start:
                continue
            high = intervals[i+1][0] if i+1 < len(intervals) else min(
                (v["y"] for v in lines if v["y"] > y and "*NOTA:" in v["text"]), default=y+160)
            region = [v for v in lines if y < v["y"] < high]
            names = [v for v in region if re.match(r"Ld[ao]s?\.", v["text"], re.I)]
            if not names:
                raise ValueError("Bloque semanal sin titulares reconocibles.")
            for j, name in enumerate(names):
                low = (names[j-1]["y"]+name["y"])/2 if j else y
                limit = (name["y"]+names[j+1]["y"])/2 if j+1 < len(names) else high
                cells = [v for v in region if low <= v["y"] < limit and v["x"] > name["right"]+5]
                address = clean(" ".join(v["text"] for v in cells if not PHONE.search(v["text"])))
                parts = re.split(r"\s+[-–]\s+", address)
                if len(parts) != 2:
                    raise ValueError("Bloque semanal sin municipio identificable.")
                phones = " ".join(m[0] for v in cells for m in PHONE.finditer(v["text"]))
                row = pharmacy(parts[0], parts[1], name["text"], phones,
                               f"Guardia localizada del {start.isoformat()} 9:30 al {end.isoformat()} 9:30; confirmar por teléfono",
                               target, source)
                row.update(guardia_localizada=True, guardia_intervalos=[{
                    "inicio": max(start_time, day_start).isoformat(),
                    "fin": min(end_time, day_end).isoformat(),
                    "inicio_original": start_time.isoformat(), "fin_original": end_time.isoformat(),
                    "tipo": "localizada",
                }])
                rows.append(row)
    return rows


def parse_fixed(pages, target, source):
    text = " ".join(v["text"] for p in pages for v in sorted(p["lines"], key=lambda v: (v["y"], v["x"])))
    if str(target.year) not in text:
        return []
    rules = []
    if "EN LA LOCALIDAD DE ALBOLOTE" in text and "Todos los días de la semana, 24 horas" in text:
        rules = [("León Felipez, 12", "Albolote", "Sánchez Sánchez", "24 horas")]
    elif "DE ARMILLA" in text and "TODOS LOS DÍAS DE LA SEMANA" in text:
        rules = [("San Miguel, 22", "Armilla", "Farmacia Poniente", "24 horas")]
    elif "URGENCIA MOTRIL" in text and "TODOS LOS DÍAS DE LA SEMANA" in text:
        rules = [("Juan de Dios Fernández Molina 4", "Motril", "Correa Gómez", "Día (9:30-22:00)"),
                 ("Alonso Terrón 1", "Motril", "Caballero Guerrero", "Día (9:30-22:00)"),
                 ("Pablo Picasso 18", "Motril", "Toledano", "Día (9:30-22:00)"),
                 ("Rambla de los Álamos, 8", "Motril", "Bullón Ocaña", "Día (9:30-22:00)"),
                 ("Rambla de los Álamos, 8", "Motril", "Bullón Ocaña", "Noche (22:00-9:30 del día siguiente)")]
    rows = []
    for address, city, name, period in rules:
        if slugify(address).replace("-", "") not in slugify(text).replace("-", ""):
            raise ValueError("El cartel fijo ha cambiado de dirección; requiere nueva interpretación.")
        rows.append(pharmacy(address, city, name, "", period, target, source))
    return rows


def parse_verified_scan(pdf, target, source):
    scan = VERIFIED_SCANS.get(hashlib.sha256(pdf).hexdigest())
    if scan is None:
        return None
    start, end = (datetime.fromisoformat(scan[key]) for key in ("inicio", "fin"))
    day_start = datetime.combine(target, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    if start >= day_end or end <= day_start:
        raise ValueError("El cartel verificado no cubre la fecha solicitada.")
    hours = {"inicio": max(start, day_start).isoformat(),
             "fin": min(end, day_end).isoformat(),
             "inicio_original": start.isoformat(), "fin_original": end.isoformat(),
             "tipo": "localizada"}
    period = (f"Guardia localizada del {start:%d/%m/%Y %H:%M} al "
              f"{end:%d/%m/%Y %H:%M}; confirmar por teléfono")
    rows = []
    for info in scan["farmacias"]:
        row = pharmacy(info["direccion"], info["localidad"], "", info["telefono"], period, target, source)
        row.update(guardia_localizada=True, guardia_intervalos=[hours.copy()])
        rows.append(row)
    return rows


def merge(rows):
    result = {}
    for row in rows:
        old = result.get(row["id"])
        if old:
            for field in ("guardia_franjas", "fuentes", "localidades_atendidas", "telefonos"):
                old[field] = list(dict.fromkeys(old.get(field, []) + row.get(field, [])))
            if old.get("guardia_intervalos") or row.get("guardia_intervalos"):
                old["guardia_intervalos"] = list({
                    json.dumps(interval, sort_keys=True): interval
                    for interval in old.get("guardia_intervalos", []) + row.get("guardia_intervalos", [])
                }.values())
            if row.get("guardia_localizada"):
                old["guardia_localizada"] = True
            if old.get("lat") is None and row.get("lat") is not None:
                for field in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas"):
                    old[field] = row.get(field)
            old["guardia_franja"] = " · ".join(old["guardia_franjas"])
        else:
            result[row["id"]] = row
    return list(result.values())


def geocode(row):
    street = street_query(row["direccion"])
    params = {"q": f"{street}, {row['localidad']}, Granada, España", "format": "jsonv2",
              "limit": 5, "countrycodes": "es", "addressdetails": 1}
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0 (public pharmacy map)"})
    with urllib.request.urlopen(req, timeout=30) as response:
        candidates = json.load(response)
    expected = saved_address_signature(street, row["localidad"])
    for item in candidates:
        if item.get("type") != "pharmacy":
            continue
        details = item.get("address", {})
        city = next((details[k] for k in ("city", "town", "village", "municipality", "suburb") if details.get(k)), "")
        address = f"{details.get('road', '')} {details.get('house_number', '')}"
        if not expected or saved_address_signature(address, locality_name(city)) != expected:
            continue
        lat, lng = float(item["lat"]), float(item["lon"])
        if not (36.5 < lat < 38.2 and -4.5 < lng < -2):
            continue
        return {"lat": lat, "lng": lng, "precision_ubicacion": "farmacia",
                "fuente_coordenadas": f"https://www.openstreetmap.org/{item['osm_type']}/{item['osm_id']}"}
    return None


def locate(rows, use_geocoder=False):
    catalogue_path = OUT_DIR / "farmacias-granada.json"
    old = {r["id"]: r for r in json.loads(catalogue_path.read_text())} if catalogue_path.exists() else {}
    osm = json.loads((OUT_DIR / "farmacias-osm-espana.json").read_text())
    strict = []
    for row in rows:
        if row["lat"] is not None:
            continue
        prior = old.get(row["id"])
        needs_contrast = row["localidad"] in {"Granada", "Loja"} and row.get("fuente", "").lower().endswith(".pdf")
        if needs_contrast:
            if (prior and prior.get("direccion") == row["direccion"] and prior.get("lat") is not None
                    and prior.get("ajuste_ubicacion_m") is not None
                    and prior["ajuste_ubicacion_m"] <= 15 and prior.get("referencia_ubicacion")):
                for field in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas",
                              "nota_ubicacion", "ajuste_ubicacion_m", "referencia_ubicacion", "osm_id"):
                    if field in prior:
                        row[field] = prior[field]
            elif use_geocoder:
                strict.append(row)
            continue
        if prior and prior["direccion"] == row["direccion"] and prior.get("lat") is not None:
            for field in ("lat", "lng", "precision_ubicacion", "fuente_coordenadas"):
                row[field] = prior.get(field)
            for field in ("nota_ubicacion", "ajuste_ubicacion_m", "referencia_ubicacion"):
                if field in prior:
                    row[field] = prior[field]
            continue
        key = saved_address_signature(row["direccion"], row["localidad"])
        matches = [r for r in osm if r.get("lat") is not None and 36.5 < r["lat"] < 38.2 and -4.5 < r["lng"] < -2
                   and ((row["telefono"] and re.sub(r"\D", "", str(r.get("telefono") or "")).removeprefix("34") == row["telefono"])
                        or (key and saved_address_signature(r.get("direccion", ""), locality_name(r.get("localidad", ""))) == key))]
        if len(matches) == 1:
            row.update(lat=matches[0]["lat"], lng=matches[0]["lng"], precision_ubicacion="farmacia",
                       fuente_coordenadas="https://www.openstreetmap.org/" + matches[0]["id"].replace("osm-", "node/"))
        elif use_geocoder:
            position = geocode(row)
            if position:
                row.update(position)
            print(f"Ubicación {row['localidad']}, {row['direccion']}: {'farmacia identificada' if position else 'pendiente; sin coincidencia fiable'}", flush=True)
            time.sleep(1.1)
    if strict:
        known = json.loads((OUT_DIR / "farmacias-espana-hoy.json").read_text())
        cache = Path.home() / ".local/state/farmacia/granada/posiciones-cartociudad.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        geocoder = Geocoder(cache=cache, ttl_days=365)
        locate_cartociudad(strict, known, geocoder, "Granada")
        index = PharmacyIndex([item for item in known if item.get("provincia") == "Granada"])
        proposals = {}
        claimed = {row["osm_id"]: row["id"] for row in rows if row.get("osm_id")}
        for row in strict:
            if row["lat"] is not None:
                continue
            references = geocoder.references(row)
            if references is not None:
                proposals[row["id"]] = propose(row, [ref for ref in references if ref.kind == "address"], index)
        placements, _ = resolve(proposals, claimed)
        for row in strict:
            position = placements.get(row["id"])
            if position and position.get("precision_ubicacion") == "farmacia":
                row.update(position, referencia_ubicacion=proposals[row["id"]]["url"])
        if geocoder.errors:
            raise ValueError("No se pudieron contrastar todas las ubicaciones de Granada y Loja.")
    for row in rows:
        if row["localidad"] in {"Granada", "Loja"} and row.get("fuente", "").lower().endswith(".pdf"):
            row["ubicacion_pendiente_verificacion"] = row["lat"] is None
    for row in rows:
        old[row["id"]] = {**row, "guardia": False}
    write_json(catalogue_path, list(old.values()))


def request(opener, path, params=None):
    url = urllib.parse.urljoin(BASE, path)
    with opener.open(urllib.request.Request(url, data=urllib.parse.urlencode(params).encode() if params else None,
                     headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"}), timeout=30) as response:
        return response.read()


def run(target, saved=None, use_geocoder=False):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    stamp = target.strftime("%d/%m/%Y")
    if saved:
        index = json.loads((saved / "indice.json").read_text())
        queries = index["consultas"]
    else:
        request(opener, "")
        selector = request(opener, "Paginas/Farmacias_Guardia-Localidades.asp", {"Fecha": stamp, "Pruebas": "no"}).decode("utf-8")
        cities = [html.unescape(v) for v in re.findall(r'<option value="([^"]+)"', selector)]
        if not cities:
            raise ValueError("El formulario oficial no contiene localidades.")
        queries = [{"localidad": c} for c in cities]
    catalogue_path = OUT_DIR / "farmacias-granada.json"
    catalogue = ({row["id"]: row for row in json.loads(catalogue_path.read_text())}
                 if catalogue_path.exists() else {})
    rows, reports, documents, verified_ids = [], [], {}, set()
    for i, query in enumerate(queries, 1):
        city = query["localidad"]
        try:
            if saved:
                if query.get("error"):
                    raise ValueError(query["error"])
                content = (saved / query["archivo"]).read_text()
            else:
                content = request(opener, "Paginas/Farmacias_Guardia-Buscador.asp", {
                    "BuscadorFarmaciasLocalidad": city, "BuscadorFarmaciasFechaBuscar": stamp,
                    "Ubicacion": "Paginas", "Pruebas": "no",
                }).decode("utf-8")
            if f"el día {stamp}" not in html.unescape(content):
                raise ValueError("Respuesta no confirma la fecha solicitada.")
            found = parse_cards(content, city, target)
            errors = []
            names = list(dict.fromkeys(html.unescape(n) for n in re.findall(r'MostrarDocumento\.asp\?Documento=([^"&]+)', content)))
            for name in names:
                if name not in documents:
                    url = BASE + "Documentos/guardias/" + urllib.parse.quote(name)
                    try:
                        pdf = (saved / index["documentos"][name]).read_bytes() if saved else request(opener, url)
                        if not pdf.startswith(b"%PDF"):
                            raise ValueError("Documento no PDF.")
                        parsed = parse_verified_scan(pdf, target, url)
                        verified_document = parsed is not None
                        if parsed is None:
                            pages = pdf_pages(pdf)
                            parsed = parse_capital(pages, target, url)
                            if parsed:
                                verified_document = True
                                documents[name] = {"rows": parsed, "verified": True,
                                                   "error": "Madrugada anterior pendiente de confirmar."}
                            if not parsed:
                                parsed = parse_loja(pages, target, url)
                                if parsed:
                                    verified_document = True
                                    documents[name] = {"rows": parsed, "verified": True,
                                                       "error": "Horarios de festivo y relevo pendientes de confirmar."}
                            if not parsed:
                                parsed = parse_weekly_blocks(pages, target, url)
                                verified_document = bool(parsed)
                            if not parsed:
                                parsed = parse_fixed(pages, target, url)
                                if parsed:
                                    documents[name] = {"rows": parsed, "error": "Horario fijo parcialmente interpretado; excepciones de festivos pendientes."}
                            if not parsed:
                                parsed = parse_weekly(pages, target, url)
                        if name not in documents:
                            documents[name] = {"rows": parsed, "verified": verified_document}
                            if verified_document and any(
                                interval["inicio"] != f"{target.isoformat()}T00:00:00"
                                or interval["fin"] != f"{(target + timedelta(days=1)).isoformat()}T00:00:00"
                                for row in parsed for interval in row["guardia_intervalos"]
                            ):
                                documents[name]["error"] = "El cartel solo confirma parte del día; relevo pendiente."
                    except (OSError, ValueError, subprocess.CalledProcessError) as error:
                        documents[name] = {"error": str(error)}
                document = documents[name]
                if "error" in document:
                    errors.append(f"{name}: {document['error']}")
                for row in document.get("rows", []):
                    if document.get("verified"):
                        prior = catalogue.get(row["id"])
                        if prior:
                            old_key = saved_address_signature(prior["direccion"], prior["localidad"])
                            new_key = saved_address_signature(row["direccion"], row["localidad"])
                            same_address = (old_key == new_key if old_key and new_key
                                            else slugify(prior["direccion"]) == slugify(row["direccion"]))
                            if not same_address:
                                errors.append(f"{name}: dirección discrepante para {row['localidad']}: "
                                              f"{prior['direccion']} / {row['direccion']}; pendiente de verificar.")
                                continue
                        verified_ids.add(row["id"])
                    found.append({**row, "localidades_atendidas": [locality_name(city)]})
            if not found and not names and "No se ha localizado ninguna farmacia" not in content:
                raise ValueError("Respuesta sin calendario reconocible.")
            state = "parcial" if errors and found else "pendiente_pdf" if errors else "disponible"
            reports.append({"nombre": city, "estado": state, "farmacias": len({row["id"] for row in found}),
                            "documentos": names, "errores": errors})
            rows.extend(found)
            print(f"{i}/{len(queries)} {city}: {state}, {len(found)}", flush=True)
        except (OSError, ValueError) as error:
            reports.append({"nombre": city, "estado": "error", "error": str(error)})
            print(f"ERROR {city}: {error}", flush=True)
        if not saved:
            time.sleep(0.2)
    rows = merge(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    locate(rows, use_geocoder)
    complete = all(r["estado"] == "disponible" for r in reports)
    calendar_path = OUT_DIR / f"guardias-granada-{target.isoformat()}.json"
    published = bool(rows) and (complete or not calendar_path.exists())
    published_rows = rows
    if not published and calendar_path.exists():
        previous = json.loads(calendar_path.read_text(encoding="utf-8"))
        if not isinstance(previous, list):
            raise ValueError("El calendario anterior de Granada no es una lista.")
        published_rows = previous
        previous_ids = {row["id"] for row in previous}
        additions = [row for row in rows if row["id"] in verified_ids and row["id"] not in previous_ids]
        if additions:
            published_rows = merge(previous + additions)
            published = True
    if published:
        write_json(calendar_path, published_rows)
    write_json(OUT_DIR / f"cobertura-granada-{target.isoformat()}.json", {
        "fecha": target.isoformat(), "provincia": "Granada", "fuente": SOURCE,
        "consultado": datetime.now(timezone.utc).isoformat(), "completa": complete,
        "consultas": reports, "farmacias": len(published_rows),
        "con_coordenadas": sum(r.get("lat") is not None and r.get("lng") is not None for r in published_rows),
        "calendario_actualizado": published,
    })
    print(f"Granada: {len(rows)} farmacias; {sum(r['lat'] is not None for r in rows)} ubicadas; cobertura completa: {complete}", flush=True)
    return complete


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    parser.add_argument("--documentos", type=Path, help="Resultados oficiales guardados para validar sin descargar.")
    parser.add_argument("--geocode", action="store_true", help="Buscar POIs de farmacia con dirección y localidad coincidentes.")
    args = parser.parse_args()
    try:
        complete = run(args.fecha, args.documentos, args.geocode)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        write_json(OUT_DIR / f"cobertura-granada-{args.fecha}.json", {
            "fecha": args.fecha.isoformat(), "provincia": "Granada", "fuente": SOURCE, "completa": False,
            "consultas": [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}],
            "calendario_actualizado": False,
        })
        raise
    raise SystemExit(0 if complete else 1)
