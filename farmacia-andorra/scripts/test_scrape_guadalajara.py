from datetime import date
import unittest

from cofcam import parse_response


class GuadalajaraTests(unittest.TestCase):
    def test_official_identifier_day_night_merge_and_contact(self):
        info = {"id": 1892, "numero_farmacia": "GU-1035-F", "domicilio": "CALLE REAL, 44",
                "localidad": "ALCOLEA DEL PINAR", "provincia": "Guadalajara",
                "fecha_inicio": "2026-10-31", "fecha_fin": "2026-11-01",
                "hora_inicio": "10:00", "hora_fin": "10:00",
                "telefono2": "600000000", "lat": "41.036498", "lng": "-2.466661"}
        data = {"success": True, "fecha": "2026-11-01", "total": 2, "filtro_hora": None,
                "data": [info, {**info, "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-02"}]}
        rows, errors = parse_response(data, date(2026, 11, 1), "Guadalajara")
        self.assertFalse(errors)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "cof-guadalajara-GU-1035-F")
        self.assertEqual(len(rows[0]["guardia_intervalos"]), 2)
        self.assertEqual(rows[0]["telefonos_adicionales"], ["600000000"])
        self.assertEqual(rows[0]["lat"], 41.036498)

    def test_empty_list_and_non_object_response_not_success(self):
        for data in ([], {"success": True, "fecha": "2026-11-01", "total": 0,
                           "filtro_hora": None, "data": []}):
            with self.assertRaises(ValueError):
                parse_response(data, date(2026, 11, 1), "Guadalajara")
