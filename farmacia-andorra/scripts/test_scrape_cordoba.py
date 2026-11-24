from datetime import date
import unittest

from scrape_cordoba import parse_schedule, selectors


DAY=date(2026,11,1)
TOWN={"codigo":"31","nombre":"Adamuz"}


def fixture(city="ADAMUZ"):
    return f"""
    <a href="javascript:resultados2026(01,11,2026,31)">Imprimir</a>
    <h2>FARMACIAS DE GUARDIA EN ADAMUZ EL DÍA 01 DE NOVIEMBRE</h2>
    <div class="textosubtitular">FARMACIA DE GUARDIA <b>HASTA LAS 22:00 HORAS</b></div>
    <tr><td class="textofarmacias"><a href="../farmacias/ampliada.php?id=37">IGLESIA,1 | </a>
    <a href='tel:957166037'>Teléfono</a></td><td class="textofarmacias">{city}</td></tr>
    <div class="textosubtitular">FARMACIA DE GUARDIA <b>TODA LA NOCHE</b></div>
    <tr><td class="textofarmacias"><a href="../farmacias/ampliada.php?id=37">IGLESIA,1 | </a>
    <a href='tel:957166037'>Teléfono</a></td><td class="textofarmacias">{city}</td></tr>
    """


class CordobaTests(unittest.TestCase):
    def test_capital_sector_is_not_used_as_a_geocoding_municipality(self):
        content=fixture("ZONA CENTRO").replace("2026,31)","2026,4)")
        rows=parse_schedule(content,DAY,{"codigo":"4","nombre":"CORDOBA"},"official")
        self.assertEqual(rows[0]["localidad"],"Córdoba")
        self.assertEqual(rows[0]["sector"],"ZONA CENTRO")

    def test_selector_and_same_pharmacy_day_night_merge(self):
        self.assertEqual(selectors('<select name="sltCiudad"><option value="31">ADAMUZ</option></select>'),
                         [{"codigo":"31","nombre":"ADAMUZ"}])
        rows=parse_schedule(fixture(),DAY,TOWN,"official")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["id"],"cof-cordoba-37")
        self.assertEqual(rows[0]["telefono"],"957166037")
        self.assertEqual(rows[0]["direccion"],"IGLESIA,1")
        self.assertEqual(len(rows[0]["guardia_franjas"]),2)
        self.assertIsNone(rows[0]["lat"])

    def test_wrong_date_wrong_town_and_empty_source_are_errors(self):
        for data,day,town in ((fixture(),date(2026,11,2),TOWN),
                              (fixture(),DAY,{"codigo":"32","nombre":"Otra"}),
                              ("Sin datos",DAY,TOWN)):
            with self.assertRaises(ValueError):
                parse_schedule(data,day,town,"official")

    def test_missing_locality_is_not_silently_inferred(self):
        with self.assertRaises(ValueError):
            parse_schedule(fixture("&nbsp;"),DAY,TOWN,"official")

    def test_valid_day_row_survives_unconfirmed_night_location(self):
        data=fixture().replace('<td class="textofarmacias">ADAMUZ</td></tr>',
                               '<td class="textofarmacias">&nbsp;</td></tr>',1)
        errors=[]
        rows=parse_schedule(data,DAY,TOWN,"official",errors)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]["guardia_franjas"]),1)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
