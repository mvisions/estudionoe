from datetime import date
import unittest

from scrape_baleares import parse_coordinates, parse_index, parse_listing, split_pharmacy_name


INDEX = """
<select id="ctl00_cphBody_ddlMallorca">
  <option value="sin">------</option><option>Palma</option><option>Inca</option>
</select>
<select id="ctl00_cphBody_ddlMenorca">
  <option value="sin">------</option><option>Maó</option>
</select>
<select id="ctl00_cphBody_ddlPitiuses">
  <option value="sin">------</option><option>Eivissa</option>
</select>
"""


def listing(day, zone, heading, name, address, pharmacy_id="18408"):
    return f"""
    <input id="ctl00_cphBody_hdnData" value="{day}" />
    <input id="ctl00_cphBody_hdnZona" value="{zone}" />
    <table id="tblLlistatGuardies">
      <tr><td><p class="lstgtitol">{heading}</p></td></tr>
      <tr><td><span class="lstgnom">{name}</span>
      <a class="lstgmapa" onClick="mostrarmapa('mapes.aspx','{pharmacy_id}');"></a>
      <span class="lstgdir">{address}</span></td></tr>
    </table>
    """


class BalearesTests(unittest.TestCase):
    def test_index_lists_all_three_islands(self):
        self.assertEqual(parse_index(INDEX), ["Palma", "Inca", "Maó", "Eivissa"])
        with self.assertRaises(ValueError):
            parse_index(INDEX.replace('<select id="ctl00_cphBody_ddlPitiuses">', '<select>'))

    def test_previous_night_is_clipped_to_selected_day(self):
        rows = parse_listing(
            listing("31/10/2026", "Palma", "SERVEI D'URGÈNCIA NOCTURN de 22:00 a 09:00",
                    "ALCOVER CASASNOVAS, R 971 909 015", "AV. JOAN MIRÓ, 186 - PALMA"),
            date(2026, 10, 31), date(2026, 11, 1), "Palma", "official", ["Palma"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "cof-baleares-18408")
        self.assertEqual(rows[0]["localidad"], "Palma")
        self.assertEqual(rows[0]["telefono"], "971909015")
        self.assertEqual(rows[0]["fecha_guardia"], "2026-11-01")
        self.assertEqual(rows[0]["guardia_intervalos"], [{
            "inicio": "2026-11-01T00:00:00+01:00",
            "fin": "2026-11-01T09:00:00+01:00",
        }])

    def test_day_and_24_hour_shifts_keep_their_full_selected_day_interval(self):
        day = parse_listing(
            listing("01/11/2026", "Palma", "SERVEI D'URGÈNCIA DIURN de 09:00 a 22:00",
                    "FARMACIA UNO 971000001", "CARRER MAJOR, 1 - PALMA"),
            date(2026, 11, 1), date(2026, 11, 1), "Palma", "official", ["Palma"],
        )
        full = parse_listing(
            listing("01/11/2026", "Eivissa", "SERVEI D'URGÈNCIA (09:00 - 09:00)",
                    "FARMACIA DOS 971000002", "AV. ESPANYA, 2 - EIVISSA"),
            date(2026, 11, 1), date(2026, 11, 1), "Eivissa", "official", ["Palma", "Eivissa"],
        )
        self.assertEqual(day[0]["guardia_intervalos"][0]["inicio"], "2026-11-01T09:00:00+01:00")
        self.assertEqual(day[0]["guardia_intervalos"][0]["fin"], "2026-11-01T22:00:00+01:00")
        self.assertEqual(full[0]["guardia_intervalos"][0]["fin"], "2026-11-02T00:00:00+01:00")

    def test_unconfirmed_date_or_zone_is_rejected(self):
        content = listing("01/11/2026", "Palma", "SERVEI D'URGÈNCIA DIURN de 09:00 a 22:00",
                          "FARMACIA UNO 971000001", "CARRER MAJOR, 1 - PALMA")
        with self.assertRaises(ValueError):
            parse_listing(content, date(2026, 10, 31), date(2026, 11, 1),
                          "Palma", "official", ["Palma"])
        with self.assertRaises(ValueError):
            parse_listing(content, date(2026, 11, 1), date(2026, 11, 1),
                          "Inca", "official", ["Palma", "Inca"])
        with self.assertRaises(ValueError):
            parse_listing(content.replace('<table id="tblLlistatGuardies">', '<table id="otra">'),
                          date(2026, 11, 1), date(2026, 11, 1),
                          "Palma", "official", ["Palma"])

    def test_pharmacy_without_official_map_link_is_retained_without_inventing_location(self):
        rows = parse_listing(
            listing("01/11/2026", "Pollença", "SERVEI D'URGÈNCIA DIURN de 09:00 a 21:00",
                    "MARCOS GARCIA 971864699", "C/ JOAN XXIII, 106", pharmacy_id=""),
            date(2026, 11, 1), date(2026, 11, 1), "Pollença", "official", ["Pollença"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "cof-baleares-tel-971864699")
        self.assertEqual(rows[0]["localidad"], "Pollença")
        self.assertIsNone(rows[0]["lat"])

    def test_map_coordinates_are_required_and_bounded_to_baleares(self):
        self.assertEqual(parse_coordinates("var latit = 39.552288, longt = 2.621433;"),
                         (39.552288, 2.621433))
        for content in ("La farmacia no existe", "var latit = 40.7, longt = 2.6;"):
            with self.assertRaises(ValueError):
                parse_coordinates(content)

    def test_phone_is_normalized_and_missing_phone_is_not_guessed(self):
        self.assertEqual(split_pharmacy_name("TITULAR   971 90 90 15"),
                         ("TITULAR", "971909015"))
        self.assertEqual(split_pharmacy_name("TITULAR"), ("TITULAR", ""))


if __name__ == "__main__":
    unittest.main()
