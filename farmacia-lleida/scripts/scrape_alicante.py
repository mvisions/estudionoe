#!/usr/bin/env python3
"""Import the COF Alicante's public annual on-call spreadsheet."""
import argparse
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo

from provincial_catalog import locate_and_catalogue, publish
from scrape_mes import fetch
from scrape_palencia import consolidate

SOURCE = "https://cofalicante.com/farmacias-de-guardia/"
TZ = ZoneInfo("Europe/Madrid")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
HEADERS = ["FECHA", "ZONA", "NOMBRE ZONA", "TURNO", "Nº FARMACIA",
           "NOMBRE FARMACIA", "DIRECCIÓN", "MUNICIPIO", "HORARIO"]


def spreadsheet_url(content, year):
    links = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', content, re.I):
        url = urllib.parse.urljoin(SOURCE, href)
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname in ("cofalicante.com", "www.cofalicante.com")
                and parsed.path == f"/ficheros/farmaciasguardia/guardias{year}.xlsx"):
            links.add(url)
    if len(links) != 1:
        raise ValueError("No se encontró un único Excel oficial del año solicitado.")
    return links.pop()


def intervals(day, hours):
    parts = re.split(r"\s+y\s+", hours.strip(), flags=re.I)
    result = []
    for part in parts:
        match = re.fullmatch(r"[Dd]e (\d{1,2}:\d{2}) a (\d{1,2}:\d{2})", part.strip())
        if not match:
            raise ValueError(f"Horario oficial no reconocible: {hours}")
        start, finish = [datetime.combine(day, datetime.strptime(value, "%H:%M").time()).replace(tzinfo=TZ)
                         for value in match.groups()]
        if finish <= start:
            finish += timedelta(days=1)
        if result and start < result[-1][1]:
            raise ValueError(f"Franjas oficiales solapadas o desordenadas: {hours}")
        result.append((start, finish))
    return result


