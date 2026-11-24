import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchDutyCoverage } from './dutyCoverage.js';

test('reads valid coverage with the requested date and abort signal', async () => {
  const controller = new AbortController();
  const coverage = { consultas: [{ estado: 'parcial', nombre: 'Palma' }] };
  const response = await fetchDutyCoverage('Baleares', 'baleares', '2026-11-02', controller.signal, async (url, options) => {
    assert.equal(url, '/data/cobertura-baleares-2026-11-02.json');
    assert.equal(options.signal, controller.signal);
    return new Response(JSON.stringify(coverage), { headers: { 'content-type': 'application/json' } });
  });
  assert.deepEqual(response, { coverage, error: '' });
});

test('reports unavailable and malformed coverage without discarding the calendar', async () => {
  const responses = [
    () => new Response('', { status: 503 }),
    () => new Response('<html></html>', { headers: { 'content-type': 'text/html' } }),
    () => new Response('{bad', { headers: { 'content-type': 'application/json' } }),
    () => new Response('{}', { headers: { 'content-type': 'application/json' } }),
    () => Promise.reject(new TypeError('Error de red')),
  ];
  for (const fetchData of responses) {
    const result = await fetchDutyCoverage('Baleares', 'baleares', '2026-11-02', undefined, fetchData);
    assert.equal(result.coverage, null);
    assert.match(result.error, /^Baleares: no se pudo consultar la cobertura \(.+\)\.$/);
  }
});

test('propagates cancellation instead of reporting it as a coverage failure', async () => {
  const abort = new DOMException('Cancelado', 'AbortError');
  await assert.rejects(
    fetchDutyCoverage('Baleares', 'baleares', '2026-11-02', undefined, async () => { throw abort; }),
    (error) => error === abort,
  );
});
