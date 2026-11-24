import json
import shutil
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import provincial_catalog
import scrape_madrid
from merge_espana import merge_catalogs


TARGET = date(2026, 11, 1)


def pharmacy(**fields):
    return {"identificador": "1", "direccion": "CL MAYOR, 2", "poblacion": "MADRID",
            "latitud": "40.42", "longitud": "-3.7", "telefono": "910000000", **fields}


def census():
    return [{"nombre": "MADRID"}] + [{"nombre": f"Municipio {i}"} for i in range(178)]


class MadridTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent / ".madrid-test-data"
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_carryover_and_today_preserve_original_intervals(self):
        data = [pharmacy(horarioGuardia="2026-10-31 09:30-2026-11-01 09:30;"
                                      "2026-11-01 22:00-2026-11-02 09:30")]
        points, rows, reports = scrape_madrid.parse(data, census(), TARGET)
        self.assertEqual(len(points), 1)
        self.assertEqual(len(reports), 179)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00")
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio_original"], "2026-10-31T09:30:00")
        self.assertEqual(rows[0]["guardia_intervalos"][1]["fin"], "2026-11-02T00:00:00")
        self.assertEqual(reports[0]["estado"], "disponible")
        self.assertEqual(reports[1]["estado"], "sin_datos")
        self.assertEqual(reports[1]["motivo_sin_datos"], "sin_registros_en_catalogo")
        self.assertTrue(reports[1]["consulta_provincial_correcta"])
        self.assertFalse(reports[1]["derivacion_oficial_confirmada"])

    def test_today_flags_and_ordinary_24h_are_not_dated_duties(self):
        _, rows, reports = scrape_madrid.parse([pharmacy(guardia=True, servicio24h=True)], census(), TARGET)
        self.assertEqual(rows, [])
        self.assertEqual(reports[0]["motivo_sin_datos"], "sin_horario_guardia_publicado")

    def test_outside_schedule_is_distinct_from_unpublished_schedule(self):
        _, rows, reports = scrape_madrid.parse([
            pharmacy(horarioGuardia="2026-10-31 09:30-2026-10-31 21:30")], census(), TARGET)
        self.assertEqual(rows, [])
        self.assertEqual(reports[0]["motivo_sin_datos"], "intervalos_fuera_de_fecha")
        self.assertEqual(reports[0]["registros_con_horario_guardia"], 1)
        self.assertEqual(reports[0]["estado"], "sin_datos")

    def test_outside_date_is_not_a_duty(self):
        self.assertEqual(scrape_madrid.intervals("2026-10-31 09:30-2026-11-01 00:00", TARGET), [])

    def test_official_overnight_convention(self):
        period = scrape_madrid.intervals("2026-11-01 22:00-2026-11-01 08:00", TARGET)[0]
        self.assertEqual(period["fin_original"], "2026-11-02T08:00:00")

    def test_invalid_schedule_is_explicit_partial_gap(self):
        points, rows, reports = scrape_madrid.parse([pharmacy(horarioGuardia="24 horas")], census(), TARGET)
        self.assertEqual(len(points), 1)
        self.assertEqual(rows, [])
        self.assertEqual(reports[0]["estado"], "error")

    def test_selector_alias_is_not_an_extra_municipality(self):
        towns = census()
        towns[1] = {"nombre": "ROZAS DE MADRID, LAS"}
        towns.append({"nombre": "LAS ROZAS"})
        _, _, reports = scrape_madrid.parse([pharmacy(poblacion="LAS ROZAS")], towns, TARGET)
        self.assertEqual(len(reports), 179)
        self.assertEqual(len(reports[1]["opciones_selector"]), 2)

    def test_missing_census_or_unknown_locality_is_rejected(self):
        with self.assertRaises(ValueError):
            scrape_madrid.parse([pharmacy()], [{"nombre": "MADRID"}], TARGET)
        with self.assertRaises(ValueError):
            scrape_madrid.parse([pharmacy(poblacion="Desconocido")], census(), TARGET)

    def test_coordinates_never_use_town_center_fallback(self):
        rows = scrape_madrid.catalogue([pharmacy(latitud="0", longitud="0")])
        self.assertIsNone(rows[0]["lat"])
        self.assertNotIn("precision_ubicacion", rows[0])

    def test_live_failure_preserves_calendar_and_catalogue(self):
        calendar = self.root / f"guardias-madrid-{TARGET}.json"
        old = {"id": "cof-madrid-1", "localidad": "Madrid", "localidades_atendidas": ["MADRID"],
               "guardia": True, "fecha_guardia": str(TARGET), "guardia_franjas": ["Noche"],
               "lat": 40.42, "lng": -3.7, "fuente": scrape_madrid.SOURCE}
        calendar.write_text(json.dumps([old]))
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "poblaciones.json").write_text(json.dumps(census()))
        def publish(*args):
            return provincial_catalog.publish(*args, output=self.root)
        with patch.object(scrape_madrid, "OUT_DIR", self.root), \
                patch.object(scrape_madrid, "discover", side_effect=OSError("HTTP 403")), \
                patch.object(scrape_madrid, "publish", side_effect=publish):
            self.assertFalse(scrape_madrid.run(TARGET, cache))
        kept = json.loads(calendar.read_text())[0]
        self.assertFalse(kept["guardia_reconfirmada"])
        self.assertIn("Noche", kept["guardia_franjas"])
        report = json.loads((self.root / f"cobertura-madrid-{TARGET}.json").read_text())
        self.assertEqual(len(report["consultas"]), 180)
        self.assertFalse(report["completa"])

    def test_offline_rejects_other_days(self):
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "indice.json").write_text('{"fecha_consulta":"2026-10-31"}')
        with patch.object(scrape_madrid, "OUT_DIR", self.root), \
                patch.object(scrape_madrid, "publish") as publish:
            self.assertFalse(scrape_madrid.run(TARGET, cache, offline=True))
            self.assertIn("captura", publish.call_args.args[4][0]["error"])

    def test_building_warning_survives_national_and_official_point_reuse(self):
        point = {"id": "osm-1", "direccion": "Calle Mayor 2", "localidad": "Madrid",
                 "provincia": "Madrid", "lat": 40.42, "lng": -3.7,
                 "precision_ubicacion": "direccion", "nota_ubicacion": "Pendiente de verificar",
                 "fuente_coordenadas": "https://www.openstreetmap.org/way/1"}
        (self.root / "farmacias-espana-hoy.json").write_text(json.dumps([point]))
        for official in (None, [point]):
            row = {**point, "id": "cof-madrid-2", "lat": None, "lng": None}
            row.pop("precision_ubicacion")
            row.pop("nota_ubicacion")
            provincial_catalog.locate_and_catalogue([row], "Madrid", output=self.root, official_points=official)
            self.assertEqual(row["precision_ubicacion"], "direccion")
            self.assertEqual(row["nota_ubicacion"], point["nota_ubicacion"])
            (self.root / "farmacias-madrid.json").unlink()

    def test_building_warning_survives_national_merge(self):
        point = {"id": "osm-1", "direccion": "Calle Mayor 2", "localidad": "Madrid",
                 "provincia": "Madrid", "lat": 40.42, "lng": -3.7,
                 "precision_ubicacion": "direccion", "nota_ubicacion": "Pendiente de verificar"}
        official = {**point, "id": "cof-madrid-1", "lat": None, "lng": None}
        official.pop("nota_ubicacion")
        result = merge_catalogs([point], [[official]], [])
        self.assertEqual(result[0]["precision_ubicacion"], "direccion")
        self.assertEqual(result[0]["nota_ubicacion"], "Pendiente de verificar")


if __name__ == "__main__":
    unittest.main()
