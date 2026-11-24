from datetime import date
import unittest

from cofcam import parse_response


DAY = date(2026, 11, 1)


class ToledoTests(unittest.TestCase):
    def row(self, **changes):
        return {"id": 1, "numero_farmacia": "TO-0001-F", "nombre": "Farmacia",
                "domicilio": "C/Mayor, 2", "localidad": "Toledo", "provincia": "Toledo",
                "fecha_inicio": "2026-10-31", "fecha_fin": "2026-11-01",
                "hora_inicio": "21:00", "hora_fin": "09:00",
                "lat": "39.86", "lng": "-4.02", **changes}

    def response(self, *rows, **changes):
        return {"success": True, "fecha": DAY.isoformat(), "total": len(rows),
                "filtro_hora": None, "data": list(rows), **changes}

    def test_official_overnight_is_clipped_and_located(self):
        rows, errors = parse_response(self.response(self.row()), DAY, "Toledo")
        self.assertFalse(errors)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00")
        self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-01T09:00:00")
        self.assertEqual(rows[0]["lat"], 39.86)

    def test_multiple_duties_for_same_pharmacy_preserve_all_intervals(self):
        rows, _ = parse_response(self.response(self.row(), self.row(
            id=2, fecha_inicio="2026-11-01", fecha_fin="2026-11-02")), DAY, "Toledo")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["guardia_intervalos"]), 2)
        self.assertEqual(len(rows[0]["guardia_franjas"]), 2)

    def test_full_day_requires_real_dated_interval(self):
        rows, _ = parse_response(self.response(self.row(
            fecha_inicio="2026-11-01", fecha_fin="2026-11-02",
            hora_inicio="09:30", hora_fin="09:30")), DAY, "Toledo")
        self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-02T00:00:00")
        with self.assertRaises(ValueError):
            parse_response(self.response(self.row(fecha_inicio="2026-11-01",
                                                 hora_inicio="09:00")), DAY, "Toledo")

    def test_bad_date_hour_filter_totals_and_province_rejected(self):
        for change in ({"fecha": "2026-10-31"}, {"total": 9}, {"filtro_hora": "05:00"},
                       {"success": False}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_response(self.response(self.row(), **change), DAY, "Toledo")
        with self.assertRaises(ValueError):
            parse_response(self.response(self.row(provincia="Madrid")), DAY, "Toledo")

    def test_generic_coordinates_never_become_a_pharmacy(self):
        rows, _ = parse_response(self.response(self.row(lat="39.4", lng="-3.0")), DAY, "Toledo")
        self.assertIsNone(rows[0]["lat"])
        self.assertIsNone(rows[0]["lng"])

    def test_capital_sector_and_localized_warning(self):
        rows, _ = parse_response(self.response(self.row(
            localidad="TOLEDO (CASCO HISTORICO)", guardia_localizada=True)), DAY, "Toledo")
        self.assertEqual(rows[0]["localidad"], "Toledo")
        self.assertEqual(rows[0]["sector"], "TOLEDO (CASCO HISTORICO)")
        self.assertIn("llamar", rows[0]["guardia_franjas"][1])

    def test_prior_completed_interval_not_carried_over(self):
        rows, _ = parse_response(self.response(self.row(), self.row(
            id=2, numero_farmacia="TO-0002-F", fecha_fin="2026-10-31", hora_inicio="09:00",
            hora_fin="21:00")), DAY, "Toledo")
        self.assertEqual(len(rows), 1)
