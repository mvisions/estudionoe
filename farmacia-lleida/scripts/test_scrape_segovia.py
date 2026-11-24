from datetime import date
import unittest

from scrape_segovia import (
    calendar_pdf_url,
    municipal_pdf_url,
    parse_calendar,
    parse_rural_calendar,
    parse_weekly_calendar,
    pharmacy_id,
    rural_pdf_url,
    _resolve_rural_candidate,
)


SOURCE_PAGE = """
<a href="https://cofsegovia.com/wp-content/uploads/2026/09/CALENDARIO-GUARDIAS-SEGOVIA-CAPITAL-2026.pdf">PDF</a>
"""

MUNICIPAL_SOURCE_PAGE = """
<a href="https://cofsegovia.com/wp-content/uploads/2026/01/GUARDIAS-CUELLAR_2026.pdf">Cuéllar</a>
<a href="https://cofsegovia.com/wp-content/uploads/2026/01/Guardias-EL-ESPINAR_2026.pdf">El Espinar</a>
"""

RURAL_SOURCE_PAGE = """
<a href="https://cofsegovia.com/wp-content/uploads/2026/10/SERVICIOS-DE-URGENCIA-RURALES-2026.pdf">Segovia rural</a>
"""

REGISTRY = [
    {"num_reg": "40-E1-00009", "nombre_comercial": "CABRERIZO IZQUIERDO, CESAR",
     "calle": "CALLE SANTA MARINA", "numero": "5", "localidad": "CUELLAR",
     "municipio": "CUÉLLAR", "provincia": "SEGOVIA", "telefono": 921140606},
    {"num_reg": "40-E1-00082", "nombre_comercial": "SANCHEZ CACERES, FAUSTO",
     "calle": "AVDA CAMILO JOSE CELA", "numero": "46", "localidad": "CUELLAR",
     "municipio": "CUÉLLAR", "provincia": "SEGOVIA", "telefono": 921142248},
    {"num_reg": "40-E1-00093", "nombre_comercial": "SANCHEZ GUTIERREZ, LORENA",
     "calle": "CTRA BAHABON", "numero": "9", "localidad": "CUELLAR",
     "municipio": "CUÉLLAR", "provincia": "SEGOVIA", "telefono": 921144794},
    {"num_reg": "40-E1-00008", "nombre_comercial": "ALCARAZ GARCIA DE LA BARRERA, FRANCISCO JAVIER",
     "calle": "CALLE RESINA", "numero": "14", "localidad": "CUELLAR",
     "municipio": "CUÉLLAR", "provincia": "SEGOVIA", "telefono": 921143093},
    {"num_reg": "40-E1-00100", "nombre_comercial": "CARRILLO MIGUEL, MONICA",
     "calle": "TRVA ALTO DEL LEON", "numero": "19", "localidad": "SAN RAFAEL",
     "municipio": "ESPINAR, EL", "provincia": "SEGOVIA", "telefono": 921171105},
    {"num_reg": "40-E1-00096", "nombre_comercial": "APARICIO HERNAN, ANA MARIA",
     "calle": "AVDA HONTANILLA", "numero": "12", "localidad": "ESPINAR (EL)",
     "municipio": "ESPINAR, EL", "provincia": "SEGOVIA", "telefono": None},
    {"num_reg": "40-E1-00017", "nombre_comercial": "BARTOLOME SANCHEZ, MARIA JESUS",
     "calle": "CALLE MARQUES DE PERALES", "numero": "2", "localidad": "ESPINAR (EL)",
     "municipio": "ESPINAR, EL", "provincia": "SEGOVIA", "telefono": 921181171},
    {"num_reg": "40-E1-00030", "nombre_comercial": "VILLAS MIGUEL, PILAR",
     "calle": "CALLE BAYONA", "numero": "21", "localidad": "BOCEGUILLAS",
     "municipio": "BOCEGUILLAS", "provincia": "SEGOVIA", "telefono": 921543849},
    {"num_reg": "40-E1-00063", "nombre_comercial": "MINGUEZ DEL POZO, CRISTINA",
     "calle": "CALLE VALENCIANA", "numero": "3", "localidad": "SAN ILDEFONSO O LA GRANJA",
     "municipio": "REAL SITIO DE SAN ILDEFONSO", "provincia": "SEGOVIA", "telefono": 921470038},
    {"num_reg": "40-E1-00064", "nombre_comercial": "MONEDERO MARTINEZ PARDO, LAURA",
     "calle": "PLAZA DOLORES (DE) (LOS)", "numero": "13",
     "localidad": "SAN ILDEFONSO O LA GRANJA", "municipio": "REAL SITIO DE SAN ILDEFONSO",
     "provincia": "SEGOVIA", "telefono": 921470017},
    {"num_reg": "40-E1-00023", "nombre_comercial": "CHAMORRO GARCIA, MIRIAM",
     "calle": "CALLE FLORENTINO TRAPERO", "numero": "5", "localidad": "AGUILAFUENTE",
     "municipio": "AGUILAFUENTE", "provincia": "SEGOVIA", "telefono": 921570030},
    {"num_reg": "40-E1-00068", "nombre_comercial": "MAROTO GOMEZ, AMPARO",
     "calle": "PLAZA IGLESIA", "numero": "5",
     "localidad": "SANTIUSTE DE SAN JUAN BAUTISTA",
     "municipio": "SANTIUSTE DE SAN JUAN BAUTISTA", "provincia": "SEGOVIA",
     "telefono": 921596007},
    {"num_reg": "40-E1-00015", "nombre_comercial": "BAUTISTA SALCEDO, MARIA DEL CARMEN",
     "calle": "CALLE INGENIERO MARTIN GIL", "numero": "10", "localidad": "CANTALEJO",
     "municipio": "CANTALEJO", "provincia": "SEGOVIA", "telefono": 921520005},
    {"num_reg": "40-E1-00016", "nombre_comercial": "CABAÑAS DE ORO, CRISTINA / DE ORO SANZ, LUISA MARIA",
     "calle": "CALLE FRONTON", "numero": "15", "localidad": "CANTALEJO",
     "municipio": "CANTALEJO", "provincia": "SEGOVIA", "telefono": 921520053},
]

