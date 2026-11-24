import assert from 'node:assert/strict';
import test from 'node:test';
import { getDutyShift, getOpenDuties, getOpenState, madridNow, shiftDate, wallMinutes } from './horarios.js';

const DATE = '2026-11-01';
const at = (time, date = DATE) => wallMinutes(`${date}T${time}`);
const textDuty = (...franjas) => ({ id: franjas.join('|'), fecha_guardia: DATE, guardia_franjas: franjas });
const intervalDuty = (...intervalos) => ({ id: JSON.stringify(intervalos), fecha_guardia: DATE, guardia_intervalos: intervalos });

test('official night texts and explicit overnight hours are night or 24 h duties', () => {
  for (const text of [
    'Noche (de 22:00 a 09:30)',
    'noche (22:00-9:30)',
    'todo el dia (9:30-9:30)',
    'FARMACIA DE GUARDIA TODA LA NOCHE',
    'FARMACIA DE GUARDIA EN HORARIO DE DE 22:00 DE LA NOCHE A 9:30 DEL DIA SIGUIENTE',
    'FARMACIA DE GUARDIA DESDE LAS 22:00 HORAS HASTA LAS 9:30 DE MAÑANA',
    'Nocturna capital: 22:00–09:30; sábados, domingos y festivos hasta 10:00 del día siguiente',
    'Día y noche: 24 horas según el cuadro provincial.',
    'Guardia de 24 horas; semana del 2026-10-26',
    '24 horas (9:30-9:30 del día siguiente)',
    'Guardia del 2026-10-26 9:30 al 2026-11-02 9:30',
    'Desde 2026-10-26 hasta 2026-11-02; horario no especificado por la fuente · Guardia nocturna localizada',
    'Madrugada: guardia nocturna/24h del día anterior; confirmar hora de cierre.',
    'Farmacia 24 horas',
  ]) {
    assert.equal(getDutyShift(textDuty(text)), 'nocturna', text);
  }
  assert.equal(getDutyShift(textDuty('Día (de 9:30 a 22:00)', 'Noche (de 22:00 a 09:30)')), 'nocturna');
});

test('daytime hours stay daytime even when the closing time says "de la noche"', () => {
  for (const text of [
    'Día (de 9:30 a 22:00); (Hasta las 21:00)',
    'dia (9:30-22:00)',
    'FARMACIA DE GUARDIA EN HORARIO DE 9:30 DE LA MAÑANA A 22:00 DE LA NOCHE',
    'FARMACIA DE GUARDIA HASTA LAS 22:00 HORAS',
    'DIURNO ( 9:30 A 22:00 HORAS)',
    'Diurna capital: laborables 09:30–22:00; sábados, domingos y festivos 10:00–22:00',
    'Diurna provincial: hasta las 22:00; confirmar hora de inicio.',
  ]) {
    assert.equal(getDutyShift(textDuty(text)), 'diurna', text);
  }
});

test('duties without a published schedule are not guessed', () => {
  for (const text of [
    'Guardia fechada según CGCOF; consultar horas del cartel y confirmar por teléfono.',
    'Desde 2026-10-26 hasta 2026-11-02; horario no especificado por la fuente · Guardia localizada',
    'Guardia según calendario municipal; consultar horario del cartel y confirmar por teléfono · *GUARDIAS LOCALIZADAS (NO PRESENCIALES) DE LUNES A SÁBADO A MEDIODÍA',
    'Guardia publicada para la fecha; horario oficial inválido, confirmar por teléfono',
    'Fuente: desde 21, hasta 10; horario y cambio de fecha pendientes de confirmar.',
  ]) {
    assert.equal(getDutyShift(textDuty(text)), null, text);
  }
  assert.equal(getDutyShift({ fecha_guardia: DATE }), null);
  assert.equal(getOpenState(textDuty('Fuente: desde 21, hasta 10; horario y cambio de fecha pendientes de confirmar.'), at('08:00')), 'desconocida');
});