def parse_workbook(content, target, source):
    with ZipFile(io.BytesIO(content)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        properties = workbook.find("s:workbookPr", NS)
        if properties is not None and properties.get("date1904") not in (None, "0", "false"):
            raise ValueError("El Excel usa una época de fechas no admitida.")
        sheets = workbook.findall("s:sheets/s:sheet", NS)
        if len(sheets) != 1 or sheets[0].get("name") != "Guardias":
            raise ValueError("El Excel no contiene una única hoja Guardias.")
        relation_id = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation = next((item for item in relations if item.get("Id") == relation_id), None)
        if relation is None or relation.get("TargetMode") == "External":
            raise ValueError("Hoja Guardias sin relación interna verificable.")
        path = relation.get("Target", "")
        path = path.lstrip("/") if path.startswith("/") else "xl/" + path
        if not re.fullmatch(r"xl/worksheets/[^/]+\.xml", path):
            raise ValueError("Ruta de hoja Excel no admitida.")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in
                       ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet = ET.fromstring(archive.read(path))
        table = []
        for row in sheet.findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row:
                reference = re.fullmatch(r"([A-I])\d+", cell.get("r", ""))
                if not reference or cell.find("s:f", NS) is not None:
                    raise ValueError("Celda o fórmula no admitida en el calendario.")
                kind = cell.get("t")
                if kind == "inlineStr":
                    inline = cell.find("s:is", NS)
                    if inline is None:
                        raise ValueError("Celda de texto sin contenido verificable.")
                    value = "".join(inline.itertext())
                elif kind in (None, "n", "s"):
                    value = cell.findtext("s:v", "", NS)
                    if kind == "s":
                        value = strings[int(value)]
                else:
                    raise ValueError("Tipo de celda no admitido en el calendario.")
                column = reference.group(1)
                if column in cells:
                    raise ValueError("Columna duplicada en el calendario.")
                cells[column] = value.strip()
            if set(cells) != set("ABCDEFGHI"):
                raise ValueError("Fila incompleta en el calendario.")
            table.append([cells[column] for column in "ABCDEFGHI"])
    if not table or table[0] != HEADERS:
        raise ValueError("Cabeceras del Excel oficial no reconocibles.")
    directory, duties, dates, towns = {}, [], set(), set()
    beginning = datetime.combine(target, datetime.min.time()).replace(tzinfo=TZ)
    ending = beginning + timedelta(days=1)
    for values in table[1:]:
        serial, zone, _, shift, identifier, name, address, town, hours = values
        if not serial.isdigit() or int(serial) <= 60:
            raise ValueError("Fecha Excel inválida.")
        day = date(1899, 12, 30) + timedelta(days=int(serial))
        if day.year != target.year:
            raise ValueError("El Excel contiene fechas de otro año.")
        if not re.fullmatch(r"\d+", identifier) or not all((name, address, town, zone, shift)):
            raise ValueError("Farmacia del calendario sin identidad o localidad verificable.")
        pharmacy = {"id": f"cof-alicante-{identifier}", "cofa_id": identifier, "nombre": name,
                    "direccion": address, "localidad": town, "provincia": "Alicante",
                    "fuente": source, "lat": None, "lng": None, "guardia": False}
        if identifier in directory and directory[identifier] != pharmacy:
            raise ValueError("Un identificador de farmacia tiene varias direcciones o titulares.")
        directory[identifier] = pharmacy
        dates.add(day)
        towns.add(town)
        for start, finish in intervals(day, hours):
            if start >= ending or finish <= beginning:
                continue
            start = max(start, beginning)
            label = f"Guardia COFA · {start:%d/%m %H:%M}–{finish:%d/%m %H:%M}"
            duties.append({**pharmacy, "guardia": True, "fecha_guardia": str(target),
                           "localidades_atendidas": [town], "guardia_franja": label,
                           "guardia_franjas": [label], "guardia_intervalos": [
                               {"inicio": start.isoformat(), "fin": finish.isoformat()}]})
    if target not in dates or (
        (target.month != 1 or target.day != 1) and target - timedelta(days=1) not in dates
    ):
        raise ValueError("El Excel no confirma el día solicitado y su madrugada anterior.")
    confirmed = consolidate(duties)
    reports = [{"nombre": town, "estado": "parcial",
                "farmacias": sum(row["localidad"] == town for row in confirmed),
                "error": "Excel anual interpretado; no acredita un censo completo ni todas las derivaciones rurales. "
                         "Confirmar posibles cambios y guardias localizadas por teléfono."}
               for town in sorted(towns)]
    if target.month == 1 and target.day == 1:
        reports.append({"nombre": "Madrugada anterior", "estado": "error",
                        "error": "El Excel anual no acredita la noche del 31 de diciembre del año anterior."})
    return list(directory.values()), confirmed, reports


def run(target, cache, offline=False, resume=False, geocode=False, allow_address=False):
    cache.mkdir(parents=True, exist_ok=True)
    reports, rows = [], []
    try:
        index = cache / f"indice-{target.year}.html"
        if offline or resume and index.exists():
            content = index.read_text()
        else:
            content = fetch(SOURCE)
            index.write_text(content)
        source = spreadsheet_url(content, target.year)
        path = cache / f"guardias{target.year}.xlsx"
        if offline or resume and path.exists():
            document = path.read_bytes()
        else:
            request = urllib.request.Request(source, headers={"User-Agent": "FarmaciasDeGuardiaTracker/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                document = response.read()
            path.write_bytes(document)
        directory, rows, reports = parse_workbook(document, target, source)
        locate_and_catalogue(directory, "Alicante")
        locate_and_catalogue(rows, "Alicante", use_geocoder=geocode, allow_address=allow_address)
        publish(target, "Alicante", SOURCE, rows, reports)
        print(f"Alicante: {len(directory)} farmacias y {len(reports)} localidades observadas en el Excel.", flush=True)
    except (OSError, ValueError, KeyError, TypeError, IndexError, BadZipFile, ET.ParseError) as error:
        print(f"ERROR Alicante: {error}", flush=True)
        publish(target, "Alicante", SOURCE, rows,
                reports + [{"nombre": "Fuente provincial", "estado": "error", "error": str(error)}])
    return False


def main():
    parser = argparse.ArgumentParser(description="Excel anual oficial de guardias de Alicante.")
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(TZ).date())
    parser.add_argument("--cache-documentos", type=Path, default=Path.home() / ".local/state/farmacia/alicante")
    parser.add_argument("--sin-red", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--permitir-direccion-exacta", action="store_true")
    args = parser.parse_args()
    if args.sin_red and args.geocode:
        parser.error("--sin-red no permite geocodificación.")
    return 0 if run(args.fecha, args.cache_documentos, args.sin_red, args.reanudar,
                    args.geocode, args.permitir_direccion_exacta) else 1


if __name__ == "__main__":
    raise SystemExit(main())
