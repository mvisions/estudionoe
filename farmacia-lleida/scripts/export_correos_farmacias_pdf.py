#!/usr/bin/env python3
"""
Localiza correos electrónicos de farmacias de España (AEMPS Distafarma,
Catálogos Oficiales Colegiales y OpenStreetMap España) y genera un PDF
paginado de 20 en 20 farmacias por página, guardando en disco cada 20 registros.
"""
import html
import http.cookiejar
import json
import math
import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import cairo

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_PDF = BASE_DIR / "docs" / "correos-farmacias-espana.pdf"
OUT_JSON = BASE_DIR / "docs" / "correos-farmacias-espana.json"
MURCIA_CATALOG = Path.home() / ".local/state/farmacia/murcia/catalogo.json"

PAGE_SIZE = 20
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def clean_str(val):
    if not val:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def truncate_text(ctx, text, max_width):
    text = clean_str(text)
    if not text:
        return "—"
    if ctx.text_extents(text).width <= max_width:
        return text
    while len(text) > 1 and ctx.text_extents(text + "…").width > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def render_pdf(records, pdf_path=OUT_PDF):
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = pdf_path.with_suffix(".tmp.pdf")

    # A4 Landscape: 841.89 x 595.28 pt
    width, height = 841.89, 595.28
    surface = cairo.PDFSurface(str(tmp_path), width, height)
    ctx = cairo.Context(surface)

    total = len(records)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))

    # Column definitions: (Header, x_start, col_width)
    cols = [
        ("Nº", 28, 32),
        ("Farmacia / Titular", 62, 185),
        ("Provincia", 252, 85),
        ("Localidad", 342, 105),
        ("Dirección", 452, 145),
        ("Teléfono", 602, 65),
        ("Correo Electrónico", 672, 142),
    ]

    for page_idx in range(total_pages):
        start_idx = page_idx * PAGE_SIZE
        end_idx = min(total, start_idx + PAGE_SIZE)
        batch = records[start_idx:end_idx]

        # Background
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()

        # Top banner
        ctx.set_source_rgb(0.086, 0.467, 0.278)  # #167747 pharmacy green
        ctx.rectangle(20, 18, width - 40, 34)
        ctx.fill()

        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(12)
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(30, 39)
        ctx.show_text("LISTADO DE CORREOS ELECTRÓNICOS DE FARMACIAS DE ESPAÑA")

        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(9.5)
        right_header = f"Página {page_idx + 1} de {total_pages}  |  Registros {start_idx + 1}–{end_idx} de {total}"
        ext = ctx.text_extents(right_header)
        ctx.move_to(width - 30 - ext.width, 39)
        ctx.show_text(right_header)

        # Table header
        y_header = 60
        ctx.set_source_rgb(0.91, 0.95, 0.92)
        ctx.rectangle(20, y_header, width - 40, 20)
        ctx.fill()

        ctx.set_source_rgb(0.1, 0.2, 0.15)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(8.5)
        for title, x, w in cols:
            ctx.move_to(x, y_header + 13)
            ctx.show_text(title)

        # Rows (20 per page)
        row_h = 23.5
        y_start = y_header + 20

        for idx_in_page, rec in enumerate(batch):
            row_y = y_start + idx_in_page * row_h

            # Zebra striping
            if idx_in_page % 2 == 1:
                ctx.set_source_rgb(0.97, 0.985, 0.975)
                ctx.rectangle(20, row_y, width - 40, row_h)
                ctx.fill()

            # Row border line
            ctx.set_source_rgb(0.88, 0.91, 0.89)
            ctx.set_line_width(0.5)
            ctx.move_to(20, row_y + row_h)
            ctx.line_to(width - 20, row_y + row_h)
            ctx.stroke()

            text_y = row_y + 15
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(8)
            ctx.set_source_rgb(0.15, 0.15, 0.15)

            values = [
                str(start_idx + idx_in_page + 1),
                rec.get("nombre") or "Farmacia",
                rec.get("provincia") or "—",
                rec.get("localidad") or "—",
                rec.get("direccion") or "—",
                rec.get("telefono") or "—",
            ]
            for val, (_, x, w) in zip(values, cols[:6]):
                ctx.move_to(x, text_y)
                ctx.show_text(truncate_text(ctx, val, w - 4))

            # Email in bold dark green
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_source_rgb(0.06, 0.38, 0.22)
            _, x_email, w_email = cols[6]
            ctx.move_to(x_email, text_y)
            ctx.show_text(truncate_text(ctx, rec.get("email", ""), w_email - 2))

        # Outer table border
        ctx.set_source_rgb(0.75, 0.82, 0.78)
        ctx.set_line_width(0.8)
        ctx.rectangle(20, y_header, width - 40, 20 + PAGE_SIZE * row_h)
        ctx.stroke()

        # Footer
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(8)
        ctx.set_source_rgb(0.45, 0.45, 0.45)
        ctx.move_to(24, height - 12)
        ctx.show_text("Fuentes: AEMPS (Distafarma - Ministerio de Sanidad), Colegios Oficiales de Farmacéuticos y OpenStreetMap España. Paginado de 20 en 20.")

        surface.show_page()

    surface.finish()
    os.replace(tmp_path, pdf_path)