CALENDAR = """
FARMACIA EN SER. DE URGENCIA DIURNO         FARMACIA EN SER. DE URGENCIA NOCTURNO
De 10:15 h. a 22:00 h.                       De 22:00 h.. a 10:15 h.
FARMACIA FERNANDEZ OLALLA                    FARMACIA FERNANDEZ OLALLA
sábado, 31 de octubre      VICENTE ALEIXANDRE,13                        VICENTE ALEIXANDRE,13
                             (Nueva Segovia) Tfno: 921 442366             (Nueva Segovia) Tfno: 921 442366
FARMACIA MARTÍN CANTERO                      FARMACIA RUJAS GÓMEZ
domingo, 1 de noviembre   CENTRO COMERCIAL LUZ DE CASTILLA             LARGA, 5
                             (Calle Guadarrama S/N) Tfno: 683 396809      (Junto c/ Coronel Rexach) Tfno: 921 441043
"""

CUELLAR_WEEK = """
SERVICIOS DE URGENCIA DE LAS FARMACIAS DEL MUNICIPIO DE CUELLAR PARA EL AÑO 2026
LUNES MARTES MIERCOLES JUEVES VIERNES SABADO DOMINGO
26-oct 27-oct 28-oct 29-oct 30-oct 31-oct 01-nov Ctra. BAHABON
02-nov 03-nov 04-nov 05-nov 06-nov 07-nov 08-nov C/ RESINA
"""

