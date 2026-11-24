from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from provincial_catalog import geocode_exact, publish
from scrape_huelva import document_links, match_official_locations, parse_capital, parse_grid, parse_locator, pharmacy, selectors


DAY = date(2026,11,1)


class HuelvaTests(unittest.TestCase):
    def test_official_abbreviations_match_but_other_house_numbers_do_not(self):
        rows=[{"direccion":"Calle Nueva 78","localidad":"Alosno","lat":None,"lng":None},
              {"direccion":"Plaza España 1","localidad":"Trigueros","lat":None,"lng":None},
              {"direccion":"Av.Andalucía, 1","localidad":"Valverde del Camino","lat":None,"lng":None}]
        points=[{"direccion":"CL NUEVA 78","localidad":"Alosno","lat":37.55,"lng":-7.11,
                 "nombre":"Farmacia","fuente_coordenadas":"official"},
                {"direccion":"PL ESPAÑA 2","localidad":"Trigueros","lat":37.38,"lng":-6.83,
                 "nombre":"Otra","fuente_coordenadas":"official"},
                {"direccion":"Avenida ANDALUCÍA 1","localidad":"Valverde del Camino","lat":37.57,"lng":-6.75,
                 "nombre":"Farmacia","fuente_coordenadas":"official"}]
        match_official_locations(rows,points)
        self.assertEqual(rows[0]["lat"],37.55)
        self.assertIsNone(rows[1]["lat"])
        self.assertEqual(rows[2]["lat"],37.57)

    def test_named_site_match_is_exact_and_ambiguous_sites_remain_pending(self):
        row={"direccion":"Urbanización Valdemorales S/N","localidad":"Mazagón","lat":None,"lng":None}
        point={"direccion":"Urbanizacion VALDEMORALES S N","localidad":"Mazagón","lat":37.12,"lng":-6.83,
               "nombre":"Farmacia","fuente_coordenadas":"official"}
        match_official_locations([row],[point])
        self.assertEqual(row["lat"],37.12)
        ambiguous={**row,"lat":None,"lng":None}
        match_official_locations([ambiguous],[point,{**point,"lat":37.13}])
        self.assertIsNone(ambiguous["lat"])

    def test_official_named_center_intersection_and_town_abbreviation(self):
        pairs=[
            ("Avd. Islantilla s/n C.C. Islantilla", "Avenida ISLANTILLA C.C. ISLANTILLA", "Islantilla", "Islantilla"),
            ("Avenida Gibraleón, esquina c/ Clavel", "Avenida GIBRALEÓN, ESQUINA C CLAVEL", "Cartaya", "Cartaya"),
            ("c/ Mesones, 42", "Calle MESONES 42", "Vva. De Los Castillejos", "Villanueva De Los Castillejos"),
        ]
        for address, official, city, official_city in pairs:
            with self.subTest(address=address):
                row={"direccion":address,"localidad":city,"lat":None,"lng":None}
                point={"direccion":official,"localidad":official_city,"lat":37.2,"lng":-7.1,
                       "nombre":"Farmacia","fuente_coordenadas":"official"}
                match_official_locations([row],[point])
                self.assertEqual(row["lat"],37.2)
                self.assertEqual(row["precision_ubicacion"],"farmacia")
                wrong_town={**row,"localidad":"Otro municipio","lat":None,"lng":None}
                match_official_locations([wrong_town],[point])
                self.assertIsNone(wrong_town["lat"])

    def test_official_locator_extracts_pharmacy_identity_and_position(self):
        content="""const Pharmacies = [
        {position: { lat: 37.8893, lng: -6.55925 },
         title: '<h4>FERNÁNDEZ MERA</h4><p>Calle EL EJIDO 4, Aracena, Huelva</p>',},
        ];"""
        points=parse_locator(content)
        self.assertEqual(len(points),1)
        self.assertEqual(points[0]["localidad"],"Aracena")
        self.assertEqual(points[0]["lat"],37.8893)
        self.assertEqual(points[0]["precision_ubicacion"],"farmacia")
        with self.assertRaises(ValueError):
            parse_locator("Sin localizador")

    def test_lepe_special_sunday_does_not_inherit_huelva_or_next_sunday_duty(self):
        page={"width":800,"lines":[
            {"x":200,"y":80,"text":"DIURNO (9:30 A 22:00)"},
            {"x":100,"y":100,"text":"DE LUNES A VIERNES"},
            {"x":500,"y":100,"text":"SÁBADOS"},
            {"x":100,"y":300,"text":"FESTIVOS (02/11/2026)"},
            {"x":500,"y":300,"text":"DOMINGOS"},
            {"x":500,"y":350,"text":"Farmacia Esperanza (C/ Alcalde César Barrios, 2)"},
            {"x":500,"y":380,"text":"Farmacia Tomás (C/ Alcalde César Barrios, 114) (08/11/2026)"},
            {"x":200,"y":450,"text":"FARMACIAS 24H"},
            {"x":200,"y":500,"text":"Farmacia José (Avda. Andalucía, 55)"},
        ]}
        rows=parse_capital(page,DAY,"source","Lepe")
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row["localidad"]=="Lepe" for row in rows))
        self.assertNotIn("114"," ".join(row["direccion"] for row in rows))

    def test_selector_and_month_year_filter(self):
        self.assertEqual(selectors('<select name="guardia"><option value="7">Aracena</option></select>'),
                         [{"codigo":"7","nombre":"Aracena"}])
        links = '<a href="https://cofhuelva.org/template/modules/cuadro-de-guardias/downloader.php?file=1&amp;localty=Aracena Noviembre 2026">PDF</a>'
        self.assertEqual(len(document_links(links,DAY)),1)
        self.assertEqual(document_links(links,date(2025,11,1)),[])
        self.assertEqual(document_links(links,date(2026,10,1)),[])

    def page(self, body):
        lines = [{"x":10+i*100,"y":150,"text":str(2+i)} for i in range(7)]
        lines.append({"x":610,"y":100,"text":"1"})
        lines.extend({"x":610,"y":110+i*10,"text":text} for i,text in enumerate(body))
        return {"width":800,"lines":lines}

    def test_cell_multiline_locality_and_actual_serving_town(self):
        rows = parse_grid(self.page(["Farmacia Soto","PL / La Piña s/n","BOLLULLOS PAR DEL","CONDADO"]),
                          DAY,"Bollullos Par del Condado","source")
        self.assertEqual(rows[0]["localidad"],"Bollullos Par Del Condado")
        self.assertEqual(rows[0]["direccion"],"Plaza La Piña s/n")
        self.assertEqual(rows[0]["localidades_atendidas"],["Bollullos Par del Condado"])

    def test_address_and_name_are_not_interchanged(self):
        rows = parse_grid(self.page(["Carmen Fernández","c/ El Ejido, 4","ARACENA"]),DAY,"Aracena","source")
        self.assertEqual(rows[0]["nombre"],"Carmen Fernández")
        self.assertEqual(rows[0]["direccion"],"c/ El Ejido, 4")
        self.assertIsNone(rows[0]["lat"])

    def test_wrong_weekday_and_addressless_cell_are_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_grid(self.page(["Solo nombre"]),DAY,"Aracena","source")
        with self.assertRaises(ValueError):
            parse_grid(self.page(["Carmen","c/ Ejido 4","ARACENA"]),date(2025,11,1),"Aracena","source")

    def test_intersection_can_be_published_without_fake_house_number(self):
        row=pharmacy("Farmacia","AV / Gibraleón, esquina c/ Clavel","Cartaya","El Rompido",
                     "Confirmar horario",DAY,"source")
        self.assertEqual(row["direccion"],"Avenida Gibraleón, esquina c/ Clavel")
        self.assertIsNone(row["lat"])

    def test_partial_update_retains_unconfirmed_not_discontinued_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            path=output/f"guardias-huelva-{DAY}.json"
            path.write_text(json.dumps([
                {"id":"old", "localidad":"Aracena", "guardia_franjas":["Guardia"]},
                {"id":"kept", "localidad":"Otro pueblo", "guardia_franjas":["Guardia"]},
            ]))
            row=pharmacy("Nueva","Calle Ejido 4","Aracena","Aracena","Guardia",DAY,"source")
            self.assertFalse(publish(DAY,"Huelva","source",[row],
                                    [{"nombre":"Aracena","estado":"disponible"},
                                     {"nombre":"Otro pueblo","estado":"error"}],output))
            rows=json.loads(path.read_text())
            self.assertNotIn("old",[r["id"] for r in rows])
            self.assertFalse(next(r for r in rows if r["id"]=="kept")["guardia_reconfirmada"])

    def test_successfully_reparsed_lepe_document_replaces_wrong_capital_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            path=output/f"guardias-huelva-{DAY}.json"
            path.write_text(json.dumps([
                {"id":"wrong", "localidad":"Huelva", "fuente":"lepe-pdf", "guardia_franjas":["Guardia"]},
                {"id":"unavailable", "localidad":"Huelva", "fuente":"other-pdf", "guardia_franjas":["Guardia"]},
            ]))
            row=pharmacy("Nueva","Calle César Barrios 2","Lepe","Lepe","DIURNO",DAY,"lepe-pdf")
            self.assertFalse(publish(DAY,"Huelva","source",[row],
                                    [{"nombre":"Lepe","estado":"parcial"},
                                     {"nombre":"Huelva","estado":"error"}],output,
                                    authoritative_sources={"lepe-pdf"}))
            rows=json.loads(path.read_text())
            self.assertNotIn("wrong",[r["id"] for r in rows])
            self.assertFalse(next(r for r in rows if r["id"]=="unavailable")["guardia_reconfirmada"])
            self.assertEqual(next(r for r in rows if r["id"]==row["id"])["localidad"],"Lepe")

    def test_geocoder_rejects_house_and_wrong_street_even_in_same_town(self):
        import io
        row={"direccion":"Calle Ejido 4","localidad":"Aracena","provincia":"Huelva"}
        candidate={"type":"pharmacy","lat":"37.89","lon":"-6.56","osm_type":"node","osm_id":123,
                   "address":{"town":"Aracena","road":"Calle Ejido","house_number":"4"}}
        with patch("provincial_catalog.urllib.request.urlopen",return_value=io.StringIO(json.dumps([candidate]))):
            self.assertIsNotNone(geocode_exact(row))
        for change in ({"type":"house"},{"address":{**candidate["address"],"road":"Otra Calle"}}):
            with patch("provincial_catalog.urllib.request.urlopen",return_value=io.StringIO(json.dumps([{**candidate,**change}]))):
                self.assertIsNone(geocode_exact(row))

    def test_explicit_exact_address_permission_never_accepts_street_or_wrong_number(self):
        import io
        row={"direccion":"Calle Iglesia 1","localidad":"Adamuz","provincia":"Córdoba"}
        candidate={"type":"house","lat":"38.0267","lon":"-4.5247","osm_type":"node","osm_id":123,
                   "address":{"village":"Adamuz","road":"Calle Iglesia","house_number":"1"}}
        with patch("provincial_catalog.urllib.request.urlopen",return_value=io.StringIO(json.dumps([candidate]))):
            position=geocode_exact(row,allow_address=True)
            self.assertEqual(position["precision_ubicacion"],"direccion")
            self.assertIn("pendiente",position["nota_ubicacion"])
        for change in ({"address":{**candidate["address"],"house_number":"2"}},
                       {"address":{"village":"Adamuz","road":"Calle Iglesia"}},
                       {"address":{**candidate["address"],"village":"Otra"}}):
            with patch("provincial_catalog.urllib.request.urlopen",return_value=io.StringIO(json.dumps([{**candidate,**change}]))):
                self.assertIsNone(geocode_exact(row,allow_address=True))


if __name__ == "__main__":
    unittest.main()
