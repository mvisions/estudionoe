import calendar
import unittest
from datetime import date, datetime

from scrape_andorra import (
    document_month,
    find_pdf_link,
    locate,
    overpass_pharmacies,
    parse_calendar,
)

TARGET = date(2026, 11, 4)
WEEKDAYS = ("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge")
DEFAULT = "F. Galeno 2 Av. Meritxell 91 Andorra Tel. 820107"
EDELWEISS = "F. Edelweiss C/ Bra. Riberaygua 31 Andorra Tel. 831227"
CARROI = "F. Carroi C/ Sant Salvador 2 Andorra Tel. 828020"
CONSELL = "F. El Consell C/ Prat de la Creu 87 Andorra Tel. 819219"
PASTEUR = "F. Pasteur Av. Bra. Armengol 5 Andorra Tel. 800970"


def calendar_fixture(target, records=None, month_name="NOVEMBRE", year=2026):
    records = records or {}
    lines = [
        "SERVEI DE GUÀRDIES I FESTIUS",
        f"{month_name} {year}",
        "DIA/ DAY 9’30→22 NIT/ NIGHT 22→9’30",
        "DATA FARMÀCIA ADREÇA FARMÀCIA ADREÇA",
    ]
    for day in range(1, calendar.monthrange(target.year, target.month)[1] + 1):
        weekday = WEEKDAYS[datetime(target.year, target.month, day).weekday()]
        day_record, night_record = records.get(day, (DEFAULT, DEFAULT))
        lines.append(f"{weekday} {day} {day_record} {night_record}")
    lines.extend([
        "SERVEI DE GUÀRDIES I FESTIUS DEL PAS DE LA CASA",
        "Del 2 al 8 de novembre F. del Pas C/ Major, 1 755860-352711",
        "La farmàcia de guàrdia és un servei d’urgència.",
    ])
    return "\n".join(lines)


def november_fixture():
    return calendar_fixture(
        TARGET,
        {
            2: (CARROI, CARROI),
            3: (EDELWEISS, EDELWEISS),
            4: (CONSELL, CONSELL),
            5: (PASTEUR, PASTEUR),
        },
    )


def overpass_payload():
    return {
        "elements": [
            {"type": "node", "id": 4512004201, "lat": 42.5063496, "lon": 1.5300827,
             "tags": {"amenity": "pharmacy", "name": "Farmàcia Edelweiss",
                      "addr:street": "Carrer Bonaventura Riberaygua", "addr:housenumber": "31"}},
            {"type": "node", "id": 5734184036, "lat": 42.5081056, "lon": 1.5291926,
             "tags": {"amenity": "pharmacy", "name": "Farmacia Pasteur",
                      "addr:street": "Carrer Bonaventura Armengol", "addr:housenumber": "7"}},
            {"type": "node", "id": 5734236535, "lat": 42.5077734, "lon": 1.5307045,
             "tags": {"amenity": "pharmacy", "name": "Farmacia Pasteur"}},
            {"type": "node", "id": 690708548, "lat": 42.5423906, "lon": 1.7339056,
             "tags": {"amenity": "pharmacy", "name": "Farmàcia del Pas",
                      "addr:street": "Carrer Major", "addr:housenumber": "1"}},
            {"type": "node", "id": 1, "lat": 42.5, "lon": 1.5,
             "tags": {"amenity": "bank", "name": "No és una farmàcia"}},
        ]
    }


