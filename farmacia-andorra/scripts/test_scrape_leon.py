import unittest
from datetime import date

from scrape_leon import parse_calendar


REGISTRY = [
    {
        "num_reg": "24-E1-00001",
        "nombre_comercial": "Farmacia de prueba",
        "telefono": 987123456,
        "calle": "CALLE MAYOR",
        "numero": "1",
        "localidad": "LEON",
        "provincia": "LEON",
    },
    {
        "num_reg": "24-E1-00002",
        "nombre_comercial": "Farmacia de prueba",
        "telefono": None,
        "calle": "PLAZA MAYOR",
        "numero": "S/N",
        "localidad": "ALMANZA",
        "municipio": "ALMANZA",
        "provincia": "LEON",
    },
    {
        "num_reg": "24-E1-00095",
        "nombre_comercial": "Farmacia de prueba",
        "telefono": 987741054,
        "calle": "CALLE JOSE ANTONIO",
        "numero": "6",
        "localidad": "VECILLA DE CURUEÑO (LA)",
        "municipio": "VECILLA, LA",
        "provincia": "LEON",
    },
    {
        "num_reg": "34-E1-00003",
        "nombre_comercial": "Farmacia de prueba de Palencia",
        "telefono": 979880029,
        "calle": "PLAZA GENERALISIMO",
        "numero": "14",
        "localidad": "CARRION DE LOS CONDES",
        "municipio": "CARRIÓN DE LOS CONDES",
        "provincia": "PALENCIA",
    },
    {
        "num_reg": "47-E1-00085",
        "nombre_comercial": "SABORIDO COIRADAS, RAQUEL",
        "telefono": None,
        "calle": "CALLE CRUZ",
        "numero": "17",
        "localidad": "UNION DE CAMPOS (LA)",
        "municipio": "UNIÓN DE CAMPOS, LA",
        "provincia": "VALLADOLID",
    },
]


def row(index, address, phone, nocturnal, schedule="", name="TITULAR DE PRUEBA"):
    schedule_markup = (
        f'<span class="farmacia-horario">{schedule}</span>' if schedule else ""
    )
    return (
        f'<tr data-index="{index}" data-nocturna="{str(nocturnal).lower()}"><td>'
        f'<span class="farmacia-nombre">{name}</span>'
        f'<span class="farmacia-direccion">{address}</span>'
        f'<span class="farmacia-telefono">{phone} - '
        f'<span class="farmacia-nocturna">{"Nocturna" if nocturnal else "Diurna"}</span></span>'
        f"{schedule_markup}"
        "</td></tr>"
    )


def calendar(rows):
    return f'<table id="farmaciasList">{"".join(rows)}</table>'


