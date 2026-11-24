import copy
import unittest
from datetime import date

import scrape_ourense as cof


def record(day="2026-11-01", shift="Nocturna", start="22:00:00", end="09:30:00", next_day=True):
    return {
        "fecha": day, "soe": "0626", "nombre": "Farmacia Ejemplo",
        "contactos_profesionales": [{"direccion": "Rúa Ejemplo, 1", "municipio": "Ourense",
                                    "provincia": "Ourense", "telefono": "988123456",
                                    "coordenadas": "[42.34,-7.86]"}],
        "horarios": [{"tipo": shift, "hora_apertura": start, "hora_cierre": end,
                      "cierre_dia_siguiente": next_day}],
    }


def response(*records):
    return {"informacion": list(records), "metadatos": {"paginacion": {"totalPaginas": 1}}}


class OurenseTests(unittest.TestCase):
    def test_previous_night_is_clipped_to_target_day(self):
        row = cof.parse(response(record()), date(2026, 11, 2), [])[0]
        self.assertEqual(row["guardia_intervalos"][0]["inicio"], "2026-11-02T00:00:00")
        self.assertEqual(row["guardia_intervalos"][0]["fin"], "2026-11-02T09:30:00")
        self.assertIsNone(row["lat"])

    def test_same_pharmacy_keeps_both_duty_intervals(self):
        today = record("2026-11-02", "Diurna", "09:30:00", "22:00:00", False)
        row = cof.parse(response(record(), today), date(2026, 11, 2), [])[0]
        self.assertEqual(len(row["guardia_intervalos"]), 2)

    def test_only_unique_matching_phone_within_15m_is_located(self):
        pharmacy = {"id": "osm-100", "provincia": "Ourense", "telefono": "+34 988123456",
                    "lat": 42.34005, "lng": -7.86}
        row = cof.parse(response(record()), date(2026, 11, 2), [pharmacy])[0]
        self.assertLessEqual(row["ajuste_ubicacion_m"], 15)
        self.assertEqual(row["referencia_ubicacion"], "https://www.openstreetmap.org/node/100")
        far = {**pharmacy, "lat": 42.341}
        self.assertIsNone(cof.parse(response(record()), date(2026, 11, 2), [far])[0]["lat"])
        duplicate = {**pharmacy, "id": "osm-101"}
        self.assertIsNone(cof.parse(response(record()), date(2026, 11, 2), [pharmacy, duplicate])[0]["lat"])

    def test_invalid_date_pagination_and_hours_are_rejected(self):
        invalid = response(record())
        invalid["metadatos"]["paginacion"]["totalPaginas"] = 2
        bad_time = record(end="10:00:00", next_day=False)
        for data in (invalid, response(record("2026-10-30")), response(bad_time)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                cof.parse(data, date(2026, 11, 2), [])

    def test_conflicting_pharmacy_details_are_rejected(self):
        other = copy.deepcopy(record("2026-11-02"))
        other["contactos_profesionales"][0]["direccion"] = "Otra, 2"
        with self.assertRaises(ValueError):
            cof.parse(response(record(), other), date(2026, 11, 2), [])


if __name__ == "__main__":
    unittest.main()
