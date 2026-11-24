from datetime import date
import unittest

from cgcof_catalog import parse


class BurgosTests(unittest.TestCase):
    def test_province_identity_and_no_foreign_default_hours(self):
        page = ('01/11/2026 GUARDIAS TODO EL DÍA '
                '<div>De 9:50 a 9:50 (24 horas)</div>'
                '<a onclick=abbre(9,9000090,0)>Plaza Mayor 11 - Aranda de Duero</a>')
        rows = parse(page, {"nombre": "Aranda de Duero (Ciudad)"}, date(2026, 11, 1),
                     province_id="09", province="Burgos")
        self.assertEqual(rows[0]["id"], "09-9000090")
        self.assertEqual(rows[0]["provincia"], "Burgos")
        self.assertEqual(rows[0]["localidades_atendidas"], ["Aranda de Duero"])
        self.assertNotIn("9:30", rows[0]["guardia_franja"])
        self.assertIsNone(rows[0]["lat"])

    def test_overnight_carryover_and_wrong_date(self):
        page = ('31/10/2026 GUARDIAS DE NOCHE '
                '<a onclick=abbre(9,9000001,0)>Calle Mayor 1 - Burgos</a>')
        rows = parse(page, {"nombre": "Burgos (Ciudad)"}, date(2026, 10, 31), True, "09", "Burgos")
        self.assertEqual(rows[0]["fecha_guardia"], "2026-11-01")
        with self.assertRaises(ValueError):
            parse(page, {"nombre": "Burgos"}, date(2026, 11, 1), False, "09", "Burgos")
