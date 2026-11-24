import { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import provincias from '../../data/provincias.json';
import 'leaflet/dist/leaflet.css';
import Calendario from './Calendario';
import SelectorProvincia from './SelectorProvincia';
import { getCoordinates, getDirectionsUrl, getMapMarkerSizes, matchesProvince, mergePharmacies, pharmacyKey, selectCoordinates } from '../farmacias';
import { getDutyShift, getOpenDuties, madridNow, shiftDate } from '../horarios';
import { getBaseLayers, getPointStyle, isNightAt } from '../mapTheme';
import { pharmacyCrossPath, pharmacyCrossVertices } from '../mapCross';
import { fetchDutyCoverage } from '../dutyCoverage';

const MAP_CENTER = [40.2, -3.4];
const MAX_ZOOM = 18;
const DATASET = '/data/farmacias-espana-hoy.json';
const EMPTY_SET = new Set();
const EMPTY_ARRAY = [];
const CrossCanvas = L.Canvas.extend({
  _updateCircle(layer) {
    if (!layer.options.pharmacyCross) {
      return L.Canvas.prototype._updateCircle.call(this, layer);
    }
    if (!this._drawing || layer._empty()) return;
    const { x, y } = layer._point;
    const radius = layer._radius;
    this._ctx.beginPath();
    pharmacyCrossVertices(radius).forEach(([dx, dy], index) => {
      this._ctx[index === 0 ? 'moveTo' : 'lineTo'](x + dx, y + dy);
    });
    this._ctx.closePath();
    this._fillStroke(this._ctx, layer);
  },
});
const CrossSVG = L.SVG.extend({
  _updateCircle(layer) {
    if (!layer.options.pharmacyCross) {
      return L.SVG.prototype._updateCircle.call(this, layer);
    }
    this._setPath(layer, layer._empty() ? 'M0 0' : pharmacyCrossPath(layer._point, layer._radius));
  },
});
const LOCAL_DATE = (() => {
  const date = new Date();
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
})();

const iconos = {
  user: L.divIcon({
    className: 'map-marker map-marker--user',
    html: '<span aria-hidden="true"></span>',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  }),
};

function haversine(lat1, lon1, lat2, lon2) {
  const radius = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function normalizeText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('es')
    .trim();
}

function slugify(value) {
  return normalizeText(value).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function hasVerifiedLocation(pharmacy) {
  const distance = pharmacy?.ajuste_ubicacion_m;
  return Number.isFinite(distance) && distance >= 0 && distance <= 15;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function FocusMap({ position, provincia }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.flyTo(position, 14, { duration: 0.7 });
    else if (!provincia) map.setView(MAP_CENTER, 6);
  }, [map, position, provincia]);
  return null;
}

function MapLight({ mode, onNightChange }) {
  const map = useMap();
  useEffect(() => {
    function update() {
      const center = map.getCenter();
      const longitude = ((center.lng + 180) % 360 + 360) % 360 - 180;
      onNightChange(mode === 'night' || (mode === 'auto' &&
        isNightAt(new Date(), Math.max(-90, Math.min(90, center.lat)), longitude)));
    }
    update();
    map.on('moveend', update);
    const timer = setInterval(update, 30000);
    document.addEventListener('visibilitychange', update);
    return () => {
      map.off('moveend', update);
      clearInterval(timer);
      document.removeEventListener('visibilitychange', update);
    };
  }, [map, mode, onNightChange]);
  return null;
}

function MarkerLayer({
  farmacias,
  userPos,
  night,
  onLargeDutyCrossesChange,
  onMaximumZoomPharmaciesChange,
}) {
  const map = useMap();
  const appearance = useRef({ night, markers: new Map(), centers: new Map() });

  useEffect(() => {
    appearance.current.night = night;
    for (const [pharmacy, marker] of appearance.current.markers) {
      marker.setStyle(getPointStyle(night, pharmacy.guardia, pharmacy.guardia_tipo === 'nocturna'));
    }
    for (const center of appearance.current.centers.values()) {
      center.setStyle({ fillOpacity: night ? 1 : 0 });
    }
  }, [night]);

  useEffect(() => {
    const individuals = L.layerGroup().addTo(map);
    for (const [pane, zIndex] of [['pharmacyPoints', '410'], ['dutyPoints', '420'], ['dutyCrosses', '430']]) {
      if (!map.getPane(pane)) map.createPane(pane).style.zIndex = zIndex;
    }
    const normalRenderer = new CrossCanvas({ pane: 'pharmacyPoints', padding: 0.3 });
    const dutyRenderer = new CrossSVG({ pane: 'dutyPoints', padding: 0.3 });
    const markers = new Map();
    const centers = new Map();
    const crosses = new Map();
    appearance.current.markers = markers;
    appearance.current.centers = centers;
    const located = farmacias.filter((pharmacy) => getCoordinates(pharmacy));
    function getMarker(farmacia) {
      if (markers.has(farmacia)) return markers.get(farmacia);
      const position = getCoordinates(farmacia);
      const sizes = getMapMarkerSizes(map.getZoom(), map.getMaxZoom());
      const marker = L.circleMarker(position, {
        pharmacyCross: true,
        renderer: farmacia.guardia ? dutyRenderer : normalRenderer,
        radius: (farmacia.guardia ? sizes.duty : sizes.normal) / 2,
        ...getPointStyle(appearance.current.night, farmacia.guardia, farmacia.guardia_tipo === 'nocturna'),
      });
      centers.set(farmacia, L.circleMarker(position, {
        renderer: farmacia.guardia ? dutyRenderer : normalRenderer,
        radius: 1,
        stroke: false,
        fillColor: '#fff',
        fillOpacity: appearance.current.night ? 1 : 0,
        interactive: false,
      }));
      const nombre = escapeHtml(farmacia.nombre || 'Farmacia');
      const direccion = escapeHtml(farmacia.direccion);
      const localidad = escapeHtml(farmacia.localidad);
      const provincia = escapeHtml(farmacia.provincia);
      const telefono = escapeHtml(farmacia.telefono);
      const distancia = userPos
        ? `<p>A ${haversine(userPos[0], userPos[1], position[0], position[1]).toFixed(1)} km</p>`
        : '';
      const detalle = farmacia.guardia
        ? `<p><strong>${farmacia.guardia_reconfirmada === false ? 'Guardia no reconfirmada' : 'De guardia'}` +
          `${farmacia.guardia_tipo === 'nocturna' ? ' · Noche / 24 h' : ''}</strong>` +
          `${farmacia.guardia_franja ? ` · ${escapeHtml(farmacia.guardia_franja)}` : ''}</p>` +
          `${farmacia.guardia_desde_ayer ? '<p>Guardia iniciada ayer que sigue abierta</p>' : ''}` +
          `${farmacia.guardia_apertura === 'desconocida' ? '<p>Horario por confirmar</p>' : ''}`
        : '';
      const phoneLine = telefono ? `<p>Tel. ${telefono}</p>` : '';
      const precision = farmacia.precision_ubicacion === 'aproximada' ? '<p>Ubicación aproximada</p>'
        : farmacia.precision_ubicacion === 'direccion'
          ? hasVerifiedLocation(farmacia)
            ? `<p>Ubicación contrastada a ${farmacia.ajuste_ubicacion_m.toFixed(1)} m</p>`
            : '<p>Ubicación por dirección; pendiente de verificar</p>'
          : '';
      const locationNote = farmacia.nota_ubicacion ? `<p>${escapeHtml(farmacia.nota_ubicacion)}</p>` : '';
      const navarraAttribution = farmacia.provincia === 'Navarra' &&
        farmacia.fuente_licencia === 'https://creativecommons.org/licenses/by/4.0/'
        ? '<p>Datos adaptados del <a href="https://datosabiertos.navarra.es/es/dataset/farmacias-de-guardia" target="_blank" rel="noopener noreferrer">Gobierno de Navarra</a>, ' +
          '<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>. Horarios pendientes de interpretación.</p>'
        : '';
      const directions = `<a class="map-popup-directions" href="${escapeHtml(getDirectionsUrl(position, userPos))}" ` +
        'target="_blank" rel="noopener noreferrer">Cómo llegar</a>';
      const farmaciaId = farmacia.id || farmacia.osm_id || farmacia.farmacia_id || '';
      const farmaciaParam = encodeURIComponent(farmaciaId);
      const farmaciaNombre = encodeURIComponent(direccion || nombre || '');
      const farmaciaLocalidad = encodeURIComponent(localidad || '');
      const farmaciaProvincia = encodeURIComponent(provincia || '');
      const farmaciaAcceso = `<a class="map-popup-directions" href="/login?farmacia=${farmaciaParam}&nombre=${farmaciaNombre}&localidad=${farmaciaLocalidad}&provincia=${farmaciaProvincia}" style="margin-left:8px;">Acceso farmacéutico</a>`;

      marker.bindPopup(
        `<div class="map-popup"><strong>${direccion || nombre}</strong>` +
        `${direccion && nombre && nombre !== direccion ? `<p>${nombre}</p>` : ''}` +
        `<p>${localidad}${provincia ? ` (${provincia})` : ''}</p>` +
        `${detalle}${phoneLine}${distancia}${precision}${locationNote}${navarraAttribution}<div style="margin-top:6px;">${directions}${farmaciaAcceso}</div></div>`
      );
      markers.set(farmacia, marker);
      return marker;
    }

    let frame = null;
    function syncLayers(layer, desired) {
      layer.eachLayer((marker) => {
        if (!desired.has(marker)) layer.removeLayer(marker);
      });
      for (const marker of desired) {
        if (!layer.hasLayer(marker)) layer.addLayer(marker);
      }
    }
    function renderMarkers() {
      const largeDutyCrosses = map.getZoom() >= map.getMaxZoom() - 4;
      const atMaximumZoom = map.getZoom() >= map.getMaxZoom();
      map.getContainer().classList.toggle('pharmacy-duty-pulsing', largeDutyCrosses);
      onLargeDutyCrossesChange(largeDutyCrosses);
      const sizes = getMapMarkerSizes(map.getZoom(), map.getMaxZoom());
      const style = map.getContainer().style;
      style.setProperty('--pharmacy-marker-size', `${sizes.normal}px`);
      style.setProperty('--duty-marker-size', `${sizes.duty}px`);
      style.setProperty('--duty-marker-border', `${sizes.dutyBorder}px`);
      const bounds = map.getBounds().pad(0.2);
      onMaximumZoomPharmaciesChange(atMaximumZoom
        ? located.filter((pharmacy) => map.getBounds().contains(getCoordinates(pharmacy)))
        : EMPTY_ARRAY);
      const visiblePoints = new Set();
      const visiblePharmacies = new Set();
      function includePoint(pharmacy) {
        if (!bounds.contains(getCoordinates(pharmacy))) return;
        visiblePharmacies.add(pharmacy);
        const marker = getMarker(pharmacy);
        if (largeDutyCrosses && pharmacy.guardia) {
          if (!crosses.has(pharmacy)) {
            const nightDuty = pharmacy.guardia_tipo === 'nocturna';
            crosses.set(pharmacy, L.marker(getCoordinates(pharmacy), {
              pane: 'dutyCrosses',
              title: `${pharmacy.guardia_reconfirmada === false ? 'Guardia sin reconfirmar' : 'Farmacia de guardia'}` +
                `${nightDuty ? ' de noche / 24 h' : ''}`,
              icon: L.divIcon({
                className: `pharmacy-duty-cross${nightDuty ? ' pharmacy-duty-cross--night' : ''}`,
                html: '<svg aria-hidden="true" viewBox="0 0 36 36"><path d="M13 2H23V13H34V23H23V34H13V23H2V13H13Z"/></svg>',
                iconSize: [36, 36],
                iconAnchor: [18, 18],
              }),
            }).bindPopup(marker.getPopup().getContent()));
          }
          visiblePoints.add(crosses.get(pharmacy));
          return;
        }
        marker.setRadius((pharmacy.guardia ? sizes.duty : sizes.normal) / 2);
        visiblePoints.add(marker);
        visiblePoints.add(centers.get(pharmacy));
      }
      for (const pharmacy of located) includePoint(pharmacy);
      syncLayers(individuals, visiblePoints);
      for (const pharmacy of markers.keys()) {
        if (!visiblePharmacies.has(pharmacy)) {
          markers.delete(pharmacy);
          centers.delete(pharmacy);
          crosses.delete(pharmacy);
        }
      }
    }
    function scheduleRender() {
      if (frame !== null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        renderMarkers();
      });
    }
    map.on('zoomend moveend', scheduleRender);
    renderMarkers();
    return () => {
      map.off('zoomend moveend', scheduleRender);
      if (frame !== null) cancelAnimationFrame(frame);
      map.removeLayer(individuals);
      map.getContainer().classList.remove('pharmacy-duty-pulsing');
      if (map.hasLayer(normalRenderer)) map.removeLayer(normalRenderer);
      if (map.hasLayer(dutyRenderer)) map.removeLayer(dutyRenderer);
    };
  }, [farmacias, map, userPos, onLargeDutyCrossesChange, onMaximumZoomPharmaciesChange]);

  return null;
}

