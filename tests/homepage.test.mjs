import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("La portada solo anuncia Lengua y conserva el enlace al control", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  assert.match(html, /class="exam-alert exam-alert-compact exam-alert-language" aria-labelledby="language-exam-alert-title"/);
  assert.match(html, /class="exam-announcements"/);
  assert.equal((html.match(/class="exam-alert-kicker">¡PRÓXIMO EXAMEN!/g) ?? []).length, 1);
  assert.doesNotMatch(html, /english-exam-alert-title|INGLÉS ACTUALIZADO/);
  assert.match(html, /CONTROL DE LENGUA · 4 DE NOVIEMBRE \(ACTUALIZADO · 21 DE OCTUBRE\)/);
  assert.match(html, /href="\.\/lengua-actual\.html">Preparar control de Lengua/);
});

test("La portada incluye Francés en naranja con un botón Próximamente desactivado", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  const cards = html.match(/<article class="mode-card"[\s\S]*?<\/article>/g) ?? [];
  assert.equal(cards.length, 5);
  const french = cards.find(card => card.includes('data-subject="french"'));
  assert.ok(french);
  assert.match(french, /<h3>Francés<\/h3>/);
  assert.match(french, /<button class="primary" type="button" disabled>Próximamente<\/button>/);
  assert.doesNotMatch(french, /href=/);
  assert.match(styles, /\.subject-grid \{ grid-template-columns: repeat\(5, minmax\(0, 1fr\)\); \}/);
  assert.match(styles, /\[data-subject="french"\]\.mode-card \.mode-icon \{ background: #fff0df; color: #a84c0a; \}/);
  assert.match(styles, /\[data-theme="dark"\] \[data-subject="french"\]/);
});

test("La portada destaca la actualización importante de Conocimiento del Medio", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  assert.match(html, /class="exam-alert exam-alert-compact exam-alert-science"[\s\S]*¡IMPORTANTE![\s\S]*CONOCIMIENTO DEL MEDIO · ACTUALIZADO[\s\S]*href="\.\/conocimiento-medio\.html">Ir a Conocimiento del Medio/);
});

test("La asignatura Conocimiento del Medio abre la nueva guía y conserva Historia como página anterior", () => {
  const home = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const newPage = readFileSync(new URL("../aula/conocimiento-medio.html", import.meta.url), "utf8");
  const previousPage = readFileSync(new URL("../aula/historia.html", import.meta.url), "utf8");

  assert.match(home, /<h3>Conocimiento del Medio<\/h3>[\s\S]*href="\.\/conocimiento-medio\.html">Explorar Conocimiento del Medio/);
  assert.match(newPage, /Taller de Historia de la Ciencia/);
  assert.match(newPage, /¿Qué es la mecánica\?/);
  assert.match(newPage, /¿Quién fue Aristóteles\?/);
  assert.match(newPage, /¿Qué pensaba sobre las esferas\?/);
  assert.match(newPage, /<footer>[\s\S]*href="\.\/historia\.html">Página anterior<\/a>/);
  assert.match(previousPage, /<title>Historia · Noé<\/title>/);
});
