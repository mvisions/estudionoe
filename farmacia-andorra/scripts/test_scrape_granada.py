import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from granada_verified_scans import VERIFIED_SCANS
from scrape_granada import geocode, locate, locality_name, merge, parse_capital, parse_cards, parse_loja, parse_verified_scan, parse_weekly, parse_weekly_blocks, pharmacy, run


class GranadaTests(unittest.TestCase):
    def test_multiple_contacts_are_not_concatenated_into_a_fake_phone(self):
        row = pharmacy("Real 3", "Hueneja", "", "858 715970 - 624 123456", "Día", date(2026, 11, 1), "official")
        self.assertEqual(row["telefono"], "858715970")
        self.assertEqual(row["telefonos"], ["858715970", "624123456"])
        self.assertEqual(locality_name("Gabias, Las"), "Las Gabias")

    def test_official_card_referral_preserves_actual_locality_and_rejects_zero_point(self):
        card = '<div id="Farmacia430"><div class="row">'
        for label, value in [("Localidad", "Gabias, Las"), ("Titular", "Titular"),
                             ("Dirección", "Real de Málaga, 65"), ("Teléfono", "958 589460")]:
            card += f'<div class="col-6">{label}</div><div class="col-6">{value}</div>'
        card += '<div class="col-12">Desde el día: 26/10/2026 hasta el día: 2/11/2026</div></div></div><!--Mapa-->'
        card += "L.marker([0, 0])"
        row = parse_cards(card, "Agrón", date(2026, 11, 1))[0]
        self.assertEqual(row["localidad"], "Las Gabias")
        self.assertEqual(row["localidades_atendidas"], ["Agrón"])
        self.assertIsNone(row["lat"])
        self.assertIn("no válidas", row["nota_ubicacion"])
        with self.assertRaisesRegex(ValueError, "fuera de"):
            parse_cards(card, "Agrón", date(2026, 11, 3))

    def test_capital_columns_and_day_night_are_independently_parsed(self):
        page = {"width": 600, "lines": [
            {"x": 150, "y": 10, "text": "SERVICIO DE URGENCIA DIURNO: DE 9,30 H. A 22,00 H."},
            {"x": 150, "y": 20, "text": "DOMINGO 1 DE NOVIEMBRE 2026"},
            {"x": 30, "y": 50, "text": "Real, 1. TLF.: 958 111111"},
            {"x": 310, "y": 60, "text": "Nueva, 2"},
            {"x": 310, "y": 70, "text": "TLF.: 958 222222"},
            {"x": 50, "y": 100, "text": "SERVICIO DE URGENCIA NOCTURNO: DE 22,00 H. A 9,30 H. DEL DÍA SIGUIENTE"},
            {"x": 30, "y": 120, "text": "Real, 1. TLF.: 958 111111"},
        ]}
        rows = merge(parse_capital([page], date(2026, 11, 1), "official"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]["guardia_franjas"]), 2)
        self.assertEqual(rows[1]["direccion"], "Nueva, 2")
        self.assertEqual(parse_capital([page], date(2026, 11, 2), "official"), [])
        page["lines"][1]["text"] = "LUNES 2 NOVIEMBRE 2026"
        self.assertEqual(len(merge(parse_capital([page], date(2026, 11, 2), "official"))), 2)
        page["lines"][0]["text"] = "SERVICIO DE URGENCIA DIURNO: HORARIO DISTINTO"
        with self.assertRaisesRegex(ValueError, "Horario"):
            parse_capital([page], date(2026, 11, 2), "official")

    def test_weekly_table_does_not_reuse_other_month_and_has_november_boundary(self):
        page = {"width": 842, "lines": [
            {"x": 30, "y": 10, "right": 100, "text": "2026"},
            {"x": 30, "y": 20, "right": 100, "text": "OCTUBRE"},
            {"x": 30, "y": 40, "right": 110, "text": "26 AL 2/11"},
            {"x": 150, "y": 40, "right": 260, "text": "Lda. Nombre"},
            {"x": 300, "y": 40, "right": 450, "text": "Real 1 - LA PEZA"},
            {"x": 550, "y": 40, "right": 650, "text": "600 662458"},
        ]}
        rows = parse_weekly([page], date(2026, 11, 1), "official")
        self.assertEqual(rows[0]["direccion"], "Real 1")
        self.assertEqual(rows[0]["localidad"], "La Peza")
        with self.assertRaises(ValueError):
            parse_weekly([page], date(2026, 11, 2), "official")

    def test_loja_preserves_daily_previous_and_current_night_without_guessing_hours(self):
        page = {"width": 600, "lines": [
            {"x": 450, "y": 10, "text": "2026"},
            {"x": 70, "y": 20, "text": "TURNOS ROTATORIOS DE GUARDIAS DIURNAS Y NOCTURNAS EN EL MES DE"},
            {"x": 70, "y": 30, "text": "NOVIEMBRE EN LA LOCALIDAD DE LOJA:"},
            {"x": 70, "y": 40, "text": "Lunes a viernes de 8,00 a 22,00 horas."},
            {"x": 70, "y": 50, "text": "Sábados, domingos y festivos de 9,00 a 22,00."},
            {"x": 70, "y": 60, "text": "Farmacia Ldo. Bruque Tallón. Avda. Rafael Pérez Álamo s/n"},
            {"x": 70, "y": 70, "text": "NOCTURNAS de 22,00 a 8,00 laborables y de 22,00 a 9,00 sábado, domingo y festivos."},
            {"x": 70, "y": 100, "text": "1 DOMINGO"},
            {"x": 150, "y": 100, "text": "LDO. BRUQUE TALLON"},
            {"x": 310, "y": 100, "text": "AVDA. RAFAEL PÉREZ DEL ÁLAMO S/N"},
            {"x": 70, "y": 120, "text": "2 LUNES"},
            {"x": 150, "y": 120, "text": "LDO. VALSECA MONTAÑO"},
            {"x": 310, "y": 120, "text": "AV. LOS ANGELES S/N"},
        ]}
        rows = parse_loja([page], date(2026, 11, 2), "official")
        self.assertEqual(len(rows), 2)
        self.assertIn("nocturna anterior", rows[0]["guardia_franja"])
        self.assertIn("nocturna", rows[1]["guardia_franja"])
        self.assertTrue(all("guardia_intervalos" not in row for row in rows))
        with self.assertRaisesRegex(ValueError, "mes solicitado"):
            parse_loja([page], date(2026, 12, 2), "official")
        page["lines"][10]["text"] = "2 MARTES"
        with self.assertRaisesRegex(ValueError, "semana contradictorio"):
            parse_loja([page], date(2026, 11, 2), "official")

    def test_geocoder_rejects_town_centroid_wrong_street_and_wrong_locality(self):
        row = pharmacy("Real, 1", "Granada", "", "", "Día", date(2026, 11, 1), "official")
        base = {"type": "pharmacy", "lat": "37.18", "lon": "-3.6", "osm_type": "node", "osm_id": 1,
                "address": {"city": "Granada", "road": "Calle Real", "house_number": "1"}}
        cases = [{**base, "type": "administrative"},
                 {**base, "address": {**base["address"], "house_number": "2"}},
                 {**base, "address": {**base["address"], "city": "Motril"}}]
        for item in cases:
            with self.subTest(item=item), patch("scrape_granada.urllib.request.urlopen",
                                                return_value=io.BytesIO(json.dumps([item]).encode())):
                self.assertIsNone(geocode(row))
        with patch("scrape_granada.urllib.request.urlopen", return_value=io.BytesIO(json.dumps([base]).encode())):
            self.assertEqual(geocode(row)["precision_ubicacion"], "farmacia")

    def test_capital_pdf_never_reuses_unverified_pharmacy_coordinates(self):
        row = pharmacy("Real 1", "Granada", "", "958111111", "Día", date(2026, 11, 2),
                       "https://example.test/guardias.pdf")
        previous = {**row, "lat": 37.18, "lng": -3.60}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "farmacias-granada.json").write_text(json.dumps([previous]))
            (output / "farmacias-osm-espana.json").write_text(json.dumps([previous]))
            with patch("scrape_granada.OUT_DIR", output):
                locate([row])
            self.assertIsNone(row["lat"])
            self.assertIsNone(row["lng"])

    def test_scanned_schedule_requires_matching_digest_and_clips_both_boundaries(self):
        pdf = b"%PDF-verified-test"
        digest = hashlib.sha256(pdf).hexdigest()
        real_scan = VERIFIED_SCANS["eb642fa63f1cde1550740d2a1afaa7dd816cb955dd3ce71a0a8f4bb12e9d94a4"]
        with patch.dict(VERIFIED_SCANS, {digest: real_scan}, clear=True):
            self.assertIsNone(parse_verified_scan(pdf + b"changed", date(2026, 11, 2), "official"))
            rows = parse_verified_scan(pdf, date(2026, 11, 2), "official")
            self.assertEqual({r["localidad"] for r in rows}, {"Iznalloz", "Moreda", "Montejícar", "Alamedilla"})
            self.assertEqual(rows[1]["telefonos"], ["958692651", "648802569"])
            self.assertTrue(all(r["guardia_localizada"] for r in rows))
            self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-02T00:00:00")
            self.assertEqual(rows[0]["guardia_intervalos"][0]["fin"], "2026-11-03T00:00:00")
            first = parse_verified_scan(pdf, date(2026, 10, 30), "official")[0]
            last = parse_verified_scan(pdf, date(2026, 11, 6), "official")[0]
            self.assertEqual(first["guardia_intervalos"][0]["inicio"], "2026-10-30T09:30:00")
            self.assertEqual(last["guardia_intervalos"][0]["fin"], "2026-11-06T09:30:00")
            for day in (date(2026, 10, 29), date(2026, 11, 7)):
                with self.assertRaisesRegex(ValueError, "no cubre"):
                    parse_verified_scan(pdf, day, "official")

    def test_verified_scans_are_added_to_prior_partial_calendar_without_losing_rows(self):
        pdf = b"%PDF-verified-test"
        digest = hashlib.sha256(pdf).hexdigest()
        real_scan = VERIFIED_SCANS["eb642fa63f1cde1550740d2a1afaa7dd816cb955dd3ce71a0a8f4bb12e9d94a4"]
        target = date(2026, 11, 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved, output = root / "saved", root / "output"
            saved.mkdir()
            output.mkdir()
            index = {"consultas": [{"localidad": "Alamedilla", "archivo": "form.html"},
                                   {"localidad": "Moreda", "archivo": "form.html"},
                                   {"localidad": "Pendiente", "error": "Sin calendario"}],
                     "documentos": {"turno.pdf": "turno.pdf"}}
            (saved / "indice.json").write_text(json.dumps(index))
            (saved / "form.html").write_text('el día 02/11/2026 MostrarDocumento.asp?Documento=turno.pdf"')
            (saved / "turno.pdf").write_bytes(pdf)
            prior = pharmacy("Calle Anterior 1", "Granada", "", "", "Horario por confirmar", target, "previous")
            prior["localidades_atendidas"] = ["Granada"]
            calendar = output / f"guardias-granada-{target}.json"
            calendar.write_text(json.dumps([prior]))
            with patch.dict(VERIFIED_SCANS, {digest: real_scan}, clear=True), \
                    patch("scrape_granada.OUT_DIR", output), patch("scrape_granada.locate"):
                self.assertFalse(run(target, saved))
            rows = json.loads(calendar.read_text())
            self.assertEqual(len(rows), 5)
            self.assertIn(prior["id"], {r["id"] for r in rows})
            selected = next(r for r in rows if r["localidad"] == "Moreda")
            self.assertEqual(selected["localidades_atendidas"], ["Alamedilla", "Moreda"])
            self.assertTrue(selected["guardia_localizada"])
            coverage = json.loads((output / f"cobertura-granada-{target}.json").read_text())
            self.assertFalse(coverage["completa"])
            self.assertTrue(coverage["calendario_actualizado"])
            self.assertEqual(coverage["farmacias"], 5)
            self.assertEqual(coverage["consultas"][-1]["estado"], "error")

    def test_partial_coverage_reports_the_preserved_calendar(self):
        target = date(2026, 11, 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved, output = root / "saved", root / "output"
            saved.mkdir()
            output.mkdir()
            (saved / "indice.json").write_text(json.dumps({
                "consultas": [{"localidad": "Pendiente", "error": "Sin calendario"}],
            }))
            prior = pharmacy("Calle Anterior 1", "Granada", "", "", "Horario por confirmar", target, "previous")
            prior.update(lat=37.1, lng=-3.6)
            calendar = output / f"guardias-granada-{target}.json"
            calendar.write_text(json.dumps([prior]))
            with patch("scrape_granada.OUT_DIR", output), patch("scrape_granada.locate"):
                self.assertFalse(run(target, saved))
            self.assertEqual(json.loads(calendar.read_text()), [prior])
            coverage = json.loads((output / f"cobertura-granada-{target}.json").read_text())
            self.assertFalse(coverage["calendario_actualizado"])
            self.assertEqual((coverage["farmacias"], coverage["con_coordenadas"]), (1, 1))

    def test_merge_preserves_coordinates_and_deduplicates_intervals(self):
        target = date(2026, 11, 2)
        first = pharmacy("Hospital 16", "Montejícar", "", "", "turno", target, "source")
        first.update(lat=37.5, lng=-3.5, precision_ubicacion="farmacia",
                     localidades_atendidas=["Montejícar"])
        second = pharmacy("Hospital 16", "Montejícar", "", "", "turno", target, "source")
        interval = {"inicio": "2026-11-02T00:00:00", "fin": "2026-11-03T00:00:00", "tipo": "localizada"}
        second.update(guardia_localizada=True, guardia_intervalos=[interval, interval.copy()],
                      localidades_atendidas=["Montejícar", "Alamedilla"])
        merged = merge([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual((merged[0]["lat"], merged[0]["lng"]), (37.5, -3.5))
        self.assertEqual(merged[0]["guardia_intervalos"], [interval])
        self.assertEqual(merged[0]["localidades_atendidas"], ["Montejícar", "Alamedilla"])
        self.assertTrue(merged[0]["guardia_localizada"])

    def test_weekly_localized_blocks_keep_the_morning_of_changeover(self):
        def line(y, x, right, text):
            return {"y": y, "x": x, "right": right, "text": text}

        page = {"width": 842, "lines": [
            line(10, 0, 300, "TURNOS DE ATENCION LOCALIZADA DIURNA Y NOCTURNA"),
            line(50, 100, 500, "LUNES 26 DE OCTUBRE A LUNES 2 DE NOVIEMBRE DE 2026"),
            line(80, 100, 200, "Lda. EJEMPLO"),
            line(80, 300, 450, "Castilla 3 – CAPILEIRA"),
            line(80, 600, 700, "958 763050"),
            line(120, 10, 800, "*NOTA: LOS CAMBIOS DE GUARDIA SE REALIZAN TODOS LOS LUNES A LAS 9:30 H."),
        ]}
        rows = parse_weekly_blocks([page], date(2026, 11, 2), "official")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["localidad"], row["direccion"], row["telefono"]),
                         ("Capileira", "Castilla 3", "958763050"))
        self.assertTrue(row["guardia_localizada"])
        self.assertEqual(row["guardia_intervalos"][0]["inicio"], "2026-11-02T00:00:00")
        self.assertEqual(row["guardia_intervalos"][0]["fin"], "2026-11-02T09:30:00")
        self.assertEqual(parse_weekly_blocks([page], date(2026, 11, 3), "official"), [])
        start = parse_weekly_blocks([page], date(2026, 10, 26), "official")[0]
        self.assertEqual(start["guardia_intervalos"][0]["inicio"], "2026-10-26T09:30:00")
        without_note = {**page, "lines": page["lines"][:-1]}
        with self.assertRaisesRegex(ValueError, "hora de cambio"):
            parse_weekly_blocks([without_note], date(2026, 11, 2), "official")

    def test_partial_publication_adds_weekly_block_without_replacing_prior_calendar(self):
        target = date(2026, 11, 2)
        page = {"width": 842, "lines": [
            {"y": 10, "x": 0, "right": 300, "text": "ATENCION LOCALIZADA"},
            {"y": 50, "x": 100, "right": 500, "text": "LUNES 26 DE OCTUBRE A LUNES 2 DE NOVIEMBRE DE 2026"},
            {"y": 80, "x": 100, "right": 200, "text": "Lda. EJEMPLO"},
            {"y": 80, "x": 300, "right": 450, "text": "Castilla 3 – CAPILEIRA"},
            {"y": 80, "x": 600, "right": 700, "text": "958 763050"},
            {"y": 120, "x": 10, "right": 800, "text": "*NOTA: LOS CAMBIOS DE GUARDIA SE REALIZAN TODOS LOS LUNES A LAS 9:30 H."},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved, output = root / "saved", root / "output"
            saved.mkdir()
            output.mkdir()
            (saved / "indice.json").write_text(json.dumps({
                "consultas": [{"localidad": "Capileira", "archivo": "form.html"},
                              {"localidad": "Bubión", "archivo": "form.html"},
                              {"localidad": "Pendiente", "error": "Sin calendario"}],
                "documentos": {"turno.pdf": "turno.pdf"},
            }))
            (saved / "form.html").write_text('el día 02/11/2026 MostrarDocumento.asp?Documento=turno.pdf"')
            (saved / "turno.pdf").write_bytes(b"%PDF-weekly")
            prior = pharmacy("Calle Anterior 1", "Granada", "", "", "Horario por confirmar", target, "previous")
            prior.update(lat=37.1, lng=-3.6)
            calendar = output / f"guardias-granada-{target}.json"
            calendar.write_text(json.dumps([prior]))
            with patch("scrape_granada.OUT_DIR", output), patch("scrape_granada.locate"), \
                    patch("scrape_granada.pdf_pages", return_value=[page]):
                self.assertFalse(run(target, saved))
            rows = json.loads(calendar.read_text())
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], prior)
            self.assertEqual(rows[1]["localidades_atendidas"], ["Capileira", "Bubión"])
            self.assertEqual(rows[1]["guardia_intervalos"][0]["fin"], "2026-11-02T09:30:00")
            coverage = json.loads((output / f"cobertura-granada-{target}.json").read_text())
            self.assertFalse(coverage["completa"])
            self.assertTrue(coverage["calendario_actualizado"])
            self.assertEqual(coverage["farmacias"], 2)
            self.assertTrue(all(report["estado"] == "parcial" for report in coverage["consultas"][:2]))
            self.assertIn("relevo pendiente", coverage["consultas"][0]["errores"][0])

    def test_partial_publication_rejects_conflicting_catalogue_address(self):
        target = date(2026, 11, 2)
        pdf = b"%PDF-verified-test"
        digest = hashlib.sha256(pdf).hexdigest()
        scan = {"inicio": "2026-10-30T09:30:00", "fin": "2026-11-06T09:30:00", "farmacias": [
            {"localidad": "Torvizcón", "direccion": "Arroyo Plaza 4", "telefono": "958852115"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved, output = root / "saved", root / "output"
            saved.mkdir()
            output.mkdir()
            (saved / "indice.json").write_text(json.dumps({
                "consultas": [{"localidad": "Torvizcón", "archivo": "form.html"}],
                "documentos": {"turno.pdf": "turno.pdf"},
            }))
            (saved / "form.html").write_text('el día 02/11/2026 MostrarDocumento.asp?Documento=turno.pdf"')
            (saved / "turno.pdf").write_bytes(pdf)
            prior = pharmacy("Arroyo Plaza 3", "Torvizcón", "", "958852115", "Anterior", target, "previous")
            prior.update(lat=36.8791181, lng=-3.2993577)
            (output / "farmacias-granada.json").write_text(json.dumps([prior]))
            calendar = output / f"guardias-granada-{target}.json"
            calendar.write_text(json.dumps([prior]))
            with patch.dict(VERIFIED_SCANS, {digest: scan}, clear=True), \
                    patch("scrape_granada.OUT_DIR", output), patch("scrape_granada.locate"):
                self.assertFalse(run(target, saved))
            self.assertEqual(json.loads(calendar.read_text()), [prior])
            coverage = json.loads((output / f"cobertura-granada-{target}.json").read_text())
            self.assertFalse(coverage["calendario_actualizado"])
            self.assertIn("dirección discrepante", coverage["consultas"][0]["errores"][0])

    def test_partial_publication_does_not_replace_an_existing_unknown_schedule(self):
        target = date(2026, 11, 2)
        pdf = b"%PDF-verified-test"
        digest = hashlib.sha256(pdf).hexdigest()
        scan = {"inicio": "2026-10-26T09:30:00", "fin": "2026-11-02T09:30:00", "farmacias": [
            {"localidad": "Cádiar", "direccion": "Plaza de la Iglesia 11", "telefono": "958768066"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved, output = root / "saved", root / "output"
            saved.mkdir()
            output.mkdir()
            (saved / "indice.json").write_text(json.dumps({
                "consultas": [{"localidad": "Cádiar", "archivo": "form.html"},
                              {"localidad": "Pendiente", "error": "Sin calendario"}],
                "documentos": {"turno.pdf": "turno.pdf"},
            }))
            (saved / "form.html").write_text('el día 02/11/2026 MostrarDocumento.asp?Documento=turno.pdf"')
            (saved / "turno.pdf").write_bytes(pdf)
            prior = pharmacy("Plaza de la Iglesia 11", "Cádiar", "", "958768066",
                             "Horario no especificado por la fuente", target, "previous")
            calendar = output / f"guardias-granada-{target}.json"
            calendar.write_text(json.dumps([prior]))
            with patch.dict(VERIFIED_SCANS, {digest: scan}, clear=True), \
                    patch("scrape_granada.OUT_DIR", output), patch("scrape_granada.locate"):
                self.assertFalse(run(target, saved))
            self.assertEqual(json.loads(calendar.read_text()), [prior])
            coverage = json.loads((output / f"cobertura-granada-{target}.json").read_text())
            self.assertFalse(coverage["calendario_actualizado"])

    def test_locate_preserves_reviewed_coordinate_evidence(self):
        target = date(2026, 11, 2)
        row = pharmacy("REAL 61", "Trevélez", "", "644328635", "Localizada", target, "official")
        previous = {**row, "lat": 36.9991287, "lng": -3.2645467,
                    "precision_ubicacion": "farmacia", "fuente_coordenadas": "https://osm.example/pharmacy",
                    "nota_ubicacion": "Dirección contrastada a 2,3 m.", "ajuste_ubicacion_m": 2.3,
                    "referencia_ubicacion": "https://osm.example/address"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "farmacias-granada.json").write_text(json.dumps([previous]))
            (output / "farmacias-osm-espana.json").write_text("[]")
            with patch("scrape_granada.OUT_DIR", output):
                locate([row])
            self.assertEqual(row["ajuste_ubicacion_m"], 2.3)
            self.assertEqual(row["referencia_ubicacion"], "https://osm.example/address")
            self.assertEqual(row["nota_ubicacion"], "Dirección contrastada a 2,3 m.")


if __name__ == "__main__":
    unittest.main()
