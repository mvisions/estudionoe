import unittest
from datetime import date, time

from scrape_soria import build_row, combine, overnight_row, parse_day, parse_sheet, registry_match


TARGET = date(2026, 11, 2)
REGISTRY = [
    {"num_reg": "42-E1-00068", "nombre_comercial": "LERIDA GARCIA, MARIA MAR", "telefono": None,
     "calle": "CALLE VALONSADERO", "numero": "22", "localidad": "SORIA", "municipio": "SORIA",
     "provincia": "SORIA"},
    {"num_reg": "42-E1-00003", "nombre_comercial": "BENITO LOPEZ, MARIA TERESA", "telefono": 975301281,
     "calle": "CALLE RONDA DE SAN FRANCISCO", "numero": "1", "localidad": "ALMAZAN",
     "municipio": "ALMAZÁN", "provincia": "SORIA"},
    {"num_reg": "42-E1-00006", "nombre_comercial": "CARRASCOSA MARTINEZ, ANGELA", "telefono": 975301211,
     "calle": "CALLE SAN SALVADOR", "numero": "1", "localidad": "ALMAZAN", "municipio": "ALMAZÁN",
     "provincia": "SORIA"},
    {"num_reg": "42-E1-00030", "nombre_comercial": "MARIN VERGES, PAULA", "telefono": 975326354,
     "calle": "CTRA  BARAONA", "numero": "15", "localidad": "MEDINACELI", "municipio": "MEDINACELI",
     "provincia": "SORIA"},
]


def item_html(town, address, icons, sheet):
    spans = "".join(f'<span class="icon-{icon}"></span>' for icon in icons)
    return (
        '<div class="farmacia-item">'
        f'<div class="farmacia-municipio"> {town} </div>'
        f'<div class="farmacia-direccion"> {address} </div>'
        f'<div class="farmacia-horario"> {spans} </div>'
        f'<div class="farmacia-ficha"> <a href="?farmacia={sheet}">Ver ficha</a> </div>'
        "</div>"
    )


def day_page(day="2", capital_icons=("sol", "luna"), province_icons=("sol",), notice=True):
    return (
        '<form method="GET">'
        f'<select name="dia"><option value="1">1</option><option value="{day}" selected>{day}</option></select>'
        '<select name="mes"><option value="11" selected>noviembre</option></select>'
        '<select name="anio"><option value="2026" selected>2026</option></select>'
        "</form>"
        '<div class="bloque-tipo-farmacia"><h3>Soria Capital</h3>'
        '<span class="horario-info"><span class="icon-sol"></span><span class="icon-luna"></span> 24 Horas</span>'
        '<span class="nota-servicio">Desde las 9:00h del día indicado hasta las 9:00h del día siguiente</span>'
        '</div><div class="lista-farmacias">'
        + item_html("Soria", "Calle VALONSADERO 22", capital_icons, 66)
        + '</div><div class="bloque-tipo-farmacia"><h3>Provincia de Soria</h3></div>'
        '<div class="lista-farmacias">'
        + item_html("Almazán", "Calle RONDA SAN FRANCISCO 1", ("sol", "luna"), 84)
        + item_html("Medinaceli", "Carretera BARAHONA", province_icons, 94)
        + "</div><h3>Mapa de Farmacias de Guardia</h3>"
        + ('<div class="aviso-localizado">Guardia de forma LOCALIZADA.</div>' if notice else "")
        + "<script>L.marker([41.7695, -2.47493]).addTo(map).bindPopup('<a href=\"?farmacia=66\">Ver ficha</a>');"
        "L.marker([41.1663, -2.42404]).addTo(map).bindPopup('<a href=\"?farmacia=94\">Ver ficha</a>');</script>"
    )


def sheet_page(town="Soria", titular="Mª DEL MAR LERIDA GARCIA", phone="+34 975 230 709"):
    return (
        '<div class="farmacia-ficha"><div class="ficha-volver"><a href="/">Volver</a></div>'
        f'<div class="ficha-header"><div class="ficha-municipio"> {town} </div>'
        '<div class="ficha-direccion"> Calle VALONSADERO 22, 42005 </div>'
        f'<div class="ficha-titular"> {titular} </div></div>'
        '<div class="ficha-dato"><div class="ficha-dato-label">Teléfono</div>'
        f'<div class="ficha-dato-valor"><a href="tel:{phone}">{phone}</a></div></div>'
        '<div class="ficha-dato"><div class="ficha-dato-label">Tipo de Guardia</div>'
        '<div class="ficha-dato-valor"> 24HORAS </div></div></div>'
    )


