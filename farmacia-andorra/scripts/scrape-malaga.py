#!/usr/bin/env python3
import urllib.request, urllib.parse, re, json, time, os

PROVINCIA_ID = "29"
PROVINCIA_NOMBRE = "Malaga"
DATE = "31/10/2026"
BASE = "https://farmaciasguardia.farmaceuticos.com/web_guardias"
OUT = "/home/mega/Documentos/farmacia/public/data/farmacias-malaga.json"
CACHE = "/tmp/opencode/geocache-malaga.json"

# Cargar caché de geocodificación
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
    # Limpiar dirección
    d = direccion.upper()
    d = d.replace("NUM.", "").replace("NÚM.", "").replace("Nº", "").replace("N°", "")
    d = d.replace("C/", "CALLE").replace("C/.", "CALLE").replace("AVDA.", "AVENIDA")
    d = d.replace("AV.", "AVENIDA").replace("PZA.", "PLAZA").replace("PZ.", "PLAZA")
    d = d.replace("CRTA", "CARRETERA").replace("CRTA.", "CARRETERA")
    d = re.sub(r"\s+", " ", d).strip()
    query = f"{d}, {localidad}, Malaga, Spain"
    url = "https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(query) + "&format=json&limit=1&countrycodes=es"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "farmacia-guardia-mvp/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        if data:
            res = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        else:
            res = None
    except Exception as e:
        print("  geocode error:", e)
        res = None
    geocache[key] = res
    # guardar caché
    with open(CACHE, "w") as f:
        json.dump(geocache, f)
    time.sleep(1.1)  # respetar rate limit Nominatim
    return res

# 1. Obtener lista de zonas de Málaga
print("Obteniendo lista de zonas...")
html = fetch(f"{BASE}/publico/Provincia_pNew.asp?id={PROVINCIA_ID}")
zonas = re.findall(r'<option value="(\d+)">(.*?)</option>', html)
# Filtrar: solo valores que empiezan con 29 (Málaga) y no son 0
zonas = [(v, t.strip()) for v, t in zonas if v.startswith("29") and v != "0"]
print(f"Encontradas {len(zonas)} zonas")

farmacias = []
seen_ids = set()

for idx, (zona_code, zona_nombre) in enumerate(zonas, 1):
    print(f"[{idx}/{len(zonas)}] Procesando: {zona_nombre} ({zona_code})")
    url = f"{BASE}/GuardiasNew.asp?date={urllib.parse.quote(DATE)}&vzona={zona_code}&vmenu=1&provincia={PROVINCIA_ID}"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  Error fetch: {e}")
        continue

    # Encontrar posiciones de secciones
    secciones = []
    for m in re.finditer(r'GUARDIAS DE (D[IÍ]A|NOCHE|TODO EL D[IÍ]A)', html, re.IGNORECASE):
        secciones.append((m.start(), m.group(0).upper()))

    # Encontrar todas las farmacias (abbre)
    matches = list(re.finditer(r'abbre\(\d+,\s*(\d+),\s*0\)\s*>\s*(.*?)</a>', html, re.IGNORECASE | re.DOTALL))

    for m in matches:
        farm_id = m.group(1)
        texto = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        # texto formato: "DIRECCION - SECTOR"
        if " - " in texto:
            direccion, sector = texto.split(" - ", 1)
        else:
            direccion, sector = texto, zona_nombre
        direccion = direccion.strip()
        sector = sector.strip()

        # Determinar franja horaria por sección
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

        if farm_id in seen_ids:
            # actualizar franja si ya existe? mantener la primera
            continue
        seen_ids.add(farm_id)

        guardia = True  # todas las de esta lista son de guardia
        print(f"  Geocodificando: {direccion} | {sector}")
        geo = geocode(direccion, sector)
        farm = {
            "id": f"mal-{farm_id}",
            "cofm_id": farm_id,
            "nombre": f"Farmacia {sector}",
            "direccion": direccion,
            "localidad": sector,
            "zona": zona_nombre,
            "provincia": "Málaga",
            "telefono": None,
            "horario": None,
            "guardia": guardia,
            "guardia_franja": franja,
            "lat": geo["lat"] if geo else None,
            "lng": geo["lng"] if geo else None,
        }
        farmacias.append(farm)

# Guardar JSON
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(farmacias, f, ensure_ascii=False, indent=2)

print(f"\nTotal farmacias: {len(farmacias)}")
print(f"Guardado en: {OUT}")
