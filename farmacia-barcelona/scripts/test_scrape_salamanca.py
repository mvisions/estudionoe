from datetime import date
import unittest

from scrape_salamanca import enrich_contact, parse


class SalamancaTests(unittest.TestCase):
    def test_contact_needs_matching_official_identity(self):
        row = {"id": "37-1", "direccion": "PLAZA MAYOR, 10", "localidad": "ALBA DE TORMES"}
        detail = "".join(f"<span><strong>{key}</strong></span><span>{value}</span>"
                         for key, value in [("Dirección", row["direccion"]), ("Localidad", row["localidad"]),
                                            ("Titular", "Farmacia"), ("Teléfono", "923000000")])
        enrich_contact(row, detail)
        self.assertEqual(row["telefono"], "923000000")
        with self.assertRaises(ValueError):
            enrich_contact(row, detail.replace("MAYOR, 10", "MAYOR, 12"))

    def test_dated_duty_has_no_foreign_default_hours(self):
        page = ('01/11/2026 GUARDIAS TODO EL DÍA '
                '<a href="#" onclick=abbre(37,37000063,0)>PLAZA MAYOR, 10 - ALBA DE TORMES</a>')
        rows = parse(page, {"nombre": "Alba de Tormes"}, date(2026, 11, 1))
        self.assertEqual(rows[0]["localidad"], "ALBA DE TORMES")
        self.assertNotIn("9:30", rows[0]["guardia_franja"])
        self.assertIsNone(rows[0]["lat"])

    def test_prior_day_only_overnight_rows_are_carried(self):
        page = ('31/10/2026 GUARDIAS DE DÍA '
                '<a onclick=abbre(37,37000001,0)>CALLE UNO, 1 - SALAMANCA</a>'
                ' GUARDIAS DE NOCHE '
                '<a onclick=abbre(37,37000002,0)>CALLE DOS, 2 - SALAMANCA</a>')
        rows = parse(page, {"nombre": "Salamanca"}, date(2026, 10, 31), True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "37-37000002")
        self.assertEqual(rows[0]["fecha_guardia"], "2026-11-01")

    def test_wrong_date_and_missing_source_never_succeed(self):
        with self.assertRaises(ValueError):
            parse("Datos no disponibles", {"nombre": "Salamanca"}, date(2026, 11, 1))
        with self.assertRaises(ValueError):
            parse("31/10/2026 GUARDIAS DE NOCHE", {"nombre": "Salamanca"}, date(2026, 11, 1))
