import unittest

from locate_guardias import verified_within_radius
from proximidad import (PharmacyIndex, Reference, contradicts, nearby_pharmacies, official_references,
                        propose, resolve)


class ProximityVerificationTests(unittest.TestCase):
    def setUp(self):
        self.row = {"id": "test-pharmacy", "direccion": "CALLE MAYOR, 1", "localidad": "Leon"}
        self.pharmacy = Reference(
            (42.6, -5.57), "osm", "pharmacy",
            "https://www.openstreetmap.org/node/1", "osm-1",
        )

    def test_single_osm_pharmacy_reference_remains_pending(self):
        proposal = propose(self.row, [self.pharmacy], PharmacyIndex([]))

        placements, pending = resolve({"test-pharmacy": proposal})

        self.assertEqual(placements, {})
        self.assertEqual(pending, {"test-pharmacy": "sin_referencia"})

    def test_independent_reference_within_15m_is_recorded(self):
        independent = Reference(
            (42.60001, -5.57), "cartociudad", "address", "https://www.cartociudad.es/"
        )

        placements, pending = resolve({
            "test-pharmacy": propose(self.row, [self.pharmacy, independent], PharmacyIndex([]))
        })

        location = placements["test-pharmacy"]
        self.assertEqual(pending, {})
        self.assertLessEqual(location["ajuste_ubicacion_m"], 15)
        self.assertIn("fuente independiente", location["nota_ubicacion"])
        self.assertTrue(verified_within_radius(location))

    def test_independent_reference_outside_15m_is_not_confirmed(self):
        independent = Reference(
            (42.6002, -5.57), "cartociudad", "address", "https://www.cartociudad.es/"
        )

        placements, pending = resolve({
            "test-pharmacy": propose(self.row, [self.pharmacy, independent], PharmacyIndex([]))
        })

        self.assertEqual(placements, {})
        self.assertEqual(pending, {"test-pharmacy": "sin_referencia"})

    def test_saved_location_requires_coordinates_and_a_distance_at_most_15m(self):
        self.assertTrue(verified_within_radius({"lat": 42.6, "lng": -5.57, "ajuste_ubicacion_m": 15}))
        self.assertFalse(verified_within_radius({"lat": 42.6, "lng": -5.57, "ajuste_ubicacion_m": 15.1}))
        self.assertFalse(verified_within_radius({"lat": 42.6, "lng": -5.57}))
        self.assertFalse(verified_within_radius({"ajuste_ubicacion_m": 5}))


class OfficialReferenceTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "official", "direccion": "CALLE MAYOR, 1", "localidad": "Soria",
            "referencia_ubicacion": {"lat": 41.7695, "lng": -2.47493, "fuente": "https://cof.example/?farmacia=1"},
        }
        self.official = official_references(self.row)

    def test_official_point_is_an_address_reference_only_when_valid(self):
        self.assertEqual(self.official, [Reference((41.7695, -2.47493), "oficial", "address",
                                                   "https://cof.example/?farmacia=1")])
        self.assertEqual(official_references({"referencia_ubicacion": {"lat": None, "lng": 1}}), [])
        self.assertEqual(official_references({}), [])

    def test_official_point_alone_is_not_placed(self):
        placements, pending = resolve({"official": propose(self.row, self.official, PharmacyIndex([]))})

        self.assertEqual(placements, {})
        self.assertEqual(pending, {"official": "una_sola_fuente"})

    def test_official_point_and_address_within_15m_are_placed(self):
        address = Reference((41.76955, -2.47493), "cartociudad", "address", "https://www.cartociudad.es/")

        placements, pending = resolve({
            "official": propose(self.row, [address, *self.official], PharmacyIndex([]))
        })

        self.assertEqual(pending, {})
        self.assertLessEqual(placements["official"]["ajuste_ubicacion_m"], 15)
        self.assertEqual(
            placements["official"]["nota_ubicacion"],
            "CartoCiudad (IGN) y el mapa oficial de la fuente de guardias sitúan esta dirección "
            "a menos de 15 m entre sí.",
        )

    def test_official_point_far_from_address_is_a_conflict(self):
        address = Reference((41.7697, -2.47493), "cartociudad", "address", "https://www.cartociudad.es/")

        placements, pending = resolve({
            "official": propose(self.row, [address, *self.official], PharmacyIndex([]))
        })

        self.assertEqual(placements, {})
        self.assertEqual(pending, {"official": "conflicto"})

    def test_official_point_next_to_one_osm_pharmacy_uses_that_pharmacy(self):
        pharmacy = {"id": "osm-7", "lat": 41.76955, "lng": -2.4749, "direccion": "Calle Mayor 1"}

        placements, pending = resolve({
            "official": propose(self.row, self.official, PharmacyIndex([pharmacy]))
        })

        location = placements["official"]
        self.assertEqual(pending, {})
        self.assertEqual((location["lat"], location["lng"], location["osm_id"]), (41.76955, -2.4749, "osm-7"))
        self.assertLessEqual(location["ajuste_ubicacion_m"], 15)
        self.assertIn("el mapa oficial de la fuente de guardias y una farmacia de OpenStreetMap",
                      location["nota_ubicacion"])


class NearbyPharmacyTests(unittest.TestCase):
    def setUp(self):
        self.row = {"id": "jcyl-1", "direccion": "Calle Mayor, 1", "localidad": "Soria"}
        self.point = (41.7695, -2.47493)
        self.node = {"id": "osm-7", "lat": 41.76951, "lng": -2.47493}

    def test_records_linked_to_the_same_osm_node_count_once(self):
        linked = {"id": "cof-3", "lat": 41.76951, "lng": -2.47493, "osm_id": "osm-7"}

        found = nearby_pharmacies(self.row, PharmacyIndex([linked, self.node]), self.point)

        self.assertEqual([pharmacy["id"] for _, pharmacy in found], ["osm-7"])

    def test_distinct_nodes_remain_ambiguous(self):
        other = {"id": "osm-8", "lat": 41.76952, "lng": -2.47493}

        found = nearby_pharmacies(self.row, PharmacyIndex([self.node, other]), self.point)

        self.assertEqual([pharmacy["id"] for _, pharmacy in found], ["osm-7", "osm-8"])

    def test_group_is_discarded_when_a_linked_record_contradicts_the_row(self):
        linked = {"id": "cof-3", "lat": 41.76951, "lng": -2.47493, "osm_id": "osm-7",
                  "direccion": "Calle Mayor, 40", "localidad": "Soria"}
        self.assertTrue(contradicts(self.row, linked))

        self.assertEqual(nearby_pharmacies(self.row, PharmacyIndex([self.node, linked]), self.point), [])


if __name__ == "__main__":
    unittest.main()
