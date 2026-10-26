import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const html = read("../aula/notas/anteriores.html");

test("Las notas anteriores conservan el contenido que estaba en la portada", () => {
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

test("La portada abre un índice numerado con las notas anteriores y las del lunes 26", () => {
  const home = read("../aula/index.html");
  const index = read("../aula/notas/index.html");
  assert.match(home, /<article class="mode-card" data-subject="notes">[\s\S]*<h3>Notas de la profesora<\/h3>[\s\S]*href="\.\/notas\/"/);
  assert.doesNotMatch(home, /teacher-notes-ticker|teacher-notes\.mjs|class="teacher-notes"/);
  assert.match(index, /<ol class="subject-index-list">/);
  const links = [...index.matchAll(/<li>\s*<a href="([^"]+)"/g)].map(([, href]) => href);
  assert.deepEqual(links, ["./anteriores.html", "./2026-10-26.html"]);
  assert.doesNotMatch(index, /class="mode-card"/);
});

test("Las notas del lunes 26 incluyen todas las tareas, materiales y recordatorios", () => {
  const monday = read("../aula/notas/2026-10-26.html");
  for (const content of [
    'datetime="2026-10-26"', "pág 57", "control del tema 2 de mañana",
    "Distributiva, operaciones combinadas, cálculo, potencias y problemas",
    "pág 48 ejercicio 10", "pág 43", "ejercicios del 1 al 5",
    "polímeros de la tela de araña", "100 ml de cola blanca escolar (PVA)",
    "35 ml de agua templada", "la seño la calentará en el cole",
    "1 cucharada de almidón de maíz (Maizena)",
    "1 cucharadita de jabón líquido para platos",
    "1 biberón de cocina de plástico blando (o jeringa de 50 ml sin aguja)",
    "1 cartulina negra o bandeja de plástico", "1 palito de madera para mezclar",
    "Halloween", "videoclip del tercer ciclo", "se grabará para el cole",
    "capítulo 6 y las actividades de Mitos Griegos",
  ]) assert.ok(monday.includes(content), content);
  assert.equal((monday.match(/<li>/g) ?? []).length, 7);
});

test("Las páginas de notas son estáticas, permiten volver al índice y se publican", () => {
  for (const page of ["index.html", "anteriores.html", "2026-10-26.html"]) {
    const notes = read(`../aula/notas/${page}`);
    assert.match(notes, /<html lang="es" data-subject="notes">/);
    assert.match(notes, /name="theme-color" content="#754399"/);
  }
  for (const page of ["anteriores.html", "2026-10-26.html"]) {
    const notes = read(`../aula/notas/${page}`);
    assert.match(notes, /href="\.\/">Índice de notas<\/a>/);
    assert.match(notes, /src="\.\.\/subject-index\.mjs"/);
    assert.doesNotMatch(notes, /<details|teacher-notes-ticker/);
  }
  assert.match(read("../.github/workflows/deploy-pages.yml"), /cp -R aula site\//);
});
