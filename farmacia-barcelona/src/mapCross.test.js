import test from 'node:test';
import assert from 'node:assert/strict';
import { pharmacyCrossPath, pharmacyCrossVertices } from './mapCross.js';

test('canvas and SVG crosses share the same centered geometry', () => {
  const vertices = pharmacyCrossVertices(10);
  assert.equal(vertices.length, 12);
  assert.deepEqual(vertices[0], [-10 * 0.34, -10]);
  assert.deepEqual(vertices[6], [10 * 0.34, 10]);
  const path = pharmacyCrossPath({ x: 20, y: 30 }, 10);
  const expected = vertices.map(([x, y], i) => `${i ? 'L' : 'M'}${20 + x},${30 + y}`).join(' ') + ' Z';
  assert.equal(path, expected);
  assert.ok(path.startsWith('M16.6,20 '));
  assert.ok(path.endsWith(' Z'));
});
