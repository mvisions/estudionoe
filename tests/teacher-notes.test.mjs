import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const html = read("../aula/index.html");

test("La portada muestra las notas nuevas de las tres asignaturas", () => {
  assert.match(html, /Notas de la profesora/);
  assert.match(html, /Repaso general de ejercicios de todo el tema/);
  assert.match(html, /Página 46: el sustantivo y el adjetivo/);
  assert.match(html, /definiciones resumidas y ejemplos/);
  assert.match(html, /Hoy se entrega el trabajo de la Edad Media/);
  assert.match(html, /Taller de Historia de la Ciencia/);
  assert.match(html, /¿Qué es la mecánica\?/);
  assert.match(html, /¿Quién fue Aristóteles\?/);
  assert.match(html, /¿Qué teoría tenía sobre «las esferas»\?/);
  assert.match(html, /<h3>Inglés<\/h3>[\s\S]*hoja de vocabulario de la libreta[\s\S]*tabla de los posesivos[\s\S]*Activity Book, página 7/);
  assert.match(html, /Paula Corrales: 2 camisetas talla 11-12/);
  assert.match(html, /Verónica Kovalchuk: sudadera \(S\) y camiseta \(S\)/);
  assert.doesNotMatch(html, /Martes 20|22\/10\/2026|María Madre/);
  assert.doesNotMatch(html, /distributiva, potencias, estimaciones y combinadas|página 39, ejercicios 6, 7 y 8|capítulo 5 de Mitos Griegos/);
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
