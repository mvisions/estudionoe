import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("La portada comunica la actualización de Francés en el aviso superior", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const announcement = html.match(/<section class="exam-alert exam-alert-compact exam-alert-french"[\s\S]*?<\/section>/)?.[0];
  assert.ok(announcement);
  assert.match(announcement, /aria-labelledby="french-alert-title"/);
  assert.match(html, /class="exam-announcements"/);
  assert.equal((html.match(/class="exam-alert exam-alert-compact/g) ?? []).length, 1);
  assert.match(announcement, /FRANCÉS · ACTUALIZADO · <time datetime="2026-11-24">24 DE NOVIEMBRE<\/time>/);
  assert.match(announcement, /Números del 1 al 10/);
  assert.match(announcement, /href="\.\/frances-numeros\.html">Empezar Francés/);
  assert.doesNotMatch(html, /exam-alert-science|exam-alert-math|exam-alert-language|exam-alert-english/);
});

test("La portada conserva el índice de Francés como acceso de la asignatura", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  const cards = html.match(/<article class="mode-card"[\s\S]*?<\/article>/g) ?? [];
  assert.equal(cards.length, 6);
  const french = cards.find(card => card.includes('data-subject="french"'));
  assert.ok(french);
  assert.match(french, /<h3>Francés<\/h3>/);
  assert.match(french, /href="\.\/frances\/">Ver índice de Francés/);
  assert.doesNotMatch(french, /Próximamente/);
  assert.match(styles, /\.subject-grid \{ grid-template-columns: repeat\(auto-fit, minmax\(min\(100%, 260px\), 1fr\)\); gap: 20px; \}/);
  assert.match(styles, /\.subject-grid \.mode-card \{[\s\S]*?min-height: 310px;[\s\S]*?border-top: 4px solid var\(--subject-accent\);/);
  assert.match(styles, /\.subject-grid \[data-subject="math"\]\.mode-card \{ --subject-accent: #527ba5; \}/);
  assert.match(styles, /\[data-subject="french"\]\.mode-card \.mode-icon \{ background: #fff0df; color: #a84c0a; \}/);
  assert.match(styles, /\[data-subject="french"\]\.mode-card \.primary \{ background: #a84c0a; border-color: #a84c0a; color: white; \}/);
  assert.match(styles, /\[data-theme="dark"\] \[data-subject="french"\]/);
  assert.match(styles, /\[data-theme="dark"\] \.subject-grid \[data-subject="french"\]\.mode-card \{ --subject-accent: #ffc18a; \}/);
});

test("La portada muestra la ardilla 3D con fondo transparente", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  const mascot = readFileSync(new URL("../aula/ardilla-3d.png", import.meta.url));

  assert.match(html, /styles\.css\?v=20261124-french/);
  assert.match(html, /<img class="hero-mascot" src="\.\/ardilla-3d\.png" alt="">/);
  assert.equal(mascot.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.match(styles, /\.hero-mascot \{[^}]*max-height: 340px/);
  assert.match(styles, /@media \(max-width: 760px\) \{[\s\S]*?\.hero-mascot \{[^}]*max-height: 285px/);
});
