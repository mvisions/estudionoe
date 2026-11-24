import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scrape_mes import main, merge_schedule, normalize_locality, parse_schedule, parse_selectors, pharmacy_sector, scrape_day, slugify, write_json
from urllib.parse import parse_qs, urlparse


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.selector = {"nombre": "Málaga capital", "parametro": "vzona", "codigo": "29000001"}

    def test_distinct_selector_namespaces(self):
        content = """
        <select name=vzona><option value=0>Elegir</option><option value=29000001>M&aacute;laga</option></select>
        <select name="vpoblacion"><option value="29000001">Otro lugar</option></select>
        """
        selectors = parse_selectors(content, "29")
        self.assertEqual(len(selectors), 2)
        self.assertEqual(selectors[0]["nombre"], "Málaga")
        self.assertEqual(selectors[1]["parametro"], "vpoblacion")

    def test_periods_entities_and_last_address_suffix(self):
        content = """
        GUARDIAS DE D&Iacute;A
        <a href=javascript:abbre(29,29000141,0)>OVELAR (antes - CARRETEROS), 3 - SECTOR CENTRO</a>
        GUARDIAS DE NOCHE
        <a href=javascript:abbre(29,29000141,0)>OVELAR (antes - CARRETEROS), 3 - SECTOR CENTRO</a>
        GUARDIAS TODO EL D&Iacute;A
        <a href=javascript:abbre(29,29000500,0)>VERACRUZ, 8 - &Aacute;lora</a>
        """
        rows = merge_schedule(parse_schedule(content, self.selector, "29", "Málaga", "2026-10-31"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["direccion"], "OVELAR (antes - CARRETEROS), 3")
        self.assertEqual(rows[0]["localidad"], "Málaga")
        self.assertEqual(rows[0]["guardia_franjas"], ["dia (9:30-22:00)", "noche (22:00-9:30)"])
        self.assertEqual(rows[1]["guardia_franja"], "todo el dia (9:30-9:30)")

    def test_unavailable_is_not_empty_schedule(self):
        self.assertIsNone(parse_schedule("<div>Datos no disponibles</div>", self.selector, "29", "Málaga", "2026-11-01"))
        self.assertEqual(parse_schedule("GUARDIAS DE DÍA", self.selector, "29", "Málaga", "2026-11-01"), [])
        with self.assertRaises(ValueError):
            parse_schedule("<html>Error del servidor</html>", self.selector, "29", "Málaga", "2026-11-01")

    def test_dates_match_public_form_without_zero_padding(self):
        for target, expected in (("2026-11-01", "1/11/2026"), ("2026-01-09", "9/1/2026")):
            with patch("scrape_mes.fetch", return_value="GUARDIAS DE DÍA") as fetch, \
                    patch("scrape_mes.time.sleep"), patch("builtins.print"):
                scrape_day([self.selector], "29", "Málaga", target, {})
            self.assertEqual(parse_qs(urlparse(fetch.call_args.args[0]).query)["date"], [expected])

    def test_printed_date_must_match_requested_date(self):
        with self.assertRaises(ValueError):
            parse_schedule("11/01/2026 GUARDIAS DE DÍA",self.selector,"29","Málaga","2026-11-01")

    def test_atomic_json_and_slug(self):
        self.assertEqual(slugify("Málaga"), "malaga")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.json"
            write_json(path, [{"localidad": "Álora"}])
            self.assertIn("Álora", path.read_text())
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_population_names_are_not_mistaken_for_municipalities(self):
        self.assertEqual(normalize_locality("Cartama - Estacion"), "Cártama")
        self.assertEqual(normalize_locality("ARROYO DE LA MIEL"), "Benalmádena")
        self.assertEqual(normalize_locality("Torrox - Torrox Costa"), "Torrox")
        self.assertEqual(normalize_locality("Torre de Benagalbon"), "Rincón de la Victoria")
        self.assertEqual(normalize_locality("La Cala del Moral"), "Rincón de la Victoria")
        self.assertEqual(normalize_locality("Chilches"), "Vélez-Málaga")

    def test_torrox_combined_locality_is_not_left_in_address(self):
        rows = parse_schedule(
            'GUARDIAS TODO EL DÍA <a href=javascript:abbre(29,29010202,0)>PLAZA LA CONSTITUCIÓN NÚM. 2 - Torrox - Torrox Costa</a>',
            {"nombre": "Torrox - Torrox Costa"}, "29", "Málaga", "2026-10-31",
        )
        self.assertEqual(rows[0]["direccion"], "PLAZA LA CONSTITUCIÓN NÚM. 2")
        self.assertEqual(rows[0]["localidad"], "Torrox")

    def test_torre_benagalbon_is_searchable_without_inventing_main_village_coverage(self):
        self.assertEqual(
            pharmacy_sector("AV. DE LA TORRE, 41 LC 2 (T. BENAGALBON)", "Rincon de la Victoria"),
            "Torre de Benagalbón",
        )
        self.assertEqual(pharmacy_sector("AV. DE LA TORRE, 41", "Rincon de la Victoria"), "")

    def test_unavailable_day_preserves_previous_calendar_and_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "guardias-malaga-2026-11-01.json"
            write_json(target, [{"cofm_id": "previous"}])
            original = target.read_text()
            with (
                patch("scrape_mes.OUT_DIR", root),
                patch("sys.argv", ["scrape_mes", "29", "Malaga", "11", "2026", "--dia", "1"]),
                patch("scrape_mes.fetch", return_value='<select name=vzona><option value=29000001>Málaga capital</option></select>'),
                patch("scrape_mes.scrape_day", return_value=([], [{"estado": "sin_datos"}])),
                patch("builtins.print"),
            ):
                with self.assertRaises(SystemExit) as exit_result:
                    main()
                self.assertEqual(exit_result.exception.code, 1)
            self.assertEqual(target.read_text(), original)
            self.assertTrue((root / "cobertura-malaga-2026-11-01.json").exists())


if __name__ == "__main__":
    unittest.main()
