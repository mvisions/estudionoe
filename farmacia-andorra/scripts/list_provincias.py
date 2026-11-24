#!/usr/bin/env python3
import urllib.request, re, json, time

BASE = "https://www.farmaceuticos.com/farmacias-de-guardia"
OUT = "/home/mega/Documentos/farmacia/data/provincias.json"

# Obtener slugs de la página principal
html = urllib.request.urlopen(BASE).read().decode("utf-8", errors="replace")
slugs = re.findall(r'farmacias-de-guardia/([a-z0-9-]+)/', html)
slugs = sorted(set(slugs))
print(f"Encontrados {len(slugs)} slugs")

provincias = []
for slug in slugs:
    try:
        url = f"{BASE}/{slug}/"
        h = urllib.request.urlopen(url).read().decode("utf-8", errors="replace")
        m = re.search(r'Provincia_pNew\.asp\?id=(\d+)', h)
        if m:
            pid = m.group(1)
            # nombre: del h2 o title
            nm = re.search(r'<h2[^>]*>(.*?)</h2>', h, re.IGNORECASE | re.DOTALL)
            nombre = nm.group(1).strip() if nm else slug
            nombre = re.sub(r'<[^>]+>', '', nombre).strip()
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
