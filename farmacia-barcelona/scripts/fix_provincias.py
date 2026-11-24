#!/usr/bin/env python3
import urllib.request, re, json, time, os

BASE = "https://www.farmaceuticos.com/farmacias-de-guardia"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "provincias.json")

# Obtener slugs de la página principal
html = urllib.request.urlopen(BASE).read().decode("utf-8", errors="replace")
slugs = sorted(set(re.findall(r'farmacias-de-guardia/([a-z0-9-]+)/', html)))

provincias = []
for slug in slugs:
    try:
        url = f"{BASE}/{slug}/"
        h = urllib.request.urlopen(url).read().decode("utf-8", errors="replace")
        m = re.search(r'Provincia_pNew\.asp\?id=(\d+)', h)
        if m:
            pid = m.group(1)
            # nombre del h2 (limpiar)
            nm = re.search(r'<h2[^>]*>(.*?)</h2>', h, re.IGNORECASE | re.DOTALL)
            nombre = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else slug
            # limpiar "Encuentra farmacias de guardia en X"
            nombre = nombre.replace("Encuentra farmacias de guardia en", "").strip()
            provincias.append({"id": pid, "nombre": nombre, "slug": slug})
            print(f"  {pid} -> {nombre} ({slug})")
        else:
            print(f"  [WARN] No id para {slug}")
    except Exception as e:
        print(f"  [ERR] {slug}: {e}")
    time.sleep(0.5)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(provincias, f, ensure_ascii=False, indent=2)
print(f"\nGuardado en {OUT}: {len(provincias)} provincias")
