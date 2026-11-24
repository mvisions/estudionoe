from datetime import date
import unittest

from scrape_murcia import catalogue, parse_calendar, utm_coordinates


class MurciaTests(unittest.TestCase):
    def setUp(self):
        self.row = {"id": "cof-murcia-1", "cofrm_id": 1, "nombre": "Titular",
                    "localidad": "Beniel", "provincia": "Murcia"}

    def test_official_utm_zone30_coordinate(self):
        lat, lng = utm_coordinates(694424.97, 4189858.17)
        self.assertAlmostEqual(lat, 37.835, delta=0.01)
        self.assertAlmostEqual(lng, -0.790, delta=0.01)
        for x, y in [(0, 0), (True, 4189858), (float("nan"), 4189858), (500000, 5000000)]:
            with self.assertRaises(ValueError):
                utm_coordinates(x, y)

    def test_only_explicit_duty_not_opening_hours(self):
        event = {"title": "Shift 1", "start": "2026-11-01T00:00", "end": "2026-11-02T00:00"}
        self.assertEqual(parse_calendar([event], self.row, date(2026, 11, 1)), [])
        event["title"] = "On-Call - Titular"
        rows = parse_calendar([event], self.row, date(2026, 11, 1))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["guardia"])
        event["title"] = "On-Call - Titular (Weekend)"
        closed = {"title": "CLOSED: Festivo", "start": "2026-04-17T00:00", "end": "2026-04-17T00:00"}
        rows = parse_calendar([closed, event], self.row, date(2026, 11, 1))
        self.assertEqual(len(rows), 1)
        event["title"] = "On-Call - Titular  (Weekend)"
        self.assertEqual(len(parse_calendar([event], {**self.row, "nombre": "Titular "},
                                           date(2026, 11, 1))), 1)

    def test_previous_dawn_exact_intersection(self):
        events = [{"title": "On-Call - Titular", "start": "2026-10-31T21:30", "end": "2026-11-01T09:30"}]
        rows = parse_calendar(events, self.row, date(2026, 11, 1))
        self.assertEqual(rows[0]["guardia_intervalos"],
                         [{"inicio": "2026-11-01T00:00:00+01:00", "fin": "2026-11-01T09:30:00+01:00"}])
        events[0]["end"] = "2026-11-01T00:00"
        self.assertEqual(parse_calendar(events, self.row, date(2026, 11, 1)), [])

    def test_wrong_year_identity_and_inverted_interval_rejected(self):
        with self.assertRaisesRegex(ValueError, "año"):
            parse_calendar([{"title": "On-Call - Titular", "start": "2025-11-01T09:30",
                             "end": "2025-11-02T09:30"}], self.row, date(2026, 11, 1))
        with self.assertRaisesRegex(ValueError, "titular"):
            parse_calendar([{"title": "On-Call - Otro", "start": "2026-11-01T09:30",
                             "end": "2026-11-02T09:30"}], self.row, date(2026, 11, 1))
        with self.assertRaisesRegex(ValueError, "invertido"):
            parse_calendar([{"title": "On-Call - Titular", "start": "2026-11-01T09:30",
                             "end": "2026-11-01T09:30"}], self.row, date(2026, 11, 1))
        with self.assertRaises(ValueError):
            parse_calendar([], self.row, date(2026, 11, 1))

    def test_all_municipalities_required_catalogue_not_duty_flags(self):
        towns = [{"name": f"{i} - Pueblo {i}", "locationType": "MUNICIPALITY"} for i in range(45)]
        data = [{"id": i, "address": "Calle Mayor 1", "town": f"Pueblo {i}",
                 "municipality": towns[i]["name"], "coordinateX": 694424.97,
                 "coordinateY": 4189858.17, "isOnCallRotation": True} for i in range(45)]
        rows = catalogue(data, towns)
        self.assertEqual(len(rows), 45)
        self.assertTrue(all(row["guardia"] is False for row in rows))
        with self.assertRaises(ValueError):
            catalogue(data[:-1], towns)
        with self.assertRaises(ValueError):
            catalogue(data, towns[:-1])


if __name__ == "__main__":
    unittest.main()
