import unittest
from datetime import date

from scrape_cadiz import parse_response


def entry(day, opening, closing, overnight, coordinates="[36.5,-6.1]"):
    return {"fecha": day, "soe": "110001", "nombre": "Farmacia",
            "contactos_profesionales": [{"direccion": "Real, 1", "municipio": "Cádiz",
                                       "coordenadas": coordinates, "telefono": "956111111"}],
            "horarios": [{"hora_apertura": opening, "hora_cierre": closing,
                          "cierre_dia_siguiente": overnight, "tipo": "Guardia"}]}


class CadizTests(unittest.TestCase):
    def test_previous_night_and_today_are_clipped_and_merged(self):
        data = {"informacion": [entry("2026-10-31", "22:00:00", "09:30:00", True),
                                entry("2026-11-01", "22:00:00", "09:30:00", True)]}
        rows = parse_response(data, date(2026, 11, 1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00")
        self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-01T09:30:00")
        self.assertEqual(rows[0]["guardia_intervalos"][1]["fin"], "2026-11-02T00:00:00")
        self.assertEqual(rows[0]["fecha_guardia"], "2026-11-01")

    def test_previous_daytime_is_not_today_guardia(self):
        data = {"informacion": [entry("2026-10-31", "09:00:00", "22:00:00", False)]}
        self.assertEqual(parse_response(data, date(2026, 11, 1)), [])

    def test_invalid_coordinate_never_becomes_marker_but_record_is_preserved(self):
        data = {"informacion": [entry("2026-11-01", "00:00:00", "00:00:00", True, "[0,0]")]}
        row = parse_response(data, date(2026, 11, 1))[0]
        self.assertIsNone(row["lat"])
        self.assertIsNone(row["lng"])
        self.assertTrue(row["guardia"])

    def test_invalid_interval_and_missing_identity_are_reported(self):
        data = {"informacion": [entry("2026-11-01", "22:00:00", "09:30:00", False)]}
        with self.assertRaises(ValueError):
            parse_response(data, date(2026, 11, 1))
        data["informacion"][0] = entry("2026-11-01", "00:00:00", "00:00:00", True)
        data["informacion"][0]["soe"] = None
        with self.assertRaises(ValueError):
            parse_response(data, date(2026, 11, 1))


if __name__ == "__main__":
    unittest.main()