ESPINAR_WEEK = """
TURNOS DE GUARDIAS PARA LAS FARMACIAS DEL MUNICIPIO DE EL ESPINAR PARA EL AÑO 2026
LUNES MARTES MIERCOLES JUEVES VIERNES SABADO DOMINGO
NOV 26-oct 27-oct 28-oct 29-oct 30-oct 31-oct 01-nov SAN RAFAEL
EL ESPINAR.
02-nov 03-nov 04-nov 05-nov 06-nov 07-nov 08-nov AV. HONTANILLA 18
"""

def rural_word(x, y, value, width=8, height=6):
    return (
        f'<word xMin="{x}" yMin="{y}" xMax="{x + width}" yMax="{y + height}">'
        f"{value}</word>"
    )


RURAL_CALENDAR = f"""<doc><page width="841.68" height="595.2">
{rural_word(10, 10, "CALENDARIO DE SERVICIOS DE URGENCIA EN LA PROVINCIA DE SEGOVIA PARA EL AÑO 2.026", 600)}
{rural_word(10, 20, "GUARDIA DE 24 H. GUARDIA DE 10 H A 22 H GUARDIA DE 10 H A 20 H", 500)}
{rural_word(10, 30, "ZBS RIAZA SEPÚLVEDA ZBS LA GRANJA ZBS LA SIERA FUENTIDUEÑA SACRAMENIA ZBS CARBONERO ZBS NAVA DE LA A ZBA VILLACASTÍN", 700)}
{rural_word(57, 146, "26-oct-26")}
{rural_word(145.727, 154.296, "CANTALEJO", 7.359, 39.164)}
{rural_word(383.977, 153.111, "Valenciana", 7.359, 32.914)}
{rural_word(383.977, 187.794, "C/", 7.359, 6.626)}
{rural_word(22.944, 195.334, "Domingo", 22.124)}
{rural_word(57.864, 194.357, "01-nov-26", 30.037, 7.359)}
{rural_word(321.05, 195.334, "BOCEGUILLAS", 39.043)}
{rural_word(434.11, 195.334, "LA", 6.795)}
{rural_word(442.495, 195.334, "GRANJA", 22.389)}
{rural_word(636.58, 195.334, "AGUILAFUENTE", 42.305)}
{rural_word(717.72, 195.334, "SANTIUSTE", 30.918)}
{rural_word(57.504, 202.517, "02-nov-26", 30.756, 7.359)}
</page></doc>"""


