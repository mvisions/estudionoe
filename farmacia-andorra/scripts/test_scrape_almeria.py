import copy
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scrape_almeria as scraper


DAY = date(2026, 11, 1)


def response(start="2026-11-01 09:00:00", end="2026-11-02 09:00:00"):
    return {"success": True, "data": {"data": {
        "informacion": [{"titulo": "Abrirán pronto", "contenido": [{
            "uuid": "official-1", "nombre": "Farmacia oficial", "direccion": "C/ Mayor, 5",
            "municipio": "Almería", "telefono": "950123456", "coordenadas": None,
            "guardias": [{"tipo_guardia": "presencial", "guardia_horario_fecha_inicio": start,
                         "guardia_horario_fecha_fin": end}],
        }]}],
        "metadatos": {"paginacion": {"paginaActual": 1, "totalPaginas": 1, "totalElementos": 1}},
    }}}


class AlmeriaTests(unittest.TestCase):
    def test_all_day_includes_not_yet_open_and_clips_interval(self):
        rows = scraper.parse_responses([(DAY, response())], DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-02T00:00:00")
        self.assertIsNone(rows[0]["lat"])

    def test_previous_day_overnight_and_target_merge(self):
        previous = response("2026-10-31 22:00:00", "2026-11-01 09:00:00")
        rows = scraper.parse_responses([(DAY-timedelta(days=1), previous), (DAY, response())], DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["guardia_intervalos"]), 2)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00")

    def test_ending_at_midnight_is_not_next_day_duty(self):
        self.assertEqual(scraper.parse_responses([(DAY-timedelta(days=1),
            response("2026-10-31 09:00:00", "2026-11-01 00:00:00"))], DAY), [])

    def test_duplicate_official_intervals_are_deduplicated(self):
        data = response()
        guards = data["data"]["data"]["informacion"][0]["contenido"][0]["guardias"]
        guards.append(copy.deepcopy(guards[0]))
        self.assertEqual(len(scraper.parse_responses([(DAY, data)], DAY)[0]["guardia_intervalos"]), 1)

    def test_zero_duration_is_explicit_not_invented_24h(self):
        errors = []
        rows = scraper.parse_responses([(DAY, response(end="2026-11-01 09:00:00"))], DAY, errors)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["guardia_intervalos"], [])
        self.assertTrue(errors)
        self.assertIn("horario oficial inválido", rows[0]["guardia_franja"])

    def test_invalid_previous_interval_cannot_prove_carryover(self):
        errors = []
        rows = scraper.parse_responses([(DAY-timedelta(days=1),
            response("2026-10-31 09:00:00", "2026-10-31 09:00:00"))], DAY, errors)
        self.assertEqual(rows, [])
        self.assertTrue(errors)

    def test_wrong_date_and_truncated_response_are_errors(self):
        with self.assertRaises(ValueError):
            scraper.response_rows(response(), DAY-timedelta(days=1))
        data = response()
        data["data"]["data"]["metadatos"]["paginacion"]["totalElementos"] = 2
        with self.assertRaises(ValueError):
            scraper.response_rows(data, DAY)

    def test_malformed_identity_records_are_omitted_with_partial_diagnostic(self):
        data = response()
        content = data["data"]["data"]["informacion"][0]["contenido"]
        malformed = [
            {"uuid":"e39eb617-a603-480b-a0cc-6dcc4b3ba2f3", "nombre":"TORRES SANCHEZ, PATRICIA",
             "direccion":None, "municipio":None, "guardias":copy.deepcopy(content[0]["guardias"])},
            {"uuid":"844ec24a-1da6-491c-bb21-e57183fc00a4", "nombre":"LOPEZ RULL, ISABEL MARIA",
             "direccion":"", "municipio":"Almería", "guardias":copy.deepcopy(content[0]["guardias"])},
        ]
        content.extend(malformed)
        data["data"]["data"]["metadatos"]["paginacion"]["totalElementos"] = len(content)

        errors = []
        rows = scraper.parse_responses([(DAY, data)], DAY, errors)

        self.assertEqual([row["id"] for row in rows], ["alm-official-1"])
        self.assertEqual(len(errors), 1)
        self.assertIn("2 de 3 registros omitidos", errors[0])
        self.assertIn("1 registro utilizable", errors[0])
        for uuid in (row["uuid"] for row in malformed):
            self.assertIn(uuid, errors[0])

    def test_malformed_only_response_fails_without_writing_empty_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calendar = root / f"guardias-almeria-{DAY}.json"
            calendar.write_text('[{"id":"previous"}]')
            html = b'<script>var vbf_vars = {"ajax_url":"https://www.cofalmeria.com/wp-admin/admin-ajax.php","nonce":"test"};</script>'

            def malformed_response(_opener, _config, requested):
                data = response(start=f"{requested} 09:00:00",
                                end=f"{requested + timedelta(days=1)} 09:00:00")
                content = data["data"]["data"]["informacion"][0]["contenido"]
                content[0]["direccion"] = None
                content[0]["municipio"] = None
                return data

            with (patch.object(scraper, "OUT_DIR", root),
                  patch.object(scraper, "request", return_value=html),
                  patch.object(scraper, "fetch_day", side_effect=malformed_response)):
                with self.assertRaisesRegex(ValueError, "Sin guardias confirmadas"):
                    scraper.run(DAY)

            self.assertEqual(json.loads(calendar.read_text()), [{"id": "previous"}])
            report = json.loads((root / f"cobertura-almeria-{DAY}.json").read_text())
            self.assertFalse(report["calendario_actualizado"])
            self.assertEqual(report["consultas"][0]["estado"], "error")

    def test_failed_source_preserves_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calendar = root / f"guardias-almeria-{DAY}.json"
            calendar.write_text('[{"id":"previous"}]')
            with patch.object(scraper, "OUT_DIR", root), patch.object(scraper, "request", side_effect=OSError("source unavailable")):
                with self.assertRaises(OSError):
                    scraper.run(DAY)
            self.assertEqual(json.loads(calendar.read_text()), [{"id": "previous"}])
            report = json.loads((root / f"cobertura-almeria-{DAY}.json").read_text())
            self.assertFalse(report["calendario_actualizado"])

    def test_invalid_previous_interval_preserves_only_unconfirmed_old_duties(self):
        pending = set()
        scraper.parse_responses([(DAY-timedelta(days=1),
            response("2026-10-31 09:00:00", "2026-10-31 09:00:00"))], DAY, [], pending)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"guardias-almeria-{DAY}.json").write_text(json.dumps([
                {"id":"alm-official-1", "guardia_franja":"Madrugada"},
                {"id":"another-old-duty"},
            ]))
            with patch.object(scraper, "OUT_DIR", root):
                retained = scraper.retain_unconfirmed([], pending, DAY)
            self.assertEqual([r["id"] for r in retained], ["alm-official-1"])
            self.assertFalse(retained[0]["guardia_reconfirmada"])

    def test_invalid_and_ambiguous_coordinates_are_not_used(self):
        self.assertFalse(scraper.valid_position({"lat": None, "lng": None}))
        self.assertFalse(scraper.valid_position({"lat": 0, "lng": 0}))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            point = {"id":"osm-1", "lat":36.84, "lng":-2.46, "telefono":"950123456"}
            (root / "farmacias-osm-espana.json").write_text(json.dumps([point, {**point, "id":"osm-2"}]))
            rows = scraper.parse_responses([(DAY, response())], DAY)
            with patch.object(scraper, "OUT_DIR", root):
                scraper.locate(rows)
            self.assertIsNone(rows[0]["lat"])

    def test_geocoder_requires_pharmacy_exact_street_number_and_locality(self):
        row = scraper.parse_responses([(DAY, response())], DAY)[0]
        candidate = {"type":"pharmacy", "lat":"36.84", "lon":"-2.46",
                     "osm_type":"node", "osm_id":123,
                     "address":{"road":"Calle Mayor", "house_number":"5", "city":"Almería"}}
        with patch.object(scraper, "request", return_value=json.dumps([candidate]).encode()):
            self.assertIsNotNone(scraper.geocode(row))
        for change in ({"type":"house"},
                       {"address":{**candidate["address"], "house_number":"7"}},
                       {"address":{**candidate["address"], "city":"Otra localidad"}}):
            with patch.object(scraper, "request", return_value=json.dumps([{**candidate, **change}]).encode()):
                self.assertIsNone(scraper.geocode(row))
        with patch.object(scraper, "request", return_value=json.dumps([candidate, candidate]).encode()):
            self.assertIsNone(scraper.geocode(row))


if __name__ == "__main__":
    unittest.main()
