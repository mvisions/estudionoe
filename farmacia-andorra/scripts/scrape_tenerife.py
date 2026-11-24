#!/usr/bin/env python3
"""Scraper de farmacias de guardia de Tenerife (Canarias) via PDFs del COF Santa Cruz."""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from scrape_mes import OUT_DIR, slugify, write_json
from scrape_sevilla import clean, pdf_pages

BASE = "https://www.coftenerife.es"
AJAX = "https://www.coftenerife.es/wp-admin/admin-ajax.php"
PROVINCIA = "Santa Cruz de Tenerife"

PHONE = re.compile(r"\((\d{3}-\d{2}-\d{2}-\d{2})\)")


def request_zones():
    url = f"{AJAX}?action=getguardias"
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardia/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    if isinstance(data, dict):
        data = data.get("data", data)
    zones = []
    for item in data:
        if isinstance(item, dict):
            zona = item.get("zona") or item.get("nombre")
            link = item.get("link", "")
            m = re.search(r"guardias=([^'\"]+)", link)
            pdf_path = m.group(1) if m else None
            if zona:
                zones.append({"zona": zona, "pdf_path": pdf_path})
    return zones


def fetch_pdf(pdf_path):
    url = f"{BASE}/wp-admin/admin-post.php?action=getPdf&guardias={urllib.parse.quote(pdf_path)}"
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciasDeGuardia/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = re.search(r"viewer\.php\?file=([^'\" ]+)", html)
    if not m:
        raise ValueError("No se encontró el PDF en la respuesta.")
    pdf_url = f"{BASE}/wp-content/plugins/pdfjs-viewer-shortcode/pdfjs/web/{m.group(1)}"
    req = urllib.request.Request(pdf_url, headers={"User-Agent": "FarmaciasDeGuardia/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_tenerife_pdf(pages, fecha, zona):
    all_lines = []
    for page in pages:
        for line in page["lines"]:
            t = clean(line["text"])
            if t:
                all_lines.append({"x": line["x"], "y": line["y"], "text": t})
    rows = []

    is_ls_df = any(re.search(r"\d{1,2}\s+\w+\s+(L-S|D-F)\s+HASTA", l["text"], re.I) for l in all_lines)

    if is_ls_df:
        name_lines = [l for l in all_lines if 100 <= l["x"] < 400 and re.search(r"Lcd|Lda", l["text"], re.I)]
        addr_lines = [l for l in all_lines if 100 <= l["x"] < 200 and not re.search(r"Lcd|Lda|Horario|H\.|De [0-9]", l["text"], re.I)]
        phone_lines = [l for l in all_lines if l["x"] >= 480]
        pharmacies = []
        for nl in name_lines:
            name = re.sub(r"\(\d{3}-\d{2}-\d{2}-\d{2}\)", "", nl["text"]).strip()
            pl = min(phone_lines, key=lambda l: abs(l["y"] - nl["y"]), default=None)
            phone = None
            if pl and abs(pl["y"] - nl["y"]) <= 5:
                pm = PHONE.search(pl["text"])
                if pm:
                    phone = pm.group(1).replace("-", "")
            al = min(addr_lines, key=lambda l: abs(l["y"] - nl["y"]), default=None)
            if al and abs(al["y"] - nl["y"]) > 15:
                al = None
            address = al["text"] if al else None
            pharmacies.append({"name": name, "address": address, "phone": phone})
        ls_pharm = pharmacies[0] if len(pharmacies) >= 1 else None
        df_pharm = pharmacies[1] if len(pharmacies) >= 2 else None
        for dl in all_lines:
            m = re.match(r"^(\d{1,2})\s+\w+\s+(L-S|D-F)\s+HASTA\s+(\d{2}:\d{2})", dl["text"], re.I)
            if not m:
                continue
            day = int(m.group(1))
            if day != fecha.day:
                continue
            sched = m.group(2).upper()
            time_str = m.group(3)
            pharm = ls_pharm if sched == "L-S" else df_pharm
            if pharm is None:
                continue
            rows.append({
                "day": day,
                "time_range": f"09:00 - {time_str}",
                "name": pharm["name"],
                "phone": pharm["phone"],
                "address": pharm["address"],
                "zona": zona,
            })
    else:
        # Standard format (Adeje style)
        day_pattern = re.compile(r"^(\d{1,2})\s+(?:lun|mar|mi[eé]r|jue|vie|s[aá]b|dom)\s+(\d{2}:\d{2})h?\s+a\s+(\d{2}:\d{2})h?", re.I)
        name_lines = [l for l in all_lines if 100 <= l["x"] < 400 and re.search(r"Lcd|Lda", l["text"], re.I)]
        addr_lines = [l for l in all_lines if 100 <= l["x"] < 200 and not re.search(r"Lcd|Lda|Horario|H\.|De [0-9]", l["text"], re.I)]
        phone_lines = [l for l in all_lines if l["x"] >= 480]
        # Handle multi-line time
        merged = []
        i = 0
        while i < len(all_lines):
            l = all_lines[i]
            t = l["text"]
            m = re.match(r"^(\d{1,2})\s+(?:lun|mar|mi[eé]r|jue|vie|s[aá]b|dom)\s*$", t, re.I)
            if m and i + 1 < len(all_lines) and 40 <= all_lines[i+1]["x"] <= 70:
                nt = all_lines[i+1]["text"]
                nm = re.match(r"^(\d{2}:\d{2})h?\s+a\s+(\d{2}:\d{2})h?$", nt, re.I)
                if nm:
                    merged.append({"x": l["x"], "y": l["y"], "text": f"{l['text']} {nt}"})
                    i += 2
                    continue
            merged.append(l)
            i += 1
        all_lines = merged
        for dl in all_lines:
            m = day_pattern.match(dl["text"])
            if not m:
                continue
            day = int(m.group(1))
            if day != fecha.day:
                continue
            time_range = f"{m.group(2)} - {m.group(3)}"
            # Prefer addresses just below the day line (y in [day_y, day_y+12])
            below = [l for l in addr_lines if dl["y"] <= l["y"] <= dl["y"] + 12]
            if below:
                addr_line = min(below, key=lambda l: l["y"])
            else:
                addr_line = min(addr_lines, key=lambda l: abs(l["y"] - dl["y"]), default=None)
                if addr_line is not None and abs(addr_line["y"] - dl["y"]) > 12:
                    addr_line = None
            name_line = None
            if addr_line:
                cands = [l for l in name_lines if l["y"] <= addr_line["y"] + 2]
                if cands:
                    name_line = max(cands, key=lambda l: l["y"])
            if name_line is None:
                name = ""
                phone = None
                address = addr_line["text"] if addr_line else None
            else:
                name = name_line["text"]
                pl = min(phone_lines, key=lambda l: abs(l["y"] - name_line["y"]), default=None)
                phone = None
                if pl and abs(pl["y"] - name_line["y"]) <= 5:
                    pm = PHONE.search(pl["text"])
                    if pm:
                        phone = pm.group(1).replace("-", "")
                address = addr_line["text"] if addr_line else None
                name = re.sub(r"\(\d{3}-\d{2}-\d{2}-\d{2}\)", "", name).strip()
            rows.append({
                "day": day,
                "time_range": time_range,
                "name": name,
                "phone": phone,
                "address": address,
                "zona": zona,
            })

    out = []
    for r in rows:
        out.append({
            "id": f"cof-tenerife-{slugify(r['zona'])}-{slugify(r['name'])}-{fecha.isoformat()}",
            "nombre": r["name"],
            "direccion": r["address"] or "",
            "localidad": r["zona"],
            "provincia": "Santa Cruz de Tenerife",
            "telefono": r["phone"],
            "lat": None,
            "lng": None,
            "guardia": True,
            "guardia_franja": r["time_range"],
            "guardia_franjas": [r["time_range"]],
            "fecha_guardia": fecha.isoformat(),
            "fuente": BASE,
            "fuentes": [BASE],
        })
    return out


def run(fecha):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zones = request_zones()
    print(f"Zonas: {len(zones)}", flush=True)
    rows = []
    reports = []
    for i, z in enumerate(zones, 1):
        zona = z["zona"]
        pdf_path = z["pdf_path"]
        if not pdf_path:
            reports.append({"nombre": zona, "estado": "sin_pdf", "error": "Sin enlace a PDF"})
            print(f"{i}/{len(zones)} {zona}: sin PDF", flush=True)
            continue
        try:
            content = fetch_pdf(pdf_path)
            pages = pdf_pages(content)
            found = parse_tenerife_pdf(pages, fecha, zona)
            rows.extend(found)
            reports.append({"nombre": zona, "estado": "disponible", "farmacias": len(found)})
            print(f"{i}/{len(zones)} {zona}: {len(found)} guardias", flush=True)
        except Exception as e:
            reports.append({"nombre": zona, "estado": "error", "error": str(e)})
            print(f"{i}/{len(zones)} {zona}: ERROR {e}", flush=True)
        time.sleep(0.5)
    path = OUT_DIR / f"guardias-tenerife-{fecha.isoformat()}.json"
    write_json(path, rows)
    report = {"fecha": fecha.isoformat(), "provincia": "Santa Cruz de Tenerife",
              "fuente": BASE, "consultas": reports,
              "farmacias": len(rows), "farmacias_confirmadas": len(rows)}
    write_json(OUT_DIR / f"cobertura-tenerife-{fecha.isoformat()}.json", report)
    print(f"Tenerife: {len(rows)} guardias publicadas.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    run(args.fecha)
