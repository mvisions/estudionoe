import unittest

from registro_jcyl import PROVINCES, SOURCE, build_catalog, build_row, street_name


def item(registration="42-E1-00050", **fields):
    return {
        "num_reg": registration, "nombre_comercial": "GARCIA LOPEZ, ANA", "telefono": 975123456,
        "calle": "CALLE COLLADO (EL)", "numero": "28", "localidad": "SORIA", "municipio": "SORIA",
        "codigo_postal": "42002", "provincia": "SORIA", **fields,
    }


def registry():
    names = {"05": "AVILA", "24": "LEON"}
    return [item(f"{code}-E1-00001", provincia=names.get(code, PROVINCES[code].upper()))
            for code in PROVINCES]


class RegistryRowTests(unittest.TestCase):
    def test_row_keeps_registration_id_phone_and_official_source(self):
        row = build_row(item())

        self.assertEqual(row["id"], "jcyl-42-e1-00050")
        self.assertEqual(row["num_reg"], "42-E1-00050")
        self.assertEqual(row["nombre"], "Farmacia Garcia Lopez, Ana")
        self.assertEqual(row["direccion"], "Calle el Collado, 28")
        self.assertEqual((row["localidad"], row["provincia"], row["codigo_postal"]), ("Soria", "Soria", "42002"))
        self.assertEqual(row["telefono"], "975123456")
        self.assertEqual(row["fuente"], SOURCE)
        self.assertEqual((row["lat"], row["lng"], row["guardia"]), (None, None, False))

    def test_trailing_ine_articles_move_before_the_street_name(self):
        self.assertEqual(street_name("CALLE TABLADA (LA)"), "Calle la Tablada")
        self.assertEqual(street_name("CTRA CONSTITUCION (DE LA)"), "Ctra de la Constitucion")
        self.assertEqual(street_name("PLAZA DOLORES (DE) (LOS)"), "Plaza de los Dolores")
        self.assertEqual(street_name("ALAMEDA (LA)"), "La Alameda")
        self.assertEqual(street_name("CALLE SAN JUAN (BARRIO ALTO)"), "Calle San Juan (Barrio Alto)")

    def test_missing_number_is_written_as_s_n(self):
        for number in ("S/N", "0", "", None):
            self.assertEqual(build_row(item(numero=number))["direccion"], "Calle el Collado, s/n")

    def test_locality_takes_accents_from_matching_municipality(self):
        row = build_row(item(localidad="SAN LEONARDO DE YAGUE", municipio="SAN LEONARDO DE YAGÜE"))
        self.assertEqual(row["localidad"], "San Leonardo de Yagüe")
        row = build_row(item(localidad="NAVALENO", municipio="SAN LEONARDO DE YAGÜE"))
        self.assertEqual(row["localidad"], "Navaleno")

    def test_province_must_match_registration_code(self):
        with self.assertRaises(ValueError):
            build_row(item(provincia="ZAMORA"))
        with self.assertRaises(ValueError):
            build_row(item("28-E1-00001", provincia="MADRID"))
        self.assertEqual(build_row(item("05-E1-00001", provincia="AVILA"))["provincia"], "Ávila")


class RegistryCatalogTests(unittest.TestCase):
    def test_complete_registry_has_one_row_per_province(self):
        rows = build_catalog(registry())
        self.assertEqual({row["provincia"] for row in rows}, set(PROVINCES.values()))

    def test_duplicated_missing_or_truncated_registry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "repite"):
            build_catalog([*registry(), item("42-E1-00001")])
        with self.assertRaisesRegex(ValueError, "Soria"):
            build_catalog([row for row in registry() if row["provincia"] != "SORIA"])
        with self.assertRaisesRegex(ValueError, "bajó"):
            build_catalog(registry(), previous_count=11)
        self.assertEqual(len(build_catalog(registry(), previous_count=10)), 9)

    def test_verified_ledger_location_is_applied_only_to_the_same_record_and_address(self):
        row = build_row(item("42-E1-00001"))
        saved = {key: row[key] for key in ("id", "provincia", "localidad", "direccion")}
        saved.update(lat=41.76, lng=-2.47, precision_ubicacion="farmacia", ajuste_ubicacion_m=4.2,
                     osm_id="osm-7")
        moved = {**saved, "direccion": "Calle Mayor, 1"}
        unverified = {**saved, "id": "jcyl-09-e1-00001", "provincia": "Burgos", "ajuste_ubicacion_m": 40}

        rows = {row["id"]: row for row in build_catalog(registry(), [saved, moved, unverified])}

        located = rows["jcyl-42-e1-00001"]
        self.assertEqual((located["lat"], located["lng"], located["osm_id"]), (41.76, -2.47, "osm-7"))
        self.assertEqual(sum(row["lat"] is not None for row in rows.values()), 1)


if __name__ == "__main__":
    unittest.main()
