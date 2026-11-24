export function getCoordinates(pharmacy) {
  if (pharmacy.ubicacion_pendiente_verificacion === true) return null;
  const validValue = (value) => typeof value === 'number' ||
    (typeof value === 'string' && value.trim() !== '');
  if (!validValue(pharmacy.lat) || !validValue(pharmacy.lng)) return null;
  const lat = Number(pharmacy.lat);
  const lng = Number(pharmacy.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng) ||
      lat < -90 || lat > 90 || lng < -180 || lng > 180 ||
      (lat === 0 && lng === 0)) return null;
  return [lat, lng];
}

export function selectCoordinates(pharmacy, previous) {
  if (pharmacy.ubicacion_pendiente_verificacion === true) return null;
  return getCoordinates(pharmacy) || (previous && getCoordinates(previous)) || null;
}

export function pharmacyKey(pharmacy) {
  return pharmacy.cofm_id
    ? `${String(pharmacy.provincia || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()}:${pharmacy.cofm_id}`
    : pharmacy.id;
}

export function getDirectionsUrl(destination, origin = null) {
  const validPosition = (position) => Array.isArray(position) && position.length === 2 &&
    getCoordinates({ lat: position[0], lng: position[1] });
  if (!validPosition(destination) || (origin !== null && !validPosition(origin))) {
    throw new RangeError('Posición no válida para calcular la ruta.');
  }
  const params = new URLSearchParams({ api: '1', destination: destination.join(',') });
  if (origin !== null) params.set('origin', origin.join(','));
  return `https://www.google.com/maps/dir/?${params}`;
}

export function matchesProvince(pharmacy, province) {
  const normalize = (value) => String(value || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  const selected = normalize(province);
  return !selected || normalize(pharmacy.provincia) === selected ||
    (pharmacy.guardia === true && Array.isArray(pharmacy.provincias_atendidas) &&
      pharmacy.provincias_atendidas.some((served) => normalize(served) === selected));
}

export const INDIVIDUAL_PHARMACY_ZOOM = 10;

export function getMapMarkerSizes(zoom, maxZoom = 18) {
  const progress = Math.max(0, Math.min(1, (zoom - 6) / 8));
  const scale = zoom >= maxZoom ? 2 : 1;
  return {
    normal: Math.round(4 + 5 * progress) * scale,
    duty: (Math.round(4 + 5 * progress) + (zoom >= INDIVIDUAL_PHARMACY_ZOOM ? 2 : 0)) * scale,
    dutyBorder: 1,
  };
}

// Catalogue rows keep the shift fields of their last import (often tomorrow's, written by
// the anticipated update); only the selected day's schedule may describe a duty.
function withoutDutyFields(pharmacy) {
  return Object.fromEntries(Object.entries(pharmacy)
    .filter(([key]) => !key.startsWith('guardia') && key !== 'fecha_guardia'));
}

export function mergePharmacies(catalog, schedules) {
  const result = new Map();
  for (const pharmacy of catalog) {
    result.set(pharmacyKey(pharmacy), { ...withoutDutyFields(pharmacy), guardia: false, guardia_franja: null });
  }
  for (const pharmacy of schedules) {
    const key = pharmacyKey(pharmacy);
    const previous = result.get(key);
    const position = selectCoordinates(pharmacy, previous);
    result.set(key, {
      ...previous,
      ...pharmacy,
      lat: position ? position[0] : null,
      lng: position ? position[1] : null,
      guardia: true,
    });
  }
  return [...result.values()];
}
