from datetime import date
import unittest

from scrape_caceres import parse_municipalities, parse_open_results, province_names


INDEX = """
<input name="_token" value="session-token">
<select name="municipio_id">
  <option value="">Seleccionar municipio</option>
  <option value="32">CACERES</option>
  <option value="193">Barco de Avila</option>
</select>
"""

RESULT = """
<select name="municipio_id">
  <option value="32" selected="selected">CACERES</option>
</select>
<a id="resultados"></a>
<div class="row mt-4 row-item-listado-farmacia">
  <div class="col-12 p-4 tarjeta-formulario"><div class="row">
    <div class="col-12 col-md-8">
      <p><strong class="d-block d-md-inline texto-rojizo">CAMPOS ACEDO, JULIA</strong>
      <span class="font-italic badge badge-success">En Servicio de Urgencias</span></p>
      <p><span class="d-block texto-rojizo">AVDA. CERVANTES, 8, 10005, CACERES</span>
      <span class="d-block texto-rojizo mt-2">927220667, 927627302</span></p>
      <p>Horario Lunes a Viernes 09:30 hasta 22:00 Diurna</p>
    </div>
    <div><a href="https://www.google.es/maps/dir//39.460143491591,-6.3715941917749">Cómo llegar</a></div>
  </div></div>
</div>
"""


class CaceresTests(unittest.TestCase):
    def test_postal_province_codes_keep_neighbor_referrals_in_their_real_province(self):
        codes = province_names()
        self.assertEqual(codes["10"], "Cáceres")
        self.assertEqual(codes["05"], "Ávila")
        self.assertEqual(codes["37"], "Salamanca")

    def test_municipality_catalogue_requires_session_token(self):
        token, municipalities = parse_municipalities(INDEX)
        self.assertEqual(token, "session-token")
        self.assertEqual(municipalities, [("32", "CACERES"), ("193", "Barco de Avila")])
        with self.assertRaises(ValueError):
            parse_municipalities(INDEX.replace('value="session-token"', 'value=""'))

    def test_urgency_result_is_current_day_guard_without_inferred_hours(self):
        rows = parse_open_results(RESULT, "32", "CACERES", date(2026, 11, 1),
                                  [("32", "CACERES")], {"10": "Cáceres"})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "cof-caceres-tel-927220667")
        self.assertEqual(row["provincia"], "Cáceres")
        self.assertEqual(row["localidad"], "CACERES")
        self.assertEqual(row["telefono"], "927220667")
        self.assertEqual(row["fecha_guardia"], "2026-11-01")
        self.assertTrue(row["guardia"])
        self.assertEqual(row["guardia_franja"], "Guardia sin horario publicado")
        self.assertNotIn("guardia_intervalos", row)
        self.assertEqual((row["lat"], row["lng"]), (39.460143491591, -6.3715941917749))
        self.assertIn("no publica un calendario fechado", row["nota_guardia"])

    def test_regularly_open_pharmacies_are_not_promoted_to_guards(self):
        rows = parse_open_results(RESULT.replace(">En Servicio de Urgencias<", ">Abierta<"),
                                  "32", "CACERES", date(2026, 11, 1),
                                  [("32", "CACERES")], {"10": "Cáceres"})
        self.assertEqual(rows, [])

    def test_unknown_status_or_unconfirmed_municipality_results_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_open_results(RESULT.replace("selected=\"selected\"", ""),
                               "32", "CACERES", date(2026, 11, 1),
                               [("32", "CACERES")], {"10": "Cáceres"})
        with self.assertRaises(ValueError):
            parse_open_results(RESULT.replace(">En Servicio de Urgencias<", ">Cerrada<"),
                               "32", "CACERES", date(2026, 11, 1),
                               [("32", "CACERES")], {"10": "Cáceres"})
        with self.assertRaises(ValueError):
            parse_open_results(RESULT.replace('id="resultados"', 'id="missing"'),
                               "32", "CACERES", date(2026, 11, 1),
                               [("32", "CACERES")], {"10": "Cáceres"})

    def test_coordinate_link_must_point_inside_spain(self):
        with self.assertRaises(ValueError):
            parse_open_results(RESULT.replace("39.460143491591,-6.3715941917749",
                                              "0,0"),
                               "32", "CACERES", date(2026, 11, 1),
                               [("32", "CACERES")], {"10": "Cáceres"})


if __name__ == "__main__":
    unittest.main()
