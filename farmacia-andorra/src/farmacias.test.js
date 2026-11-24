import assert from 'node:assert/strict';
import test from 'node:test';
import { getCoordinates, getDirectionsUrl, getMapMarkerSizes, INDIVIDUAL_PHARMACY_ZOOM, matchesProvince, mergePharmacies, pharmacyKey, selectCoordinates } from './farmacias.js';

test('directions target exact pharmacy coordinates and use available user location', () => {
  const url = new URL(getDirectionsUrl([37.98, -1.21], [37.99, -1.1]));
  assert.equal(url.origin + url.pathname, 'https://www.google.com/maps/dir/');
  assert.equal(url.searchParams.get('api'), '1');
  assert.equal(url.searchParams.get('destination'), '37.98,-1.21');
  assert.equal(url.searchParams.get('origin'), '37.99,-1.1');
  assert.equal(new URL(getDirectionsUrl([37.98, -1.21])).searchParams.has('origin'), false);
  for (const position of [null, [], [null, null], [0, 0], [91, 0], ['bad', 1]]) {
    assert.throws(() => getDirectionsUrl(position), RangeError);
  }
  assert.throws(() => getDirectionsUrl([37.98, -1.21], [null, null]), RangeError);
});

test('official duty referrals remain visible without relabelling their actual province', () => {
  const pharmacy = { provincia: 'León', provincias_atendidas: ['Palencia'], guardia: true };
  assert.equal(matchesProvince(pharmacy, 'Palencia'), true);
  assert.equal(matchesProvince(pharmacy, 'leon'), true);
  assert.equal(matchesProvince(pharmacy, 'Burgos'), false);
  assert.equal(matchesProvince({ ...pharmacy, guardia: false }, 'Palencia'), false);
  assert.equal(matchesProvince({ provincia: 'Palencia' }, 'PALENCIA'), true);
  assert.equal(matchesProvince({ provincia: 'León', guardia: true }, 'Palencia'), false);
  assert.equal(matchesProvince({ provincia: 'León' }, 'Palencia'), false);
});