class AndorraTest(unittest.TestCase):
    def test_parse_day_and_inherited_night(self):
        rows = {row["nombre"]: row for row in parse_calendar(november_fixture(), TARGET)}
        self.assertEqual(set(rows), {"F. Edelweiss", "F. El Consell"})

        consell = rows["F. El Consell"]
        self.assertEqual(consell["fecha_guardia"], "2026-11-04")
        self.assertEqual(consell["provincia"], "Andorra")
        self.assertEqual(consell["guardia_intervalos"][0], {
            "inicio": "2026-11-04T09:30:00",
            "fin": "2026-11-04T22:00:00",
            "inicio_original": "2026-11-04T09:30:00",
            "fin_original": "2026-11-04T22:00:00",
            "tipo": "DIA/ DAY 9’30→22",
        })
        self.assertEqual(consell["guardia_intervalos"][1]["inicio"], "2026-11-04T22:00:00")
        self.assertEqual(consell["guardia_intervalos"][1]["fin"], "2026-11-05T00:00:00")
        self.assertEqual(consell["guardia_intervalos"][1]["fin_original"], "2026-11-05T09:30:00")
        self.assertIn("NIT/ NIGHT 22→9’30", consell["guardia_franja"])

        edelweiss = rows["F. Edelweiss"]
        self.assertTrue(edelweiss["guardia_desde_ayer"])
        self.assertEqual(edelweiss["guardia_intervalos"], [{
            "inicio": "2026-11-04T00:00:00",
            "fin": "2026-11-04T09:30:00",
            "inicio_original": "2026-11-03T22:00:00",
            "fin_original": "2026-11-04T09:30:00",
            "tipo": "NIT/ NIGHT 22→9’30 · madrugada iniciada el 2026-11-03",
        }])
        self.assertIn("madrugada iniciada", edelweiss["guardia_franja"])

    def test_same_pharmacy_combines_day_and_night_intervals(self):
        rows = {row["nombre"]: row for row in parse_calendar(november_fixture(), date(2026, 11, 3))}
        edelweiss = rows["F. Edelweiss"]
        self.assertEqual(len(edelweiss["guardia_intervalos"]), 2)
        self.assertEqual(edelweiss["guardia_intervalos"][1]["inicio"], "2026-11-03T22:00:00")
        self.assertEqual(edelweiss["guardia_intervalos"][1]["fin"], "2026-11-04T00:00:00")
        self.assertIn("DIA/ DAY 9’30→22", edelweiss["guardia_franja"])
        self.assertIn("NIT/ NIGHT 22→9’30", edelweiss["guardia_franja"])
        carroi = rows["F. Carroi"]
        self.assertEqual(carroi["guardia_intervalos"][0]["inicio"], "2026-11-03T00:00:00")
        self.assertEqual(carroi["guardia_intervalos"][0]["fin"], "2026-11-03T09:30:00")
        self.assertEqual(carroi["guardia_intervalos"][0]["inicio_original"], "2026-11-02T22:00:00")

    def test_rejects_wrong_month_and_unknown_format(self):
        text = november_fixture()
        with self.assertRaises(ValueError):
            parse_calendar(text, date(2026, 12, 4))
        with self.assertRaises(ValueError):
            parse_calendar(text.replace("NOVEMBRE 2026", "DESEMBRE 2026"), TARGET)
        with self.assertRaises(ValueError):
            parse_calendar(text.replace("DIA/ DAY 9’30→22", ""), TARGET)
        with self.assertRaises(ValueError):
            parse_calendar(text.replace("Dimecres 4", "Dijous 4"), TARGET)
        with self.assertRaises(ValueError):
            document_month("sense cap mes")

    def test_rejects_day_without_both_columns_or_extra_text(self):
        broken = calendar_fixture(TARGET, {4: (CONSELL, "")})
        with self.assertRaises(ValueError):
            parse_calendar(broken, TARGET)
        extra = calendar_fixture(TARGET, {4: (CONSELL, CONSELL)}).replace(
            f"{CONSELL} {CONSELL}", f"{CONSELL} texto suelto {CONSELL}"
        )
        with self.assertRaises(ValueError):
            parse_calendar(extra, TARGET)

    def test_finds_only_the_official_pdf_for_the_requested_month(self):
        page = (
            '<a href="https://example.test/octubre.pdf" data-name="farmacies_guardia_octubre_2026">'
            'Servei de farmàcies de guàrdia - Octubre 2026</a>'
            '<a href="https://example.test/novembre.pdf" data-name="farmacies_guardia_novembre_2026">'
            'Servei de farmàcies de guàrdia - Novembre 2026</a>'
        )
        self.assertEqual(
            find_pdf_link(page, TARGET),
            ("https://example.test/novembre.pdf", "farmacies_guardia_novembre_2026"),
        )
        with self.assertRaises(ValueError):
            find_pdf_link(page, date(2026, 12, 4))
        with self.assertRaises(ValueError):
            find_pdf_link("<html>sense enllaços</html>", TARGET)

    def test_coordinates_only_for_one_unique_name_and_address_match(self):
        rows = {row["nombre"]: row for row in parse_calendar(november_fixture(), TARGET)}
        pharmacies = overpass_pharmacies(overpass_payload())
        self.assertEqual(len(pharmacies), 4)
        self.assertTrue(locate(rows["F. Edelweiss"], pharmacies))
        self.assertEqual(rows["F. Edelweiss"]["osm_id"], "osm-4512004201")
        self.assertNotIn("ajuste_ubicacion_m", rows["F. Edelweiss"])
        self.assertFalse(locate(rows["F. El Consell"], pharmacies))
        self.assertTrue(rows["F. El Consell"]["ubicacion_pendiente_verificacion"])

        pasteur = {
            "id": "test", "nombre": "F. Pasteur", "direccion": "Av. Bra. Armengol 5",
            "localidad": "Andorra", "telefono": "800970",
        }
        self.assertFalse(locate(pasteur, pharmacies))
        self.assertNotIn("lat", pasteur)


if __name__ == "__main__":
    unittest.main()