class ParseDayTests(unittest.TestCase):
    def test_sun_and_moon_icons_set_the_published_schedule(self):
        items, localized = parse_day(day_page(), TARGET)

        self.assertTrue(localized)
        capital, almazan, medinaceli = items
        self.assertEqual((capital["bloque"], capital["turno"], capital["horas"]),
                         ("Soria Capital", "24 horas", (time(9), time(9))))
        self.assertEqual(capital["punto"], (41.7695, -2.47493))
        self.assertEqual((almazan["turno"], almazan["horas"], almazan["punto"]), ("24 horas", None, None))
        self.assertEqual((medinaceli["turno"], medinaceli["horas"]), ("hasta las 22:00", None))
        self.assertEqual(medinaceli["direccion"], "Carretera BARAHONA")

    def test_other_selected_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no 02/11/2026"):
            parse_day(day_page(day="3"), TARGET)

    def test_unknown_icon_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Iconos de horario no reconocidos"):
            parse_day(day_page(province_icons=("luna",)), TARGET)

    def test_missing_localized_notice_is_reported(self):
        self.assertFalse(parse_day(day_page(notice=False), TARGET)[1])


class SheetAndRegistryTests(unittest.TestCase):
    def setUp(self):
        self.items = parse_day(day_page(), TARGET)[0]

    def test_sheet_fields(self):
        self.assertEqual(parse_sheet(sheet_page()), {
            "municipio": "Soria", "direccion": "Calle VALONSADERO 22, 42005",
            "titular": "Mª DEL MAR LERIDA GARCIA", "telefono": "975230709", "tipo": "24HORAS",
        })

    def test_same_house_number_on_another_street_is_not_confused(self):
        sheet = parse_sheet(sheet_page("Almazán", "Mª TERESA BENITO LOPEZ", "975 301 281"))

        self.assertEqual(registry_match(self.items[1], sheet, REGISTRY)["num_reg"], "42-E1-00003")

    def test_a_single_coincidence_is_ambiguous(self):
        sheet = parse_sheet(sheet_page("Almazán", "OTRA PERSONA", "975 000 000"))

        with self.assertRaisesRegex(ValueError, "No se identifica de forma única"):
            registry_match(self.items[1], sheet, REGISTRY)

    def test_address_without_number_takes_the_official_registry_number(self):
        sheet = parse_sheet(sheet_page("Medinaceli", "PAULA MARÍN VERGÉS", "975 326 354"))
        official = registry_match(self.items[2], sheet, REGISTRY)

        row = build_row(self.items[2], sheet, official, TARGET, "https://cof.example/?farmacia=94")

        self.assertEqual(row["id"], "jcyl-42-e1-00030")
        self.assertEqual(row["direccion"], "Ctra Baraona, 15")
        self.assertEqual(row["guardia_intervalos"], [])
        self.assertEqual(row["guardia_apertura"], "desconocida")
        self.assertIn("hasta las 22:00", row["guardia_franjas"][0])
        self.assertIn("localizada", row["guardia_franjas"][1])
        self.assertEqual(row["referencia_ubicacion"]["lat"], 41.1663)
        self.assertIsNone(row["lat"])


class CapitalScheduleTests(unittest.TestCase):
    def setUp(self):
        item = parse_day(day_page(), TARGET)[0][0]
        sheet = parse_sheet(sheet_page())
        self.row = build_row(item, sheet, REGISTRY[0], TARGET, "https://cof.example/?farmacia=66")

    def test_capital_duty_runs_from_nine_to_nine_next_day(self):
        self.assertEqual(self.row["guardia_intervalos"], [
            {"inicio": "2026-11-02T09:00:00+01:00", "fin": "2026-11-03T09:00:00+01:00"},
        ])
        self.assertNotIn("guardia_apertura", self.row)

    def test_previous_capital_duty_covers_the_early_morning(self):
        night = overnight_row(self.row, date(2026, 11, 3))

        self.assertEqual(night["guardia_intervalos"], [
            {"inicio": "2026-11-03T00:00:00+01:00", "fin": "2026-11-03T09:00:00+01:00"},
        ])
        self.assertTrue(night["guardia_desde_ayer"])
        self.assertEqual(night["fecha_guardia"], "2026-11-03")

    def test_same_pharmacy_on_consecutive_days_keeps_both_intervals(self):
        today = {**self.row, "fecha_guardia": "2026-11-03", "guardia_intervalos": [
            {"inicio": "2026-11-03T09:00:00+01:00", "fin": "2026-11-04T09:00:00+01:00"}]}

        (row,) = combine([overnight_row(self.row, date(2026, 11, 3)), today])

        self.assertEqual([interval["inicio"] for interval in row["guardia_intervalos"]],
                         ["2026-11-03T00:00:00+01:00", "2026-11-03T09:00:00+01:00"])
        self.assertNotIn("guardia_desde_ayer", row)
        self.assertEqual(row["guardia_franja"], " · ".join(row["guardia_franjas"]))


if __name__ == "__main__":
    unittest.main()
