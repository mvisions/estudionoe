import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scrape_navarra as nav


DAY = date(2026, 11, 2)


def record(start="10", end="21", **changes):
    row = {"fecha": "02/11/2026", "desde": start, "hasta": end, "localidad": "Pamplona / Iruña",
           "grupo": "Pamplona y comarca/Iruñerria", "direccion": "C/ Yanguas y Miranda, 17",
           "farmacia": "Marfil Garcia, Alberto", "cod_Farmacia": "F00205", "telefono": "948 245030"}
    row.update(changes)
    return row


def response(*rows):
    return {"success": True, "result": {"records": list(rows), "total": len(rows)}}


class NavarraTests(unittest.TestCase):
    def test_duplicates_keep_raw_source_hours_without_inferred_intervals(self):
        row = nav.parse(response(record(), record("21", "10")), DAY)[0]
        self.assertEqual(row["horarios_fuente"], [{"desde": "10", "hasta": "21"},
                                                  {"desde": "21", "hasta": "10"}])
        self.assertNotIn("guardia_intervalos", row)
        self.assertIn("pendientes de confirmar", row["guardia_franja"])
        self.assertEqual(row["fuente"], nav.SOURCE)
        self.assertEqual(row["fuente_licencia"], nav.LICENSE)

    def test_province_group_does_not_make_other_towns_pamplona(self):
        extra = record(localidad="Barañáin", cod_Farmacia="F00300")
        rows = nav.parse(response(record(), extra), DAY)
        self.assertEqual(len(rows), 1)

    def test_daily_city_records_keep_locality_and_literal_hours(self):
        tudela = record(localidad="Tudela", cod_Farmacia="F00559")
        estella = record(localidad="Estella-Lizarra", cod_Farmacia="F00060")
        weekly = record(localidad="Tafalla", cod_Farmacia="F00400")
        rows = nav.parse(response(record(), tudela, estella, weekly), DAY)
        self.assertEqual({row["localidad"] for row in rows},
                         {"Pamplona / Iruña", "Tudela", "Estella-Lizarra"})
        for row in rows:
            self.assertEqual(row["localidades_atendidas"], [row["localidad"]])
            self.assertNotIn("guardia_intervalos", row)

    def test_incomplete_or_wrong_date_and_conflicting_identity_rejected(self):
        incomplete = response(record())
        incomplete["result"]["total"] = 2
        different = record(direccion="Otra dirección")
        for data in (incomplete, response(record(fecha="01/11/2026")),
                     response(record(start="26")), response(record(), different)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                nav.parse(data, DAY)

    def test_missing_city_is_reported_as_pending(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            with patch.object(nav, "fetch", return_value=response(record())), \
                    patch.object(nav, "publish", return_value=False) as publish:
                self.assertFalse(nav.run(DAY, path / "cache", path / "data"))
            reports = publish.call_args.args[4]
            self.assertEqual([(report["nombre"], report["estado"]) for report in reports[:3]],
                             [("Pamplona / Iruña", "parcial"), ("Tudela", "pendiente"),
                              ("Estella-Lizarra", "pendiente")])


if __name__ == "__main__":
    unittest.main()
