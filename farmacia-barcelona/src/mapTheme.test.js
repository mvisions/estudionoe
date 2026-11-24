import assert from 'node:assert/strict';
import test from 'node:test';
import { getBaseLayers, getPointStyle, isNightAt } from './mapTheme.js';

test('pharmacy crosses are blue and duty crosses green with red borders in both themes', () => {
  assert.deepEqual(getPointStyle(false, false), {
    color: '#23679d', weight: 1, fillColor: '#3284c7', fillOpacity: 1,
  });
  assert.equal(getPointStyle(false, true).fillColor, '#238851');
  assert.equal(getPointStyle(false, true).color, '#e12626');
  assert.equal(getPointStyle(true, true).fillColor, '#559b73');
  assert.equal(getPointStyle(true, true).color, '#ff5555');
  for (const duty of [false, true]) {
    const style = getPointStyle(true, duty);
    assert.notEqual(style.color, '#fff');
    assert.equal(style.fillOpacity, 0.85);
    assert.equal(style.weight, 1);
  }
  assert.notEqual(getPointStyle(true, true).fillColor, getPointStyle(true, false).fillColor);
});

test('overview uses official IGN tiles for Spain while preserving the OSM base', () => {
  for (const mode of ['auto', 'day', 'night']) {
    const [osm, overview] = getBaseLayers(mode);
    assert.equal(osm.key, 'osm');
    assert.equal(overview.key, 'ign-overview');
    assert.match(overview.url, /Layer=IGNBaseTodo.*TileMatrix=\{z\}&TileRow=\{y\}&TileCol=\{x\}$/);
    assert.equal(overview.maxZoom, 6);
    assert.ok(overview.zIndex > (osm.zIndex ?? 1));
    const [[south, west], [north, east]] = overview.bounds;
    assert.ok(south < 27.6 && west < -18.1 && north > 43.8 && east > 4.4);
    assert.match(overview.attribution, /CC BY 4\.0.*scne\.es/);
  }
});

test('satellite view uses IGN PNOA imagery with labels and keeps the required credits', () => {
  const [imagery, labels] = getBaseLayers('satellite');
  assert.match(imagery.url, /^https:\/\/www\.ign\.es\/wmts\/pnoa-ma\?.*Layer=OI\.OrthoimageCoverage/);
  assert.match(labels.url, /^https:\/\/www\.ign\.es\/wmts\/ign-base\?.*Layer=IGNBaseOrto.*Format=image\/png/);
  for (const url of [imagery.url, labels.url]) {
    assert.match(url, /TileMatrix=\{z\}&TileRow=\{y\}&TileCol=\{x\}$/);
  }
  assert.match(imagery.attribution, /CC BY 4\.0 <a href="https:\/\/www\.scne\.es\/">scne\.es<\/a>/);
  assert.match(imagery.attribution, /OpenStreetMap/);
  assert.ok(labels.zIndex > (imagery.zIndex ?? 1));
  const [[south, west], [north, east]] = labels.bounds;
  assert.ok(south < 27.6 && west < -18.1 && north > 43.8 && east > 4.4, 'labels cover Canarias, Baleares and the north coast');
});

test('night and 24 h duty crosses are purple, including their border', () => {
  assert.equal(getPointStyle(false, true, true).fillColor, '#8a3ab9');
  assert.equal(getPointStyle(true, true, true).fillColor, '#a47fd0');
  assert.equal(getPointStyle(false, true, true).color, '#4b1569');
  assert.equal(getPointStyle(true, true, true).color, '#e3c6ff');
  for (const night of [false, true]) {
    assert.notEqual(getPointStyle(night, true, true).color, getPointStyle(night, true).color);
    assert.notEqual(getPointStyle(night, true, true).fillColor, getPointStyle(night, true).fillColor);
    assert.deepEqual(getPointStyle(night, false, true), getPointStyle(night, false));
  }
});

test('Andalucía is dark before sunrise and light during the real current day', () => {
  assert.equal(isNightAt(new Date('2026-11-01T05:30:00Z'), 36.72, -4.42), true);
  assert.equal(isNightAt(new Date('2026-11-01T12:00:00Z'), 36.72, -4.42), false);
  assert.equal(isNightAt(new Date('2026-11-01T20:00:00Z'), 36.72, -4.42), true);
});

test('sunrise is seasonal rather than a fixed 08:00 schedule', () => {
  assert.equal(isNightAt(new Date('2026-06-21T05:30:00Z'), 36.72, -4.42), false);
  assert.equal(isNightAt(new Date('2026-12-21T05:30:00Z'), 36.72, -4.42), true);
});

test('the same instant follows map longitude, not computer timezone', () => {
  const now = new Date('2026-03-20T12:00:00Z');
  assert.equal(isNightAt(now, 0, 0), false);
  assert.equal(isNightAt(now, 0, 180), true);
});

test('polar day and polar night do not need a missing sunrise fallback', () => {
  assert.equal(isNightAt(new Date('2026-06-21T00:00:00Z'), 89, 0), false);
  assert.equal(isNightAt(new Date('2026-12-21T12:00:00Z'), 89, 0), true);
});

test('invalid solar inputs fail explicitly', () => {
  assert.throws(() => isNightAt(new Date('invalid'), 36, -4), RangeError);
  assert.throws(() => isNightAt(new Date(), 91, -4), RangeError);
});
