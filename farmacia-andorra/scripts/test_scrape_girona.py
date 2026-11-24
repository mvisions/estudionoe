from datetime import date
import json

import pytest

from proximidad import PharmacyIndex
from scrape_girona import DETAIL, SOURCE, locate, parse, run


TARGET = date(2026, 11, 2)


def page(schedule="09:00 - 09:00 (dia seg.)", indicator=True, title="02/11/2026"):
    icon = '<img alt="Guàrdia no presencial. Per ser atès cal trucar al telèfon indicat.">' if indicator else ""
    return f"""
    <div class="pharmacies-of-guard-title">TOTES LES FARMÀCIES DE GUÀRDIA DEL DIA {title}</div>
    <table><tr class="pharmacy-detail" href="/farmacies/detall-guardia/123">
    <td>Farmacia A</td><td>GIRONA</td><td>{schedule}
    <td>{icon}</td><td>Carrer A 1</td><td>972111111</td><td></td></tr></table>
    """


def test_missing_closing_cell_and_located_duty():
    row = parse(page(), TARGET)[0]
    assert row["guardia_franja"] == "09:00 - 09:00 (día siguiente); guardia no presencial, llamar antes"
    assert row["ubicacion_pendiente_verificacion"] is True
    assert row["fecha_guardia"] == "2026-11-02"


def test_multiple_daytime_intervals():
    row = parse(page("09:00 - 14:00 16:00 - 21:00", False), TARGET)[0]
    assert row["guardia_franjas"] == ["09:00 - 14:00", "16:00 - 21:00"]


@pytest.mark.parametrize("html", [
    page(title="03/11/2026"),
    page("09:00 - 09:00"),
    page("09:00 - 21:00 (dia seg.)"),
    page("horario desconocido"),
    page().replace('alt="Guàrdia no presencial.', 'alt="Indicador distinto.'),
])
def test_rejects_unconfirmed_date_or_ambiguous_schedule(html):
    with pytest.raises(ValueError):
        parse(html, TARGET)


def test_marker_requires_identified_osm_pharmacy_within_15_metres():
    row = parse(page(), TARGET)[0]
    ref = {"id": "osm-77", "provincia": "Girona", "telefono": "972111111",
           "direccion": "Carrer A 1", "localidad": "GIRONA", "lat": 42.0, "lng": 2.8}
    marker = "position: new google.maps.LatLng('42.00001', '2.8'), id: 123,"
    locate(row, marker, PharmacyIndex([ref]))
    assert row["ubicacion_pendiente_verificacion"] is False
    assert row["ajuste_ubicacion_m"] <= 15
    far = parse(page(), TARGET)[0]
    locate(far, marker, PharmacyIndex([{**ref, "lat": 42.001}]))
    assert far["ubicacion_pendiente_verificacion"] is True
    with pytest.raises(ValueError):
        locate(far, marker.replace("id: 123", "id: 124"), PharmacyIndex([ref]))


def test_run_publishes_partial_coverage_and_preserves_telephone_warning(tmp_path, monkeypatch):
    ref = {"id": "osm-77", "provincia": "Girona", "telefono": "972111111",
           "direccion": "Carrer A 1", "localidad": "GIRONA", "lat": 42.0, "lng": 2.8}
    (tmp_path / "farmacias-espana-hoy.json").write_text(json.dumps([ref]))
    marker = "position: new google.maps.LatLng('42.00001', '2.8'), id: 123,"
    monkeypatch.setattr("scrape_girona.request", lambda url, data=None: page() if url == SOURCE else marker)
    monkeypatch.setattr("scrape_girona.time.sleep", lambda _: None)
    assert run(TARGET, tmp_path) is False
    coverage = json.loads((tmp_path / "cobertura-girona-2026-11-02.json").read_text())
    duty = json.loads((tmp_path / "guardias-girona-2026-11-02.json").read_text())[0]
    assert coverage["completa"] is False
    assert coverage["farmacias_confirmadas"] == 1
    assert duty["fuentes"] == [SOURCE, DETAIL + "123"]
    assert "llamar antes" in duty["guardia_franja"]
    assert duty["ubicacion_pendiente_verificacion"] is False


def test_invalid_response_does_not_replace_existing_calendar(tmp_path, monkeypatch):
    path = tmp_path / "guardias-girona-2026-11-02.json"
    path.write_text("previous")
    monkeypatch.setattr("scrape_girona.request", lambda url, data=None: page(title="03/11/2026"))
    with pytest.raises(ValueError):
        run(TARGET, tmp_path)
    assert path.read_text() == "previous"
