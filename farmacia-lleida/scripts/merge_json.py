#!/usr/bin/env python3
import json, os, glob

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "data")
files = glob.glob(os.path.join(OUT_DIR, "farmacias-*.json"))
# Excluir farmacias-todas.json
files = [f for f in files if not f.endswith("farmacias-todas.json")]

all_data = []
for f in files:
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
            all_data.extend(data)
    except Exception as e:
        print(f"Error leyendo {f}: {e}")

out = os.path.join(OUT_DIR, "farmacias-todas.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)
print(f"Combinadas {len(all_data)} farmacias de {len(files)} archivos en {out}")