class SegoviaTests(unittest.TestCase):
    def test_only_the_official_capital_pdf_for_requested_year_is_accepted(self):
        self.assertEqual(
            calendar_pdf_url(SOURCE_PAGE, 2026),
            "https://cofsegovia.com/wp-content/uploads/2026/09/"
            "CALENDARIO-GUARDIAS-SEGOVIA-CAPITAL-2026.pdf",
        )
        with self.assertRaises(ValueError):
            calendar_pdf_url(SOURCE_PAGE, 2027)
        with self.assertRaises(ValueError):
            calendar_pdf_url(SOURCE_PAGE.replace("cofsegovia.com", "other.example"), 2026)

    def test_previous_night_and_current_day_and_night_are_extracted(self):
        rows, reports = parse_calendar(
            CALENDAR, date(2026, 11, 1), "https://cofsegovia.com/official.pdf")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["nombre"], "FARMACIA FERNANDEZ OLALLA")
        self.assertEqual(rows[0]["telefono"], "921442366")
        self.assertEqual(rows[0]["guardia_intervalos"], [{
            "inicio": "2026-10-31T22:00:00+01:00",
            "fin": "2026-11-01T10:15:00+01:00",
        }])
        self.assertEqual(rows[1]["nombre"], "FARMACIA MARTÍN CANTERO")
        self.assertEqual(rows[1]["guardia_intervalos"][0]["inicio"],
                         "2026-11-01T10:15:00+01:00")
        self.assertEqual(rows[2]["nombre"], "FARMACIA RUJAS GÓMEZ")
        self.assertEqual(rows[2]["guardia_intervalos"][0]["fin"],
                         "2026-11-02T10:15:00+01:00")
        self.assertEqual(reports[0]["estado"], "parcial")

    def test_missing_current_date_or_changed_hours_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_calendar(CALENDAR.replace("domingo, 1 de noviembre", "domingo, 8 de noviembre"),
                           date(2026, 11, 1), "official")
        with self.assertRaises(ValueError):
            parse_calendar(CALENDAR.replace("De 10:15 h. a 22:00 h.", "De 10:00 h. a 22:00 h."),
                           date(2026, 11, 1), "official")

    def test_fallback_pharmacy_id_is_deterministic(self):
        first = pharmacy_id(None, "Farmacia", "Calle Mayor 1")
        self.assertEqual(first, pharmacy_id(None, "Farmacia", "Calle Mayor 1"))

    def test_weekly_pdf_links_are_official_and_year_specific(self):
        self.assertEqual(
            municipal_pdf_url(MUNICIPAL_SOURCE_PAGE, "Cuéllar", 2026),
            "https://cofsegovia.com/wp-content/uploads/2026/01/GUARDIAS-CUELLAR_2026.pdf",
        )
        self.assertEqual(
            municipal_pdf_url(MUNICIPAL_SOURCE_PAGE, "El Espinar", 2026),
            "https://cofsegovia.com/wp-content/uploads/2026/01/Guardias-EL-ESPINAR_2026.pdf",
        )
        with self.assertRaises(ValueError):
            municipal_pdf_url(MUNICIPAL_SOURCE_PAGE.replace("cofsegovia.com", "other.example"),
                              "Cuéllar", 2026)
        with self.assertRaises(ValueError):
            municipal_pdf_url(MUNICIPAL_SOURCE_PAGE, "Cuéllar", 2027)

    def test_rural_pdf_link_is_official_and_year_specific(self):
        self.assertEqual(
            rural_pdf_url(RURAL_SOURCE_PAGE, 2026),
            "https://cofsegovia.com/wp-content/uploads/2026/10/"
            "SERVICIOS-DE-URGENCIA-RURALES-2026.pdf",
        )
        with self.assertRaises(ValueError):
            rural_pdf_url(RURAL_SOURCE_PAGE.replace("cofsegovia.com", "other.example"), 2026)
        with self.assertRaises(ValueError):
            rural_pdf_url(RURAL_SOURCE_PAGE, 2027)

    def test_rural_daily_services_resolve_from_official_register_and_keep_hours(self):
        rows, report = parse_rural_calendar(
            RURAL_CALENDAR, date(2026, 11, 1), "official-rural-pdf", REGISTRY)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(set(by_id), {
            "jcyl-40-e1-00030", "jcyl-40-e1-00063",
            "jcyl-40-e1-00023", "jcyl-40-e1-00068",
        })
        self.assertEqual(by_id["jcyl-40-e1-00063"]["direccion"], "Calle Valenciana 3")
        self.assertEqual(by_id["jcyl-40-e1-00063"]["guardia_intervalos"], [{
            "inicio": "2026-11-01T10:00:00+01:00",
            "fin": "2026-11-01T22:00:00+01:00",
        }])
        self.assertEqual(by_id["jcyl-40-e1-00023"]["guardia_intervalos"], [{
            "inicio": "2026-11-01T10:00:00+01:00",
            "fin": "2026-11-01T20:00:00+01:00",
        }])
        self.assertEqual(report["estado"], "parcial")
        self.assertIn("Cantalejo", report["error"])

    def test_rural_short_labels_resolve_only_to_unique_registered_pharmacies(self):
        aliases = (
            ("FUENTESAUCO", "FUENTESAUCO DE FUENTIDUEÑA"),
            ("ESCALONA", "ESCALONA DEL PRADO"),
            ("ESCARABAJOSA", "ESCARABAJOSA DE CABEZAS"),
            ("CARBONERO M", "CARBONERO EL MAYOR"),
            ("NAVAS DE SA", "NAVAS DE SAN ANTONIO"),
            ("TORREVAL", "TORRE VAL DE SAN PEDRO"),
            ("ZARZUELA PINAR", "ZARZUELA DEL PINAR"),
        )
        for index, (label, municipality) in enumerate(aliases):
            with self.subTest(label=label):
                registration = {
                    "num_reg": f"40-E1-009{index:02}",
                    "nombre_comercial": f"FARMACIA {municipality}",
                    "calle": "CALLE MAYOR",
                    "numero": "1",
                    "localidad": municipality,
                    "municipio": municipality,
                    "provincia": "SEGOVIA",
                    "telefono": 921000000 + index,
                }
                rows, _ = parse_rural_calendar(
                    RURAL_CALENDAR.replace("BOCEGUILLAS", label),
                    date(2026, 11, 1),
                    "official-rural-pdf",
                    [*REGISTRY, registration],
                )
                resolved = [row for row in rows if row["id"] == f"jcyl-{registration['num_reg'].lower()}"]
                self.assertEqual(len(resolved), 1)
                self.assertEqual(resolved[0]["direccion"], "Calle Mayor 1")

    def test_rural_label_with_multiple_registered_pharmacies_stays_unresolved(self):
        nava_rows = [
            {
                "num_reg": f"40-E1-009{index:02}",
                "nombre_comercial": f"FARMACIA NAVA {index}",
                "calle": f"CALLE MAYOR {index}",
                "numero": str(index),
                "localidad": "NAVA DE LA ASUNCION",
                "municipio": "NAVA DE LA ASUNCION",
                "provincia": "SEGOVIA",
            }
            for index in (10, 11)
        ]
        self.assertIsNone(_resolve_rural_candidate("NAVA DE LA A", [*REGISTRY, *nava_rows], ""))

    def test_maello_is_resolved_and_keeps_its_official_province(self):
        maello = {
            "num_reg": "05-E1-00032",
            "nombre_comercial": "GUERRA GARCIA, NOELIA",
            "calle": "CALLE VILORIO",
            "numero": "8",
            "localidad": "MAELLO",
            "municipio": "MAELLO",
            "provincia": "AVILA",
            "telefono": 920192126,
        }
        rows, report = parse_rural_calendar(
            RURAL_CALENDAR.replace("BOCEGUILLAS", "MAELLO (ÁVILA)"),
            date(2026, 11, 1),
            "official-rural-pdf",
            [*REGISTRY, maello],
        )
        row = next(item for item in rows if item["id"] == "jcyl-05-e1-00032")
        self.assertEqual(row["direccion"], "Calle Vilorio 8")
        self.assertEqual(row["localidad"], "Maello")
        self.assertEqual(row["provincia"], "Ávila")
        self.assertEqual(report["farmacias"], 3)
        self.assertNotIn("MAELLO", report["error"])

    def test_rural_calendar_rejects_changed_layout_and_missing_date(self):
        with self.assertRaisesRegex(ValueError, "zonas y horarios"):
            parse_rural_calendar(
                RURAL_CALENDAR.replace("GUARDIA DE 10 H A 22 H", "HORARIO CAMBIADO"),
                date(2026, 11, 1), "official-rural-pdf", REGISTRY)
        with self.assertRaisesRegex(ValueError, "única fecha"):
            parse_rural_calendar(
                RURAL_CALENDAR.replace("01-nov-26", "08-nov-26"),
                date(2026, 11, 1), "official-rural-pdf", REGISTRY)

    def test_cuellar_weekly_rotation_uses_official_register_identity(self):
        rows, report = parse_weekly_calendar(
            CUELLAR_WEEK, date(2026, 11, 1), "Cuéllar", "official-pdf", REGISTRY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "jcyl-40-e1-00093")
        self.assertEqual(rows[0]["direccion"], "Carretera BAHABON 9")
        self.assertEqual(rows[0]["telefono"], "921144794")
        self.assertEqual(rows[0]["localidades_atendidas"], ["Cuéllar"])
        self.assertNotIn("guardia_intervalos", rows[0])
        self.assertEqual(report["estado"], "parcial")
        self.assertIn("sin horario publicado", rows[0]["guardia_franja"])

    def test_el_espinar_override_is_recorded_and_locality_preserved(self):
        rows, _ = parse_weekly_calendar(
            ESPINAR_WEEK, date(2026, 11, 2), "El Espinar", "official-pdf", REGISTRY)
        self.assertEqual(rows[0]["id"], "jcyl-40-e1-00096")
        self.assertEqual(rows[0]["direccion"], "Avenida HONTANILLA 18")
        self.assertEqual(rows[0]["localidad"], "El Espinar")
        self.assertIn("indica el número 12", rows[0]["nota_direccion"])
        self.assertIn("publica el número 18", rows[0]["nota_direccion"])
        self.assertIsNone(rows[0]["telefono"])

    def test_calendar_year_boundary_and_erroneous_week(self):
        cuellar = CUELLAR_WEEK.replace(
            "26-oct 27-oct 28-oct 29-oct 30-oct 31-oct 01-nov Ctra. BAHABON",
            "29-dic 30-dic 31-dic 01-ene 02-ene 03-ene 04-ene STA. MARINA",
        )
        rows, _ = parse_weekly_calendar(
            cuellar, date(2026, 1, 4), "Cuéllar", "official-pdf", REGISTRY)
        self.assertEqual(rows[0]["id"], "jcyl-40-e1-00009")
        erroneous = ESPINAR_WEEK.replace(
            "NOV 26-oct 27-oct 28-oct 29-oct 30-oct 31-oct 01-nov SAN RAFAEL",
            "ENE 31-dic 01-ene 01-ene 02-ene 03-ene 04-ene C/ MARQUES PERALES",
        )
        with self.assertRaisesRegex(ValueError, "fechas inconsistentes"):
            parse_weekly_calendar(
                erroneous, date(2026, 1, 1), "El Espinar", "official-pdf", REGISTRY)

    def test_cuellar_special_august_and_september_rows_are_resolved(self):
        special = """
        SERVICIOS DE URGENCIA DE LAS FARMACIAS DEL MUNICIPIO DE CUELLAR PARA EL AÑO 2026
        DOMINGO 30 DE AGOSTO Y LUNES 31 DE AGO                            C/ RESINA
        MARTES 1 Y MIERCOLES 2 de SEPTIEMBRE                              STA. MARINA
        JUEVES 3 Y VIERNES 4 de SEPTIEMBRE                                Av C.J. CELA
        SABADO 5 Y DOMINGO 6 de Septiembre                               Ctra. BAHABON
        """
        expected = {
            date(2026, 8, 30): "jcyl-40-e1-00008",
            date(2026, 9, 1): "jcyl-40-e1-00009",
            date(2026, 9, 3): "jcyl-40-e1-00082",
            date(2026, 9, 5): "jcyl-40-e1-00093",
        }
        for target, identifier in expected.items():
            with self.subTest(target=target):
                rows, _ = parse_weekly_calendar(special, target, "Cuéllar", "official-pdf", REGISTRY)
                self.assertEqual(rows[0]["id"], identifier)

    def test_unmapped_weekly_label_fails_closed(self):
        unknown = CUELLAR_WEEK.replace("Ctra. BAHABON", "Farmacia desconocida")
        with self.assertRaisesRegex(ValueError, "Etiqueta de turno no reconocida"):
            parse_weekly_calendar(
                unknown, date(2026, 11, 1), "Cuéllar", "official-pdf", REGISTRY)


if __name__ == "__main__":
    unittest.main()
