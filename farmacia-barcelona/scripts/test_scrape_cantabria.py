from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scrape_cantabria import coordinate_index, interval, parse, run


DAY = date(2026, 11, 1)


class CantabriaTests(unittest.TestCase):
    def row(self, **changes):
        return {"name": "Farmacia", "address": "(SANTANDER) CL. MAYOR, 2",
                "phone": None, "hours": "22:00 — 09:00", "overnight": True, **changes}

    def test_previous_night_and_midnight_clip(self):
        result = interval(self.row(), date(2026, 10, 31), DAY)
        self.assertEqual(result["inicio"], "2026-11-01T00:00:00")
        self.assertEqual(result["fin"], "2026-11-01T09:00:00")
        self.assertEqual(interval(self.row(hours="09:00 — 00:00"), DAY, DAY)["fin"], "2026-11-02T00:00:00")

    def test_equal_hours_require_official_overnight(self):
        self.assertEqual(interval(self.row(hours="09:00 — 09:00"), DAY, DAY)["fin"], "2026-11-02T00:00:00")
        with self.assertRaises(ValueError):
            interval(self.row(hours="09:00 — 09:00", overnight=False), DAY, DAY)

    def test_zone_dedup_preserves_intervals_and_official_coordinates(self):
        prior = self.row()
        today = self.row(hours="09:00 — 09:00")
        zone = {"name": "Santander", "id": "santander",
                "schedule": {"2026-10-31": [prior], "2026-11-01": [today]}}
        phones = [{"name": prior["name"], "address": prior["address"], "phone": "942000000"}]
        geo = {"features": [{"geometry": {"type": "Point", "coordinates": [-3.8, 43.46]},
                             "properties": {"TELEFONO_1": "942000000"}}]}
        catalog, duties, reports = parse({"zones": [zone, {**zone, "name": "Otra zona", "id": "otra"}]},
                                         phones, geo, DAY)
        self.assertEqual(len(duties), 1)
        self.assertEqual(len(duties[0]["guardia_intervalos"]), 2)
        self.assertEqual(duties[0]["zonas_atendidas"], ["Santander", "Otra zona"])
        self.assertEqual(duties[0]["localidades_atendidas"], ["Santander"])
        self.assertEqual(duties[0]["lat"], 43.46)
        self.assertFalse(catalog[0]["guardia"])
        self.assertEqual(reports[-1]["estado"], "parcial")

    def test_no_nearest_date_fallback(self):
        zone = {"id": "santander", "name": "Santander", "schedule": {"2026-10-30": [self.row()]}}
        _, duties, reports = parse({"zones": [zone]}, [], {"features": []}, DAY)
        self.assertFalse(duties)
        self.assertNotEqual(reports[0]["estado"], "disponible")

    def test_institutional_truncation_and_generic_coords_rejected(self):
        with self.assertRaises(ValueError):
            coordinate_index({"features": [], "exceededTransferLimit": True})
        self.assertFalse(coordinate_index({"features": [
            {"properties": {"TELEFONO_1": "942000000"},
             "geometry": {"type": "Point", "coordinates": [0, 0]}}]}))

    def test_master_coordinate_identity_must_include_exact_address(self):
        info = self.row()
        zone = {"id": "santander", "name": "Santander",
                "schedule": {"2026-10-31": [info], "2026-11-01": [info]}}
        point = {**info, "lat": 43.46, "lng": -3.8}
        _, duties, _ = parse({"zones": [zone]}, [], {"features": []}, DAY, [point])
        self.assertEqual(duties[0]["lat"], 43.46)
        _, duties, _ = parse({"zones": [zone]}, [], {"features": []}, DAY,
                             [{**point, "address": "(SANTANDER) CL. MAYOR, 3"}])
        self.assertIsNone(duties[0]["lat"])

    def test_failed_cartography_keeps_official_duties_and_reports_error(self):
        info = self.row()
        zone = {"id": "santander", "name": "Santander",
                "schedule": {"2026-10-31": [info], "2026-11-01": [info]}}
        point = {**info, "lat": 43.46, "lng": -3.8}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / f"calendario-{DAY}.json").write_text(json.dumps({"zones": [zone]}))
            (cache / "telefonos.json").write_text("[]")
            (cache / "coordenadas.json").write_text(json.dumps({"error": {"code": 400}}))
            (cache / "posiciones-cof.json").write_text(json.dumps([point]))
            with patch("scrape_cantabria.locate_and_catalogue"), \
                    patch("scrape_cantabria.publish", return_value=False) as publish:
                self.assertFalse(run(DAY, cache, offline=True))
            duties, reports = publish.call_args.args[3:5]
            self.assertEqual(len(duties), 1)
            self.assertEqual(duties[0]["lat"], 43.46)
            self.assertEqual(duties[0]["lng"], -3.8)
            self.assertTrue(any(r["nombre"] == "Cartografía institucional" and r["estado"] == "error"
                                for r in reports))

    def test_failed_cartography_without_master_keeps_location_pending(self):
        info = self.row()
        zone = {"id": "santander", "name": "Santander",
                "schedule": {"2026-10-31": [info], "2026-11-01": [info]}}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / f"calendario-{DAY}.json").write_text(json.dumps({"zones": [zone]}))
            (cache / "telefonos.json").write_text("[]")
            with patch("scrape_cantabria.locate_and_catalogue"), \
                    patch("scrape_cantabria.publish", return_value=False) as publish:
                self.assertFalse(run(DAY, cache, offline=True))
            duties, reports = publish.call_args.args[3:5]
            self.assertEqual(len(duties), 1)
            self.assertIsNone(duties[0]["lat"])
            self.assertTrue(any(r["nombre"] == "Cartografía institucional" and r["estado"] == "error"
                                for r in reports))

    def test_bad_online_cartography_does_not_replace_valid_cached_snapshot(self):
        info = self.row()
        zone = {"id": "santander", "name": "Santander",
                "schedule": {"2026-10-31": [info], "2026-11-01": [info]}}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            path = cache / "coordenadas.json"
            original = {"features": []}
            path.write_text(json.dumps(original))
            with patch("scrape_cantabria.fetch", side_effect=[{"zones": [zone]}, [], {"error": {"code": 400}}]), \
                    patch("scrape_cantabria.master_positions", return_value=[]), \
                    patch("scrape_cantabria.locate_and_catalogue"), \
                    patch("scrape_cantabria.publish", return_value=False) as publish:
                self.assertFalse(run(DAY, cache))
            self.assertEqual(json.loads(path.read_text()), original)
            duties, reports = publish.call_args.args[3:5]
            self.assertEqual(len(duties), 1)
            self.assertTrue(any(r["nombre"] == "Cartografía institucional" and r["estado"] == "error"
                                for r in reports))
