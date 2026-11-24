import unittest
from datetime import date

import scrape_asturias as cof


DAY = date(2026, 11, 2)


def section(hours, label, name="Farmacia Test", internal="896", phone="985115427", town="OVIEDO"):
    return f'''<h5 class="HorarioGuardias"><a name='{hours}'>{label}</a></h5>
    <h6 class="LocalidadGuardias">{town}</h6><ul class="ListadoResultados"><li>
    <span class="TituloResultado">{name}</span>
    <span class="ico-localizacion">Dirección: C/ LA TENDERINA 207-33010</span>
    <span class="ico-telefono">Teléfono: {phone}</span>
    <a href="javascript:VerMapa('A','B','C','D','E','475','{internal}')">Ver Mapa</a>
    </li></ul>'''


def page(body, day="02", city="OVIEDO"):
    return (f'<h3 class="FechaGuardias"><span>Lunes {day} de Noviembre de 2026</span></h3>'
            f'<h4 class="MunicipioGuardias">{city}</h4>' + body)


def rows(body, previous=None, city="OVIEDO"):
    entries = cof.parse_page(page(body, city=city), DAY)
    before = cof.parse_page(page(previous, day="01", city=city), date(2026, 11, 1)) if previous else []
    return cof.build_rows(entries, before, DAY)


class AsturiasTests(unittest.TestCase):
    def test_previous_and_next_night_are_clipped_and_merged(self):
        body = section("00:00 - 09:30", "Desde las 10 de la noche de ayer a las 9,30 horas de hoy")
        body += section("22:00 - 09:30", "Desde las 10 de la noche de hoy a las 9,30 horas de mañana")
        result = rows(body, previous=section("22:00 - 09:30", "Desde las 10 de la noche de hoy", internal="7"))
        self.assertEqual(len(result), 1, "own early-morning shift: no carry-over from the day before")
        self.assertEqual(result[0]["direccion"], "C/ LA TENDERINA 207")
        self.assertEqual(result[0]["guardia_intervalos"], [
            {"inicio": "2026-11-02T00:00:00", "fin": "2026-11-02T09:30:00", "tipo": "nocturna"},
            {"inicio": "2026-11-02T22:00:00", "fin": "2026-11-03T00:00:00", "tipo": "nocturna"},
        ])

    def test_24_hour_shift_from_9_30_carries_into_next_morning(self):
        label = "De 9,30 de la mañana de hoy a 9,30 de la mañana de mañana"
        result = rows(section("09:30 - 09:30", label, town="LUGONES"),
                      previous=section("09:30 - 09:30", label, internal="5", name="Anterior", town="LUGONES"),
                      city="SIERO")
        by_id = {row["id"]: row for row in result}
        today, before = by_id["cof-asturias-896"], by_id["cof-asturias-5"]
        self.assertEqual((today["localidad"], today["municipio"]), ("Lugones", "Siero"))
        self.assertEqual(today["guardia_intervalos"],
                         [{"inicio": "2026-11-02T09:30:00", "fin": "2026-11-03T00:00:00", "tipo": "24 horas"}])
        self.assertEqual(before["guardia_intervalos"],
                         [{"inicio": "2026-11-02T00:00:00", "fin": "2026-11-02T09:30:00", "tipo": "24 horas"}])
        self.assertIn("Continúa el turno del 01/11", before["guardia_franja"])

    def test_explicit_24_hour_and_on_call_shifts(self):
        row = rows(section("00:00 - 00:00", "Las 24 horas"))[0]
        self.assertEqual(row["guardia_intervalos"][0]["fin"], "2026-11-03T00:00:00")
        self.assertEqual(row["guardia_intervalos"][0]["tipo"], "24 horas")
        row = rows(section("00:00 - 00:00", "Guardia no presencial"))[0]
        self.assertIn("llamar antes de acudir", row["guardia_franja"])

    def test_municipality_names(self):
        self.assertEqual(cof.place_name("S.M.R.A."), "San Martín del Rey Aurelio")
        self.assertEqual(cof.place_name("PEÑAMELLERA BAJA"), "Peñamellera Baja")
        self.assertEqual(cof.place_name("EL FRANCO"), "El Franco")

    def test_invalid_date_shift_and_phone_fail_closed(self):
        shift = section("09:30 - 22:00", "De 9,30 horas a 10 de la noche")
        for value in (page(shift, day="03"), page(section("Mañanas", "Otro horario")),
                      page(section("09:30 - 22:00", "De 9,30 horas a 10 de la noche", phone="123")),
                      page(shift).replace('<h4 class="MunicipioGuardias">OVIEDO</h4>', "")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cof.parse_page(value, DAY)


if __name__ == "__main__":
    unittest.main()
