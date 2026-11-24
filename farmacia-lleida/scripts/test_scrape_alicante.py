from datetime import date
import io
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

from scrape_alicante import HEADERS, intervals, parse_workbook, spreadsheet_url


def workbook(rows):
    stream = io.BytesIO()
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with ZipFile(stream, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{namespace}" '
                         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                         '<sheets><sheet name="Guardias" r:id="r1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels",
                         '<Relationships><Relationship Id="r1" Target="/xl/worksheets/sheet.xml"/></Relationships>')
        data = []
        for number, row in enumerate([HEADERS, *rows], 1):
            cells = ''.join(f'<c r="{column}{number}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
                            for column, value in zip("ABCDEFGHI", row))
            data.append(f"<row>{cells}</row>")
        archive.writestr("xl/worksheets/sheet.xml",
                         f'<worksheet xmlns="{namespace}"><sheetData>{"".join(data)}</sheetData></worksheet>')
    return stream.getvalue()


def entry(day, identifier="123", hours="De 9:00 a 9:00"):
    return [str((day - date(1899, 12, 30)).days), "27", "", "14", identifier,
            "Farmacia de prueba", "Calle Mayor 1", "Elche/Elx", hours]


class AlicanteTests(unittest.TestCase):
    def test_official_year_link_only(self):
        url = "https://www.cofalicante.com/ficheros/farmaciasguardia/guardias2026.xlsx"
        self.assertEqual(spreadsheet_url(f'<a href="{url}">Excel</a>', 2026), url)
        for content in (f'<a href="{url}">Excel</a>', '<a href="https://otro.es/guardias2027.xlsx">Excel</a>'):
            with self.assertRaises(ValueError):
                spreadsheet_url(content, 2027)

    def test_split_shifts_and_overnight_are_preserved(self):
        day = date(2026, 11, 1)
        batch = intervals(day, "De 9:00 a 13:30 y de 17:00 a 9:00")
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[1][1].date(), date(2026, 11, 2))
        for hours in ("Abierta", "De 25:00 a 9:00", "De 9:00 a 20:00 y de 17:00 a 9:00"):
            with self.assertRaises(ValueError):
                intervals(day, hours)

    def test_today_and_previous_night_consolidate_without_losing_intervals(self):
        target = date(2026, 11, 1)
        document = workbook([entry(date(2026, 10, 31)),
                             entry(target, hours="De 9:00 a 13:30 y de 17:00 a 9:00")])
        directory, rows, reports = parse_workbook(document, target, "https://official.example/guardias.xlsx")
        self.assertEqual(len(directory), 1)
        self.assertFalse(directory[0]["guardia"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provincia"], "Alicante")
        self.assertEqual(rows[0]["localidad"], "Elche/Elx")
        self.assertEqual(len(rows[0]["guardia_intervalos"]), 3)
        self.assertEqual(rows[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T00:00:00+01:00")
        self.assertEqual(rows[0]["guardia_intervalos"][-1]["fin"], "2026-11-02T09:00:00+01:00")
        self.assertIsNone(rows[0]["lat"])
        self.assertEqual(reports[0]["estado"], "parcial")

    def test_wrong_year_missing_day_and_changed_identity_are_rejected(self):
        target = date(2026, 11, 1)
        changed = entry(target)
        changed[6] = "Otra calle 2"
        for rows in ([entry(date(2025, 11, 1))], [entry(target)],
                     [entry(date(2026, 10, 31)), changed]):
            with self.assertRaises(ValueError):
                parse_workbook(workbook(rows), target, "official")

    def test_midnight_end_is_not_a_current_day_duty(self):
        target = date(2026, 11, 1)
        rows = [entry(date(2026, 10, 31), hours="De 9:00 a 0:00"),
                entry(target, identifier="456", hours="De 9:00 a 21:00")]
        _, duties, _ = parse_workbook(workbook(rows), target, "official")
        self.assertEqual([row["cofa_id"] for row in duties], ["456"])

    def test_january_carryover_is_explicitly_unverified(self):
        target = date(2026, 1, 1)
        _, _, reports = parse_workbook(workbook([entry(target)]), target, "official")
        self.assertEqual(reports[-1]["estado"], "error")


if __name__ == "__main__":
    unittest.main()
