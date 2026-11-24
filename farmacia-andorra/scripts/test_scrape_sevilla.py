import unittest
import hashlib
import json
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch

from scrape_sevilla import REVIEWED_COORDINATES, MunicipalIndex, apply_reviewed_location, locate_saved, make_pharmacy, merge_records, normalize_municipalities, parse_capital, parse_document, parse_grid, parse_single, prepare_document, publish_day, quarter_dates, refresh_saved_coordinates, reviewed_records, saved_address_signature, street_query


def line(text, x, y, right=None):
    return {"text": text, "x": x, "y": y, "right": right if right is not None else x+100}


class SevillaTests(unittest.TestCase):
    def test_reviewed_points_have_unique_id_and_traceable_evidence(self):
        rows = json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 23)
        self.assertEqual(len({row["id"] for row in rows}), 23)
        for row in rows:
            with self.subTest(id=row["id"]):
                self.assertTrue(36.8 < row["lat"] < 38.3)
                self.assertTrue(-6.6 < row["lng"] < -4.6)
                self.assertRegex(row["telefono"], r"^[69]\d{8}$")
                self.assertTrue(row["fuente"].startswith("https://"))
                self.assertTrue(row["evidencia"])

    def test_review_requires_unchanged_address_and_phone(self):
        review = json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))[0]
        reviews = {review["id"]: review}
        row = {"id": review["id"], "direccion": review["direccion"],
               "telefonos": [review["telefono"]], "lat": None, "lng": None}
        self.assertTrue(apply_reviewed_location(row, reviews))
        self.assertEqual(row["lat"], review["lat"])
        row["direccion"] = "Dirección nueva, 4"
        self.assertFalse(apply_reviewed_location(row, reviews))
        self.assertIsNone(row["lat"])
        self.assertNotIn("direccion_coordenadas", row)
        row["direccion"] = review["direccion"]
        row["telefonos"] = ["954000000"]
        self.assertFalse(apply_reviewed_location(row, reviews))

    def test_reviewed_time_annotations_are_accepted_without_changing_schedule(self):
        reviews = {r["id"]: r for r in json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))}
        for review in reviews.values():
            for address in review.get("direcciones_alternativas", []):
                with self.subTest(id=review["id"], address=address):
                    row = {"id": review["id"], "direccion": address, "telefonos": [review["telefono"]],
                           "lat": None, "lng": None, "guardia_franjas": ["Día"]}
                    self.assertTrue(apply_reviewed_location(row, reviews))
                    self.assertEqual(row["direccion_coordenadas"], address)
                    self.assertEqual(row["direccion"], address)
                    self.assertEqual(row["guardia_franjas"], ["Día"])

    def test_review_overrides_catalogue_but_changed_address_cannot_reuse_it(self):
        review = json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))[0]
        row = {"id": review["id"], "direccion": review["direccion"],
               "telefonos": [review["telefono"]], "localidad": "Gines", "lat": None, "lng": None}
        with tempfile.TemporaryDirectory() as directory, patch("scrape_sevilla.OUT_DIR", Path(directory)):
            old = {**row, "lat": 37.5, "lng": -5.5}
            (Path(directory) / "farmacias-sevilla.json").write_text(json.dumps([old]))
            locate_saved([row])
            self.assertEqual(row["lat"], review["lat"])
            row.update({"direccion": "Dirección nueva, 4", "lat": None, "lng": None})
            locate_saved([row])
            self.assertIsNone(row["lat"])

    def test_refresh_preserves_schedules_and_updates_daily_and_quarter_counts(self):
        review = json.loads(REVIEWED_COORDINATES.read_text(encoding="utf-8"))[0]
        row = {"id": review["id"], "direccion": review["direccion"],
               "telefonos": [review["telefono"]], "lat": None, "lng": None,
               "guardia": True, "fecha_guardia": "2026-11-01", "guardia_franjas": ["Noche"]}
        with tempfile.TemporaryDirectory() as directory, patch("scrape_sevilla.OUT_DIR", Path(directory)):
            root = Path(directory)
            calendar = root / "guardias-sevilla-2026-11-01.json"
            report = root / "cobertura-sevilla-2026-11-01.json"
            quarter = root / "cobertura-sevilla-2026-T4.json"
            calendar.write_text(json.dumps([row]))
            report.write_text(json.dumps({"completa": False, "con_coordenadas": 0}))
            quarter.write_text(json.dumps({"fechas": [{"fecha": "2026-11-01", "con_coordenadas": 0}]}))
            self.assertEqual(refresh_saved_coordinates(), 1)
            saved = json.loads(calendar.read_text())[0]
            for field in ("guardia", "fecha_guardia", "guardia_franjas"):
                self.assertEqual(saved[field], row[field])
            self.assertEqual(json.loads(report.read_text()), {"completa": False, "con_coordenadas": 1})
            self.assertEqual(json.loads(quarter.read_text())["fechas"][0]["con_coordenadas"], 1)
            self.assertEqual(refresh_saved_coordinates(), 0)

    def test_quarter_has_all_92_days_and_no_dates_outside_it(self):
        days = quarter_dates(2026, 4)
        self.assertEqual(len(days), 92)
        self.assertEqual(days[0], date(2026, 10, 1))
        self.assertEqual(days[-1], date(2026, 12, 31))
        self.assertEqual(len(set(days)), 92)
        self.assertEqual(len(quarter_dates(2024, 1)), 91)

    def test_prepared_pdf_pages_do_not_require_another_conversion(self):
        page = {"lines": [
            line("Farmacias de Guardia de CARMONA desde 26-oct-2026 hasta el 01-nov-2026", 30, 10),
            line("DOMINGO 1", 30, 50), line("Día (de 9:30 a 22:00)", 30, 60),
            line("Ŀ\x03Santa Ana, 2 (954145553)", 60, 70),
        ]}
        with patch("scrape_sevilla.pdf_pages") as convert:
            rows = parse_document(b"%PDF-public", date(2026, 11, 1), "official.pdf", [page])
            convert.assert_not_called()
        self.assertEqual(len(rows), 1)

    def test_cache_refetches_source_but_only_reconverts_changed_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch("scrape_sevilla.public_request", side_effect=[b"%PDF-a", b"%PDF-a", b"%PDF-b"]) as fetch, \
                 patch("scrape_sevilla.pdf_pages", side_effect=[[{"lines": []}], [{"lines": [line("new", 1, 1)]}]]) as convert:
                first = prepare_document(None, "https://example.org/T4/source.pdf", cache=cache)
                second = prepare_document(None, "https://example.org/T4/source.pdf", cache=cache)
                third = prepare_document(None, "https://example.org/T4/source.pdf", cache=cache)
                self.assertEqual(fetch.call_count, 3)
                self.assertEqual(convert.call_count, 2)
                self.assertEqual(first["pages"], second["pages"])
                self.assertNotEqual(second["pages"], third["pages"])

    def test_partial_day_does_not_replace_existing_and_empty_day_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory, patch("scrape_sevilla.OUT_DIR", Path(directory)):
            path = Path(directory) / "guardias-sevilla-2026-11-01.json"
            path.write_text('[{"id":"previous"}]')
            row = make_pharmacy("Real, 2 (954111111)", "Camas", "Día", date(2026, 11, 1), "official.pdf")
            report = publish_day(date(2026, 11, 1), [row], [{"estado": "sin_fecha"}], [])
            self.assertFalse(report["calendario_actualizado"])
            self.assertEqual(json.loads(path.read_text()), [{"id": "previous"}])
            empty = publish_day(date(2026, 12, 31), [], [{"estado": "sin_fecha"}], [])
            self.assertFalse(empty["completa"])
            self.assertFalse((Path(directory) / "guardias-sevilla-2026-12-31.json").exists())
            self.assertTrue((Path(directory) / "cobertura-sevilla-2026-12-31.json").exists())

    def test_index_preserves_municipalities_and_quarter_document_namespaces(self):
        parser = MunicipalIndex()
        parser.feed('<table><tr><td>Écija</td><td>Écija</td>'
                    '<td><a href="https://x/images/farmaciasguardia/T1/ecija.pdf">PDF</a></td>'
                    '<td></td><td></td><td><a href="https://x/images/farmaciasguardia/T4/ecija.pdf">PDF</a></td>'
                    '</tr></table>')
        self.assertEqual(len(parser.rows), 1)
        self.assertEqual(parser.rows[0]["municipio"], "Écija")
        self.assertIn("/T4/", parser.rows[0]["trimestres"][3][0])

    def test_week_crosses_month_boundary_and_keeps_both_shifts(self):
        page = {"lines": [
            line("Farmacias de Guardia de CARMONA desde 26-oct-2026 hasta el 01-nov-2026", 30, 10),
            line("SÁBADO 31", 30, 20),
            line("Día (de 9:30 a 22:00)", 30, 30),
            line("Ŀ\x03Calle Vieja, 1 (954000001) - Otra farmacia", 60, 40),
            line("DOMINGO 1", 30, 50),
            line("Día (de 9:00 a 21:00)", 30, 60),
            line("Ŀ\x03Santa Ana, 2 (954145553) - Cecilia López", 60, 70),
            line("Noche (de 21:00 a 09:00)", 30, 80),
            line("Ŀ\x03Santa Ana, 2 (954145553) - Cecilia López", 60, 90),
        ]}
        rows = merge_records(parse_single(page, date(2026, 11, 1), "official.pdf"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["telefono"], "954145553")
        self.assertEqual(rows[0]["guardia_franjas"], ["Día (de 9:00 a 21:00)", "Noche (de 21:00 a 09:00)"])
        self.assertEqual(parse_single(page, date(2025, 11, 1), "official.pdf"), [])

    def test_capital_sunday_excludes_saturday_and_keeps_common_night(self):
        page = {"width": 1200, "lines": [
            line("LUNES A SÁBADO - SEMANA DEL 26 DE OCTUBRE DE 2026 AL 1 DE NOVIEMBRE DE 2026", 20, 65),
            line("URGENCIA DE NOCHE (de 22:00 a 9:30)", 320, 670),
            line("» Calle Sábado, 1 - T: 954111111 Sólo Sábado.", 30, 130),
            line("» Sólo Lunes. Calle Lunes, 1 - T: 954222222", 320, 700),
            line("» Sólo Domingo. Calle Domingo, 1 - T: 954333333", 320, 730),
            line("» Calle Común, 1 - T: 954444444", 600, 700),
            line("ZONA CENTRO", 900, 100),
            line("» Calle Día, 1 - T: 954555555", 900, 130),
        ]}
        rows = parse_capital(page, date(2026, 11, 1), "official.pdf")
        self.assertEqual({r["telefono"] for r in rows}, {"954333333", "954444444", "954555555"})
        self.assertEqual(next(r for r in rows if r["telefono"] == "954333333")["guardia_franja"], "Noche (de 22:00 a 9:30)")

    def test_grid_separates_dates_and_preserves_wrapped_addresses(self):
        page = {"width": 600, "lines": [
            line("sábado 31 octubre 2026", 100, 50, 200),
            line("domingo 1 noviembre 2026", 400, 50, 500),
            line("Día (de 9:30 a 22:00)", 20, 80),
            line("Camas", 20, 100), line("Real, 1 (954111111)", 110, 100),
            line("Día (de 9:30 a 22:00)", 320, 80),
            line("Villamanrique de la", 320, 100), line("Concejo, 2", 410, 100),
            line("Condesa", 320, 112), line("(955755535)", 410, 112),
        ]}
        rows = parse_grid(page, date(2026, 11, 1), "official.pdf")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["localidad"], "Villamanrique de la Condesa")
        self.assertEqual(rows[0]["direccion"], "Concejo, 2")

    def test_forwarded_guardia_uses_actual_locality_not_requesting_municipality(self):
        row = make_pharmacy("El Viso del Alcor - Manuel Jiménez Leon,81 (955.740.331) - Farmacia", "Mairena del Alcor",
                            "Noche", date(2026, 11, 1), "official.pdf")
        self.assertEqual(row["localidad"], "El Viso Del Alcor")
        self.assertEqual(row["telefono"], "955740331")

    def test_incomplete_source_phone_is_not_fabricated_and_can_merge_with_complete_day_record(self):
        day = make_pharmacy("Avenida Juan XXIII - T: 954 655 461", "Sevilla", "Día", date(2026, 11, 1), "official.pdf")
        night = make_pharmacy("Avenida Juan XXIII - T: 954 655 46", "Sevilla", "Noche", date(2026, 11, 1),
                              "official.pdf", allow_missing_phone=True)
        self.assertIsNone(night["telefono"])
        merged = merge_records([night, day])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["telefono"], "954655461")
        self.assertEqual(merged[0]["guardia_franjas"], ["Noche", "Día"])

    def test_special_hours_retained(self):
        row = make_pharmacy("(De 8:00 a 9:30 h) - Real, 2 (954111111)", "Camas", "Día (de 9:30 a 22:00)",
                            date(2026, 11, 1), "official.pdf")
        self.assertIn("De 8:00 a 9:30", row["guardia_franja"])

    def test_secondary_contact_not_misread_as_pharmacist_name(self):
        row = make_pharmacy("Bancos, 24 (954885076-619237676)", "Alanís", "Día",
                            date(2026, 11, 1), "official.pdf")
        self.assertEqual(row["telefonos"], ["954885076", "619237676"])
        self.assertEqual(row["nombre"], "")

    def test_poster_municipality_abbreviations_match_official_index(self):
        rows = [{"localidad": "Bollullos Mitación"}, {"localidad": "San Juan Aznalfarache"},
                {"localidad": "Valencina Concepción"}, {"localidad": "Sevilla"}]
        normalize_municipalities(rows, [
            {"municipio": "Bollullos de la Mitación"}, {"municipio": "San Juan de Aznalfarache"},
            {"municipio": "Valencina de la Concepción"},
        ])
        self.assertEqual(rows[0]["localidad"], "Bollullos de la Mitación")
        self.assertEqual(rows[1]["localidad"], "San Juan de Aznalfarache")
        self.assertEqual(rows[2]["localidad"], "Valencina de la Concepción")
        self.assertEqual(rows[3]["localidad"], "Sevilla")

    def test_street_queries_remove_directions_not_street_names_or_house_numbers(self):
        self.assertEqual(street_query("AMADOR DE LOS RIOS, 31. Entre Puerta Osario y Puerta Carmona"), "AMADOR DE LOS RIOS, 31")
        self.assertEqual(street_query("Avd.del Aljarafe, 70 Bajo B"), "Avenida del Aljarafe, 70")
        self.assertEqual(street_query("28 de Febrero, 4"), "28 de Febrero, 4")
        self.assertEqual(saved_address_signature("AMADOR DE LOS RIOS, 31. Entre Puerta Osario", "Sevilla"),
                         saved_address_signature("Calle Amador de los Ríos 31", "Sevilla"))
        self.assertNotEqual(saved_address_signature("Amador de los Ríos 31", "Sevilla"),
                            saved_address_signature("Amador de los Ríos 32", "Sevilla"))

    def test_visual_transcription_is_bound_to_exact_date_and_document_fingerprint(self):
        content = b"verified public document"
        review = {
            "documento": "official.pdf", "fecha": "2026-11-01", "pagina": 4,
            "sha256": hashlib.sha256(content).hexdigest(), "localidad": "Mairena del Alcor",
            "registro": "Daoiz, 8 (955942032) - Antonio Ballesteros",
            "franjas": ["Día (de 9:30 a 22:00)"],
        }
        with patch("scrape_sevilla.Path.read_text", return_value=json.dumps([review])):
            self.assertEqual(len(reviewed_records(content, date(2026, 11, 1), "official.pdf")), 1)
            self.assertEqual(reviewed_records(content, date(2026, 11, 2), "official.pdf"), [])
            with self.assertRaises(ValueError):
                reviewed_records(b"changed", date(2026, 11, 1), "official.pdf")


if __name__ == "__main__":
    unittest.main()
