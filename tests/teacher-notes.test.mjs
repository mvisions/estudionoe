import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const html = read("../aula/index.html");

test("La portada incluye las notas de Matemáticas y Conocimiento del Medio", () => {
  assert.match(html, /Notas de la profesora/);
  assert.match(html, /Martes 20/);
  assert.match(html, /distributiva, potencias, estimaciones y combinadas/);
  assert.match(html, /página 39, ejercicios 6, 7 y 8/);
  assert.match(html, /Edad Media\. Entregarás el trabajo el jueves/);
  assert.match(html, /capítulo 5 de Mitos Griegos/);
  assert.match(html, /Tienes toda la semana para leerlo y realizar sus actividades/);
  assert.match(html, /se entregarán al finalizarlas/);
  assert.match(html, /ordena las páginas para no perderlas/);
});

test("Las notas completas están disponibles sin JavaScript y el duplicado no se anuncia", () => {
  assert.match(html, /<details class="teacher-notes-details">[\s\S]*<summary>Leer todas las notas sin movimiento<\/summary>[\s\S]*class="teacher-notes-list"/);
  assert.match(html, /id="teacher-notes-ticker" aria-hidden="true" hidden/);
  assert.match(html, /aria-controls="teacher-notes-ticker" hidden>Pausar movimiento/);
});

test("El módulo de las notas se carga y se incluye en el despliegue", () => {
  assert.match(html, /src="\.\.\/teacher-notes\.mjs"/);
  assert.match(read("../.github/workflows/deploy-pages.yml"), /cp teacher-notes\.mjs site\//);
});
