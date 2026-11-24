from datetime import date
import json
import unittest

from scrape_valencia import parse_page


DAY = date(2026, 11, 1)


class ValenciaTests(unittest.TestCase):
    def page(self, hours, **changes):
        row = ["", 39.085559, -0.475595, "C/Mayor 6", "La Pobla Llarga", "46670",
               "960000000", "", "Abierta", hours, "/farmacia/ver/412/?guardia=1"]
        for index, value in changes.items():
            row[int(index)] = value
        return ('<input id="buscarFecha" name="buscarFecha" value="01/11/2026 00:00">'
                + "var distribuidores = " + json.dumps([row]) + ";")

    def test_ordinary_opening_is_never_guardia(self):
        catalog, duties = parse_page(self.page("00:00-23:59"), DAY, "00:00")
        self.assertEqual(len(catalog), 1)
        self.assertFalse(duties)

    def test_explicit_urgency_preserves_official_coordinates_and_time(self):
        catalog, duties = parse_page(self.page("00:00-09:00 (incluye horario de urgencias)"), DAY, "00:00")
        self.assertEqual(duties[0]["lat"], 39.085559)
        self.assertEqual(duties[0]["guardia_intervalos"][0]["fin"], "2026-11-01T09:00:00")
        self.assertEqual(duties[0]["localidades_atendidas"], ["La Pobla Llarga"])

    def test_wrong_date_and_ambiguous_intervals_rejected(self):
        with self.assertRaises(ValueError):
            parse_page(self.page("00:00-09:00"), date(2026, 11, 2), "00:00")
        with self.assertRaises(ValueError):
            parse_page(self.page("09:00-09:00 (incluye horario de urgencias)"), DAY, "00:00")

    def test_invalid_coordinates_not_drawn(self):
        catalog, _ = parse_page(self.page("00:00-23:59", **{"1": 0, "2": 0}), DAY, "00:00")
        self.assertIsNone(catalog[0]["lat"])

    def test_malformed_unrelated_html_does_not_corrupt_valid_records(self):
        content = '<input value="Pu\udcc3ol">' + self.page("00:00-09:00 (incluye horario de urgencias)")
        _, duties = parse_page(content, DAY, "00:00")
        self.assertEqual(len(duties), 1)
        with self.assertRaises(UnicodeEncodeError):
            parse_page(self.page("00:00-23:59", **{"4": "Pu\udcc3ol"}), DAY, "00:00")
