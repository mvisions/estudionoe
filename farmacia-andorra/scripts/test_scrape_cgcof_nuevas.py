from datetime import date
import unittest

from cgcof_catalog import parse

PROVINCES = [("06", "Badajoz", "Mérida"), ("26", "La Rioja", "Logroño"),
             ("50", "Zaragoza", "Calatayud"), ("51", "Ceuta", "Ceuta"),
             ("52", "Melilla", "Melilla")]


class NewCgcofProvinceTests(unittest.TestCase):
    def test_identity_date_and_carryover_per_province(self):
        for code, province, town in PROVINCES:
            with self.subTest(province=province):
                page = (f'01/11/2026 GUARDIAS TODO EL DÍA <div>De 9:30 a 9:30 (24 horas)</div>'
                        f'<a onclick=abbre({int(code)},{code}000001,0)>Calle Mayor 1 - {town}</a>')
                rows = parse(page, {"nombre": town}, date(2026, 11, 1),
                             province_id=code, province=province)
                self.assertEqual(rows[0]["id"], f"{code}-{code}000001")
                self.assertEqual(rows[0]["provincia"], province)
                self.assertIsNone(rows[0]["lat"])
                night = page.replace("01/11/2026 GUARDIAS TODO EL DÍA", "31/10/2026 GUARDIAS DE NOCHE")
                carried = parse(night, {"nombre": town}, date(2026, 10, 31), True, code, province)
                self.assertEqual(carried[0]["fecha_guardia"], "2026-11-01")
                with self.assertRaises(ValueError):
                    parse(night, {"nombre": town}, date(2026, 11, 1), False, code, province)


class GeocoderRateLimitTests(unittest.TestCase):
    def test_rate_limit_keeps_identity_matches_and_saves(self):
        import json, tempfile, urllib.error
        from pathlib import Path
        from unittest import mock
        import provincial_catalog
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            osm = {"id": "osm-1", "nombre": "Farmacia Sol", "direccion": "Calle Sol 2",
                   "localidad": "Mérida", "provincia": "Badajoz", "lat": 38.9, "lng": -6.3}
            (root / "farmacias-espana-hoy.json").write_text(json.dumps([osm]))
            first = {"id": "06-1", "nombre": "Otra", "direccion": "Calle Luna 1",
                     "localidad": "Mérida", "provincia": "Badajoz", "lat": None, "lng": None}
            second = {**osm, "id": "06-2", "lat": None, "lng": None}
            limit = urllib.error.HTTPError("u", 429, "Too many requests", {}, None)
            with mock.patch.object(provincial_catalog, "geocode_exact", side_effect=limit) as geo, \
                    mock.patch.object(provincial_catalog.time, "sleep"):
                provincial_catalog.locate_and_catalogue([first, second], "Badajoz", output=root,
                                                        use_geocoder=True)
            self.assertEqual(geo.call_count, 1)
            self.assertEqual((second["lat"], second["lng"]), (38.9, -6.3))
            saved = json.loads((root / "farmacias-badajoz.json").read_text())
            self.assertEqual({row["id"] for row in saved}, {"06-1", "06-2"})
