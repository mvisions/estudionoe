#!/usr/bin/env python3
"""
Genera un calendario mensual de guardias para un pueblo.
Uso: python3 calendario_pueblo.py <provincia_id> <zona_code> <nombre_pueblo> <mes> <año>
Ejemplo: python3 calendario_pueblo.py 29 29000019 "Alhaurin de la Torre" 10 2026
"""
import sys, os, urllib.request, urllib.parse, re, json, time, calendar

if len(sys.argv) < 6:
    print("Uso: calendario_pueblo.py <provincia_id> <zona_code> <nombre_pueblo> <mes> <año>")
    sys.exit(1)

PROV_ID = sys.argv[1]
ZONA_CODE = sys.argv[2]
PUEBLO = sys.argv[3]
MES = int(sys.argv[4])
ANIO = int(sys.argv[5])

BASE = "https://farmaciasguardia.farmaceuticos.com/web_guardias"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "calendarios")
os.makedirs(OUT_DIR, exist_ok=True)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "farmacia-guardia-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("latin-1", errors="replace")

calendario = {
    "pueblo": PUEBLO,
    "provincia_id": PROV_ID,
    "zona_code": ZONA_CODE,
    "mes": f"{ANIO:04d}-{MES:02d}",
    "dias": {}
}

num_dias = calendar.monthrange(ANIO, MES)[1]
for dia in range(1, num_dias + 1):
    fecha = f"{dia:02d}/{MES:02d}/{ANIO}"
    url = f"{BASE}/GuardiasNew.asp?date={urllib.parse.quote(fecha)}&vzona={ZONA_CODE}&vmenu=1&provincia={PROV_ID}"
    print(f"  {fecha} ...", end=" ", flush=True)
    try:
        html = fetch(url)
        matches = re.findall(r'abbre\(\d+,\s*(\d+),\s*0\)\s*>\s*(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        farmacias = []
        for fid, texto in matches:
            texto = re.sub(r'<[^>]+>', '', texto).strip()
            farmacias.append({"id": fid, "direccion": texto})
        calendario["dias"][f"{ANIO:04d}-{MES:02d}-{dia:02d}"] = farmacias
        print(f"{len(farmacias)} farmacias")
    except Exception as e:
        print(f"ERROR: {e}")
        calendario["dias"][f"{ANIO:04d}-{MES:02d}-{dia:02d}"] = []
    time.sleep(1.0)

out_file = os.path.join(OUT_DIR, f"calendario-{PUEBLO.lower().replace(' ', '-')}-{ANIO}-{MES:02d}.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(calendario, f, ensure_ascii=False, indent=2)

print(f"\nCalendario guardado en: {out_file}")
