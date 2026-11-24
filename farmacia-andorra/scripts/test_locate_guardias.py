import json
import tempfile
import unittest
from pathlib import Path

from locate_guardias import LEDGER, locate_guardias
from proximidad import Reference, distance_m


class FakeGeocoder:
    def __init__(self, references):
        self._references = references
        self.requests = 0
        self.errors = 0

    def references(self, row):
        self.requests += 2
        return self._references

    def save(self):
        pass


class LocateGuardiasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.pharmacy = {
            "id": "test-1",
            "nombre": "Farmacia de prueba",
            "direccion": "Calle Mayor 10",
            "localidad": "Prueba",
            "provincia": "Madrid",
            "lat": None,
            "lng": None,
        }
        for filename, rows in (
            ("guardias-madrid-2026-11-01.json", [dict(self.pharmacy, guardia=True)]),
            ("farmacias-madrid.json", [dict(self.pharmacy, guardia=False)]),
            ("farmacias-osm-espana.json", []),
            ("farmacias-espana-hoy.json", []),
        ):
            (self.output / filename).write_text(json.dumps(rows), encoding="utf-8")
        (self.output / "cobertura-madrid-2026-11-01.json").write_text(
            json.dumps({"con_coordenadas": 0}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_two_sources_within_15m_are_saved_to_guard_catalog_and_ledger(self):
        second_point = (40.000134, -3.0)
        self.assertLessEqual(distance_m((40.0, -3.0), second_point), 15)
        geocoder = FakeGeocoder([
            Reference((40.0, -3.0), "osm", "address", "https://osm.example/address"),
            Reference(second_point, "cartociudad", "address", "https://carto.example/"),
        ])

        placements, pending = locate_guardias(self.output, geocoder=geocoder)

        self.assertEqual(len(placements), 1)
        self.assertFalse(pending)
        self.assertEqual(geocoder.requests, 2)
        guard = json.loads((self.output / "guardias-madrid-2026-11-01.json").read_text())[0]
        catalog = json.loads((self.output / "farmacias-madrid.json").read_text())[0]
        self.assertEqual(guard["lat"], 40.0)
        self.assertEqual(catalog["lat"], 40.0)
        self.assertEqual(catalog["precision_ubicacion"], "direccion")
        ledger = json.loads((self.output / LEDGER).read_text())
        self.assertEqual(len(ledger), 1)
        self.assertEqual(
            json.loads((self.output / "cobertura-madrid-2026-11-01.json").read_text())["con_coordenadas"],
            1,
        )

    def test_disagreeing_sources_are_not_saved(self):
        second_point = (40.000136, -3.0)
        self.assertGreater(distance_m((40.0, -3.0), second_point), 15)
        geocoder = FakeGeocoder([
            Reference((40.0, -3.0), "osm", "address", "https://osm.example/address"),
            Reference(second_point, "cartociudad", "address", "https://carto.example/"),
        ])

        placements, pending = locate_guardias(self.output, geocoder=geocoder)

        self.assertFalse(placements)
        self.assertEqual(len(pending), 1)
        guard = json.loads((self.output / "guardias-madrid-2026-11-01.json").read_text())[0]
        self.assertIsNone(guard["lat"])
        self.assertFalse((self.output / LEDGER).exists())

    def test_existing_catalog_location_is_copied_without_geocoding(self):
        catalog = json.loads((self.output / "farmacias-madrid.json").read_text())
        catalog[0].update(lat=40.0, lng=-3.0, precision_ubicacion="farmacia")
        (self.output / "farmacias-madrid.json").write_text(json.dumps(catalog), encoding="utf-8")

        class NoLookup:
            requests = 0
            errors = 0

            def references(self, row):
                raise AssertionError("La farmacia ya tiene coordenadas en el catálogo.")

            def save(self):
                pass

        placements, pending = locate_guardias(self.output, geocoder=NoLookup())

        guard = json.loads((self.output / "guardias-madrid-2026-11-01.json").read_text())[0]
        self.assertEqual(guard["lat"], 40.0)
        self.assertFalse(placements)
        self.assertFalse(pending)

    def test_explicitly_unverified_location_cannot_be_restored_from_catalogue_or_ledger(self):
        guard_path = self.output / "guardias-madrid-2026-11-01.json"
        guard = dict(self.pharmacy, guardia=True, ubicacion_pendiente_verificacion=True)
        guard_path.write_text(json.dumps([guard]), encoding="utf-8")
        catalog = dict(self.pharmacy, lat=40.0, lng=-3.0)
        (self.output / "farmacias-madrid.json").write_text(json.dumps([catalog]), encoding="utf-8")
        (self.output / LEDGER).write_text(json.dumps([catalog]), encoding="utf-8")
        geocoder = FakeGeocoder([])

        placements, pending = locate_guardias(self.output, geocoder=geocoder)

        self.assertFalse(placements)
        self.assertFalse(pending)
        self.assertEqual(geocoder.requests, 0)
        self.assertIsNone(json.loads(guard_path.read_text())[0]["lat"])

    def test_saved_location_is_reused_without_a_new_lookup(self):
        geocoder = FakeGeocoder([
            Reference((40.0, -3.0), "osm", "address", "https://osm.example/address"),
            Reference((40.000134, -3.0), "cartociudad", "address", "https://carto.example/"),
        ])
        locate_guardias(self.output, geocoder=geocoder)
        historical_path = self.output / "guardias-madrid-2026-10-31.json"
        historical_path.write_text(
            json.dumps([dict(self.pharmacy, guardia=True)]), encoding="utf-8"
        )
        (self.output / "cobertura-madrid-2026-10-31.json").write_text(
            json.dumps({"con_coordenadas": 0}), encoding="utf-8"
        )

        class NoLookup:
            requests = 0
            errors = 0

            def references(self, row):
                raise AssertionError("La ubicación guardada no debe geocodificarse otra vez.")

            def save(self):
                pass

        placements, pending = locate_guardias(self.output, geocoder=NoLookup())

        self.assertFalse(placements)
        self.assertFalse(pending)
        self.assertEqual(
            json.loads((self.output / "guardias-madrid-2026-11-01.json").read_text())[0]["lat"],
            40.0,
        )
        self.assertEqual(json.loads(historical_path.read_text())[0]["lat"], 40.0)
        self.assertEqual(
            json.loads((self.output / "cobertura-madrid-2026-10-31.json").read_text())[
                "con_coordenadas"
            ],
            1,
        )

    def test_province_filter_limits_geocoding_to_matching_guard_files(self):
        segovia = dict(self.pharmacy, id="segovia-1", provincia="Segovia")
        (self.output / "guardias-segovia-2026-11-01.json").write_text(
            json.dumps([segovia]), encoding="utf-8"
        )
        (self.output / "cobertura-segovia-2026-11-01.json").write_text(
            json.dumps({"con_coordenadas": 0}), encoding="utf-8"
        )

        class RecordingGeocoder:
            requests = 0
            errors = 0

            def __init__(self):
                self.ids = []

            def references(self, row):
                self.ids.append(row["id"])
                return []

            def save(self):
                pass

        geocoder = RecordingGeocoder()
        locate_guardias(self.output, geocoder=geocoder, province="Segovia")

        self.assertEqual(geocoder.ids, ["segovia-1"])

    def test_excluded_province_does_not_change_guard_files(self):
        guard_path = self.output / "guardias-madrid-2026-11-01.json"
        original = guard_path.read_text()
        geocoder = FakeGeocoder([Reference((40.0, -3.0), "osm", "pharmacy", "https://osm.example/")])
        placements, _ = locate_guardias(self.output, geocoder=geocoder, excluded_provinces=["Madrid"])
        self.assertFalse(placements)
        self.assertEqual(geocoder.requests, 0)
        self.assertEqual(guard_path.read_text(), original)


class CatalogCandidateTests(unittest.TestCase):
    REGISTRY = "farmacias-registro-jcyl.json"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        base = {"nombre": "Farmacia", "localidad": "Prueba", "provincia": "Madrid", "lat": None, "lng": None}
        self.registry = [
            dict(base, id="jcyl-1", direccion="Calle Real, 5"),
            dict(base, id="jcyl-2", direccion="Calle Nueva, s/n"),
            dict(base, id="jcyl-3", direccion="Calle Alta, 3", provincia="Segovia"),
        ]
        for filename, rows in (
            ("guardias-madrid-2026-11-01.json", [dict(base, id="test-1", direccion="Calle Mayor 10", guardia=True)]),
            (self.REGISTRY, self.registry),
            ("farmacias-osm-espana.json", []),
            ("farmacias-espana-hoy.json", []),
        ):
            (self.output / filename).write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def recording(self, located_id=None):
        class RecordingGeocoder:
            requests = 0
            errors = 0

            def __init__(self):
                self.ids = []

            def references(self, row):
                self.ids.append(row["id"])
                self.requests += 2
                if row["id"] != located_id:
                    return []
                return [Reference((40.0, -3.0), "osm", "address", "https://osm.example/address"),
                        Reference((40.00005, -3.0), "cartociudad", "address", "https://carto.example/")]

            def save(self):
                pass

        return RecordingGeocoder()

    def test_catalog_rows_follow_guards_and_verified_locations_are_saved(self):
        geocoder = self.recording("jcyl-1")

        placements, _ = locate_guardias(self.output, geocoder=geocoder, max_requests=0,
                                        catalog_candidates=[self.REGISTRY], province="Madrid")

        self.assertEqual(geocoder.ids, ["test-1", "jcyl-1"])
        self.assertEqual(len(placements), 1)
        registry = {row["id"]: row for row in json.loads((self.output / self.REGISTRY).read_text())}
        self.assertEqual(registry["jcyl-1"]["lat"], 40.0)
        self.assertIsNone(registry["jcyl-2"]["lat"])
        self.assertEqual([row["id"] for row in json.loads((self.output / LEDGER).read_text())], ["jcyl-1"])

    def test_catalog_rows_are_ignored_unless_requested(self):
        geocoder = self.recording()

        locate_guardias(self.output, geocoder=geocoder)

        self.assertEqual(geocoder.ids, ["test-1"])

    def test_query_budget_is_spent_on_guards_first(self):
        geocoder = self.recording()

        locate_guardias(self.output, geocoder=geocoder, max_requests=2, catalog_candidates=[self.REGISTRY])

        self.assertEqual(geocoder.ids, ["test-1"])

    def test_catalog_rows_already_located_in_the_national_catalog_are_skipped(self):
        (self.output / "farmacias-espana-hoy.json").write_text(
            json.dumps([dict(self.registry[0], lat=40.0, lng=-3.0)]), encoding="utf-8")
        geocoder = self.recording()

        locate_guardias(self.output, geocoder=geocoder, max_requests=0, catalog_candidates=[self.REGISTRY])

        self.assertEqual(geocoder.ids, ["test-1", "jcyl-3"])

    def test_unknown_catalog_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            locate_guardias(self.output, geocoder=self.recording(), catalog_candidates=["farmacias-nada.json"])


if __name__ == "__main__":
    unittest.main()
