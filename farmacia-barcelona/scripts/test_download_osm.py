import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import download_osm as downloader


class DownloadOsmTests(unittest.TestCase):
    def test_north_query_does_not_filter_by_country(self):
        query = downloader.query_for("norte")
        self.assertNotIn("ISO3166", query)
        self.assertIn('(42.0,-9.5,44.0,4.5)', query)

    def test_spanish_pharmacy_above_zaragoza_is_accepted(self):
        data = {"elements":[{"type":"node","id":1,"lat":43.36,"lon":-8.41,
                             "tags":{"amenity":"pharmacy","addr:country":"ES"}}]}
        rows = downloader.parse_response(data, "norte")
        self.assertEqual(rows[0]["lat"], 43.36)
        self.assertFalse(rows[0]["guardia"])
        data["elements"][0]["tags"]["addr:country"] = "FR"
        self.assertEqual(len(downloader.parse_response(data, "norte")), 1)

    def test_overpass_timeout_remark_and_empty_results_are_failures(self):
        for data in [{"remark":"runtime error: Query timed out", "elements":[]},
                     {"elements":[]}, {}]:
            with self.assertRaises(ValueError):
                downloader.parse_response(data, "norte")

    def test_failed_region_does_not_erase_previous_northern_or_southern_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"osm.json"
            path.write_text('[{"id":"osm-1","lat":43.0,"lng":-3.0}]')
            before = path.read_bytes()
            with patch.object(downloader, "download", side_effect=RuntimeError("timeout")):
                with self.assertRaises(RuntimeError):
                    downloader.refresh(["norte"], path)
            self.assertEqual(path.read_bytes(), before)

    def test_targeted_north_refresh_preserves_other_regions_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"osm.json"
            old = [{"id":"osm-1","lat":36.7,"lng":-4.5}, {"id":"osm-2","lat":43.0,"lng":-3.0}]
            path.write_text(json.dumps(old))
            north = {"id":"osm-3","lat":43.1,"lng":-3.0}
            with patch.object(downloader, "download", return_value=[north,north]):
                downloader.refresh(["norte"], path)
            rows = json.loads(path.read_text())
            self.assertEqual({r["id"] for r in rows}, {"osm-1","osm-3"})


if __name__ == "__main__":
    unittest.main()
