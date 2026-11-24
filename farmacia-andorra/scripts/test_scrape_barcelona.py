import json
import shutil
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import provincial_catalog
import scrape_barcelona as scraper

TARGET = date(2026, 11, 1)


def census():
    return ["BARCELONA", "SANT CUGAT DEL VALLÈS"] + [
        f"Municipio {i}" for i in range(309)]


def pdf(rows, total=None, town=None):
    footer = (f"Municipi: {town}" if town else
              f"Total farmàcies de la regió Barcelona ciutat : {len(rows) if total is None else total}")
    return "COL·LEGI DE FARMACÈUTICS DE BARCELONA\n" + "\n".join(rows) + "\n" + footer


def line(identifier="1", town="BARCELONA", phone="932479620", address="XUCLÀ 21"):
    return f"  {identifier} TITULAR, NOM  {address}  08001  {town}  {phone}".rstrip()


class BarcelonaTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent / ".barcelona-test-data"
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_public_pdf_with_and_without_telephone(self):
        points = scraper.parse_pdf(pdf([line(), line("2", phone="")]))
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["direccion"], "XUCLÀ 21")
        self.assertIsNone(points[1]["telefono"])
        self.assertFalse(points[0]["guardia"])
        self.assertIsNone(points[0]["lat"])

    def test_totals_duplicates_and_unrecognized_rows_fail_closed(self):
        for text in (pdf([line()], total=2), pdf([line(), line()]),
                     pdf(["  1 Name  Address  NO POSTCODE"]),
                     "Non-official " + line()):
            with self.assertRaises(ValueError):
                scraper.parse_pdf(text)

    def test_census_is_311_unique_municipalities(self):
        self.assertEqual(len(scraper.census(census())), 311)
        for towns in (census()[:-1], [*census()[:-1], "BARCELONA"]):
            with self.assertRaises(ValueError):
                scraper.census(towns)
        self.assertEqual(scraper.municipality("ESTANY, L'"), scraper.municipality("L'ESTANY"))

    def test_submunicipal_membership_requires_official_pdf_identity(self):
        document = pdf([line(town="VALLDOREIX")])
        points = scraper.catalogue([document], census(), {})
        self.assertTrue(points[0]["municipio_pendiente"])
        membership = pdf([line(town="VALLDOREIX")], town="SANT CUGAT DEL VALLÈS")
        points = scraper.catalogue([document], census(), {"SANT CUGAT DEL VALLÈS": membership})
        self.assertEqual(points[0]["localidad"], "SANT CUGAT DEL VALLÈS")
        self.assertEqual(points[0]["localidad_original"], "VALLDOREIX")
        self.assertTrue(points[0]["municipio_verificado_pdf"])
        changed = pdf([line(town="VALLDOREIX", address="Different 2")],
                      town="SANT CUGAT DEL VALLÈS")
        with self.assertRaises(ValueError):
            scraper.catalogue([document], census(), {"SANT CUGAT DEL VALLÈS": changed})

    def test_all_census_reports_say_guardia_was_not_queried(self):
        points = scraper.catalogue([pdf([line()])], census(), {})
        evidence = {"estado": "bloqueado_recaptcha", "error": scraper.BLOCKER}
        reports = scraper.reports_for(census(), points, TARGET, evidence)
        self.assertEqual(len(reports), 311)
        self.assertEqual(reports[0]["farmacias_catalogo"], 1)
        self.assertTrue(all(r["estado"] == "error" for r in reports))
        self.assertTrue(all(not r["consulta_guardia_realizada"] for r in reports))
        self.assertTrue(all(r["farmacias"] == 0 for r in reports))

    def test_only_public_pages_and_client_are_read_to_confirm_captcha(self):
        official = b'<a href="https://www.farmaguia.net">Farmaguia</a>'
        form = b'<script src="https://mobi.farmaguia.net/assets/js/advancedSearch.js?v=1"></script>'
        client = b'executeGRecaptchaAction("advancedSearch", callback)'
        with patch.object(scraper, "request", side_effect=[official, form, client]) as request:
            evidence = scraper.duty_evidence()
        self.assertFalse(evidence["api_protegida_consultada"])
        self.assertEqual(request.call_count, 3)
        self.assertTrue(all(call.args[0].startswith("https://") for call in request.call_args_list))

    def test_client_change_does_not_trigger_api_attempt(self):
        with patch.object(scraper, "request", side_effect=[
            b'<a href="https://www.farmaguia.net/">Farmaguia</a>',
            b'<script src="https://mobi.farmaguia.net/assets/js/advancedSearch.js"></script>',
            b'newClient()',
        ]) as request:
            with self.assertRaises(ValueError):
                scraper.duty_evidence()
            self.assertEqual(request.call_count, 3)

    def test_offline_replay_publishes_catalogue_but_never_fabricates_guards(self):
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "region.txt").write_text(pdf([line()]))
        (cache / "indice.json").write_text(json.dumps({
            "fecha_consulta": str(TARGET), "consultado": f"{TARGET}T07:00:00+01:00",
            "municipios": census(), "documentos_regionales": ["region.txt"],
            "documentos_municipales": {},
            "guardias": {"estado": "bloqueado_recaptcha", "error": scraper.BLOCKER},
        }))
        (self.root / "farmacias-espana-hoy.json").write_text("[]")
        def locate(*args, **kwargs):
            return provincial_catalog.locate_and_catalogue(*args, **kwargs, output=self.root)
        def publish(*args):
            return provincial_catalog.publish(*args, output=self.root)
        with patch.object(scraper, "OUT_DIR", self.root), \
                patch.object(scraper, "locate_and_catalogue", side_effect=locate), \
                patch.object(scraper, "publish", side_effect=publish), \
                patch.object(scraper, "request", side_effect=AssertionError("Network forbidden")):
            self.assertFalse(scraper.run(TARGET, cache, offline=True))
        catalog = json.loads((self.root / "farmacias-barcelona.json").read_text())
        self.assertFalse(catalog[0]["guardia"])
        self.assertFalse((self.root / f"guardias-barcelona-{TARGET}.json").exists())
        coverage = json.loads((self.root / f"cobertura-barcelona-{TARGET}.json").read_text())
        self.assertFalse(coverage["completa"])
        self.assertEqual(coverage["municipios_censados"], 311)

    def test_source_failure_preserves_older_calendar_and_catalogue(self):
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "indice.json").write_text(json.dumps({"municipios": census()}))
        catalog = self.root / "farmacias-barcelona.json"
        catalog.write_text('[{"id":"saved"}]')
        calendar = self.root / f"guardias-barcelona-{TARGET}.json"
        calendar.write_text(json.dumps([{
            "id": "cof-barcelona-1", "localidad": "BARCELONA",
            "localidades_atendidas": ["BARCELONA"], "guardia": True,
            "guardia_franjas": ["Noche 22:00–08:00"], "fuente": scraper.FINDER,
            "lat": 41.38, "lng": 2.17,
        }]))
        def publish(*args):
            return provincial_catalog.publish(*args, output=self.root)
        with patch.object(scraper, "OUT_DIR", self.root), \
                patch.object(scraper, "discover", side_effect=OSError("HTTP unavailable")), \
                patch.object(scraper, "publish", side_effect=publish):
            self.assertFalse(scraper.run(TARGET, cache))
        self.assertEqual(catalog.read_text(), '[{"id":"saved"}]')
        kept = json.loads(calendar.read_text())[0]
        self.assertFalse(kept["guardia_reconfirmada"])
        self.assertIn("Noche 22:00–08:00", kept["guardia_franjas"])
        report = json.loads((self.root / f"cobertura-barcelona-{TARGET}.json").read_text())
        self.assertEqual(len(report["consultas"]), 311)

    def test_wrong_day_or_invalid_cached_census_is_reported_without_network(self):
        cache = self.root / "cache"
        cache.mkdir()
        for manifest in (
            {"fecha_consulta": "2026-10-31"},
            {"fecha_consulta": str(TARGET), "municipios": ["BARCELONA"],
             "documentos_regionales": [], "documentos_municipales": {}, "guardias": {}},
        ):
            (cache / "indice.json").write_text(json.dumps(manifest))
            with patch.object(scraper, "OUT_DIR", self.root), \
                    patch.object(scraper, "publish") as publish, \
                    patch.object(scraper, "request", side_effect=AssertionError("Network forbidden")):
                self.assertFalse(scraper.run(TARGET, cache, offline=True))
                self.assertEqual(publish.call_args.args[4][0]["estado"], "error")


if __name__ == "__main__":
    unittest.main()