test('structured intervals use original times and midnight clipping', () => {
  assert.equal(getDutyShift(intervalDuty(
    { inicio: '2026-11-01T00:00:00+01:00', fin: '2026-11-01T09:00:00+01:00' },
  )), 'nocturna');
  assert.equal(getDutyShift(intervalDuty({
    inicio: '2026-11-01T09:00', fin: '2026-11-02T00:00',
    inicio_original: '2026-11-01T09:00', fin_original: '2026-11-02T09:00',
  })), 'nocturna');
  assert.equal(getDutyShift(intervalDuty({
    inicio: '2026-11-01T09:30', fin: '2026-11-01T23:00',
    inicio_original: '2026-11-01T09:30', fin_original: '2026-11-01T23:00',
  })), 'diurna');
  assert.equal(getDutyShift(intervalDuty({ inicio: '2026-11-01T09:00', fin: '2026-11-01T23:59' })), 'nocturna');
  assert.equal(getDutyShift(intervalDuty({ inicio: '2026-11-01T09:00', fin: '2026-11-01T21:00' })), 'diurna');
  assert.equal(getDutyShift({
    ...intervalDuty({ inicio: '2026-11-01T09:00', fin: '2026-11-01T22:00', tipo: 'DIURNO (De 9 a 22 h)/NOCTURNO: LOCALIZADA' }),
    guardia_franjas: ['DIURNO (De 9 a 22 h)/NOCTURNO: LOCALIZADA: 01/11 09:00–01/11 22:00'],
  }), 'nocturna');
  assert.equal(getDutyShift({
    ...intervalDuty({ inicio: '2026-11-01T09:00', fin: '2026-11-01T22:00', tipo: 'SERVICIO DIURNO (de 09,00 h a 22,00 h)' }),
    guardia_franjas: ['SERVICIO DIURNO (de 09,00 h a 22,00 h): 01/11 09:00–01/11 22:00'],
  }), 'diurna');
});

test('open state compares Madrid wall time with each duty schedule', () => {
  const night = textDuty('Noche (de 22:00 a 09:30)');
  assert.equal(getOpenState(night, at('23:00')), 'abierta');
  assert.equal(getOpenState(night, at('03:00')), 'cerrada');
  assert.equal(getOpenState(night, at('03:00', '2026-11-02')), 'abierta');
  assert.equal(getOpenState(textDuty('FARMACIA DE GUARDIA TODA LA NOCHE'), at('23:00')), 'desconocida');
  const alicante = intervalDuty({ inicio: '2026-11-01T09:00:00+01:00', fin: '2026-11-02T09:00:00+01:00' });
  assert.equal(getOpenState(alicante, at('08:59')), 'cerrada');
  assert.equal(getOpenState(alicante, at('09:00')), 'abierta');
  const clipped = intervalDuty({ inicio: '2026-11-01T21:00', fin: '2026-11-01T23:59' });
  assert.equal(getOpenState(clipped, at('03:00', '2026-11-02')), 'desconocida');
});

test('open duties include last night duties that are still running', () => {
  const yesterdayNight = { ...textDuty('Noche (de 22:00 a 09:30)'), id: 'ayer', fecha_guardia: '2026-10-31' };
  const yesterdayDay = { ...textDuty('Día (de 9:30 a 22:00)'), id: 'ayer-dia', fecha_guardia: '2026-10-31' };
  const todayNight = { ...textDuty('Noche (de 22:00 a 09:30)'), id: 'hoy' };
  const unknown = { ...textDuty('Guardia fechada según CGCOF; consultar horas del cartel.'), id: 'sin-horario' };
  const open = getOpenDuties([todayNight, unknown], [yesterdayNight, yesterdayDay], at('03:00'), DATE);
  assert.deepEqual(open.map(({ id, guardia_apertura: state, guardia_desde_ayer: fromYesterday }) =>
    [id, state, fromYesterday === true]), [
    ['sin-horario', 'desconocida', false],
    ['ayer', 'abierta', true],
  ]);
  assert.equal(open[1].guardia_tipo, 'nocturna');
});

test('Madrid wall time follows winter and summer offsets', () => {
  assert.deepEqual(madridNow(new Date('2026-11-01T22:30:00Z')), {
    date: '2026-11-01', time: '23:30', minutes: at('23:30'),
  });
  assert.equal(madridNow(new Date('2026-07-01T22:30:00Z')).date, '2026-07-02');
  assert.equal(madridNow(new Date('2026-07-01T22:30:00Z')).time, '00:30');
  assert.equal(shiftDate('2026-03-01', -1), '2026-02-28');
});
