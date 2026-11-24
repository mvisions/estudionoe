from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cofcam import parse_response, run


DAY = date(2026, 11, 1)


class CofcamTests(unittest.TestCase):
    def response(self, province, identifier):
        return {"success": True, "fecha": str(DAY), "total": 1, "filtro_hora": None,
                "data": [{"id": 1, "numero_farmacia": identifier, "provincia": province,
                          "localidad": province, "domicilio": "Calle Mayor 1",
                          "fecha_inicio": "2026-10-26", "fecha_fin": "2026-11-02",
                          "hora_inicio": "09:30", "hora_fin": "09:30",
                          "lat": "39.1", "lng": "-2.1"}]}

    def test_regional_identity_formats_and_continuous_week(self):
        for province, identifier in (("Albacete", "AB-0026-F"), ("Cuenca", "CU-0006-F"),
                                     ("Ciudad Real", "1023")):
            with self.subTest(province=province):
                rows, errors = parse_response(self.response(province, identifier), DAY, province)
                self.assertFalse(errors)
                self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00")
                self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-02T00:00:00")

    def test_failed_source_preserves_calendar_and_publishes_explicit_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "farmacias-espana-hoy.json").write_text("[]")
            schedule = root / f"guardias-cuenca-{DAY}.json"
            schedule.write_text(json.dumps([{"id": "kept", "localidad": "Cuenca",
                                              "guardia_franjas": ["Guardia"]}]))
            import provincial_catalog
            original_publish = provincial_catalog.publish
            with patch("cofcam.OUT_DIR", root), patch("cofcam.request", side_effect=OSError("HTTP 503")), \
                    patch("cofcam.publish", side_effect=lambda *args: original_publish(*args, output=root)):
                self.assertFalse(run(DAY, "Cuenca", root / "cache"))
            rows = json.loads(schedule.read_text())
            self.assertEqual(rows[0]["id"], "kept")
            self.assertFalse(rows[0]["guardia_reconfirmada"])
            report = json.loads((root / f"cobertura-cuenca-{DAY}.json").read_text())
            self.assertFalse(report["completa"])
            self.assertEqual(report["consultas"][0]["estado"], "error")