test('markers grow with zoom, remain small in distant views and stop growing up close', () => {
  assert.deepEqual(getMapMarkerSizes(6), { normal: 4, duty: 4, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(10), { normal: 7, duty: 9, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(14), { normal: 9, duty: 11, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(2), getMapMarkerSizes(6));
  assert.deepEqual(getMapMarkerSizes(17), getMapMarkerSizes(14));
  for (let zoom = 6; zoom < 14; zoom += 1) {
    const current = getMapMarkerSizes(zoom);
    const next = getMapMarkerSizes(zoom + 1);
    assert.ok(next.duty >= current.duty);
    assert.equal(current.duty - current.normal, zoom >= INDIVIDUAL_PHARMACY_ZOOM ? 2 : 0);
  }
});

test('only maximum zoom doubles both circles and follows the actual map limit', () => {
  assert.deepEqual(getMapMarkerSizes(18), { normal: 18, duty: 22, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(18, 19), { normal: 9, duty: 11, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(19, 19), { normal: 18, duty: 22, dutyBorder: 1 });
  assert.deepEqual(getMapMarkerSizes(17, 18), getMapMarkerSizes(14));
});

test('missing, blank, boolean and invalid coordinates never become markers', () => {
  for (const value of [null, undefined, '', ' ', false]) {
    assert.equal(getCoordinates({ lat: value, lng: -4.5 }), null);
    assert.equal(getCoordinates({ lat: 36.7, lng: value }), null);
  }
  assert.equal(getCoordinates({ lat: 0, lng: 0 }), null);
  assert.equal(getCoordinates({ lat: NaN, lng: -4.5 }), null);
  assert.equal(getCoordinates({ lat: 91, lng: -4.5 }), null);
  assert.equal(getCoordinates({ lat: 43, lng: 181 }), null);
  assert.deepEqual(getCoordinates({ lat: '36.7', lng: '-4.5' }), [36.7, -4.5]);
});

test('northern and foreign pharmacies are not blocked by country or latitude', () => {
  for (const position of [[43.36, -8.41], [43.26, -2.93], [43.3, -1.99],
    [48.86, 2.35], [51.51, -0.12], [0, 30]]) {
    assert.deepEqual(getCoordinates({ lat: position[0], lng: position[1] }), position);
  }
});

test('locations awaiting verification cannot fall back to older catalogue coordinates', () => {
  const previous = { id: 'granada-test', lat: 37.18, lng: -3.60 };
  const pending = { id: 'granada-test', lat: null, lng: null, ubicacion_pendiente_verificacion: true };
  assert.equal(selectCoordinates(pending, previous), null);
  assert.equal(getCoordinates({ ...previous, ubicacion_pendiente_verificacion: true }), null);
  const [result] = mergePharmacies([previous], [pending]);
  assert.equal(getCoordinates(result), null);
  assert.deepEqual(selectCoordinates({ ...pending, ubicacion_pendiente_verificacion: false }, previous), [37.18, -3.60]);
});

test('new schedule pharmacies and new coordinates are included without old catalogue IDs', () => {
  const catalog = [
    { cofm_id: '1', provincia: 'Málaga', lat: 36.7, lng: -4.5, guardia: true },
    { cofm_id: '3', provincia: 'Málaga', lat: 36.7, lng: -4.5, guardia: true },
  ];
  const schedules = [
    { cofm_id: '1', provincia: 'Malaga', lat: null, lng: null, guardia_franja: 'noche' },
    { cofm_id: '2', provincia: 'Málaga', localidad: 'Antequera', lat: 37.02, lng: -4.56 },
  ];
  const result = mergePharmacies(catalog, schedules);
  assert.equal(result.length, 3);
  assert.equal(result.filter((item) => item.guardia).length, 2);
  assert.equal(result.find((item) => item.cofm_id === '1').guardia_franja, 'noche');
  assert.deepEqual(getCoordinates(result.find((item) => item.cofm_id === '1')), [36.7, -4.5]);
  assert.equal(result.find((item) => item.cofm_id === '2').localidad, 'Antequera');
});

test('source identifiers do not collide between provinces or null cofm IDs', () => {
  assert.notEqual(pharmacyKey({ cofm_id: '1', provincia: 'Málaga' }), pharmacyKey({ cofm_id: '1', provincia: 'Madrid' }));
  assert.equal(pharmacyKey({ cofm_id: null, id: 'osm-1' }), 'osm-1');
});

test('catalogue rows never carry shift data from another day', () => {
  const tomorrow = {
    id: 'andorra-test', lat: 42.5, lng: 1.53, guardia: false, fecha_guardia: '2026-11-04',
    guardia_desde_ayer: true, guardia_apertura: 'desconocida', guardia_localizada: true,
    guardia_franja: 'madrugada', guardia_franjas: ['madrugada'],
    guardia_intervalos: [{ inicio: '2026-11-04T00:00:00', fin: '2026-11-04T09:30:00' }],
  };
  const today = { id: 'andorra-test', fecha_guardia: '2026-11-03', guardia_franja: 'día y noche',
    guardia_intervalos: [{ inicio: '2026-11-03T09:30:00', fin: '2026-11-04T00:00:00' }] };
  const [onDuty] = mergePharmacies([tomorrow], [today]);
  assert.equal(onDuty.guardia, true);
  assert.equal(onDuty.fecha_guardia, '2026-11-03');
  assert.equal(onDuty.guardia_franja, 'día y noche');
  assert.deepEqual(onDuty.guardia_intervalos, today.guardia_intervalos);
  for (const field of ['guardia_desde_ayer', 'guardia_apertura', 'guardia_localizada', 'guardia_franjas']) {
    assert.equal(field in onDuty, false, field);
  }
  const [offDuty] = mergePharmacies([tomorrow], []);
  assert.deepEqual(Object.keys(offDuty).filter((key) => key.startsWith('guardia') || key === 'fecha_guardia'),
    ['guardia', 'guardia_franja']);
  assert.deepEqual(getCoordinates(offDuty), [42.5, 1.53]);
});
