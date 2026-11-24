#!/usr/bin/env python3
import json, os, subprocess, sys, time

PROV_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "provincias.json")
with open(PROV_FILE, encoding="utf-8") as f:
    provincias = json.load(f)

# Permitir filtrar por argumentos: update_all.py Madrid Málaga Sevilla
filtro = [a.lower() for a in sys.argv[1:]]
if filtro:
    provincias = [p for p in provincias if p["nombre"].lower() in filtro]

for p in provincias:
    print(f"\n=== Actualizando {p['nombre']} (id={p['id']}) ===")
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "scrape_province.py"), p["id"], p["nombre"]]
    subprocess.run(cmd, check=False)
    time.sleep(2)

print("\nActualización completa.")
PY