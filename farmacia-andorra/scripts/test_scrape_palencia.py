from datetime import date
from calendar import Calendar
import subprocess
import unittest
from unittest.mock import patch

from scrape_palencia import (background, catalogue, color_pharmacy, consolidate, duty, links,
                             matching_color, parse_capital, parse_colors, parse_pdf,
                             parse_weekly, pharmacy_from_cell, raster)


def line(value, x, y, width=40):
    return {"text": value, "x": x, "right": x + width, "y": y}


class PalenciaTests(unittest.TestCase):
    def color_calendar(self):
        width, height = 600, 500
        pixels = bytearray(b"\xff" * width * height * 3)
        def fill(left, top, right, bottom, color):
            for y in range(top, bottom):
                start = (y * width + left) * 3
                pixels[start:start + (right - left) * 3] = bytes(color) * (right - left)
        colors = [(255, 0, 0), (146, 208, 80)]
        lines, words = [], []
        for index, month in enumerate(("OCTUBRE", "NOVIEMBRE", "DICIEMBRE")):
            words.append(line(month, 70 + index * 200, 120, 60))
            for week, days in enumerate(Calendar().monthdayscalendar(2026, 10 + index)):
                for weekday, number in enumerate(days):
                    if not number:
                        continue
                    x, y = 20 + index * 200 + weekday * 22, 160 + week * 22
                    color = colors[0] if number == 1 or (index == 0 and number == 31) else colors[1]
                    fill(x - 3, y - 2, x + 14, y + 15, color)
                    words.append(line(str(number), x, y, 10))
        for index, color in enumerate(colors):
            top, bottom = 390 + index * 50, 420 + index * 50
            fill(340, top + 1, 590, bottom, color)
            for y in (top, bottom):
                fill(210, y, 590, y + 1, (0, 0, 0))
            lines.append(line("GUARDIA 24 HORAS", 220, top + 10, 80))
            words.extend([line(f"Titular {index}", 350, top + 4, 60),
                          line(f"(C/ Mayor, {index + 1}) TFNO: 97900000{index + 1}", 350, top + 15, 230)])
        return {"width": width, "lines": lines, "words": words}, (width, height, bytes(pixels))

    def test_calendar_colors_match_date_and_previous_night(self):
        page, image = self.color_calendar()
        directory = []
        with patch("scrape_palencia.raster", return_value=image):
            rows = parse_colors(b"pdf", page, "Guardo", date(2026, 11, 1), "official", directory)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["direccion"], "C/ Mayor, 1")
        self.assertEqual(rows[0]["telefono"], "979000001")
        self.assertIn("Madrugada", rows[1]["guardia_franja"])
        self.assertEqual(rows[0]["guardia_intervalos"], [])
        self.assertIn("pendiente", rows[0]["guardia_franja"])
        self.assertIsNone(rows[0]["lat"])
        self.assertEqual(len(directory), 2)
        self.assertTrue(all(row["guardia"] is False for row in directory))

    def test_cervera_localities_follow_printed_row_not_zone_name(self):
        page, original = self.color_calendar()
        width, height, data = original
        pixels = bytearray(data + b"\xff" * width * 180 * 3)
        names = ["CERVERA DE PISUERGA", "CERVERA DE PISUERGA", "SALINAS DE PISUERGA",
                 "SAN SALVADOR DE CANTAMUDA", "CASTREJON DE LA PEÑA"]
        colors = [(255, 0, 0), (146, 208, 80), (255, 192, 0),
                  (160, 130, 200), (100, 205, 220)]
        page["lines"] = []
        page["words"] = [word for word in page["words"] if word["y"] < 390]
        for index, (name, color) in enumerate(zip(names, colors)):
            top, bottom = 390 + index * 50, 420 + index * 50
            for y in range(top + 1, bottom):
                at = (y * width + 340) * 3
                pixels[at:at + 250 * 3] = bytes(color) * 250
            for y in (top, bottom):
                at = (y * width + 210) * 3
                pixels[at:at + 380 * 3] = b"\x00" * 380 * 3
            page["lines"].append(line(name, 120, top + 10, 100))
            if index:
                page["lines"].append(line("GUARDIA 24H", 120, top - 5, 90))
            page["words"].extend([line(f"Titular {index}", 350, top + 4, 80),
                                  line(f"(Plaza Mayor, {index + 1}) TLFNº: 97900000{index + 1}",
                                       350, top + 15, 230)])
        directory = []
        with patch("scrape_palencia.raster", return_value=(width, height + 180, bytes(pixels))):
            rows = parse_colors(b"pdf", page, "Cervera de Pisuerga", date(2026, 11, 1),
                                "official", directory)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["localidad"], "Cervera de Pisuerga")
        self.assertEqual([row["localidad"] for row in directory],
                         ["Cervera de Pisuerga", "Cervera de Pisuerga", "Salinas de Pisuerga",
                          "San Salvador de Cantamuda", "Castrejón de la Peña"])
        self.assertTrue(all(row["guardia"] is False and row["lat"] is None for row in directory))
        page["lines"] = page["lines"][:-1]
        with self.assertRaisesRegex(ValueError, "incompleta"):
            parse_colors(b"pdf", page, "Cervera de Pisuerga", date(2026, 11, 1), "official")

    def test_partial_calendar_and_unknown_color_are_rejected(self):
        page, image = self.color_calendar()
        page["words"] = [word for word in page["words"] if word["text"] != "15"]
        with patch("scrape_palencia.raster", return_value=image):
            with self.assertRaisesRegex(ValueError, "incompleto"):
                parse_colors(b"pdf", page, "Guardo", date(2026, 11, 1), "official")
        with self.assertRaisesRegex(ValueError, "ausente"):
            matching_color((0, 0, 255), [(255, 0, 0)])
        with self.assertRaisesRegex(ValueError, "ambiguo"):
            matching_color((240, 0, 0), [(255, 0, 0), (238, 0, 0)])
        self.assertEqual(matching_color((238, 0, 0), [(255, 0, 0)]), (255, 0, 0))
        self.assertEqual(matching_color((146, 205, 220), [(183, 222, 232)]), (183, 222, 232))

    def test_shared_color_keeps_both_pharmacies(self):
        page, image = self.color_calendar()
        width, height, data = image
        pixels = bytearray(data)
        for y in range(441, 470):
            for x in range(340, 590):
                at = (y * width + x) * 3
                pixels[at:at + 3] = bytes((255, 0, 0))
        with patch("scrape_palencia.raster", return_value=(width, height, bytes(pixels))):
            rows = parse_colors(b"pdf", page, "Aguilar de Campoo", date(2026, 11, 1), "official")
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["direccion"] for row in rows}, {"C/ Mayor, 1", "C/ Mayor, 2"})

    def test_raster_integrity_and_barruelo_identity(self):
        result = subprocess.CompletedProcess([], 0, stdout=b"P6\n2 1\n255\n" + b"\xff" * 6)
        with patch("scrape_palencia.subprocess.run", return_value=result):
            image = raster(b"pdf")
        self.assertEqual(image[:2], (2, 1))
        with self.assertRaisesRegex(ValueError, "Color"):
            background(image, 0, 0, 2, 1)
        with patch("scrape_palencia.subprocess.run", return_value=subprocess.CompletedProcess(
                [], 0, stdout=b"P6\n2 1\n255\n" + b"\xff" * 3)):
            with self.assertRaisesRegex(ValueError, "incompleta"):
                raster(b"pdf")
        row = color_pharmacy(["ENARA ARRIBAS ANGULO", "Constitución nº 12",
                              "(BARRUELO DE SANTULLAN) TLFO: 979606048"], "official", "Aguilar de Campoo")
        self.assertEqual(row["localidad"], "Barruelo de Santullán")
        self.assertEqual(row["direccion"], "Constitución nº 12")

    def test_catalogue_opening_hours_are_not_duties(self):
        page = ('<tr><td>Farmacia Ejemplo</td><td>Centro de salud</td>'
                '<td>C/ Mayor, 1<br>TELEFONO 979 000 001</td><td>24 horas</td></tr>')
        rows = catalogue(page)
        self.assertEqual(rows[0]["telefono"], "979000001")
        self.assertFalse(rows[0]["guardia"])
        self.assertIsNone(rows[0]["lat"])
        with self.assertRaises(ValueError):
            catalogue(page.replace("979 000 001", "979"))

    def test_official_pdf_links_and_no_empty_index(self):
        result = links('<a href="calendarios de guardias 1.pdf">AGUILAR</a>')
        self.assertIn("calendarios%20de%20guardias%201.pdf", result[0]["url"])
        with self.assertRaises(ValueError):
            links('<a href="https://example.com/1.pdf">Otro</a>')
        with self.assertRaises(ValueError):
            links("")

    def test_verified_cross_province_referral_keeps_actual_province(self):
        row = pharmacy_from_cell(["JOSE LUIS", "AV CONSTITUCION, Nº 24", "SAHAGÚN"], "official")
        self.assertEqual(row["provincia"], "León")
        self.assertEqual(row["localidad"], "Sahagún")
        item = duty(row, date(2026, 10, 31), date(2026, 11, 1), "nocturna",
                    "Saldaña", ("22:00", "10:00"))
        self.assertEqual(item["provincias_atendidas"], ["Palencia"])
        self.assertEqual(item["localidades_atendidas"], ["Saldaña"])
        self.assertEqual(item["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00+01:00")
        self.assertEqual(item["guardia_intervalos"][0]["fin"], "2026-11-01T10:00:00+01:00")

    def test_separate_diurnal_and_overnight_intervals_survive_merge(self):
        row = pharmacy_from_cell(["Titular", "C/ Mayor, 1"], "official", "Palencia")
        items = [duty(row, date(2026, 11, 1), date(2026, 11, 1), section, "Palencia", hours)
                 for section, hours in (("diurna", ("10:00", "22:00")),
                                        ("nocturna", ("22:00", "10:00")))]
        result = consolidate(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["guardia_intervalos"]), 2)
        self.assertIn("2026-11-02T10:00:00+01:00",
                      [item["fin"] for item in result[0]["guardia_intervalos"]])

    def test_capital_date_and_unknown_diurnal_hours(self):
        page = {"width": 600, "lines": [
            line("DOMINGO", 20, 200), line("1 de", 20, 220), line("NOVIEMBRE", 20, 235),
            line("Titular A", 120, 205), line("C/ Mayor, 1", 120, 225),
            line("Titular B", 270, 205), line("C/ Mayor, 2", 270, 225),
            line("Titular B", 450, 205), line("C/ Mayor, 2", 450, 225),
        ]}
        rows = parse_capital(page, 2026, date(2026, 11, 1), "official")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["guardia_intervalos"], [])
        self.assertIn("pendiente", rows[0]["guardia_franja"])
        self.assertEqual(len(parse_capital(page, 2026, date(2026, 11, 3), "official")), 0)
        with self.assertRaises(ValueError):
            parse_capital(page, 2025, date(2025, 11, 1), "official")

    def test_weekly_target_and_previous_night(self):
        page = {"width": 600, "lines": [
            line("DIURNA", 220, 180), line("NOCTURNA", 450, 180),
            line("SEMANA", 50, 250), line("(26 DE OCTUBRE)", 20, 270, 130),
            line("(1 DE NOVIEMBRE)", 20, 315, 130),
            line("Titular A", 220, 270), line("(C/ Mayor, 1) SALDAÑA", 200, 295, 130),
            line("Titular B", 430, 270), line("(C/ Mayor, 2) SALDAÑA", 420, 295, 140),
        ]}
        rows = parse_weekly(page, 2026, "Saldaña", date(2026, 11, 1), "official")
        self.assertEqual(len(rows), 3)
        self.assertIn("Madrugada", rows[2]["guardia_franja"])

    def test_weekend_venta_columns_and_name_at_row_boundary(self):
        page = {"width": 600, "lines": [
            line("DIURNA", 220, 180), line("NOCTURNA", 450, 180),
            line("SEMANA", 50, 250), line("(26 DE OCTUBRE)", 20, 270, 130),
            line("(1 DE NOVIEMBRE)", 20, 315, 130),
        ]}
        for x in (200, 340, 465):
            page["lines"].extend([line("ANDRÉS SANZ VIDAL", x, 249.99, 100),
                                  line("( Avda. de la Estación,36", x, 270, 100)])
        rows = parse_weekly(page, 2026, "Venta de Baños", date(2026, 11, 1), "official", "venta")
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["nombre"] for row in rows}, {"ANDRÉS SANZ VIDAL"})
        self.assertEqual({row["localidad"] for row in rows}, {"Venta de Baños"})
        self.assertEqual(rows[3]["guardia_intervalos"][0]["fin"], "2026-11-01T09:30:00+01:00")
        self.assertEqual(len(consolidate(rows)[0]["guardia_intervalos"]), 4)
        with self.assertRaisesRegex(ValueError, "festivos"):
            parse_weekly(page, 2026, "Venta de Baños", date(2026, 10, 30), "official", "venta")

    def test_villada_weekend_uses_only_official_third_column(self):
        page = {"width": 600, "lines": [
            line("DIURNA", 220, 180), line("NOCTURNA", 360, 180),
            line("SEMANA", 50, 250), line("(26 DE OCTUBRE)", 20, 270, 130),
            line("(1 DE NOVIEMBRE)", 20, 315, 130),
            line("NO IMPORTAR", 210, 270, 90),
            line("NO IMPORTAR", 340, 270, 90),
            line("JOSE LUIS", 460, 249.99, 80),
            line("AV CONSTITUCION, 24 SAHAGÚN", 460, 290, 120),
        ]}
        rows = parse_weekly(page, 2026, "Villada", date(2026, 11, 1), "official", "villada")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["provincia"], "León")
        self.assertEqual(rows[0]["nombre"], "JOSE LUIS")
        self.assertEqual(rows[0]["guardia_intervalos"], [])
        self.assertIn("24 horas", rows[0]["guardia_franja"])

    def test_color_calendar_is_not_guessed_and_capital_year_is_checked(self):
        page = {"width": 600, "lines": [line("GUARDO-2026", 200, 100),
                                        line("OCTUBRE", 100, 180),
                                        line("20 21", 100, 250)]}
        with patch("scrape_palencia.pdf_pages", return_value=[page]):
            with self.assertRaisesRegex(ValueError, "colores"):
                parse_pdf(b"pdf", "GUARDO", date(2026, 11, 1), "official")
            with patch("scrape_palencia.subprocess.run", return_value=subprocess.CompletedProcess(
                    [], 0, stdout=b"CreationDate: Mon Sep 14 11:13:12 2025 CEST")):
                with self.assertRaisesRegex(ValueError, "año de creación"):
                    parse_pdf(b"pdf", "PALENCIA (semana)", date(2026, 11, 1), "official")


if __name__ == "__main__":
    unittest.main()
