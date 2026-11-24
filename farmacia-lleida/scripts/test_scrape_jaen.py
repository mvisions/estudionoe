import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scrape_jaen as scraper


TARGET = scraper.date(2026, 11, 1)


def pharmacy(number, street, city="Jaén", owner="Ana Pérez García"):
    return {"id": f"cof-jaen-{number}", "nombre": owner, "direccion": street,
            "localidad": city, "provincia": "Jaén", "telefono": "953000001",
            "lat": None, "lng": None, "guardia": False}


def line(text, x, y, right=None):
    return {"text": text, "x": x, "y": y, "right": right if right is not None else x+15}


class JaenTests(unittest.TestCase):
    def test_official_catalogue_extracts_phone_city_and_directory_number(self):
        content = """<h4>1 FARMACIAS ENCONTRADAS:</h4><div class="card mt-2">
        <div>Nº Farmacia: 7</div><div>Propietario</div><div>Ana García Pérez</div>
        <div>Datos farmacia</div><div class="row">
        <div class="col-8 p-0">NUEVA, 2</div>
        <div class="col-4 p-0">Teléfono: 953000001</div></div>
        <div class="row"><div class="col-8 p-0">Población: BEDMAR</div>
        <div class="col-4 p-0">Cod. postal: 23537</div></div></div>"""
        rows, total = scraper.parse_catalogue(content)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["id"], "cof-jaen-7")
        self.assertEqual(rows[0]["localidad"], "Bedmar")
        self.assertEqual(rows[0]["telefono"], "953000001")
        with self.assertRaises(ValueError):
            scraper.parse_catalogue("<h4>Sin resultados</h4>")

    def test_monthly_cell_requires_matching_year_weekday_and_readable_identity(self):
        directory = [pharmacy(1, "Nueva, 2", "Bedmar")]
        page = {"width":800, "lines":[line("NOVIEMBRE 2026", 200, 20),
                                     line("LUNES", 30, 55)]}
        page["lines"].extend(line(str(day), 50+100*((day+5)%7), 80+100*((day+5)//7)) for day in range(1,31))
        page["lines"].append(line("C/Nueva 2", 620, 100))
        rows = scraper.parse_month_cells([page], TARGET, "Bedmar", "official", directory)
        self.assertEqual([r["id"] for r in rows], ["cof-jaen-1"])
        self.assertEqual(scraper.parse_month_cells([page], scraper.date(2025,11,1), "Bedmar", "official", directory), [])
        page["lines"].pop()
        with self.assertRaisesRegex(ValueError, "colores"):
            scraper.parse_month_cells([page], TARGET, "Bedmar", "official", directory)

    def test_monthly_document_precedes_annual_but_never_other_year_or_month(self):
        rows = [{"anio": 2026, "mes": 11, "url": "monthly"},
                {"anio": 2026, "mes": None, "url": "annual"},
                {"anio": 2025, "mes": 11, "url": "old"},
                {"anio": 2026, "mes": 10, "url": "october"}]
        self.assertEqual(scraper.choose_documents(rows, TARGET), rows[:1])
        self.assertEqual(scraper.choose_documents(rows[1:], TARGET), rows[1:2])
        self.assertEqual(scraper.choose_documents(rows[2:], TARGET), [])

    def test_capital_day_and_night_columns_are_merged_without_losing_contacts(self):
        directory = [pharmacy(1, "Alameda, 4"), pharmacy(2, "Andalucía, 32"),
                     pharmacy(3, "Priego, 45"), pharmacy(4, "Madrid, 72")]
        page = {"width": 600, "lines": [
            line("JAÉN – NOVIEMBRE 2026", 40, 20),
            line("DIURNA (9.30 h a 22:00 h.)", 159, 157, 316),
            line("NOCTURNA (22:00 h. a 9:30 h.)", 363, 157, 546),
            line("Alameda nº 4", 145, 178), line("Andalucía nº 32", 345, 178),
            line("1", 60, 189), line("Domingo", 81, 189, 125),
            line("Andalucía nº 32", 145, 190), line("Madrid nº 72", 345, 190),
            line("Priego nº 45", 145, 202),
            line("2", 60, 225), line("Lunes", 81, 225, 125),
        ]}
        rows = scraper.merge(scraper.parse_capital([page], TARGET, "official", directory))
        self.assertEqual(len(rows), 4)
        shared = next(v for v in rows if v["id"]=="cof-jaen-2")
        self.assertEqual(len(shared["guardia_franjas"]), 2)
        self.assertEqual(shared["telefono"], "953000001")
        self.assertEqual(scraper.parse_capital([page], scraper.date(2025, 11, 1), "official", directory), [])
        self.assertEqual(scraper.parse_capital([page], scraper.date(2026, 10, 1), "official", directory), [])

    def test_sunday_belongs_to_october_week_not_first_november_week(self):
        directory = [pharmacy(1, "Andalucía, 58", "Arjonilla"),
                     pharmacy(2, "Andalucía, 1", "Arjonilla")]
        page = {"width": 600, "lines": [
            line("Guardia de 24 horas", 280, 10),
            line("octubre-26 28", 30, 30),
            line("29 30 1 2 3 4 Andalucía 1", 100, 30),
            line("5 6 7 8 9 10 11 Andalucía 1", 80, 45),
            line("12 13 14 15 16 17 18 Andalucía 1", 80, 60),
            line("19 20 21 22 23 24 25 Andalucía 1", 80, 75),
            line("26 27 28 29 30 31 1 Andalucía 58", 80, 90),
            line("noviembre-26 2", 30, 105),
            line("3 4 5 6 7 8 Andalucía 1", 100, 105),
        ]}
        rows = scraper.parse_week_grid([page], TARGET, "Arjonilla", "official", directory)
        self.assertEqual([v["id"] for v in rows], ["cof-jaen-1"])
        self.assertIn("2026-10-26", rows[0]["guardia_franja"])
        self.assertEqual(scraper.parse_week_grid([page], scraper.date(2025, 11, 1), "Arjonilla", "official", directory), [])

    def test_ambiguous_identity_is_not_selected_and_referral_uses_actual_city(self):
        row = pharmacy(1, "Nueva, 2", "Bedmar", "Ana Díez Sánchez")
        result = scraper.duty("BEDMAR (DIEZ)", "Jimena", "24 horas", TARGET, "official", [row])
        self.assertEqual(result["localidad"], "Bedmar")
        self.assertEqual(result["localidades_atendidas"], ["Jimena"])
        with self.assertRaises(ValueError):
            scraper.resolve_label("BEDMAR (DIEZ)", "Jimena", [row, {**row, "id":"other"}])
        with self.assertRaises(ValueError):
            scraper.resolve_label("Servicios localizables", "Jimena", [row])

    def test_single_distinctive_word_identifies_unique_pharmacy(self):
        rows = [pharmacy(1, "Julio Burell, 41", "Baeza", "Luis Lorite Moreno"),
                pharmacy(2, "Puche Pardo, 6", "Baeza", "Farmacia La Muralla")]
        # Only the second pharmacy contains the distinctive token "muralla".
        resolved = scraper.resolve_label("FARMACIA LA FARMACIA LA FARMACIA LA MURALLA",
                                       "Baeza", rows)
        self.assertEqual(resolved["id"], "cof-jaen-2")

    def test_verified_nickname_maps_alcaudete_apodos(self):
        directory = [
            pharmacy(4, "PLAZA 28 DE FEBRERO, S/N", "Alcaudete", "Battikhi Prados, Yusef"),
            pharmacy(5, "EL CARMEN, 69", "Alcaudete", "Gonzalez Gonzalez, Rafael"),
            pharmacy(222, "AVDA. ANDALUCIA, 18", "Alcaudete", "Barea Cano, Lidia"),
            pharmacy(306, "ZAGALES, 14", "Alcaudete", "Serrano Maestre, Maria del Carmen"),
        ]
        self.assertEqual(scraper.resolve_label("FARMACIA LA MURALLA", "Alcaudete", directory)["id"], "cof-jaen-5")
        self.assertEqual(scraper.resolve_label("FARMACIA EL BIGOTE", "Alcaudete", directory)["id"], "cof-jaen-222")
        self.assertEqual(scraper.resolve_label("FARMACIA LA PLAZA", "Alcaudete", directory)["id"], "cof-jaen-4")
        self.assertEqual(scraper.resolve_label("FARMACIA ZAGALES", "Alcaudete", directory)["id"], "cof-jaen-306")

    def test_source_address_discrepancy_is_visible_not_silently_rewritten(self):
        row = pharmacy(1, "Julio Burell, 41", "Baeza", "Luis Lorite Moreno")
        result = scraper.duty("LDO. LORITE C/JULIO BUREL, Nº35", "Baeza", "Guardia", TARGET, "official", [row])
        self.assertIn("35", result["nota_ubicacion"])
        self.assertIn("41", result["nota_ubicacion"])
        self.assertIsNone(result["lat"])

    def test_exact_full_date_never_rotates_other_day(self):
        row = pharmacy(1, "Tarifa, 27", "Jódar", "Josefa Herrera Rodríguez")
        page = {"width":600, "lines":[line("DOMINGO 01/11/2026", 40, 80),
                                     line("Josefa Herrera Rodríguez, C/Tarifa 27", 220, 80)]}
        rows = scraper.parse_dated_lists([page], TARGET, "Jódar", "official", [row])
        self.assertEqual([v["id"] for v in rows], [row["id"]])
        self.assertEqual(scraper.parse_dated_lists([page], scraper.date(2026, 11, 2), "Jódar", "official", [row]), [])

    def test_failed_refresh_preserves_dated_calendar_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(scraper, "OUT_DIR", Path(folder)):
            path = Path(folder)/"guardias-jaen-2026-11-01.json"
            saved = scraper.duty("C/Alameda 4", "Jaén", "24 horas", TARGET, "official", [pharmacy(1, "Alameda, 4")])
            scraper.write_json(path, [saved])
            before = path.read_bytes()
            complete = scraper.publish(TARGET, [], [{"nombre":"Jaén", "estado":"error"}], [])
            self.assertFalse(complete)
            self.assertEqual(path.read_bytes(), before)
            report = json.loads((Path(folder)/"cobertura-jaen-2026-11-01.json").read_text())
            self.assertFalse(report["completa"])
            self.assertFalse(report["calendario_actualizado"])
            self.assertEqual(report["farmacias"], 1)

    def test_partial_refresh_updates_confirmed_town_and_preserves_missing_one(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(scraper, "OUT_DIR", Path(folder)):
            path = Path(folder)/"guardias-jaen-2026-11-01.json"
            directory = [pharmacy(1, "Alameda, 4"), pharmacy(2, "Nueva, 2", "Bedmar"),
                         pharmacy(3, "Madrid, 72")]
            old = [scraper.duty("Alameda 4", "Jaén", "24 horas", TARGET, "old", directory),
                   scraper.duty("Nueva 2", "Bedmar", "24 horas", TARGET, "old", directory)]
            scraper.write_json(path, old)
            fresh = [scraper.duty("Madrid 72", "Jaén", "24 horas", TARGET, "new", directory)]
            scraper.publish(TARGET, fresh, [{"nombre":"Jaén","estado":"disponible"},
                                            {"nombre":"Bedmar","estado":"pendiente_pdf"}], [])
            self.assertEqual({v["id"] for v in json.loads(path.read_text())}, {"cof-jaen-2","cof-jaen-3"})

    def test_geocoder_rejects_generic_streets_and_ambiguous_pharmacies(self):
        row = pharmacy(1, "Alameda, 4")
        item = {"type":"pharmacy", "lat":"37.78", "lon":"-3.78", "osm_type":"node", "osm_id":1,
                "address":{"city":"Jaén", "road":"Alameda", "house_number":"4"}}
        with patch.object(scraper, "request", return_value=json.dumps([item]).encode()):
            self.assertTrue(scraper.valid_coordinates(scraper.geocode(row)))
        for candidates in [[{**item, "type":"residential"}], [{**item, "address":{}}],
                           [item, {**item, "osm_id":2}]]:
            with patch.object(scraper, "request", return_value=json.dumps(candidates).encode()):
                self.assertIsNone(scraper.geocode(row))
        self.assertFalse(scraper.valid_coordinates({"lat":0,"lng":0}))
        self.assertFalse(scraper.valid_coordinates({"lat":True,"lng":-3.8}))


if __name__ == "__main__":
    unittest.main()
