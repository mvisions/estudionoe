#!/usr/bin/env python3
"""Import the public COFB catalogue; report protected duty searches without bypassing them."""
import argparse
import html
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from merge_espana import coordinates
from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import OUT_DIR, slugify, write_json

SOURCE = "https://www.cofb.org/ca/qui-som/el-collegi/cercador-de-farmacies/"
DUTY_SOURCE = "https://www.cofb.org/ca/que-oferim/ciutadans/farmacies-obertes/"
FINDER = "https://www.farmaguia.net/"
MOBILE = "https://mobi.farmaguia.net/advanced_search"
TZ = ZoneInfo("Europe/Madrid")
BLOCKER = ("Farmaguia exige reCAPTCHA antes de la búsqueda de guardias. "
           "No se consulta la API protegida ni se infieren guardias de horarios habituales.")
# These are candidate municipal queries, not aliases: membership is accepted only
# when the official municipal PDF contains the same pharmacy ID and address.
VERIFICATION_TOWNS = (
    "BALENYÀ", "CÀNOVES I SAMALÚS", "CERDANYOLA DEL VALLÈS", "FIGARÓ-MONTMANY",
    "GUALBA", "MASIES DE RODA, LES", "MASIES DE VOLTREGÀ, LES", "OLÈRDOLA",
    "PONT DE VILOMARA I ROCAFORT, EL", "SANT CUGAT DEL VALLÈS",
    "SANT LLORENÇ D'HORTONS", "SANT MATEU DE BAGES", "SANT PERE DE RIBES",
    "SANT QUIRZE DEL VALLÈS", "SITGES", "SUBIRATS", "TERRASSA",
)
ROW = re.compile(
    r"^\s*(\d+)\s+(.+?)\s{2,}(.+?)\s{2,}(\d{5})\s+(.+?)"
    r"(?:\s{2,}(\d{9}))?\s*$")


def municipality(value):
    value = value.strip()
    match = re.fullmatch(r"(.+),\s*(EL|ELS|LA|LES|L')", value, re.I)
    if match:
        value = match[2] + " " + match[1]
    return slugify(value)