def save_checkpoint(records):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_json = OUT_JSON.with_suffix(".tmp.json")
    tmp_json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_json, OUT_JSON)
    render_pdf(records, OUT_PDF)
    print(f"[GUARDADO] {len(records)} farmacias ({math.ceil(len(records)/PAGE_SIZE)} páginas de {PAGE_SIZE}) -> {OUT_PDF}", flush=True)


def add_record(records, seen_emails, item):
    email = clean_str(item.get("email", "")).lower()
    if not email or not EMAIL_RE.match(email):
        return False
    if any(bad in email for bad in ["example.", "sentry.", "wix.", "schema."]):
        return False
    if email in seen_emails:
        return False
    seen_emails.add(email)
    records.append({
        "nombre": clean_str(item.get("nombre") or "Farmacia"),
        "provincia": clean_str(item.get("provincia") or ""),
        "localidad": clean_str(item.get("localidad") or ""),
        "direccion": clean_str(item.get("direccion") or ""),
        "telefono": clean_str(item.get("telefono") or ""),
        "email": email,
        "fuente": clean_str(item.get("fuente") or ""),
    })
    if len(records) % PAGE_SIZE == 0:
        save_checkpoint(records)
    return True


def fetch_distafarma_ccaa(cid, cname):
    results = []
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        opener.open("https://distafarma.aemps.es/farmacom/faces/inicio.xhtml", timeout=20).read()
        data = urllib.parse.urlencode({"idCCAA": str(cid)}).encode()
        r2 = opener.open(
            "https://distafarma.aemps.es/farmacom/faces/sec/CCAA/listadoCCAA.xhtml",
            data=data, timeout=20
        ).read().decode("utf-8", errors="ignore")
        m_rc = re.search(r"rowCount:(\d+)", r2)
        rc = int(m_rc.group(1)) if m_rc else 0
        if rc == 0:
            return results

        vs_m = re.search(r'name="javax\.faces\.ViewState"[^>]+value="([^"]+)"', r2)
        if not vs_m:
            return results
        vs = vs_m.group(1)

        # Load all rows in the CCAA table
        post_page = urllib.parse.urlencode({
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "tablaFarmaciasCCAA",
            "javax.faces.partial.execute": "tablaFarmaciasCCAA",
            "javax.faces.partial.render": "tablaFarmaciasCCAA",
            "tablaFarmaciasCCAA": "tablaFarmaciasCCAA",
            "tablaFarmaciasCCAA_pagination": "true",
            "tablaFarmaciasCCAA_first": "0",
            "tablaFarmaciasCCAA_rows": str(max(200, rc + 10)),
            "tablaFarmaciasCCAA_encodeFeature": "true",
            "bandejaEntradaForm_SUBMIT": "1",
            "javax.faces.ViewState": vs,
        }).encode()
        req_p = urllib.request.Request(
            "https://distafarma.aemps.es/farmacom/faces/sec/CCAA/listadoCCAA.xhtml",
            data=post_page,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Faces-Request": "partial/ajax",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        r3 = opener.open(req_p, timeout=25).read().decode("utf-8", errors="ignore")
        vs_u = re.search(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[(.*?)\]\]></update>', r3)
        if vs_u:
            vs = vs_u.group(1)

        for idx in range(rc):
            post_detail = urllib.parse.urlencode({
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": f"tablaFarmaciasCCAA:{idx}:j_id_6c",
                "javax.faces.partial.execute": "@all",
                "javax.faces.partial.render": "idPopupCargando idFormConsultaFarmacia idPopupConsultaFarmacia",
                f"tablaFarmaciasCCAA:{idx}:j_id_6c": f"tablaFarmaciasCCAA:{idx}:j_id_6c",
                "bandejaEntradaForm_SUBMIT": "1",
                "javax.faces.ViewState": vs,
            }).encode()
            req_d = urllib.request.Request(
                "https://distafarma.aemps.es/farmacom/faces/sec/CCAA/listadoCCAA.xhtml",
                data=post_detail,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Faces-Request": "partial/ajax",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            r4 = opener.open(req_d, timeout=20).read().decode("utf-8", errors="ignore")
            vs_u = re.search(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[(.*?)\]\]></update>', r4)
            if vs_u:
                vs = vs_u.group(1)

            def field(label):
                fm = re.search(rf"{label}:\s*([^<]+)", r4, re.I)
                return html.unescape(fm.group(1)).strip() if fm else ""

            email = field("Correo electrónico")
            if email:
                results.append({
                    "nombre": field("Nombre"),
                    "provincia": field("Provincia").title(),
                    "localidad": field("Localidad").title(),
                    "direccion": field("Dirección"),
                    "telefono": field("Teléfono") or field("Móvil"),
                    "email": email.lower(),
                    "fuente": "AEMPS Distafarma",
                })
    except Exception as e:
        print(f"AVISO Distafarma CCAA {cname}: {e}", flush=True)
    return results


def main():
    records = []
    seen_emails = set()

    # 1. Catálogo Oficial COF Región de Murcia (en caché local)
    if MURCIA_CATALOG.exists():
        print("Cargando correos del catálogo oficial del COF Región de Murcia...", flush=True)
        for row in json.loads(MURCIA_CATALOG.read_text(encoding="utf-8")):
            add_record(records, seen_emails, {
                "nombre": row.get("name"),
                "provincia": "Murcia",
                "localidad": (row.get("town") or "").title(),
                "direccion": row.get("address"),
                "telefono": row.get("phone"),
                "email": row.get("email"),
                "fuente": "COF Región de Murcia",
            })

    # 2. OpenStreetMap España (Overpass API)
    print("Consultando farmacias con correo electrónico en OpenStreetMap España...", flush=True)
    q = """[out:json][timeout:90];
area["ISO3166-1"="ES"][admin_level=2]->.es;
(
  nwr["amenity"="pharmacy"]["email"](area.es);
  nwr["amenity"="pharmacy"]["contact:email"](area.es);
);
out center tags;"""
    try:
        req = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": q}).encode(),
            headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            osm_data = json.load(resp)
        for el in osm_data.get("elements", []):
            tags = el.get("tags", {})
            raw_email = tags.get("email") or tags.get("contact:email") or ""
            for part in re.split(r"[;,/\s]+", raw_email):
                part = part.strip()
                if "@" in part:
                    street = tags.get("addr:street", "")
                    num = tags.get("addr:housenumber", "")
                    addr = f"{street} {num}".strip() or tags.get("addr:full", "")
                    city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or tags.get("addr:municipality") or ""
                    prov = tags.get("addr:province") or tags.get("addr:state") or ""
                    phone = tags.get("phone") or tags.get("contact:phone") or ""
                    add_record(records, seen_emails, {
                        "nombre": tags.get("name") or tags.get("operator") or "Farmacia",
                        "provincia": prov,
                        "localidad": city,
                        "direccion": addr,
                        "telefono": phone,
                        "email": part,
                        "fuente": "OpenStreetMap España",
                    })
    except Exception as e:
        print(f"AVISO OSM: {e}", flush=True)

    # 3. AEMPS Distafarma (Ministerio de Sanidad - todas las CCAA de España)
    print("Consultando registro oficial AEMPS Distafarma por Comunidad Autónoma...", flush=True)
    ccaas = [
        ("1", "Andalucía"), ("2", "Aragón"), ("3", "Principado de Asturias"),
        ("4", "Islas Baleares"), ("5", "Canarias"), ("6", "Cantabria"),
        ("7", "Castilla-La Mancha"), ("8", "Castilla y León"), ("9", "Cataluña"),
        ("10", "Comunidad Valenciana"), ("11", "Extremadura"), ("12", "Galicia"),
        ("13", "Comunidad de Madrid"), ("14", "Región de Murcia"),
        ("15", "Comunidad Foral de Navarra"), ("16", "País Vasco"), ("17", "La Rioja"),
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_distafarma_ccaa, cid, cname): cname for cid, cname in ccaas}
        for fut in as_completed(futures):
            cname = futures[fut]
            batch = fut.result()
            added = 0
            for item in batch:
                if add_record(records, seen_emails, item):
                    added += 1
            print(f"  AEMPS {cname}: {len(batch)} consultadas ({added} nuevas añadidas)", flush=True)

    # Final save if total is not an exact multiple of 20
    save_checkpoint(records)
    print(f"FINALIZADO: {len(records)} correos electrónicos únicos de farmacias en {math.ceil(len(records)/PAGE_SIZE)} páginas.", flush=True)


if __name__ == "__main__":
    main()
