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
