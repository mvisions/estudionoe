import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import scrape_pontevedra as cof


INDEX = '''<select id="municipio"><option value="">Municipio</option>
<option value="1">Vigo</option><option value="2">Pontevedra</option>
<option value="3">Bueu</option></select>'''
CARD = '''<div class="ficha_farmacia"><strong>Farmacia Prueba</strong>
<ul><li>Calle Uno, 5</li><li>986123456</li></ul></div>'''


def schedule(town="Vigo", month="Noviembre de 2026"):
    def section(shift, cards):
        return (f'<div class="titulo_tipo_horario"><span>{shift}</span></div>'
                f'<table><tr><td class="center">2</td><td>{cards}</td></tr></table>')
    return (f'<span>{town}</span> <span>{month}</span>'
            + section("Diurno", CARD) + section("Nocturno", CARD))


class PontevedraTests(unittest.TestCase):
    def test_selectors_include_unconsulted_municipalities(self):
        self.assertEqual(cof.selectors(INDEX), [("1", "Vigo"), ("2", "Pontevedra"), ("3", "Bueu")])

    def test_shifts_are_merged_without_inventing_hours(self):
        rows = cof.parse(schedule(), "Vigo", date(2026, 11, 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["telefono"], "986123456")
        self.assertEqual(len(rows[0]["guardia_franjas"]), 2)
        self.assertNotIn("guardia_intervalos", rows[0])
        self.assertIsNone(rows[0]["lat"])

    def test_wrong_date_or_city_and_missing_turn_fail_closed(self):
        for content in (schedule(month="Octubre de 2026"), schedule(town="Pontevedra"),
                        schedule().replace("Nocturno", "Otro")):
            with self.subTest(content=content), self.assertRaises(ValueError):
                cof.parse(content, "Vigo", date(2026, 11, 2))

    def test_invalid_ficha_does_not_publish_partial_city(self):
        with self.assertRaises(ValueError):
            cof.parse(schedule().replace("986123456", "123"), "Vigo", date(2026, 11, 2))

    def test_reverse_portal_requires_same_address_unique_phone_and_15m(self):
        row = cof.parse(schedule(), "Vigo", date(2026, 11, 2))[0]
        pharmacy = {"id": "osm-100", "provincia": "Pontevedra", "telefono": "+34 986123456",
                    "lat": 42.24, "lng": -8.7}
        reference = {"type": "portal", "noNumber": False, "muni": "Vigo", "address": "CALLE UNO",
                     "portalNumber": 5, "lat": 42.24005, "lng": -8.7}

        class FakeGeocoder:
            errors = 0

            def lookup(self, key, url, compact):
                return reference

            def save(self):
                pass

        cof.locate([row], [pharmacy], FakeGeocoder())
        self.assertEqual(row["lat"], pharmacy["lat"])
        self.assertLessEqual(row["ajuste_ubicacion_m"], 15)
        row = cof.parse(schedule(), "Vigo", date(2026, 11, 2))[0]
        reference["portalNumber"] = 6
        cof.locate([row], [pharmacy], FakeGeocoder())
        self.assertIsNone(row["lat"])
        reference["portalNumber"] = 5
        reference["lat"] = 42.241
        cof.locate([row], [pharmacy], FakeGeocoder())
        self.assertIsNone(row["lat"])
        reference["lat"] = 42.24005
        cof.locate([row], [pharmacy, {**pharmacy, "id": "osm-101"}], FakeGeocoder())
        self.assertIsNone(row["lat"])

    def test_publication_is_partial_and_preserves_verified_coordinates(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "data"
            output.mkdir()
            prior = cof.parse(schedule(), "Vigo", date(2026, 11, 2))[0]
            prior.update(lat=42.2, lng=-8.7, ajuste_ubicacion_m=4.0)
            (output / "farmacias-pontevedra.json").write_text(json.dumps([prior]))

            def fake_fetch(url, params=None):
                return INDEX if params is None else schedule(params["municipio_nombre"])

            with patch.object(cof, "fetch", side_effect=fake_fetch), patch.object(cof.time, "sleep"):
                complete = cof.run(date(2026, 11, 2), root / "cache", output)
            self.assertFalse(complete)
            duties = json.loads((output / "guardias-pontevedra-2026-11-02.json").read_text())
            coverage = json.loads((output / "cobertura-pontevedra-2026-11-02.json").read_text())
            self.assertEqual(len(duties), 2)
            self.assertEqual(next(row for row in duties if row["localidad"] == "Vigo")["ajuste_ubicacion_m"], 4.0)
            self.assertEqual(coverage["con_coordenadas"], 1)
            self.assertFalse(coverage["completa"])
            self.assertEqual(next(row for row in coverage["consultas"] if row["nombre"] == "Bueu")["estado"], "pendiente")


if __name__ == "__main__":
    unittest.main()
