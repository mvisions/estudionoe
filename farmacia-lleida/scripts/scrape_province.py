#!/usr/bin/env python3
"""
Scraper de farmacias de guardia para una provincia.
Uso: python3 scrape_province.py <provincia_id> <nombre_provincia>
Ejemplo: python3 scrape_province.py 29 Malaga
"""
import sys, os, urllib.request, urllib.parse, re, json, time, sqlite3

if len(sys.argv) < 3:
    print("Uso: scrape_province.py <provincia_id> <nombre_provincia>")
    sys.exit(1)

PROVINCIA_ID = sys.argv[1]
PROVINCIA_NOMBRE = sys.argv[2]
BASE = "https://farmaciasguardia.farmaceuticos.com/web_guardias"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "farmacias.db")
CACHE = "/tmp/opencode/geocache.json"
DATE = time.strftime("%d/%m/%Y")

geocache = {}
if os.path.exists(CACHE):
    with open(CACHE) as f:
        geocache = json.load(f)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "farmacia-guardia-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("latin-1", errors="replace")

def geocode(direccion, localidad):
    key = f"{direccion}|{localidad}"
    if key in geocache:
        return geocache[key]
    d = direccion.upper()
    for old, new in [("NUM.", ""), ("NÚM.", ""), ("Nº", ""), ("N°", ""), ("C/", "CALLE "), ("C/.", "CALLE "),
                     ("AVDA.", "AVENIDA "), ("AV.", "AVENIDA "), ("PZA.", "PLAZA "), ("PZ.", "PLAZA "),
                     ("CRTA", "CARRETERA"), ("CRTA.", "CARRETERA"), ("ED.", "EDIFICIO "),
                     ("LCAL.", "LOCAL "), ("LC.", "LOCAL "), ("NÚM", ""), ("NUM", "")]:
        d = d.replace(old, new)
    d = re.sub(r"\s+", " ", d).strip()
    # Intentar varias queries
    queries = [
        f"{d}, {localidad}, {PROVINCIA_NOMBRE}, Spain",
        f"{d}, {PROVINCIA_NOMBRE}, Spain",
        f"{localidad}, {PROVINCIA_NOMBRE}, Spain",
    ]
    res = (None, None)
    for q in queries:
        url = "https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(q) + "&format=json&limit=1&countrycodes=es"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "farmacia-guardia-mvp/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if data:
                res = (float(data[0]["lat"]), float(data[0]["lon"]))
                break
        except Exception as e:
            pass
        time.sleep(1.1)
    geocache[key] = res
    with open(CACHE, "w") as f:
        json.dump(geocache, f)
    time.sleep(1.1)
    return res


print(f"Obteniendo zonas de {PROVINCIA_NOMBRE}...")
html = fetch(f"{BASE}/publico/Provincia_pNew.asp?id={PROVINCIA_ID}")
m_zona = re.search(r'<select name="vzona">(.*?)</select>', html, re.DOTALL)
zonas = [(v, t.strip()) for v, t in re.findall(r'<option value="(\d+)">(.*?)</option>', m_zona.group(1))
         if v.startswith(PROVINCIA_ID) and v != "0"] if m_zona else []
m_pob = re.search(r'<select name="vpoblacion">(.*?)</select>', html, re.DOTALL)
poblaciones = [(v, t.strip()) for v, t in re.findall(r'<option value="(\d+)">(.*?)</option>', m_pob.group(1))
               if v.startswith(PROVINCIA_ID) and v != "0"] if m_pob else []
seen_codes = set()
zonas_combinadas = []
for code, name in zonas + poblaciones:
    if code not in seen_codes:
        seen_codes.add(code)
        zonas_combinadas.append((code, name))
print(f"  {len(zonas)} zonas + {len(poblaciones)} poblaciones = {len(zonas_combinadas)} unicas")

farmacias = []
total = 0
for idx, (zona_code, zona_nombre) in enumerate(zonas_combinadas, 1):
    print(f"[{idx}/{len(zonas)}] {zona_nombre}")
    url = f"{BASE}/GuardiasNew.asp?date={urllib.parse.quote(DATE)}&vzona={zona_code}&vmenu=1&provincia={PROVINCIA_ID}"
    try:
        html = fetch(url)
        matches_check = re.findall(r'abbre\(\d+,\s*(\d+),\s*0\)', html)
        if not matches_check:
            url = f"{BASE}/GuardiasNew.asp?date={urllib.parse.quote(DATE)}&vpoblacion={zona_code}&vmenu=1&provincia={PROVINCIA_ID}"
            html = fetch(url)
    except Exception as e:
        print(f"  Error fetch: {e}")
        continue

    secciones = [(m.start(), m.group(0).upper()) for m in re.finditer(r'GUARDIAS DE (D[IÍ]A|NOCHE|TODO EL D[IÍ]A)', html, re.IGNORECASE)]
    matches = list(re.finditer(r'abbre\(\d+,\s*(\d+),\s*0\)\s*>\s*(.*?)</a>', html, re.IGNORECASE | re.DOTALL))

    for m in matches:
        farm_id = m.group(1)
        texto = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        direccion, sector = (texto.split(" - ", 1) if " - " in texto else (texto, zona_nombre))
        direccion = direccion.strip()
        sector = sector.strip()

        pos = m.start()
        franja = "desconocida"
        for sec_pos, sec_name in reversed(secciones):
            if pos > sec_pos:
                if "NOCHE" in sec_name:
                    franja = "noche (22:00-9:30)"
                elif "TODO" in sec_name:
                    franja = "todo el dia (9:30-9:30)"
                else:
                    franja = "dia (9:30-22:00)"
                break

        lat, lng = geocode(direccion, sector)
        farmacias.append({
            "id": f"{PROVINCIA_ID}-{farm_id}",
            "cofm_id": farm_id,
            "nombre": f"Farmacia {sector}",
            "direccion": direccion,
            "localidad": sector,
            "zona": zona_nombre,
            "provincia": PROVINCIA_NOMBRE,
            "telefono": None,
            "horario": None,
            "guardia": True,
            "guardia_franja": franja,
            "fecha_guardia": DATE,
            "lat": lat,
            "lng": lng,
        })
        total += 1

# Deduplicar por cofm_id
seen_ids = set()
unique = []
for f in farmacias:
    if f["cofm_id"] in seen_ids:
        continue
    seen_ids.add(f["cofm_id"])
    unique.append(f)
out_file = os.path.join(os.path.dirname(__file__), "..", "public", "data", f"farmacias-{PROVINCIA_NOMBRE.lower()}.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)
print(f"  (deduplicadas: {len(farmacias)} -> {len(unique)})")
print(f"\nTotal farmacias procesadas: {total}")
print(f"Guardado en: {out_file}")
print(f"Provincia {PROVINCIA_NOMBRE} completada.")