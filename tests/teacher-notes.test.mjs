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

test("La portada abre un índice numerado con las notas anteriores y las de cada día", () => {
  const home = read("../aula/index.html");
  const index = read("../aula/notas/index.html");
  assert.match(home, /<article class="mode-card" data-subject="notes">[\s\S]*<h3>Notas de la profesora<\/h3>[\s\S]*href="\.\/notas\/"/);
  assert.match(home, /Las más recientes son las del miércoles 4 de noviembre\./);
  assert.doesNotMatch(home, /teacher-notes-ticker|teacher-notes\.mjs|class="teacher-notes"/);
  assert.match(index, /<ol class="subject-index-list">/);
  const links = [...index.matchAll(/<li>\s*<a href="([^"]+)"/g)].map(([, href]) => href);
  assert.deepEqual(links, ["./anteriores.html", "./2026-10-26.html", "./2026-10-27.html", "./2026-11-03.html", "./2026-11-04.html"]);
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

test("Las notas del martes 27 incluyen las actividades y todos los materiales del taller", () => {
  const tuesday = read("../aula/notas/2026-10-27.html");
  for (const content of [
    'datetime="2026-10-27"', "AGENDA 5ºC", "Control tema 2.",
    "Cono", "Tema 10.", "Actividad de inicio.",
    "los tres vídeos de Classroom Sociales", "los cambios de la Edad Moderna en el mundo",
    "la conquista de las Américas", "los pueblos que vivían allí al llegar Colón",
    "Practicaremos la escucha activa", "extraer información relevante",
    "realizar en libreta un esquema de ese contenido",
    "polímeros de la tela de araña", "100 ml de cola blanca escolar (PVA)",
    "35 ml de agua templada", "la seño la calentará en el cole",
    "1 cucharada de almidón de maíz (Maizena)",
    "1 cucharadita de jabón líquido para platos",
    "1 biberón de cocina de plástico blando (o jeringa de 50 ml sin aguja)",
    "1 cartulina negra o bandeja de plástico", "1 palito de madera para mezclar",
    "ESTOS MATERIALES COMPLETAN LA BASE DEL TALLER DE OCTUBRE.",
  ]) assert.ok(tuesday.includes(content), content);
  assert.equal((tuesday.match(/<li>/g) ?? []).length, 7);
});

test("Las notas del martes 3 recogen el texto de la profesora y enlazan las nuevas hojas", () => {
  const tuesday = read("../aula/notas/2026-11-03.html");
  for (const content of [
    'datetime="2026-11-03"', "Mates", "Corregimos ejercicios del jueves pasado.",
    "los múltiplos son los «resultados» de las tablas de multiplicar",
    "Hoy en clase pág 42 ej 3.", "Pág 44. Ej 1.", "Cono",
    "Taller de Ciencias: experimentamos con Aristóteles.",
    "La Edad moderna y sus descubrimientos.", "¿Quién fue Nicolás Copérnico?",
    'href="../matematicas-multiplos.html"', 'href="../conocimiento-medio-copernico.html"',
  ]) assert.ok(tuesday.includes(content), content);
});

test("Las notas del miércoles 4 conservan el control, la lectura y las tareas de Plástica", () => {
  const wednesday = read("../aula/notas/2026-11-04.html");
  for (const content of [
    "<h1>Miércoles 4 de noviembre</h1>", 'datetime="2026-11-04"',
    '<h2 id="language-notes-title">LENGUA</h2>',
    "** Control dictados y regla tema 3.",
    "Al terminar, lectura de Mitos Griegos.",
    "Capítulos: hasta Edipo y el enigma de la Esfinge incluido .",
    "Recuerda y adjuntando de cada capítulo leído, las respuestas a las actividades del final del libro.",
    "Se entregarán todas juntas al finalizar la lectura completa del libro.",
    '<h2 id="art-notes-title">PLÁSTICA</h2>',
    "Continuamos Taller de Ciencias.",
    "Mañana en la clase de ordenador buscaremos a Copérnico y a Galileo.",
  ]) assert.ok(wednesday.includes(content), content);
  assert.equal((wednesday.match(/<section /g) ?? []).length, 2);
});

test("Las páginas de notas son estáticas, permiten volver al índice y se publican", () => {
  for (const page of ["index.html", "anteriores.html", "2026-10-26.html", "2026-10-27.html", "2026-11-03.html", "2026-11-04.html"]) {
    const notes = read(`../aula/notas/${page}`);
    assert.match(notes, /<html lang="es" data-subject="notes">/);
    assert.match(notes, /name="theme-color" content="#754399"/);
    assert.match(notes, /id="theme-toggle"/);
    assert.match(notes, /src="\.\.\/\.\.\/pet-companion\.mjs\?v=[^"]+"/);
    assert.match(notes, /src="\.\.\/\.\.\/visitor-tracker\.mjs"/);
  }
  for (const page of ["anteriores.html", "2026-10-26.html", "2026-10-27.html", "2026-11-03.html", "2026-11-04.html"]) {
    const notes = read(`../aula/notas/${page}`);
    assert.match(notes, /href="\.\/">Índice de notas<\/a>/);
    assert.match(notes, /src="\.\.\/subject-index\.mjs"/);
    assert.doesNotMatch(notes, /<details|teacher-notes-ticker/);
  }
  assert.match(read("../.github/workflows/deploy-pages.yml"), /cp -R aula site\//);
});