def request(url, fields=None):
    time.sleep(1.1)
    payload = urllib.parse.urlencode(fields).encode() if fields is not None else None
    req = urllib.request.Request(url, data=payload,
                                 headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def select(content, name):
    match = re.search(r'<select\b[^>]*name="' + re.escape(name) + r'"[^>]*>(.*?)</select>',
                      content, re.S)
    if not match:
        raise ValueError(f"Selector COFB ausente: {name}")
    return [{"id": html.unescape(identifier), "nombre": html.unescape(
        re.sub("<[^>]+>", "", label)).strip()}
        for identifier, label in re.findall(
            r'<option\b[^>]*value="([^"]+)"[^>]*>(.*?)</option>', match[1], re.S)]


def census(towns):
    if (len(towns) != 311 or len({municipality(t) for t in towns}) != 311
            or "barcelona" not in {municipality(t) for t in towns}):
        raise ValueError("Censo municipal COFB no contrastado: se esperan 311 municipios únicos.")
    return {municipality(town): town for town in towns}


def discover():
    content = request(SOURCE).decode("utf-8")
    towns = [option["nombre"] for option in select(content, "municipi")]
    census(towns)
    regions = select(content, "regionId")
    if len(regions) != 6:
        raise ValueError("Las seis regiones del catálogo público COFB han cambiado.")
    form = re.search(r'<form\b[^>]*name="cofbpharmacysearch_form_sector_abs".*?</form>',
                     content, re.S)
    action = re.search(r'\baction="([^"]+)"', form[0]) if form else None
    token = re.search(r'name="cofbpharmacysearch_csrf"\s+value="([^"]+)"', content)
    if (not action or html.unescape(action[1]) != "https://www.cofb.org/wp-admin/admin-post.php"
            or not token or 'value="cofbpharmacysearch_print_report"' not in form[0]):
        raise ValueError("Formulario público COFB no reconocible.")
    return towns, regions, html.unescape(action[1]), html.unescape(token[1])


def duty_evidence():
    official = request(DUTY_SOURCE).decode("utf-8")
    if not re.search(r'href="https://www\.farmaguia\.net/?["/]', official):
        raise ValueError("El COFB ya no identifica Farmaguia como buscador oficial.")
    content = request(MOBILE).decode("utf-8")
    scripts = re.findall(r'<script\b[^>]*src="([^"]*assets/js/advancedSearch\.js[^"]*)"',
                         content)
    if len(scripts) != 1:
        raise ValueError("Cliente público Farmaguia no reconocible; no se consulta su API.")
    url = urllib.parse.urljoin(MOBILE, html.unescape(scripts[0]))
    if urllib.parse.urlparse(url).netloc != "mobi.farmaguia.net":
        raise ValueError("Cliente Farmaguia fuera del dominio oficial.")
    script = request(url).decode("utf-8")
    if not re.search(r'executeGRecaptchaAction\(["\']advancedSearch["\']', script):
        raise ValueError("Protección Farmaguia cambiada; requiere nueva investigación del cliente público.")
    return {"estado": "bloqueado_recaptcha", "fuente_cofb": DUTY_SOURCE,
            "formulario": MOBILE, "cliente_publico": url.split("?")[0],
            "api_protegida_consultada": False, "error": BLOCKER}


def parse_pdf(text, regional=True):
    if "COL·LEGI DE FARMACÈUTICS DE BARCELONA" not in text:
        raise ValueError("PDF sin cabecera oficial COFB.")
    rows = []
    for line in text.splitlines():
        match = ROW.fullmatch(line)
        if match:
            identifier, name, address, postcode, town, phone = match.groups()
            rows.append({"id": f"cof-barcelona-{identifier}", "nombre": name,
                         "direccion": address, "codigo_postal": postcode,
                         "localidad": town, "telefono": phone, "provincia": "Barcelona",
                         "guardia": False, "lat": None, "lng": None, "fuente": SOURCE})
        elif re.match(r"^\s*\d+\s+", line):
            raise ValueError(f"Fila de farmacia COFB no reconocible: {line.strip()}")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Identificadores duplicados en PDF COFB.")
    if regional:
        totals = re.findall(r"Total farmàcies de la regió [^\n]*:\s*(\d+)", text)
        if len(totals) != 1 or int(totals[0]) != len(rows):
            raise ValueError(f"Total regional COFB no coincide con {len(rows)} registros extraídos.")
    return rows


def pdf_report(cache, filename, url, fields):
    data = request(url, fields)
    if not data.startswith(b"%PDF-"):
        raise ValueError("El formulario COFB no devuelve un PDF; no se publica un catálogo incompleto.")
    path = cache / filename
    path.write_bytes(data)
    subprocess.run(["pdftotext", "-layout", str(path), str(path.with_suffix(".txt"))],
                   check=True, capture_output=True)
    return path.with_suffix(".txt").read_text()


def catalogue(documents, towns, memberships):
    groups = census(towns)
    result = {}
    for document in documents:
        for row in parse_pdf(document):
            prior = result.get(row["id"])
            if prior and prior != row:
                raise ValueError(f"Farmacia contradictoria entre regiones: {row['id']}")
            result[row["id"]] = row
    if not result:
        raise ValueError("Catálogo COFB vacío.")
    verified = {}
    for town, document in memberships.items():
        if municipality(town) not in groups:
            raise ValueError(f"Consulta de municipio fuera del censo: {town}")
        if f"Municipi: {town}" not in document:
            raise ValueError(f"PDF municipal no identifica la consulta solicitada: {town}")
        for point in parse_pdf(document, regional=False):
            row = result.get(point["id"])
            if not row or row["direccion"] != point["direccion"]:
                raise ValueError("La consulta municipal no coincide con el catálogo regional.")
            prior = verified.get(point["id"])
            if prior and prior != town:
                raise ValueError(f"Farmacia asignada a dos municipios: {point['id']}")
            verified[point["id"]] = town
    for row in result.values():
        original = row["localidad"]
        town = verified.get(row["id"]) or groups.get(municipality(original))
        row["localidad_original"] = original
        if town:
            row["localidad"] = town
            row["municipio_cofb"] = town
            row["municipio_verificado_pdf"] = row["id"] in verified
        else:
            row["municipio_pendiente"] = True
    return list(result.values())


def reports_for(towns, points, target, evidence):
    census(towns)
    return [{"nombre": town, "estado": "error", "error": evidence["error"],
             "motivo_sin_datos": evidence["estado"], "fecha_evaluada": target.isoformat(),
             "farmacias": 0, "farmacias_catalogo": sum(
                 p.get("municipio_cofb") == town for p in points),
             "consulta_guardia_realizada": False, "derivacion_oficial_confirmada": False,
             "metodo": "Censo municipal y evaluación de los seis PDF regionales COFB; guardias protegidas",
             "recurso_consultado": SOURCE, "fuente_guardias": MOBILE}
            for town in towns]


def run(target, cache, offline=False, use_geocoder=False, allow_address=False):
    cache.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    towns, points = [], []
    try:
        if offline:
            manifest = json.loads((cache / "indice.json").read_text())
            if manifest["fecha_consulta"] != target.isoformat():
                raise ValueError("La captura COFB no corresponde al día solicitado.")
            towns = manifest["municipios"]
            documents = [(cache / name).read_text() for name in manifest["documentos_regionales"]]
            memberships = {town: (cache / name).read_text()
                           for town, name in manifest["documentos_municipales"].items()}
            evidence = manifest["guardias"]
        else:
            acquired = datetime.now(TZ)
            if target != acquired.date():
                raise ValueError("La captura del catálogo actual solo admite hoy; use una captura fechada.")
            towns, regions, url, token = discover()
            documents, filenames, memberships, municipal_files = [], [], {}, {}
            base = {"cofbpharmacysearch_csrf": token,
                    "action": "cofbpharmacysearch_print_report"}
            for region in regions:
                filename = f"{target}-region-{slugify(region['id'])}.pdf"
                text = pdf_report(cache, filename, url, {
                    **base, "id": "reg_sec_abs", "regionId": region["id"],
                    "sectorId": "", "absId": ""})
                parse_pdf(text)
                documents.append(text)
                filenames.append(str(Path(filename).with_suffix(".txt")))
            provisional = catalogue(documents, towns, {})
            if any(p.get("municipio_pendiente") for p in provisional):
                for town in VERIFICATION_TOWNS:
                    if town not in towns:
                        raise ValueError(f"Municipio de verificación ausente del selector: {town}")
                    filename = f"{target}-municipio-{slugify(town)}.pdf"
                    memberships[town] = pdf_report(cache, filename, url, {
                        **base, "id": "mun_cp", "municipi": town, "cp": ""})
                    municipal_files[town] = str(Path(filename).with_suffix(".txt"))
            points = catalogue(documents, towns, memberships)
            evidence = duty_evidence()
            if datetime.now(TZ).date() != acquired.date():
                raise ValueError("Consulta atravesó medianoche; repetir con la fecha correcta.")
            manifest = {"fecha_consulta": target.isoformat(), "consultado": acquired.isoformat(),
                        "municipios": towns, "regiones": regions,
                        "documentos_regionales": filenames,
                        "documentos_municipales": municipal_files, "guardias": evidence}
            write_json(cache / "indice.json", manifest)
        points = catalogue(documents, towns, memberships)
        locate_and_catalogue(points, "Barcelona", use_geocoder=use_geocoder,
                             allow_address=allow_address)
        reports = reports_for(towns, points, target, evidence)
        publish(target, "Barcelona", DUTY_SOURCE, [], reports)
        path = OUT_DIR / f"cobertura-barcelona-{target}.json"
        coverage = json.loads(path.read_text())
        coverage.update(consultado=manifest["consultado"], captura_sin_red=offline,
                        municipios_censados=len(towns), regiones_consultadas=len(documents),
                        consultas_municipales_catalogo=len(memberships),
                        farmacias_catalogo=len(points), catalogo_con_coordenadas=sum(
                            bool(coordinates(p)) for p in points),
                        farmacias_municipio_pendiente=sum(
                            bool(p.get("municipio_pendiente")) for p in points),
                        municipios_con_registros_catalogo=sum(
                            r["farmacias_catalogo"] > 0 for r in reports),
                        fuente_catalogo=SOURCE, evidencia_guardias=evidence,
                        limitacion=BLOCKER + " Los 311 municipios están censados, no consultados para guardias. "
                        "Las localidades sin registros propios no acreditan ausencia de farmacia o derivación comarcal.")
        write_json(path, coverage)
        print(f"Barcelona: catálogo COFB de {len(points)} farmacias; guardias bloqueadas por reCAPTCHA.",
              flush=True)
        return False
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        evidence = {"estado": "error_fuente", "error": str(error)}
        if not towns and (cache / "indice.json").exists():
            try:
                towns = json.loads((cache / "indice.json").read_text())["municipios"]
            except (OSError, ValueError, KeyError, TypeError):
                pass
        try:
            reports = reports_for(towns, points, target, evidence)
        except (ValueError, TypeError):
            reports = [{"nombre": "Catálogo provincial COFB", "estado": "error", "error": str(error)}]
        publish(target, "Barcelona", DUTY_SOURCE, [], reports)
        print(f"ERROR Barcelona: {error}", flush=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path("data/barcelona-cache"))
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite --geocode")
    raise SystemExit(0 if run(args.fecha, args.cache_documentos, args.sin_red,
                             args.geocode, args.permitir_direccion_exacta) else 1)
