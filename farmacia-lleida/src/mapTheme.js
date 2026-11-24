const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
// Attribution required by the IGN WMTS services (AccessConstraints: «CC BY 4.0 scne.es»).
const IGN_CREDIT = 'Ortofoto PNOA y rótulos CC BY 4.0 <a href="https://www.scne.es/">scne.es</a>';
const IGN_MAP_CREDIT = 'Cartografía CC BY 4.0 <a href="https://www.scne.es/">scne.es</a>';

function ignTiles(service, layer, format) {
  return `https://www.ign.es/wmts/${service}?request=GetTile&service=WMTS&VERSION=1.0.0` +
    `&Layer=${layer}&Style=default&Format=${format}&TileMatrixSet=GoogleMapsCompatible` +
    '&TileMatrix={z}&TileRow={y}&TileCol={x}';
}

export function getBaseLayers(mode) {
  if (mode !== 'satellite') {
    return [
      { key: 'osm', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: OSM_CREDIT },
      {
        key: 'ign-overview',
        url: ignTiles('ign-base', 'IGNBaseTodo', 'image/png'),
        attribution: IGN_MAP_CREDIT,
        bounds: [[27, -19], [44, 5]],
        maxZoom: 6,
        zIndex: 2,
      },
    ];
  }
  return [
    { key: 'pnoa', url: ignTiles('pnoa-ma', 'OI.OrthoimageCoverage', 'image/jpeg'), attribution: `${IGN_CREDIT} · ${OSM_CREDIT}` },
    // Label tiles only exist inside this extent; outside it the service answers 400.
    { key: 'ign-rotulos', url: ignTiles('ign-base', 'IGNBaseOrto', 'image/png'), attribution: '', zIndex: 2, bounds: [[27, -19], [44, 5]] },
  ];
}

export function getPointStyle(night, duty, nightDuty = false) {
  const dutyFill = nightDuty ? (night ? '#a47fd0' : '#8a3ab9') : (night ? '#559b73' : '#238851');
  // Small night crosses need a violet border; a red one makes them read as red.
  const dutyBorder = nightDuty ? (night ? '#e3c6ff' : '#4b1569') : (night ? '#ff5555' : '#e12626');
  return {
    color: duty ? dutyBorder : (night ? '#48677b' : '#23679d'),
    weight: 1,
    fillColor: duty ? dutyFill : (night ? '#527d99' : '#3284c7'),
    fillOpacity: night ? 0.85 : 1,
  };
}

export function isNightAt(date, latitude, longitude) {
  if (!(date instanceof Date) || !Number.isFinite(date.getTime()) ||
      !Number.isFinite(latitude) || Math.abs(latitude) > 90 ||
      !Number.isFinite(longitude) || Math.abs(longitude) > 180) {
    throw new RangeError('Fecha o posición no válida para calcular la luz solar.');
  }
  const year = date.getUTCFullYear();
  const day = (Date.UTC(year, date.getUTCMonth(), date.getUTCDate()) - Date.UTC(year, 0, 1)) / 86400000;
  const daysInYear = (Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)) / 86400000;
  const minutes = date.getUTCHours() * 60 + date.getUTCMinutes() + date.getUTCSeconds() / 60;
  const angle = 2 * Math.PI / daysInYear * (day + (minutes / 60 - 12) / 24);
  const equation = 229.18 * (0.000075 + 0.001868 * Math.cos(angle) -
    0.032077 * Math.sin(angle) - 0.014615 * Math.cos(2 * angle) - 0.040849 * Math.sin(2 * angle));
  const declination = 0.006918 - 0.399912 * Math.cos(angle) + 0.070257 * Math.sin(angle) -
    0.006758 * Math.cos(2 * angle) + 0.000907 * Math.sin(2 * angle) -
    0.002697 * Math.cos(3 * angle) + 0.00148 * Math.sin(3 * angle);
  const solarMinutes = ((minutes + equation + 4 * longitude) % 1440 + 1440) % 1440;
  const hourAngle = (solarMinutes / 4 - 180) * Math.PI / 180;
  const lat = latitude * Math.PI / 180;
  const altitude = Math.asin(Math.sin(lat) * Math.sin(declination) +
    Math.cos(lat) * Math.cos(declination) * Math.cos(hourAngle)) * 180 / Math.PI;
  // Sunrise/sunset uses the standard apparent horizon including refraction.
  return altitude < -0.833;
}
