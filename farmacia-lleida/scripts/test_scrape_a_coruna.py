import unittest
from datetime import date, datetime

from scrape_a_coruna import intervals, parse

DAY = date(2026, 11, 4)


def record(**extra):
    return {"codigoSanidad": "C-375-F", "nombre": "Farmacia", "direccion": "Real 1", "nombrePoblacion": "Ferrol",
            "telefono": "981000000", "latitud": None, "longitud": None,
            "nombreGuardiaTipoTurno": "Nocturno", "horario": "00:00 - 21:00", **extra}


class ACorunaTest(unittest.TestCase):
    def test_schedule_with_next_day_and_closed_suffix(self):
        spans = intervals("09:00 - 21:00; 22:00 - 09:30 (día posterior) (Ahora cerrada)", DAY)
        self.assertEqual(spans[1], (datetime(2026, 11, 4, 22), datetime(2026, 11, 5, 9, 30)))
        self.assertEqual(intervals("24 Horas", DAY), [(datetime(2026, 11, 4), datetime(2026, 11, 5))])
        with self.assertRaises(ValueError):
            intervals("Mañanas", DAY)

    def test_parse_clips_to_day_and_requires_requested_date(self):
        data = {"formulario": 'value="04/11/2026"',
                "listadoTodas": [record(horario="22:00 - 09:30 (día posterior)")]}
        row, = parse(data, DAY, [])
        self.assertEqual(row["guardia_intervalos"][0]["fin"], "2026-11-05T00:00:00")
        self.assertEqual(row["guardia_intervalos"][0]["fin_original"], "2026-11-05T09:30:00")
        self.assertIsNone(row["lat"])
        with self.assertRaises(ValueError):
            parse({**data, "formulario": 'value="05/11/2026"'}, DAY, [])


if __name__ == "__main__":
    unittest.main()
