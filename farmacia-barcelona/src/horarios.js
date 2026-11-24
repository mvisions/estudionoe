import { pharmacyKey } from './farmacias.js';

const DAY = 1440;
// A duty covers the night when it is open for the whole 03:00–06:00 window.
const NIGHT_START = 3 * 60;
const NIGHT_LENGTH = 3 * 60;
const TIME = String.raw`(?<![\d/])([01]?\d|2[0-4])[:.,]([0-5]\d)(?!\d)`;
const DATED_RANGE = new RegExp(
  String.raw`(\d{4}-\d{2}-\d{2})\s+([01]?\d|2[0-4]):([0-5]\d)\s+al\s+(\d{4}-\d{2}-\d{2})\s+([01]?\d|2[0-4]):([0-5]\d)`,
  'g',
);
const TIME_RANGE = new RegExp(
  `${TIME}(?:\\s*(?:h\\.?|horas?|de la (?:manana|tarde|noche)))?` +
  String.raw`\s*(?:-|–|—|\ba\b|\bal\b|hasta(?:\s+las)?)\s*` + TIME,
  'g',
);
const NIGHT_WORDS = /\bnoche\b|nocturn|madrugada|\b24\s*(?:h\b|horas)|permanente/;
const DAY_WORDS = /\bdia\b|diurn/;
const UNTIL = new RegExp(String.raw`hasta (?:las )?${TIME}`);

function fold(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function dayStart(date) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(date || ''));
  return match ? Date.UTC(+match[1], match[2] - 1, +match[3]) / 60000 : null;
}

export function wallMinutes(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(value || ''));
  return match ? Date.UTC(+match[1], match[2] - 1, +match[3], +match[4], +match[5]) / 60000 : null;
}

export function shiftDate(date, days) {
  const start = dayStart(date);
  if (start === null) throw new RangeError('Fecha no válida.');
  return new Date((start + days * DAY) * 60000).toISOString().slice(0, 10);
}

export function madridNow(date = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Madrid',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date).map(({ type, value }) => [type, value]));
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour}:${parts.minute}`,
    minutes: Date.UTC(+parts.year, parts.month - 1, +parts.day, +parts.hour, +parts.minute) / 60000,
  };
}

function textList(pharmacy) {
  if (Array.isArray(pharmacy.guardia_franjas) && pharmacy.guardia_franjas.length) return pharmacy.guardia_franjas;
  return pharmacy.guardia_franja ? [pharmacy.guardia_franja] : [];
}

function stripRanges(text) {
  return text.replace(DATED_RANGE, ' ').replace(TIME_RANGE, ' ')
    .replace(/(\d)\s*(?:h\.?|horas?)?\s*de la noche/g, '$1');
}

function textIntervals(text, start) {
  const intervals = [];
  for (const match of text.matchAll(DATED_RANGE)) {
    intervals.push({
      start: wallMinutes(`${match[1]}T${match[2].padStart(2, '0')}:${match[3]}`),
      end: wallMinutes(`${match[4]}T${match[5].padStart(2, '0')}:${match[6]}`),
    });
  }
  for (const match of text.replace(DATED_RANGE, ' ').matchAll(TIME_RANGE)) {
    const from = start + Number(match[1]) * 60 + Number(match[2]);
    let to = start + Number(match[3]) * 60 + Number(match[4]);
    if (to <= from) to += DAY;
    intervals.push({ start: from, end: to });
  }
  return intervals.filter(({ start: from, end }) => from !== null && end !== null && end > from);
}

function scheduleIntervals(pharmacy, start) {
  return (pharmacy.guardia_intervalos || []).map((interval) => {
    const from = wallMinutes(interval.inicio_original || interval.inicio);
    const end = wallMinutes(interval.fin_original || interval.fin);
    // Some sources clip duties at midnight; without the original end the duty may continue.
    const openEnded = !interval.fin_original && end !== null && end >= start + DAY - 1;
    return { start: from, end, openEnded };
  }).filter(({ start: from, end }) => from !== null && end !== null && end > from);
}

function coversNight(intervals, start) {
  return intervals.some((interval) => [start + NIGHT_START, start + DAY + NIGHT_START].some((window) =>
    interval.start <= window && (interval.openEnded || interval.end >= window + NIGHT_LENGTH)));
}

function keywordShift(text) {
  const folded = stripRanges(fold(text));
  if (NIGHT_WORDS.test(folded)) return 'nocturna';
  const until = UNTIL.exec(folded);
  if (until) return Number(until[1]) < 12 ? 'nocturna' : 'diurna';
  return DAY_WORDS.test(folded) ? 'diurna' : null;
}

function analyze(pharmacy, fallbackDate) {
  const start = dayStart(pharmacy.fecha_guardia) ?? dayStart(fallbackDate);
  if (start === null) return { start: null, intervals: [], complete: false, shift: null };
  const scheduled = scheduleIntervals(pharmacy, start);
  if (scheduled.length) {
    const words = [...textList(pharmacy), ...(pharmacy.guardia_intervalos || []).map((interval) => interval.tipo)];
    const night = coversNight(scheduled, start) || words.some((text) => keywordShift(text) === 'nocturna');
    return { start, intervals: scheduled, complete: true, shift: night ? 'nocturna' : 'diurna' };
  }
  const intervals = [];
  const shifts = [];
  let complete = true;
  for (const text of textList(pharmacy)) {
    const parsed = textIntervals(fold(text), start);
    if (parsed.length) {
      intervals.push(...parsed);
      shifts.push(coversNight(parsed, start) ? 'nocturna' : 'diurna');
    } else {
      complete = false;
      shifts.push(keywordShift(text));
    }
  }
  const shift = shifts.includes('nocturna') ? 'nocturna' : shifts.includes('diurna') ? 'diurna' : null;
  return { start, intervals, complete: complete && intervals.length > 0, shift };
}

export function getDutyShift(pharmacy, fallbackDate = null) {
  return analyze(pharmacy, fallbackDate).shift;
}

export function getOpenState(pharmacy, now, fallbackDate = null) {
  const { intervals, complete } = analyze(pharmacy, fallbackDate);
  if (intervals.some((interval) => interval.start <= now && now < interval.end)) return 'abierta';
  if (!complete || intervals.some((interval) => interval.openEnded && now >= interval.end)) return 'desconocida';
  return 'cerrada';
}

export function getOpenDuties(todayRows, yesterdayRows, now, date) {
  const result = new Map();
  for (const row of todayRows) {
    const state = getOpenState(row, now, date);
    if (state !== 'cerrada') result.set(pharmacyKey(row), { ...row, guardia_apertura: state });
  }
  const yesterday = shiftDate(date, -1);
  for (const row of yesterdayRows) {
    const key = pharmacyKey(row);
    if (result.get(key)?.guardia_apertura === 'abierta' || getOpenState(row, now, yesterday) !== 'abierta') continue;
    result.set(key, {
      ...row,
      guardia_tipo: getDutyShift(row, yesterday),
      guardia_apertura: 'abierta',
      guardia_desde_ayer: true,
    });
  }
  return [...result.values()];
}
