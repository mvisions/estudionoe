import unittest
from datetime import date

from scrape_zamora import parse_calendar


REGISTRY = [
    {
        "num_reg": "49-E1-00001",
        "nombre_comercial": "LOPEZ ARIAS TESTA, JOSE ANTONIO",
        "telefono": 980531510,
        "calle": "CALLE SANTA CLARA",
        "numero": "6",
        "localidad": "ZAMORA",
        "provincia": "ZAMORA",
    },
    {
        "num_reg": "49-E1-00002",
        "nombre_comercial": "RODRIGUEZ RAMOS, CATALINA",
        "telefono": None,
        "calle": "CALLE CALLE VEGA",
        "numero": "1",
        "localidad": "ZAMORA",
        "provincia": "ZAMORA",
    },
]


def page(day="2", month="11", year="2026", zone="Zamora Capital", nocturnal=True):
    shifts = (
        " Nocturna LA VEGA, 1 Dirección: LA VEGA, 1 Nombre: RODRIGUEZ RAMOS, CATALINA "
        "Teléfono: 980510159"
        if nocturnal else ""
    )
    return (
        '<form id="vista-mes-completo-settings">'
        f'<select name="zonasGuardia"><option value="{zone}" selected>{zone}</option></select>'
        f'<select name="listaMeses"><option value="{month}" selected>Noviembre</option></select>'
        f'<select name="listaAnios"><option value="{year}" selected>{year}</option></select>'
        "</form>"
        "<table><tr><td>"
        f'{day} Diurna SANTA CLARA, 6 Dirección: SANTA CLARA, 6 '
        f"Nombre: LOPEZ-ARIAS TESTA, JOSE ANTONIO Teléfono: 980531510{shifts}"
        "</td></tr></table>"
    )


class ZamoraCalendarTests(unittest.TestCase):
    def setUp(self):
        self.target = date(2026, 11, 2)

    def test_imports_only_selected_date_and_matches_both_official_pharmacies(self):
        rows = parse_calendar(page(), self.target, REGISTRY)

        self.assertEqual(len(rows), 2)
        diurna = next(row for row in rows if "diurna" in row["guardia_franja"].lower())
        nocturna = next(row for row in rows if "nocturna" in row["guardia_franja"].lower())
        self.assertEqual(diurna["id"], "jcyl-49-e1-00001")
        self.assertEqual(nocturna["id"], "jcyl-49-e1-00002")
        self.assertEqual(nocturna["direccion"], "CALLE CALLE VEGA, 1")
        self.assertEqual(diurna["fecha_guardia"], "2026-11-02")
        self.assertEqual(diurna["guardia_intervalos"], [])
        self.assertEqual(diurna["guardia_apertura"], "desconocida")
        self.assertTrue(diurna["ubicacion_requiere_verificacion"])

    def test_rejects_calendar_for_another_month(self):
        with self.assertRaisesRegex(ValueError, "no 2026-11"):
            parse_calendar(page(month="10"), self.target, REGISTRY)

    def test_rejects_a_different_selected_zone(self):
        with self.assertRaisesRegex(ValueError, "no confirma la zona Zamora Capital"):
            parse_calendar(page(zone="Benavente"), self.target, REGISTRY)

    def test_rejects_day_without_both_published_shifts(self):
        with self.assertRaisesRegex(ValueError, "no confirma los turnos diurno y nocturno"):
            parse_calendar(page(nocturnal=False), self.target, REGISTRY)

    def test_rejects_ambiguous_official_identity(self):
        registry = [*REGISTRY, {**REGISTRY[0], "num_reg": "49-E1-00003"}]
        with self.assertRaisesRegex(ValueError, "No se identifica de forma única"):
            parse_calendar(page(), self.target, registry)


if __name__ == "__main__":
    unittest.main()
