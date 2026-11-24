import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


UPDATER = Path(__file__).resolve().parent / "daily_update.sh"


class DailyUpdateTests(unittest.TestCase):
    def environment(self, directory):
        root = Path(directory)
        data = root / "data"
        data.mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        python = bin_dir / "python3"
        python.write_text(
            '#!/bin/bash\nprintf "python TZ=%s %s\\n" "$TZ" "$*" >> "$TEST_CALLS"\n'
            'if [[ "$1" == "scripts/scrape_valencia.py" && "${TEST_DELAY_WORKER:-}" == "1" ]]; then\n'
            '  sleep 1; echo "valencia worker finished" >> "$TEST_CALLS"\n'
            'fi\n'
            'if [[ "$1" == "scripts/scrape_mes.py" && "${TEST_MES_OK:-}" != "1" ]]; then exit 1; fi\n'
            'if [[ "$1" == "scripts/scrape_valencia.py" && "${TEST_WORKER_FAIL:-}" == "1" ]]; then exit 1; fi\n'
        )
        npm = bin_dir / "npm"
        npm.write_text(
            '#!/bin/bash\nprintf "npm %s\\n" "$*" >> "$TEST_CALLS"\n'
            'if [[ "${TEST_BUILD_FAIL:-}" == "1" ]]; then exit 1; fi\n'
            'while [[ $# -gt 0 ]]; do\n'
            '  if [[ "$1" == "--outDir" ]]; then mkdir -p "$2"; echo nueva > "$2/index.html"; fi\n'
            '  shift\n'
            'done\n'
        )
        python.chmod(0o755)
        npm.chmod(0o755)
        return {
            **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "XDG_STATE_HOME": str(root / "state"), "TEST_CALLS": str(root / "calls"),
            "FARMACIA_DATA_DIR": str(data), "FARMACIA_DIST_DIR": str(root / "dist"),
            "FARMACIA_LOCK_WAIT": "1",
        }

    def test_failed_source_does_not_skip_sevilla_build_or_status_log(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            calls = Path(environment["TEST_CALLS"]).read_text()
            self.assertIn("scripts/complete_malaga.py", calls)
            self.assertIn("scripts/complete_malaga.py --fecha", calls)
            self.assertIn("scripts/scrape_sevilla.py --trimestre", calls)
            self.assertIn("scripts/scrape_granada.py --geocode", calls)
            self.assertIn("scripts/scrape_cadiz.py", calls)
            self.assertIn("scripts/scrape_jaen.py --geocode --cache-documentos", calls)
            self.assertIn("scripts/scrape_almeria.py --geocode", calls)
            self.assertIn("scripts/scrape_huelva.py --geocode --cache-documentos", calls)
            self.assertIn("scripts/scrape_cordoba.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_toledo.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_guadalajara.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_valencia.py --cache-documentos", calls)
            self.assertIn("scripts/scrape_zamora.py --cache-documentos", calls)
            self.assertIn("scripts/scrape_soria.py --cache-documentos", calls)
            self.assertIn("scripts/scrape_cantabria.py --geocode --cache-documentos", calls)
            self.assertIn("scripts/scrape_pontevedra.py --geocode --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_pontevedra.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_ourense.py", calls)
            self.assertLess(calls.index("scripts/scrape_ourense.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_asturias.py --geocode --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_asturias.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_navarra.py --geocode --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_navarra.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_salamanca.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_burgos.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_palencia.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertIn("scripts/scrape_murcia.py --cache-documentos", calls)
            self.assertIn("scripts/scrape_alicante.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_alicante.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_badajoz.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_alicante.py"), calls.index("scripts/scrape_badajoz.py"))
            self.assertIn("scripts/scrape_la_rioja.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_badajoz.py"), calls.index("scripts/scrape_la_rioja.py"))
            self.assertIn("scripts/scrape_zaragoza.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_la_rioja.py"), calls.index("scripts/scrape_zaragoza.py"))
            self.assertIn("scripts/scrape_ceuta.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_zaragoza.py"), calls.index("scripts/scrape_ceuta.py"))
            self.assertIn("scripts/scrape_melilla.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_ceuta.py"), calls.index("scripts/scrape_melilla.py"))
            self.assertLess(calls.index("scripts/scrape_melilla.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/scrape_baleares.py --cache-documentos", calls)
            self.assertIn("scripts/scrape_segovia.py --cache-documentos", calls)
            self.assertLess(calls.index("scripts/scrape_segovia.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/locate_guardias.py --cache", calls)
            self.assertIn("scripts/registro_jcyl.py --cache-documentos", calls)
            self.assertIn("--catalogo farmacias-registro-jcyl.json", calls)
            self.assertLess(calls.index("scripts/scrape_segovia.py"), calls.index("scripts/registro_jcyl.py"))
            self.assertLess(calls.index("scripts/registro_jcyl.py"), calls.index("scripts/locate_guardias.py"))
            self.assertLess(calls.index("scripts/locate_guardias.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_murcia.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_burgos.py"), calls.index("scripts/scrape_palencia.py"))
            self.assertLess(calls.index("scripts/scrape_palencia.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_salamanca.py"), calls.index("scripts/scrape_burgos.py"))
            self.assertLess(calls.index("scripts/scrape_burgos.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_cantabria.py"), calls.index("scripts/scrape_salamanca.py"))
            self.assertLess(calls.index("scripts/scrape_salamanca.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_cantabria.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_zamora.py"), calls.index("scripts/locate_guardias.py"))
            self.assertLess(calls.index("scripts/scrape_zamora.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_soria.py"), calls.index("scripts/locate_guardias.py"))
            self.assertLess(calls.index("scripts/scrape_soria.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_valencia.py"), calls.index("scripts/merge_espana.py"))
            for province in ("albacete", "ciudad_real", "cuenca"):
                self.assertIn(f"scripts/scrape_{province}.py --geocode --permitir-direccion-exacta --cache-documentos", calls)
                self.assertLess(calls.index(f"scripts/scrape_{province}.py"), calls.index("scripts/merge_espana.py"))
            self.assertIn("scripts/merge_espana.py", calls)
            self.assertLess(calls.index("scripts/scrape_granada.py"), calls.index("scripts/scrape_cadiz.py"))
            self.assertLess(calls.index("scripts/scrape_cadiz.py"), calls.index("scripts/scrape_jaen.py"))
            self.assertLess(calls.index("scripts/scrape_jaen.py"), calls.index("scripts/scrape_almeria.py"))
            self.assertLess(calls.index("scripts/scrape_almeria.py"), calls.index("scripts/scrape_huelva.py"))
            self.assertLess(calls.index("scripts/scrape_huelva.py"), calls.index("scripts/scrape_cordoba.py"))
            self.assertLess(calls.index("scripts/scrape_cordoba.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/scrape_toledo.py"), calls.index("scripts/scrape_guadalajara.py"))
            self.assertLess(calls.index("scripts/scrape_guadalajara.py"), calls.index("scripts/merge_espana.py"))
            self.assertLess(calls.index("scripts/merge_espana.py"), calls.index("npm run build"))
            self.assertLess(calls.index("scripts/scrape_cordoba.py"), calls.index("scripts/scrape_toledo.py"))
            self.assertLess(calls.index("scripts/scrape_cuenca.py"), calls.index("scripts/scrape_girona.py"))
            self.assertIn("TZ=Europe/Madrid", calls)
            self.assertIn("npm run build", calls)
            state = Path(environment["XDG_STATE_HOME"]) / "farmacia"
            self.assertEqual(json.loads((state / "last-update.json").read_text())["salida"], 1)
            self.assertIn("salida=1", (state / "daily-update.log").read_text())

    def test_independent_worker_runs_in_parallel_and_finishes_before_final_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            environment.update(TEST_DELAY_WORKER="1", TEST_MES_OK="1")
            result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            calls = Path(environment["TEST_CALLS"]).read_text()
            self.assertLess(calls.index("scripts/scrape_segovia.py"), calls.index("valencia worker finished"))
            self.assertLess(calls.index("valencia worker finished"), calls.index("scripts/locate_guardias.py"))
            self.assertLess(calls.index("valencia worker finished"), calls.index("scripts/merge_espana.py"))
            for province in ("valencia", "murcia", "baleares"):
                self.assertEqual(calls.count(f"scripts/scrape_{province}.py"), 1)
            state = Path(environment["XDG_STATE_HOME"]) / "farmacia"
            self.assertEqual(json.loads((state / "last-update.json").read_text())["salida"], 0)

    def test_failed_background_worker_fails_run_but_does_not_skip_build(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            environment.update(TEST_MES_OK="1", TEST_WORKER_FAIL="1")
            result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            calls = Path(environment["TEST_CALLS"]).read_text()
            self.assertIn("scripts/merge_espana.py", calls)
            self.assertIn("npm run build", calls)
            state = Path(environment["XDG_STATE_HOME"]) / "farmacia"
            self.assertEqual(json.loads((state / "last-update.json").read_text())["salida"], 1)

    def dates(self, environment):
        def date(offset):
            return subprocess.run(["date", "-d", offset, "+%F"], env={**environment, "TZ": "Europe/Madrid"},
                                  capture_output=True, text=True, check=True).stdout.strip()
        return date("today"), date("tomorrow")

    def test_default_run_prepares_tomorrow_and_skips_today_only_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            environment.update(TEST_MES_OK="1")
            _, tomorrow = self.dates(environment)
            result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            calls = Path(environment["TEST_CALLS"]).read_text()
            for line in calls.splitlines():
                if "scripts/scrape_" in line and "scrape_mes.py" not in line and "scrape_sevilla.py" not in line:
                    self.assertIn(f"--fecha {tomorrow}", line)
            year, month, day = (int(part) for part in tomorrow.split("-"))
            self.assertIn(f"scripts/scrape_mes.py 29 Malaga {month} {year} --dia {day}", calls)
            self.assertIn(f"scripts/scrape_sevilla.py --trimestre {(month - 1)//3 + 1} --anio {year}", calls)
            for source in ("madrid", "barcelona", "caceres", "valladolid", "leon"):
                self.assertNotIn(f"scripts/scrape_{source}.py", calls)
            state = json.loads((Path(environment["XDG_STATE_HOME"]) / "farmacia/last-update.json").read_text())
            self.assertEqual((state["modo"], state["fecha"]), ("manana", tomorrow))

    def test_today_run_adds_today_only_sources_and_retries_only_missing_provinces(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            environment.update(TEST_MES_OK="1")
            today, _ = self.dates(environment)
            data = Path(environment["FARMACIA_DATA_DIR"])
            for slug in ("valencia", "murcia", "baleares", "malaga", "sevilla", "granada", "soria"):
                (data / f"guardias-{slug}-{today}.json").write_text("[]")
            result = subprocess.run(["bash", str(UPDATER), "--hoy"], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            calls = Path(environment["TEST_CALLS"]).read_text()
            for source in ("madrid", "barcelona", "caceres"):
                self.assertIn(f"scripts/scrape_{source}.py", calls)
            for source in ("valencia", "murcia", "baleares", "mes", "sevilla", "granada", "soria"):
                self.assertNotIn(f"scripts/scrape_{source}.py", calls)
            self.assertIn(f"scripts/scrape_leon.py --cache-documentos {Path(environment['XDG_STATE_HOME'])}"
                          f"/farmacia/leon --fecha {today}", calls)
            self.assertIn(f"scripts/scrape_valladolid.py --geocode --cache-documentos "
                          f"{Path(environment['XDG_STATE_HOME'])}/farmacia/valladolid --fecha {today}", calls)
            self.assertIn(f"scripts/scrape_zamora.py --cache-documentos {Path(environment['XDG_STATE_HOME'])}"
                          f"/farmacia/zamora --fecha {today}", calls)
            self.assertNotIn("scripts/registro_jcyl.py", calls)
            self.assertIn("scripts/locate_guardias.py", calls)
            self.assertNotIn("--catalogo", calls)
            self.assertLess(calls.index("scripts/merge_espana.py"), calls.index("npm run build"))

    def test_morning_retry_with_nothing_missing_keeps_the_published_site(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            today, _ = self.dates(environment)
            data = Path(environment["FARMACIA_DATA_DIR"])
            slugs = set()
            for line in UPDATER.read_text().splitlines():
                words = line.split()
                if words and words[0] in ("dated", "dated_worker", "today_only", "dated_today_only"):
                    slugs.add(words[1])
            slugs |= {"malaga", "sevilla"}
            self.assertIn("leon", slugs)
            for slug in slugs:
                (data / f"guardias-{slug}-{today}.json").write_text("[]")

            result = subprocess.run(["bash", str(UPDATER), "--hoy"], env=environment, capture_output=True, timeout=15)

            self.assertEqual(result.returncode, 0)
            self.assertFalse(Path(environment["TEST_CALLS"]).exists())
            log = (Path(environment["XDG_STATE_HOME"]) / "farmacia/daily-update.log").read_text()
            self.assertIn(f"Nada pendiente para {today}", log)

    def test_build_replaces_published_site_atomically_and_failure_keeps_it(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            environment.update(TEST_MES_OK="1")
            dist = Path(environment["FARMACIA_DIST_DIR"])
            dist.mkdir()
            (dist / "index.html").write_text("anterior")
            failed = subprocess.run(["bash", str(UPDATER)], env={**environment, "TEST_BUILD_FAIL": "1"},
                                    capture_output=True, timeout=15)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual((dist / "index.html").read_text(), "anterior")
            self.assertFalse(Path(f"{dist}.next").exists())

            result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)

            self.assertEqual(result.returncode, 0)
            self.assertEqual((dist / "index.html").read_text().strip(), "nueva")
            self.assertFalse(Path(f"{dist}.next").exists())
            self.assertIn(f"--outDir {dist}.next --emptyOutDir", Path(environment["TEST_CALLS"]).read_text())

    def test_today_run_waits_for_the_lock_then_gives_up(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            state = Path(environment["XDG_STATE_HOME"]) / "farmacia"
            state.mkdir(parents=True)
            with (state / "daily-update.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                result = subprocess.run(["bash", str(UPDATER), "--hoy"], env=environment,
                                        capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 75)
            self.assertFalse(Path(environment["TEST_CALLS"]).exists())

    def test_overlap_is_rejected_without_overwriting_previous_status(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self.environment(directory)
            state = Path(environment["XDG_STATE_HOME"]) / "farmacia"
            state.mkdir(parents=True)
            previous = state / "last-update.json"
            previous.write_text('{"salida":0}')
            with (state / "daily-update.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                result = subprocess.run(["bash", str(UPDATER)], env=environment, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 75)
            self.assertFalse(Path(environment["TEST_CALLS"]).exists())
            self.assertEqual(previous.read_text(), '{"salida":0}')
            self.assertIn("otra ejecución activa", (state / "daily-update.log").read_text())


if __name__ == "__main__":
    unittest.main()