function getLocationError(error) {
  if (error.code === 1) return 'No se concedió permiso para acceder a la ubicación.';
  if (error.code === 2) return 'No se pudo determinar tu ubicación.';
  if (error.code === 3) return 'La solicitud de ubicación tardó demasiado.';
  return 'No se pudo acceder a la ubicación.';
}

export default function Mapa() {
  const [farmacias, setFarmacias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [farmaciasError, setFarmaciasError] = useState('');
  const [fecha, setFecha] = useState(LOCAL_DATE);
  const [userPos, setUserPos] = useState(null);
  const [focusPos, setFocusPos] = useState(null);
  const [geoError, setGeoError] = useState('');
  const [locating, setLocating] = useState(false);
  const [showNearest, setShowNearest] = useState(false);
  const [showAll, setShowAll] = useState(true);
  const [mapMode, setMapMode] = useState('auto');
  const [mapNight, setMapNight] = useState(() => isNightAt(new Date(), ...MAP_CENTER));
  const [largeDutyCrosses, setLargeDutyCrosses] = useState(false);
  const [farmaciasEnZoomMaximo, setFarmaciasEnZoomMaximo] = useState(EMPTY_ARRAY);
  const [provinciaSeleccionada, setProvinciaSeleccionada] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [additionalResults, setAdditionalResults] = useState({ key: '', count: 0 });
  const [guardias, setGuardias] = useState({
    clave: `*:${LOCAL_DATE}`,
    estado: 'loading',
    ids: new Set(),
    provincias: [],
    farmacias: [],
    avisos: [],
  });
  const [reload, setReload] = useState(0);
  const [turno, setTurno] = useState('todas');
  const [reloj, setReloj] = useState(() => madridNow());
  const [corte, setCorte] = useState(() => madridNow().minutes);
  const [guardiasAyer, setGuardiasAyer] = useState({ clave: '', farmacias: [], faltan: [] });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch(DATASET, { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudieron cargar las farmacias (${response.status}).`);
        return response.json();
      }),
      fetch('/data/coordenadas-malaga-capital.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudieron cargar las coordenadas de Málaga (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-malaga.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Málaga (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-sevilla.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Sevilla (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-granada.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Granada (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-cadiz.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Cádiz (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-jaen.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Jaén (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-almeria.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Almería (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-huelva.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Huelva (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-cordoba.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Córdoba (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-madrid.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Madrid (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-toledo.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Toledo (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-guadalajara.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Guadalajara (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-albacete.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Albacete (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-ciudad-real.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Ciudad Real (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-cuenca.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Cuenca (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-barcelona.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Barcelona (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-valencia.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Valencia (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-valladolid.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Valladolid (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-cantabria.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Cantabria (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-pontevedra.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Pontevedra (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-ourense.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Ourense (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-a-coruna.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de A Coruña (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-andorra.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Andorra (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-asturias.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Asturias (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-navarra.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Navarra (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-salamanca.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Salamanca (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-burgos.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Burgos (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-palencia.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Palencia (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-murcia.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Murcia (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-alicante.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Alicante (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-badajoz.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Badajoz (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-la-rioja.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de La Rioja (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-zaragoza.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Zaragoza (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-ceuta.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Ceuta (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-melilla.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Melilla (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-baleares.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Baleares (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-caceres.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Cáceres (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-segovia.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Segovia (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-leon.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de León (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-zamora.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Zamora (${response.status}).`);
        return response.json();
      }),
      fetch('/data/farmacias-soria.json', { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar el catálogo de Soria (${response.status}).`);
        return response.json();
      }),
    ])
      .then(([data, cityCoordinates, ...provinceCatalogs]) => {
        if (!Array.isArray(data) || provinceCatalogs.some((catalog) => !Array.isArray(catalog))) {
          throw new Error('El archivo de farmacias tiene un formato no válido.');
        }
        if (!cityCoordinates || typeof cityCoordinates !== 'object' || Array.isArray(cityCoordinates)) {
          throw new Error('El archivo de coordenadas de Málaga tiene un formato no válido.');
        }
        const catalog = new Map();
        for (const pharmacy of [...data, ...provinceCatalogs.flat()]) {
          const key = pharmacyKey(pharmacy);
          if (key) {
            const previous = catalog.get(key);
            const position = selectCoordinates(pharmacy, previous);
            catalog.set(key, {
              ...previous,
              ...pharmacy,
              lat: position ? position[0] : null,
              lng: position ? position[1] : null,
            });
          }
        }
        const unique = [...catalog.values()].map((pharmacy) => {
          const coordinates = cityCoordinates[String(pharmacy.cofm_id)];
          if (!coordinates || getCoordinates(pharmacy)) return pharmacy;
          return { ...pharmacy, lat: coordinates.lat, lng: coordinates.lng };
        });
        setFarmacias(unique);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setFarmaciasError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reload]);

  const claveGuardias = `${provinciaSeleccionada || '*'}:${fecha}`;
  const guardiasActuales = guardias.clave === claveGuardias;
  const estadoGuardias = guardiasActuales ? guardias.estado : 'loading';
  const idsGuardia = guardiasActuales ? guardias.ids : EMPTY_SET;
  const provinciasConCalendario = guardiasActuales ? guardias.provincias : EMPTY_ARRAY;
  const avisosGuardias = guardiasActuales ? guardias.avisos : EMPTY_ARRAY;
  const farmaciasGuardia = guardiasActuales ? guardias.farmacias : EMPTY_ARRAY;
  const esHoy = fecha === reloj.date;
  const turnoActivo = turno === 'abiertas' && !esHoy ? 'todas' : turno;
  const claveAyer = turnoActivo === 'abiertas' && estadoGuardias === 'available'
    ? `${claveGuardias}:${provinciasConCalendario.join(',')}`
    : '';
  const ayerCargado = Boolean(claveAyer) && guardiasAyer.clave === claveAyer;
  const filasAyer = ayerCargado ? guardiasAyer.farmacias : EMPTY_ARRAY;
  const provinciasSinAyer = ayerCargado ? guardiasAyer.faltan : EMPTY_ARRAY;

  useEffect(() => {
    const controller = new AbortController();

    async function cargarGuardias() {
      const provinciasObjetivo = provinciaSeleccionada
        ? provincias.filter((item) => normalizeText(item.nombre) === normalizeText(provinciaSeleccionada))
        : provincias;
      const calendarios = [];
      const errores = [];

      for (let index = 0; index < provinciasObjetivo.length; index += 8) {
        const lote = provinciasObjetivo.slice(index, index + 8);
        const resultados = await Promise.all(lote.map(async (provincia) => {
          try {
            const response = await fetch(
              `/data/guardias-${slugify(provincia.nombre)}-${fecha}.json`,
              { signal: controller.signal }
            );
            if (!response.ok && response.status !== 404) throw new Error(`${provincia.nombre}: HTTP ${response.status}`);
            const contentType = response.headers.get('content-type') || '';
            const hasCalendar = response.ok && !contentType.includes('text/html');
            if (hasCalendar && !contentType.includes('json')) {
              throw new Error(`${provincia.nombre}: respuesta que no es JSON`);
            }
            const data = hasCalendar ? await response.json() : null;
            if (hasCalendar && !Array.isArray(data)) throw new Error(`${provincia.nombre}: formato de calendario no válido`);
            let coverageError = '';
            const provinceSlug = slugify(provincia.nombre);
            if (['malaga', 'sevilla', 'granada', 'cadiz', 'jaen', 'almeria', 'huelva', 'cordoba', 'madrid', 'toledo', 'guadalajara', 'albacete', 'ciudad-real', 'cuenca', 'barcelona', 'girona', 'valencia', 'valladolid', 'cantabria', 'pontevedra', 'ourense', 'a-coruna', 'andorra', 'asturias', 'navarra', 'salamanca', 'burgos', 'palencia', 'murcia', 'alicante', 'badajoz', 'la-rioja', 'zaragoza', 'ceuta', 'melilla', 'baleares', 'caceres', 'segovia', 'leon', 'avila', 'soria', 'zamora'].includes(provinceSlug)) {
              const coverageResult = await fetchDutyCoverage(provincia.nombre, provinceSlug, fecha, controller.signal);
              coverageError = coverageResult.error;
              if (coverageResult.coverage) {
                const coverage = coverageResult.coverage;
                const missing = coverage.consultas.filter((item) => !['disponible', 'sin_modificaciones'].includes(item.estado));
                if (missing.length) {
                  const named = [...new Set(missing
                    .filter((item) => ['pizarra', 'san-pedro-alcantara', 'alora', 'antequera'].includes(slugify(item.nombre)))
                    .map((item) => item.nombre))];
                  coverageError = provinceSlug === 'almeria' && missing.some((item) => item.estado === 'parcial')
                    ? 'Almería: algunos horarios oficiales son inválidos; confirmar por teléfono. La madrugada anterior puede estar incompleta.'
                    : `${provincia.nombre}: ${missing.length} ${missing.length === 1 ? 'consulta' : 'consultas'} con cobertura incompleta${named.length ? ` (incluye ${named.join(', ')})` : ''}. No implica que no haya guardias.`;
                  if (!coverage.consultas.some((item) => ['disponible', 'parcial'].includes(item.estado)) &&
                      (!hasCalendar || data.length === 0)) {
                    errores.push(coverageError);
                    return null;
                  }
                }
              }
            }
            if (!hasCalendar) {
              if (coverageError) errores.push(coverageError);
              return null;
            }
            return { provincia: provincia.nombre, data, coverageError };
          } catch (error) {
            if (error.name !== 'AbortError') errores.push(error.message);
            return null;
          }
        }));
        calendarios.push(...resultados.filter(Boolean));
        if (controller.signal.aborted) return;
      }

      if (controller.signal.aborted) return;
      const ids = new Set(
        calendarios.flatMap(({ data }) => data.map(pharmacyKey)).filter(Boolean)
      );
      if (calendarios.length > 0) {
        setGuardias({
          clave: claveGuardias,
          estado: 'available',
          ids,
          farmacias: calendarios.flatMap(({ data }) => data),
          provincias: calendarios.map(({ provincia }) => provincia),
          avisos: [
            ...errores,
            ...calendarios.map(({ coverageError }) => coverageError).filter(Boolean),
          ],
        });
      } else if (errores.length > 0) {
        setGuardias({
          clave: claveGuardias,
          estado: 'error',
          ids: new Set(),
          provincias: [],
          farmacias: [],
          avisos: errores,
        });
      } else {
        setGuardias({ clave: claveGuardias, estado: 'unavailable', ids: new Set(), provincias: [], farmacias: [], avisos: [] });
      }
    }

    cargarGuardias().catch((error) => {
      if (error.name !== 'AbortError' && !controller.signal.aborted) {
        setGuardias({
          clave: claveGuardias,
          estado: 'error',
          ids: new Set(),
          provincias: [],
          farmacias: [],
          avisos: [error.message],
        });
      }
    });

    return () => controller.abort();
  }, [claveGuardias, fecha, provinciaSeleccionada, reload]);

  useEffect(() => {
    if (!claveAyer) return undefined;
    const controller = new AbortController();
    const ayer = shiftDate(fecha, -1);
    Promise.all(provinciasConCalendario.map(async (provincia) => {
      try {
        const response = await fetch(`/data/guardias-${slugify(provincia)}-${ayer}.json`, { signal: controller.signal });
        const data = response.ok && (response.headers.get('content-type') || '').includes('json')
          ? await response.json()
          : null;
        return Array.isArray(data) ? { data } : { falta: provincia };
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        return { falta: provincia };
      }
    }))
      .then((resultados) => setGuardiasAyer({
        clave: claveAyer,
        farmacias: resultados.flatMap(({ data }) => data || []),
        faltan: resultados.map(({ falta }) => falta).filter(Boolean),
      }))
      .catch(() => {});
    return () => controller.abort();
  }, [claveAyer, fecha, provinciasConCalendario]);

  const guardiasClasificadas = useMemo(
    () => farmaciasGuardia.map((row) => ({ ...row, guardia_tipo: getDutyShift(row, fecha) })),
    [farmaciasGuardia, fecha],
  );

  // The evaluation minute only advances when the set of open duties changes, so the
  // minute clock does not rebuild the map layers (and close popups) every minute.
  useEffect(() => {
    function tick() {
      const now = madridNow();
      setReloj(now);
      if (turnoActivo !== 'abiertas') return;
      const firma = (minutes) => getOpenDuties(guardiasClasificadas, filasAyer, minutes, fecha)
        .map((row) => `${pharmacyKey(row)}:${row.guardia_apertura}:${row.guardia_desde_ayer ? 1 : 0}`)
        .join('|');
      setCorte((previous) => (firma(previous) === firma(now.minutes) ? previous : now.minutes));
    }
    const timer = setInterval(tick, 60000);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [fecha, filasAyer, guardiasClasificadas, turnoActivo]);

  const guardiasAbiertas = useMemo(
    () => (turnoActivo === 'abiertas'
      ? getOpenDuties(guardiasClasificadas, filasAyer, corte, fecha)
      : EMPTY_ARRAY),
    [corte, fecha, filasAyer, guardiasClasificadas, turnoActivo],
  );
  const guardiasTurno = useMemo(() => {
    if (turnoActivo === 'noche') return guardiasClasificadas.filter((row) => row.guardia_tipo === 'nocturna');
    return turnoActivo === 'abiertas' ? guardiasAbiertas : guardiasClasificadas;
  }, [guardiasAbiertas, guardiasClasificadas, turnoActivo]);

  const farmaciasFiltradas = useMemo(() => {
    const province = normalizeText(provinciaSeleccionada);
    const query = normalizeText(busqueda);
    return mergePharmacies(farmacias, guardiasTurno)
      .filter((pharmacy) => {
        if (!matchesProvince(pharmacy, province)) return false;
        if ((!showAll || turnoActivo !== 'todas') && !pharmacy.guardia) return false;
        if (!query) return true;
        return [
          pharmacy.nombre,
          pharmacy.direccion,
          pharmacy.localidad,
          pharmacy.provincia,
          pharmacy.zona,
          pharmacy.sector,
        ].some((value) => normalizeText(value).includes(query));
      })
      .map((pharmacy) => {
        const position = getCoordinates(pharmacy);
        const distance = userPos && position
          ? haversine(userPos[0], userPos[1], position[0], position[1])
          : null;
        return { ...pharmacy, position, distance };
      })
      .sort((a, b) => {
        if (showNearest && a.distance !== null && b.distance !== null) return a.distance - b.distance;
        if (a.distance !== null) return -1;
        if (b.distance !== null) return 1;
        return String(a.localidad || '').localeCompare(String(b.localidad || ''), 'es');
      });
  }, [busqueda, farmacias, guardiasTurno, provinciaSeleccionada, showAll, showNearest, turnoActivo, userPos]);
  const resultsKey = `${claveGuardias}:${busqueda}:${showAll}:${showNearest}:${turnoActivo}`;
  const visibleCount = 100 + (additionalResults.key === resultsKey ? additionalResults.count : 0);

  function locateUser() {
    if (!navigator.geolocation) {
      setGeoError('Este navegador no permite compartir la ubicación.');
      return;
    }

    setLocating(true);
    setGeoError('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const coordinates = [position.coords.latitude, position.coords.longitude];
        setUserPos(coordinates);
        setFocusPos(coordinates);
        setShowNearest(true);
        setLocating(false);
      },
      (error) => {
        setGeoError(getLocationError(error));
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
  }

  const guardiasDisponibles = estadoGuardias === 'available';
  const guardiasFiltradas = farmaciasFiltradas.filter((pharmacy) => pharmacy.guardia);
  const guardiasNoReconfirmadas = guardiasFiltradas.filter((pharmacy) => pharmacy.guardia_reconfirmada === false).length;
  const guardiasUbicadas = guardiasFiltradas.filter((pharmacy) => pharmacy.position).length;
  const nocturnasUbicadas = guardiasFiltradas
    .filter((pharmacy) => pharmacy.position && pharmacy.guardia_tipo === 'nocturna').length;
  const horarioPorConfirmar = guardiasFiltradas.filter((pharmacy) => pharmacy.guardia_apertura === 'desconocida').length;
  const coberturaSeleccionada = provinciaSeleccionada
    ? 1
    : provincias.length;
  const coberturaTexto = provinciasConCalendario.length > 0
    ? `Calendarios cargados para ${provinciasConCalendario.length} de ${coberturaSeleccionada} ${coberturaSeleccionada === 1 ? 'provincia' : 'provincias'}: ${provinciasConCalendario.join(', ')}.`
    : '';
  const avisosTexto = avisosGuardias.length > 0
    ? ` · ${avisosGuardias.length} ${avisosGuardias.length === 1 ? 'aviso' : 'avisos'}`
    : '';
  const informeResumen = estadoGuardias === 'loading'
    ? 'Cargando…'
    : guardiasDisponibles
      ? `${provinciasConCalendario.length} ${provinciasConCalendario.length === 1 ? 'provincia' : 'provincias'}${avisosTexto}`
      : `Sin calendarios${avisosTexto}`;

  return (
    <main className="tracker-layout">
      <aside className="tracker-panel" aria-label="Buscar farmacias">
        <div className="panel-content">
          <p className="eyebrow">Buscador de guardias</p>
          <h1 className="panel-title">¿Qué farmacia necesitas?</h1>
          <p className="panel-description">
            Consulta las farmacias disponibles y encuentra la más cercana.
          </p>

          <label className="control-label" htmlFor="province">Provincia</label>
          <SelectorProvincia
            provincia={provinciaSeleccionada}
            onChange={(provincia) => {
              setProvinciaSeleccionada(provincia);
              setFocusPos(null);
            }}
          />

          <label className="search-wrap" htmlFor="pharmacy-search">
            <span className="search-icon" aria-hidden="true">⌕</span>
            <input
              className="search-input"
              id="pharmacy-search"
              type="search"
              placeholder="Localidad, dirección o farmacia"
              value={busqueda}
              onChange={(event) => setBusqueda(event.target.value)}
            />
          </label>

          <section className="calendar-section" aria-label="Seleccionar fecha">
            <span className="control-label">Fecha de guardia</span>
            <Calendario fecha={fecha} hoy={LOCAL_DATE} onSelect={(value) => {
              const now = madridNow();
              setReloj(now);
              setCorte(now.minutes);
              setFecha(value);
            }} />
          </section>

          <button
            className="location-button"
            type="button"
            onClick={locateUser}
            disabled={locating}
          >
            <span aria-hidden="true">◎</span>
            {locating ? 'Buscando ubicación…' : userPos ? 'Actualizar mi ubicación' : 'Usar mi ubicación'}
          </button>
          {geoError && <p className="data-notice data-notice--error" role="status">{geoError}</p>}

          <details className={`report-panel${avisosGuardias.length > 0 ? ' report-panel--warning' : ''}`}>
            <summary className="report-summary">
              <span className="report-title">Informe</span>
              <span className="report-meta" role="status">{informeResumen}</span>
            </summary>
            <div className="report-body">
              {estadoGuardias === 'loading' && <p>Buscando calendarios de guardia por provincia…</p>}
              {estadoGuardias === 'unavailable' && (
                <p>
                  Todavía no hay calendarios publicados para {provinciaSeleccionada || 'España'} el {new Date(`${fecha}T12:00:00`).toLocaleDateString('es-ES')}.
                  Se irán incorporando a medida que se añadan los scrapers de cada zona.
                </p>
              )}
              {guardiasDisponibles && coberturaTexto && <p>{coberturaTexto}</p>}
              {guardiasDisponibles && idsGuardia.size === 0 && (
                <p>El calendario no contiene farmacias de guardia para esta fecha.</p>
              )}
              {avisosGuardias.length > 0 && (
                <ul className="report-list">
                  {avisosGuardias.map((aviso, index) => {
                    const separator = aviso.indexOf(': ');
                    return (
                      <li key={`${index}:${aviso}`}>
                        {separator > 0 && separator < 40
                          ? <><strong>{aviso.slice(0, separator)}</strong>{aviso.slice(separator)}</>
                          : aviso}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </details>
          {farmaciasError && (
            <p className="data-notice data-notice--error" role="alert">
              {farmaciasError}{' '}
              <button
                type="button"
                onClick={() => {
                  setFarmaciasError('');
                  setLoading(true);
                  setReload((value) => value + 1);
                }}
              >
                Reintentar
              </button>
            </p>
          )}

          <div className="results-header">
            <h3>{showAll && turnoActivo === 'todas' ? 'Farmacias' : 'Farmacias de guardia'}</h3>
            <span className="results-count">
              {loading ? 'Cargando…' : `${farmaciasFiltradas.length} resultados`}
            </span>
          </div>
          {estadoGuardias !== 'loading' && (
            <p className="duty-summary" role="status">
              <span className="legend-cross" aria-hidden="true" />
              {guardiasFiltradas.length - guardiasNoReconfirmadas} guardias confirmadas
              {guardiasNoReconfirmadas > 0 && ` · ${guardiasNoReconfirmadas} no reconfirmadas`}
              {' · '}{guardiasUbicadas} ubicadas{largeDutyCrosses ? ' con cruz grande' : ''}
              {nocturnasUbicadas > 0 && ` · ${nocturnasUbicadas} de noche / 24 h`}
            </p>
          )}
          <div className="shift-filter" role="group" aria-label="Filtrar guardias por horario">
            {[['todas', 'Todas'], ['noche', 'Noche y 24 h'], ['abiertas', 'Abiertas ahora']].map(([value, label]) => (
              <button
                key={value}
                type="button"
                data-turno={value}
                aria-pressed={turnoActivo === value}
                disabled={value === 'abiertas' && !esHoy}
                title={value === 'abiertas' && !esHoy ? 'Solo disponible con la fecha de hoy' : undefined}
                onClick={() => {
                  if (value === 'abiertas') {
                    const now = madridNow();
                    setReloj(now);
                    setCorte(now.minutes);
                  }
                  setTurno(value);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          {turnoActivo === 'noche' && (
            <p className="data-notice" role="status">
              Guardias que cubren la madrugada: nocturnas, de 24 h y las que siguen abiertas desde anoche.
              Las que no publican horario solo aparecen en «Todas».
            </p>
          )}
          {turnoActivo === 'abiertas' && (
            <p className="data-notice" role="status">
              {ayerCargado
                ? `Abiertas a las ${reloj.time} (hora peninsular), incluidas las guardias que empezaron ayer.`
                : 'Comprobando también las guardias que empezaron ayer…'}
              {horarioPorConfirmar > 0 &&
                ` ${horarioPorConfirmar} sin horas exactas publicadas (p. ej. «24 horas» o «toda la noche») se muestran como «Horario por confirmar»: llama antes de ir.`}
              {provinciasSinAyer.length > 0 && reloj.time < '12:00' &&
                ` Sin calendario de ayer en ${provinciasSinAyer.length === 1 ? 'una provincia' : `${provinciasSinAyer.length} provincias`}` +
                ` (${provinciasSinAyer.slice(0, 4).join(', ')}${provinciasSinAyer.length > 4 ? '…' : ''}):` +
                ' pueden faltar guardias nocturnas iniciadas ayer.'}
            </p>
          )}
          {turno === 'abiertas' && !esHoy && (
            <p className="data-notice" role="status">
              «Abiertas ahora» solo funciona con la fecha de hoy; se muestran todas las guardias.
            </p>
          )}
          {turnoActivo === 'todas' && (
            <label className="show-all-label">
              <input
                type="checkbox"
                checked={showAll}
                onChange={(event) => setShowAll(event.target.checked)}
              />
              Mostrar todas las farmacias
            </label>
          )}
          {showAll && turnoActivo === 'todas' && (
            <p className="data-notice" role="status">
              Mostrando todas las farmacias conocidas, no solo las de guardia.
              Solo «De guardia» identifica las incluidas en el calendario seleccionado.
            </p>
          )}

          {provinciasConCalendario.includes('Navarra') && (
            <p className="data-notice">
              Datos adaptados del <a href="https://datosabiertos.navarra.es/es/dataset/farmacias-de-guardia" target="_blank" rel="noopener noreferrer">Gobierno de Navarra</a>
              {' '}(<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>).
              Horarios pendientes de interpretación; confirmar por teléfono.
            </p>
          )}
          <div className="results-list" aria-live="polite">
            {farmaciasFiltradas.slice(0, visibleCount).map((pharmacy) => (
              <button
                className="pharmacy-result"
                key={pharmacyKey(pharmacy)}
                type="button"
                onClick={() => pharmacy.position && setFocusPos(pharmacy.position)}
                disabled={!pharmacy.position}
              >
                <span className="pharmacy-result-top">
                  <strong>{pharmacy.direccion || pharmacy.nombre || 'Farmacia'}</strong>
                  {pharmacy.guardia && (
                    <span className={`duty-badge${pharmacy.guardia_tipo === 'nocturna' ? ' duty-badge--night' : ''}`}>
                      {pharmacy.guardia_reconfirmada === false ? 'Sin reconfirmar'
                        : pharmacy.guardia_tipo === 'nocturna' ? 'Noche / 24 h' : 'De guardia'}
                    </span>
                  )}
                </span>
                <span className="pharmacy-meta">
                  {[pharmacy.localidad, pharmacy.provincia].filter(Boolean).join(' · ') || 'España'}
                  {pharmacy.distance !== null && (
                    <> · <span className="pharmacy-distance">{pharmacy.distance.toFixed(1)} km</span></>
                  )}
                  {pharmacy.guardia_franja && ` · ${pharmacy.guardia_franja}`}
                  {pharmacy.guardia_desde_ayer && ' · Guardia iniciada ayer'}
                  {pharmacy.guardia_apertura === 'desconocida' && ' · Horario por confirmar'}
                  {!pharmacy.position && ' · Ubicación pendiente de verificar'}
                  {pharmacy.position && pharmacy.precision_ubicacion === 'aproximada' && ' · Ubicación aproximada'}
                  {pharmacy.position && pharmacy.precision_ubicacion === 'direccion' && !hasVerifiedLocation(pharmacy) &&
                    ' · Ubicación por dirección; pendiente de verificar'}
                  {pharmacy.position && pharmacy.precision_ubicacion === 'direccion' && hasVerifiedLocation(pharmacy) &&
                    ` · Ubicación contrastada a ${pharmacy.ajuste_ubicacion_m.toFixed(1)} m`}
                </span>
              </button>
            ))}
            {!loading && farmaciasFiltradas.length === 0 && (
              <p className="empty-results">
                {estadoGuardias === 'available'
                  ? 'No se encontraron farmacias para estos filtros.'
                  : 'No hay resultados con los datos de guardia disponibles. Puedes mostrar todas las farmacias.'}
              </p>
            )}
            {farmaciasFiltradas.length > visibleCount && (
              <button
                type="button"
                className="pharmacy-result"
                onClick={() => setAdditionalResults({ key: resultsKey, count: visibleCount })}
              >
                Mostrar más ({visibleCount} de {farmaciasFiltradas.length})
              </button>
            )}
          </div>
        </div>
      </aside>

      <section className={`map-wrap${mapNight ? ' map-wrap--night' : ''}${mapMode === 'satellite' ? ' map-wrap--satellite' : ''}`} aria-label="Mapa de farmacias">
        <MapContainer center={MAP_CENTER} zoom={6} maxZoom={MAX_ZOOM} scrollWheelZoom>
          {getBaseLayers(mapMode).map(({ key, ...layer }) => <TileLayer key={key} {...layer} />)}
          <FocusMap position={focusPos} provincia={provinciaSeleccionada} />
          <MapLight mode={mapMode} onNightChange={setMapNight} />
          {userPos && (
            <Marker position={userPos} icon={iconos.user}>
              <Popup>Tu ubicación</Popup>
            </Marker>
          )}
          <MarkerLayer farmacias={farmaciasFiltradas} userPos={userPos} night={mapNight}
            onLargeDutyCrossesChange={setLargeDutyCrosses}
            onMaximumZoomPharmaciesChange={setFarmaciasEnZoomMaximo} />
        </MapContainer>
        {farmaciasEnZoomMaximo.length > 0 && (
          <section className="map-zoom-pharmacies" aria-label="Farmacias visibles en el zoom máximo">
            <header className="map-zoom-pharmacies__header">
              <strong>Farmacias en esta vista</strong>
              <span>{farmaciasEnZoomMaximo.length}</span>
            </header>
            <ul>
              {farmaciasEnZoomMaximo.map((pharmacy) => {
                const position = getCoordinates(pharmacy);
                return (
                  <li key={pharmacyKey(pharmacy)}>
                    <strong>{pharmacy.direccion || pharmacy.nombre || 'Farmacia'}</strong>
                    <span>{[pharmacy.localidad, pharmacy.provincia].filter(Boolean).join(' · ') || 'España'}</span>
                    {pharmacy.guardia ? (
                      <span className={`map-zoom-pharmacies__duty${pharmacy.guardia_tipo === 'nocturna' ? ' map-zoom-pharmacies__duty--night' : ''}`}>
                        {pharmacy.guardia_reconfirmada === false ? 'Guardia sin reconfirmar'
                          : pharmacy.guardia_tipo === 'nocturna' ? 'De guardia · Noche / 24 h' : 'De guardia'}
                        {pharmacy.guardia_franja && ` · ${pharmacy.guardia_franja}`}
                      </span>
                    ) : <span>Sin guardia confirmada</span>}
                    {pharmacy.guardia_apertura === 'desconocida' && <span>Horario por confirmar</span>}
                    {pharmacy.telefono && <span>Tel. {pharmacy.telefono}</span>}
                    {pharmacy.distance !== null && <span>A {pharmacy.distance.toFixed(1)} km</span>}
                    {pharmacy.nota_ubicacion && <span>{pharmacy.nota_ubicacion}</span>}
                    <span style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <a href={getDirectionsUrl(position, userPos)} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                        Cómo llegar
                      </a>
                      <a href={`/login?farmacia=${encodeURIComponent(pharmacy.id || pharmacy.osm_id || '')}&nombre=${encodeURIComponent(pharmacy.nombre || pharmacy.direccion || '')}&localidad=${encodeURIComponent(pharmacy.localidad || '')}&provincia=${encodeURIComponent(pharmacy.provincia || '')}`} onClick={(e) => e.stopPropagation()}>
                        Acceso farmacéutico
                      </a>
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        <div className="map-theme-control" role="group" aria-label="Vista del mapa">
          {[['auto', 'Auto'], ['day', 'Día'], ['night', 'Noche'], ['satellite', 'Satélite']].map(([mode, label]) => (
            <button key={mode} type="button" aria-pressed={mapMode === mode}
              onClick={() => setMapMode(mode)}>
              {label}
            </button>
          ))}
          <span role="status">{mapMode === 'satellite' ? 'Vista satélite' : mapNight ? 'Mapa nocturno' : 'Mapa diurno'}</span>
        </div>
        <div className="map-legend" aria-label="Leyenda del mapa">
          {turnoActivo !== 'noche' && <span className="legend-item"><span className="legend-cross" />Guardia de día o sin horario ({guardiasUbicadas - nocturnasUbicadas})</span>}
          <span className="legend-item"><span className="legend-cross legend-cross--night" />Guardia de noche / 24 h ({nocturnasUbicadas})</span>
          {showAll && turnoActivo === 'todas' && <span className="legend-item"><span className="legend-cross legend-cross--normal" />Sin guardia confirmada</span>}
          {userPos && <span className="legend-item"><span className="legend-dot legend-dot--user" />Tu ubicación</span>}
          <span className="legend-item map-legend-help">
            {estadoGuardias === 'loading' ? 'Consultando guardias…'
              : guardiasFiltradas.length === 0 ? 'Sin guardias confirmadas para estos filtros y fecha; no implica ausencia de servicio.'
                : 'Farmacias individuales sin agrupación · Tamaño adaptado al zoom'}
          </span>
        </div>
      </section>
    </main>
  );
}