class LeonCalendarTests(unittest.TestCase):
    def setUp(self):
        self.target = date(2026, 11, 2)

    def test_extracts_and_clips_previous_night_and_keeps_day_hours_unknown(self):
        content = calendar([
            row(0, "CALLE MAYOR, 1 LEÓN", "987 123 456", True,
                "Horario nocturno, desde las 22:00 del día 01/11 hasta las 9:30 del día 02/11"),
            row(1, "CALLE MAYOR, 1 LEÓN", "987 123 456", False),
            row(2, "CALLE MAYOR, 1 LEÓN", "987 123 456", True,
                "Horario nocturno, desde las 22:00 del día 02/11 hasta las 9:30 del día 03/11"),
        ])

        rows = parse_calendar(content, self.target, REGISTRY)

        self.assertEqual(len(rows), 1)
        pharmacy = rows[0]
        self.assertEqual(pharmacy["id"], "jcyl-24-e1-00001")
        self.assertEqual(pharmacy["localidad"], "Leon")
        self.assertEqual(pharmacy["telefono"], "987123456")
        self.assertEqual(len(pharmacy["guardia_intervalos"]), 2)
        self.assertEqual(pharmacy["guardia_intervalos"][0]["inicio"], "2026-11-02T00:00:00+01:00")
        self.assertEqual(pharmacy["guardia_intervalos"][0]["fin"], "2026-11-02T09:30:00+01:00")
        self.assertEqual(pharmacy["guardia_intervalos"][1]["inicio"], "2026-11-02T22:00:00+01:00")
        self.assertEqual(pharmacy["guardia_intervalos"][1]["fin"], "2026-11-03T09:30:00+01:00")
        self.assertTrue(pharmacy["guardia_desde_ayer"])
        self.assertEqual(pharmacy["guardia_apertura"], "desconocida")
        self.assertTrue(pharmacy["ubicacion_requiere_verificacion"])

    def test_does_not_accept_night_periods_for_another_date(self):
        content = calendar([
            row(0, "CALLE MAYOR, 1 LEÓN", "987 123 456", True,
                "Horario nocturno, desde las 31/10 hasta las 01/11"),
            row(1, "CALLE MAYOR, 1 LEÓN", "987 123 456", False),
        ])

        with self.assertRaisesRegex(ValueError, "fechas y horas oficiales"):
            parse_calendar(content, self.target, REGISTRY)

    def test_rejects_missing_municipality_in_official_registry(self):
        content = calendar([
            row(0, "CALLE MAYOR, 1 LUGAR DESCONOCIDO", "987 123 456", False),
        ])

        with self.assertRaisesRegex(ValueError, "No se identifica el municipio"):
            parse_calendar(content, self.target, REGISTRY)

    def test_splits_source_address_when_locality_is_attached_to_the_street_number(self):
        content = calendar([
            row(0, "PZ MAYOR, S/NALMANZA", "987 710 071", False),
            row(1, "CALLE MAYOR, 1 LEÓN", "987 123 456", True,
                "Horario nocturno, desde las 22:00 del día 01/11 hasta las 9:30 del día 02/11"),
            row(2, "CALLE MAYOR, 1 LEÓN", "987 123 456", True,
                "Horario nocturno, desde las 22:00 del día 02/11 hasta las 9:30 del día 03/11"),
        ])

        rows = parse_calendar(content, self.target, REGISTRY)

        almanza = next(pharmacy for pharmacy in rows if pharmacy["localidad"] == "Almanza")
        self.assertEqual(almanza["direccion"], "PZ MAYOR, S/N")

    def test_resolves_official_calendar_municipality_alias(self):
        night_before = "Horario nocturno, desde las 22:00 del día 01/11 hasta las 9:30 del día 02/11"
        night_today = "Horario nocturno, desde las 22:00 del día 02/11 hasta las 9:30 del día 03/11"
        content = calendar([
            row(0, "CR DE CURUEÑO, 82 VECILLA (LA)", "987 741 054", True, night_before),
            row(1, "CR DE CURUEÑO, 82 VECILLA (LA)", "987 741 054", False),
            row(2, "CR DE CURUEÑO, 82 VECILLA (LA)", "987 741 054", True, night_today),
        ])

        pharmacies = parse_calendar(content, self.target, REGISTRY)

        self.assertEqual(len(pharmacies), 1)
        self.assertEqual(pharmacies[0]["id"], "jcyl-24-e1-00095")
        self.assertEqual(pharmacies[0]["localidad"], "Vecilla De Curueño (La)")

    def test_excludes_unique_official_pharmacy_registered_outside_leon(self):
        night_before = "Horario nocturno, desde las 22:00 del día 01/11 hasta las 9:30 del día 02/11"
        night_today = "Horario nocturno, desde las 22:00 del día 02/11 hasta las 9:30 del día 03/11"
        content = calendar([
            row(0, "CALLE MAYOR, 1 LEÓN", "987 123 456", True, night_before),
            row(1, "CALLE MAYOR, 1 LEÓN", "987 123 456", True, night_today),
            row(2, "CALLE MAYOR, 1 LEÓN", "987 123 456", False),
            row(3, "PLAZA MAYOR 16CARRIÓN DE LOS CONDES", "979 880 029", True, night_today),
        ])

        pharmacies = parse_calendar(content, self.target, REGISTRY)

        self.assertEqual(len(pharmacies), 1)
        self.assertEqual(pharmacies[0]["localidad"], "Leon")

    def test_excludes_phoneless_registry_pharmacy_outside_leon_by_name_and_address(self):
        night_before = "Horario nocturno, desde las 22:00 del día 01/11 hasta las 9:30 del día 02/11"
        night_today = "Horario nocturno, desde las 22:00 del día 02/11 hasta las 9:30 del día 03/11"
        rows = [
            row(0, "CALLE MAYOR, 1 LEÓN", "987 123 456", True, night_before),
            row(1, "CALLE MAYOR, 1 LEÓN", "987 123 456", True, night_today),
            row(2, "CALLE MAYOR, 1 LEÓN", "987 123 456", False),
        ]
        outside = "C/ LA CRUZ Nº 17 UNIÓN DE CAMPOS (LA)"

        pharmacies = parse_calendar(
            calendar(rows + [row(3, outside, "618646123", False, name="RAQUEL SABORIDO")]),
            self.target, REGISTRY,
        )
        self.assertEqual([pharmacy["localidad"] for pharmacy in pharmacies], ["Leon"])

        with self.assertRaisesRegex(ValueError, "No se identifica el municipio oficial"):
            parse_calendar(
                calendar(rows + [row(3, outside, "618646123", False, name="OTRA TITULAR")]),
                self.target, REGISTRY,
            )

    def test_rejects_missing_rota_category_or_incomplete_rows(self):
        content = calendar([
            row(0, "CALLE MAYOR, 1 LEÓN", "987 123 456", False),
        ])

        with self.assertRaisesRegex(ValueError, "no confirma madrugada anterior"):
            parse_calendar(content, self.target, REGISTRY)


if __name__ == "__main__":
    unittest.main()
