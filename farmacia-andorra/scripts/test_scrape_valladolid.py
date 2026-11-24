from datetime import date
import unittest

from scrape_valladolid import apply_positions, markers, parse_catalogue, parse_schedule


class ValladolidTests(unittest.TestCase):
    def test_map_positions_are_not_map_center(self):
        content = """var markers = [
        {"lat": '41.625',
         "lng": '-4.774',
         "description": 'Nombre<br />Calle Industrias , 19 , Arroyo de la Encomienda<br />tlf. 983408069',
        },
        {"lat": '0',
         "lng": '0',
         "description": 'Nombre<br />Calle Otra , 1 , Valladolid<br />tlf. 983000000'
        }];"""
        points = markers(content)
        self.assertEqual(len(points), 1)
        row = {"direccion": "Calle Industrias, 19", "localidad": "Arroyo de la Encomienda", "lat": None}
        apply_positions([row], points)
        self.assertEqual(row["lat"], 41.625)
        wrong = {"direccion": "Calle Industrias, 20", "localidad": row["localidad"], "lat": None}
        apply_positions([wrong], points)
        self.assertIsNone(wrong["lat"])

    def test_wrong_date_never_published(self):
        with self.assertRaises(ValueError):
            parse_schedule("Fecha: 31/10/2026 " * 3, date(2026, 11, 1))

    def test_three_sections_and_nonpresential_provincial_service(self):
        content = "Fecha: 01/11/2026 " * 3
        for grid in ("PageContent_GridFarmacias", "PageContent_GridFarmaciasDiurnas",
                     "PageContent_GridFarmaciasProvincia"):
            provincial = grid.endswith("Provincia")
            cells = (["Arroyo de la Encomienda", "47195", "Calle Industrias, 19 (Zona: PISUERGA)",
                      '<a href="tel:600000000">Llamar</a>', "2", ""] if provincial
                     else ["Calle Mayor, 2 (Zona: CENTRO)", "", ""])
            content += f'<tr id="{grid}_DXDataRow0">'
            for i, cell in enumerate(cells):
                style = (' style="background-image:url(sol_luna_peq.png);telephone-call.png"'
                         if provincial and i == 4 else "")
                link = (f'<a href="FarmaciaFichaGuardia.aspx?Id={len(cells)}&amp;Base=228"></a>'
                        if i == len(cells) - 1 else "")
                content += f"<td{style}>{cell}{link}</td>"
            content += "</tr>"
        content += 'var markers = [];'
        rows = parse_schedule(content, date(2026, 11, 1))
        self.assertEqual(len(rows), 3)
        self.assertIn("Nocturna", rows[1]["guardia_franjas"][0])
        self.assertIn("24 horas", rows[2]["guardia_franjas"][0])
        self.assertIn("llamar", rows[2]["guardia_franjas"][0])
        self.assertEqual(rows[2]["localidad"], "Arroyo de la Encomienda")

    def test_guard_identifier_not_confused_with_catalogue_identifier(self):
        content = '<tr id="GridFarmacias_DXDataRow0">'
        cells = ["228", "Valladolid", "CENTRO", "Farmacia", "Calle Mayor, 2 47001", "983000000",
                 '<a href="FarmaciaFicha.aspx?Id=228"></a>']
        content += "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>var markers = [];"
        rows = parse_catalogue(content)
        self.assertEqual(rows[0]["id"], "cof-valladolid-catalogo-228")
        self.assertEqual(rows[0]["direccion"], "Calle Mayor, 2")
