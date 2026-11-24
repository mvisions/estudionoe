import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from complete_malaga import address_key, enrich_calendar, geocode, match_saved_osm, normalize_street


def response(items):
    return io.StringIO(json.dumps(items))


class GeocodingTests(unittest.TestCase):
    def test_enrichment_does_not_erase_existing_calendar_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/"guardias-malaga-2026-11-01.json"
            path.write_text(json.dumps([{"cofm_id":"1","lat":36.7,"lng":-4.4}]))
            with patch("complete_malaga.OUT_DIR",root):
                enrich_calendar("2026-11-01",{"1":{"lat":None,"lng":None}})
            self.assertEqual(json.loads(path.read_text())[0]["lat"],36.7)

    def test_number_abbreviations_and_corner_aliases(self):
        self.assertEqual(normalize_street("PLAZA LA CONSTITUCIÓN NÚM. 2"), "PLAZA LA CONSTITUCIÓN 2")
        self.assertEqual(normalize_street("ESQUINA C/ ANTONIO FERRANDIS NUM. 1"), "Calle ANTONIO FERRANDIS 1")
        self.assertEqual(normalize_street("C/ NÚÑEZ NUM. 3"), "Calle NÚÑEZ 3")

    def test_saved_address_key_preserves_municipality_and_number(self):
        self.assertEqual(address_key("PLAZA DE SANTA MARIA NUM. 9", "Coín"),
                         address_key("Plaza de Santa María 9", "Coin"))
        self.assertNotEqual(address_key("Plaza Santa María 9", "Coin"),
                            address_key("Plaza Santa María 8", "Coin"))
        self.assertNotEqual(address_key("Plaza Santa María 9", "Coin"),
                            address_key("Plaza Santa María 9", "Nerja"))
        self.assertIsNone(address_key("Plaza Santa María", "Coin"))

    def test_saved_osm_only_matches_unambiguous_exact_address(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            osm = {"id": "osm-1", "direccion": "Plaza Santa María 9", "localidad": "Coín",
                   "lat": 36.660627, "lng": -4.7591665}
            source = root / "farmacias-osm-espana.json"
            source.write_text(json.dumps([osm]))
            entry = {"direccion": "PLAZA DE SANTA MARIA NUM. 9", "localidad": "Coin", "lat": None, "lng": None}
            with patch("complete_malaga.OUT_DIR", root):
                match_saved_osm({"1": entry})
                self.assertEqual(entry["lat"], osm["lat"])
                source.write_text(json.dumps([osm, {**osm, "id": "osm-2"}]))
                pending = {**entry, "lat": None, "lng": None}
                match_saved_osm({"1": pending})
                self.assertIsNone(pending["lat"])

    @patch("complete_malaga.urllib.request.urlopen")
    def test_exact_pharmacy_preferred_over_house_on_same_street(self, open_url):
        open_url.return_value = response([
            {"lat": "36.745", "lon": "-3.883", "type": "house",
             "address": {"town": "Nerja", "house_number": "1"}},
            {"lat": "36.747", "lon": "-3.880", "type": "pharmacy",
             "address": {"town": "Nerja", "house_number": "1"}},
        ])
        result = geocode("C/ ANTONIO FERRANDIS NUM. 1", "Nerja")
        self.assertEqual(result["precision_ubicacion"], "farmacia")
        self.assertEqual(result["lat"], 36.747)

    @patch("complete_malaga.time.sleep")
    @patch("complete_malaga.urllib.request.urlopen")
    def test_wrong_locality_is_rejected_even_inside_province(self, open_url, _sleep):
        open_url.side_effect = lambda *_args, **_kwargs: response([{
            "lat": "36.8", "lon": "-4.7", "type": "pharmacy",
            "address": {"town": "Pizarra", "house_number": "3"},
        }])
        self.assertIsNone(geocode("Carreteros, 3", "Antequera"))

    @patch("complete_malaga.time.sleep")
    @patch("complete_malaga.urllib.request.urlopen")
    def test_old_street_alias_is_used_and_exact_point_identified(self, open_url, _sleep):
        open_url.side_effect = [
            response([]),
            response([{
                "lat": "37.02", "lon": "-4.56", "type": "pharmacy",
                "address": {"town": "Antequera", "house_number": "3"},
            }]),
        ]
        result = geocode("OVELAR Y CID, 3 (carreteros 3)", "Antequera")
        self.assertEqual(result["precision_ubicacion"], "farmacia")
        self.assertIn("carreteros", open_url.call_args.args[0].full_url)

    @patch("complete_malaga.time.sleep")
    @patch("complete_malaga.urllib.request.urlopen")
    def test_street_not_claimed_as_exact_pharmacy(self, open_url, _sleep):
        open_url.side_effect = lambda *_args, **_kwargs: response([{
            "lat": "36.83", "lon": "-4.7", "type": "residential",
            "address": {"town": "Álora"},
        }])
        self.assertEqual(geocode("Veracruz, 8", "Alora")["precision_ubicacion"], "aproximada")

    @patch("complete_malaga.time.sleep")
    @patch("complete_malaga.urllib.request.urlopen")
    def test_town_center_is_not_accepted_as_pharmacy(self, open_url, _sleep):
        open_url.side_effect = lambda *_args, **_kwargs: response([{
            "lat": "36.83", "lon": "-4.7", "type": "administrative",
            "address": {"town": "Álora"},
        }])
        self.assertIsNone(geocode("Veracruz, 8", "Alora"))


if __name__ == "__main__":
    unittest.main()
