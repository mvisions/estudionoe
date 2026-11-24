import tempfile
import unittest
from pathlib import Path

from merge_espana import assign_province, catalog_paths, in_ring, merge_catalogs


RING = [[-7, 35], [-5, 35], [-5, 37], [-7, 37], [-7, 35]]
POLYGONS = [("Cádiz", (-7, 35, -5, 37), [RING])]


class MergeSpainTests(unittest.TestCase):
    def test_polygon_assignment_preserves_foreign_and_unlocated_records(self):
        self.assertEqual(assign_province({"lat":36, "lng":-6}, POLYGONS)["provincia"], "Cádiz")
        for row in ({"lat":48.86, "lng":2.35}, {"lat":None, "lng":None}, {"lat":0, "lng":0}):
            self.assertEqual(assign_province(row, POLYGONS), row)

    def test_polygon_holes_are_not_assigned_by_bounding_rectangle(self):
        hole = [[-6.5, 35.5], [-5.5, 35.5], [-5.5, 36.5], [-6.5, 36.5], [-6.5, 35.5]]
        self.assertTrue(in_ring((-6,36), RING))
        self.assertNotIn("provincia", assign_province({"lat":36, "lng":-6},
                         [("Cádiz", (-7,35,-5,37), [RING,hole])]))

    def test_incomplete_official_catalog_never_excludes_osm_province(self):
        osm = [{"id":"osm-1", "lat":36, "lng":-6}, {"id":"osm-2", "lat":36.1, "lng":-6}]
        official = [{"id":"cad-1", "provincia":"Cádiz", "lat":36.2, "lng":-6, "guardia":True}]
        rows = merge_catalogs(osm, [official], POLYGONS)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["provincia"]=="Cádiz" for row in rows))
        self.assertTrue(all(row["guardia"] is False for row in rows))

    def test_exact_identity_merge_keeps_coordinates_and_official_id(self):
        osm = [{"id":"osm-1", "lat":36, "lng":-6, "telefono":"+34 956 123 456"}]
        official = [{"id":"cad-1", "provincia":"Cádiz", "lat":None, "lng":None, "telefono":"956123456"}]
        rows = merge_catalogs(osm, [official], POLYGONS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "cad-1")
        self.assertEqual(rows[0]["lat"], 36)

    def test_explicitly_unverified_location_does_not_inherit_osm_coordinates(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6, "telefono": "956123456"}]
        official = [{"id": "cad-1", "provincia": "Cádiz", "lat": None, "lng": None,
                     "telefono": "956123456", "ubicacion_pendiente_verificacion": True}]
        rows = merge_catalogs(osm, [official], POLYGONS)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["lat"])
        self.assertIsNone(rows[0]["lng"])

    def test_location_requiring_verification_does_not_inherit_osm_coordinates(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6, "telefono": "956123456"}]
        official = [{"id": "cad-1", "provincia": "Cádiz", "lat": None, "lng": None,
                     "telefono": "956123456", "ubicacion_requiere_verificacion": True}]

        rows = merge_catalogs(osm, [official], POLYGONS)

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["lat"])
        self.assertIsNone(rows[0]["lng"])

    def test_nearby_distinct_pharmacies_are_not_deduplicated_by_distance(self):
        osm = [{"id":"osm-1", "lat":36, "lng":-6}, {"id":"osm-2", "lat":36.00001, "lng":-6}]
        self.assertEqual(len(merge_catalogs(osm, [], POLYGONS)), 2)

    def test_ambiguous_phone_does_not_remove_known_pharmacies(self):
        osm = [{"id":"osm-1", "lat":36, "lng":-6, "telefono":"956123456"},
               {"id":"osm-2", "lat":36.1, "lng":-6, "telefono":"956123456"}]
        official = [{"id":"cad-1", "provincia":"Cádiz", "telefono":"956123456"}]
        self.assertEqual(len(merge_catalogs(osm, [official], POLYGONS)), 3)

    def test_registry_row_inherits_osm_point_and_records_the_node(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6, "telefono": "956123456"}]
        registry = [{"id": "jcyl-1", "provincia": "Cádiz", "telefono": "956123456", "lat": None, "lng": None}]

        rows = merge_catalogs(osm, [registry], POLYGONS)

        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["id"], rows[0]["lat"], rows[0]["osm_id"]), ("jcyl-1", 36, "osm-1"))

    def test_located_row_replaces_the_osm_node_linked_by_osm_id(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6}]
        official = [{"id": "cad-1", "provincia": "Cádiz", "lat": 36.00001, "lng": -6, "osm_id": "osm-1"}]

        rows = merge_catalogs(osm, [official], POLYGONS)

        self.assertEqual([row["id"] for row in rows], ["cad-1"])
        self.assertEqual(rows[0]["lat"], 36.00001)

    def test_osm_link_with_a_different_phone_is_not_merged(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6, "telefono": "956000000"}]
        official = [{"id": "cad-1", "provincia": "Cádiz", "telefono": "956123456", "osm_id": "osm-1"}]

        self.assertEqual(len(merge_catalogs(osm, [official], POLYGONS)), 2)

    def test_later_catalog_replaces_registry_row_through_the_alias_chain(self):
        osm = [{"id": "osm-1", "lat": 36, "lng": -6, "telefono": "956123456"}]
        registry = [{"id": "jcyl-1", "provincia": "Cádiz", "telefono": "956123456"}]
        provincial = [{"id": "cof-1", "provincia": "Cádiz", "lat": None, "lng": None, "osm_id": "osm-1"}]

        rows = merge_catalogs(osm, [registry, provincial], POLYGONS)

        self.assertEqual([(row["id"], row["lat"]) for row in rows], [("cof-1", 36)])

    def test_same_id_in_a_later_catalog_keeps_one_row_and_its_location(self):
        registry = [{"id": "jcyl-1", "provincia": "Cádiz", "direccion": "Calle Mayor, 1", "lat": 36, "lng": -6}]
        guards = [{"id": "jcyl-1", "provincia": "Cádiz", "direccion": "Calle Mayor 1", "lat": None, "lng": None}]

        rows = merge_catalogs([], [registry, guards], POLYGONS)

        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["direccion"], rows[0]["lat"]), ("Calle Mayor 1", 36))

    def test_base_registry_is_merged_first_and_the_location_ledger_is_not_a_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for name in ("farmacias-avila.json", "farmacias-registro-jcyl.json", "farmacias-soria.json",
                         "farmacias-osm-espana.json", "farmacias-espana-hoy.json", "farmacias-todas.json",
                         "farmacias-coordenadas-verificadas.json"):
                (output / name).write_text("[]", encoding="utf-8")

            self.assertEqual([path.name for path in catalog_paths(output)],
                             ["farmacias-registro-jcyl.json", "farmacias-avila.json", "farmacias-soria.json"])


if __name__ == "__main__":
    unittest.main()
