import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("La portada conserva el aviso de examen de Lengua y enlaza directamente al último test", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const announcement = html.match(/<section class="exam-alert exam-alert-compact exam-alert-language"[\s\S]*?<\/section>/)?.[0];
  assert.ok(announcement);
  assert.match(announcement, /aria-labelledby="language-exam-alert-title"/);
  assert.match(html, /class="exam-announcements"/);
  assert.equal((html.match(/class="exam-alert-kicker">¡PRÓXIMO EXAMEN!/g) ?? []).length, 1);
  assert.doesNotMatch(html, /english-exam-alert-title|INGLÉS ACTUALIZADO/);
  assert.match(html, /CONTROL DE LENGUA · 4 DE NOVIEMBRE \(ACTUALIZADO · 21 DE OCTUBRE\)/);
  assert.match(announcement, /href="\.\/test-diptongos\.html">Preparar control de Lengua/);
  assert.doesNotMatch(html, /href="\.\/lengua-actual\.html"/);
});

test("Los avisos abren la última página de cada asignatura y las tarjetas conservan los índices", () => {
  const homeUrl = new URL("../aula/index.html", import.meta.url);
  const html = readFileSync(homeUrl, "utf8");
  const cards = html.match(/<article class="mode-card"[\s\S]*?<\/article>/g) ?? [];
  for (const [alert, subject] of [
    ["science", "conocimiento-medio"],
    ["math", "matematicas"],
    ["language", "lengua"],
    ["english", "ingles"],
  ]) {
    const announcement = html.match(new RegExp(`<section class="exam-alert exam-alert-compact exam-alert-${alert}"[\\s\\S]*?<\\/section>`))?.[0];
    const announcementLink = announcement?.match(/<a href="([^"]+)"/)?.[1];
    const indexUrl = new URL(`./${subject}/index.html`, homeUrl);
    const index = readFileSync(indexUrl, "utf8");
    const list = index.match(/<ol class="subject-index-list">[\s\S]*?<\/ol>/)?.[0];
    assert.ok(list, `${subject}: debe tener una lista cronológica`);
    const latestLink = [...list.matchAll(/<a href="([^"]+)"/g)].at(-1)?.[1];
    assert.ok(latestLink, `${subject}: debe tener una página publicada`);
    assert.ok(announcementLink, `${subject}: debe tener un enlace en el aviso`);
    assert.equal(new URL(announcementLink, homeUrl).href, new URL(latestLink, indexUrl).href, `${subject}: el aviso debe abrir la última página`);
    assert.ok(cards.some(card => card.includes(`href="./${subject}/"`)), `${subject}: la tarjeta debe abrir el índice`);
  }
});

test("La portada anuncia la gramática de Inglés con la fecha y el enlace directo", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const announcement = html.match(/<section class="exam-alert exam-alert-compact exam-alert-english"[\s\S]*?<\/section>/)?.[0];
  assert.ok(announcement);
  assert.match(announcement, /aria-labelledby="english-grammar-alert-title"/);
  assert.match(announcement, /id="english-grammar-alert-title"[^>]*>INGLÉS · ACTUALIZADO · <time datetime="2026-10-26">26 DE OCTUBRE<\/time>/);
  assert.match(announcement, /To be, to have y pronombres posesivos/);
  assert.match(announcement, /vídeos y test con ranking/);
  assert.match(announcement, /href="\.\/ingles-gramatica\.html">Repasar gramática de Inglés/);
});

test("La portada incluye Francés en naranja con un botón Próximamente desactivado", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  const cards = html.match(/<article class="mode-card"[\s\S]*?<\/article>/g) ?? [];
  assert.equal(cards.length, 6);
  const french = cards.find(card => card.includes('data-subject="french"'));
  assert.ok(french);
  assert.match(french, /<h3>Francés<\/h3>/);
  assert.match(french, /<button class="primary" type="button" disabled>Próximamente<\/button>/);
  assert.doesNotMatch(french, /href=/);
  assert.match(styles, /\.subject-grid \{ grid-template-columns: repeat\(auto-fit, minmax\(min\(100%, 260px\), 1fr\)\); gap: 20px; \}/);
  assert.match(styles, /\.subject-grid \.mode-card \{[\s\S]*?min-height: 310px;[\s\S]*?border-top: 4px solid var\(--subject-accent\);/);
  assert.match(styles, /\.subject-grid \[data-subject="math"\]\.mode-card \{ --subject-accent: #527ba5; \}/);
  assert.match(styles, /\[data-subject="french"\]\.mode-card \.mode-icon \{ background: #fff0df; color: #a84c0a; \}/);
  assert.match(styles, /\[data-theme="dark"\] \[data-subject="french"\]/);
  assert.match(styles, /\[data-theme="dark"\] \.subject-grid \[data-subject="french"\]\.mode-card \{ --subject-accent: #ffc18a; \}/);
});

test("La portada destaca la actualización importante de Conocimiento del Medio", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const announcement = html.match(/<section class="exam-alert exam-alert-compact exam-alert-science"[\s\S]*?<\/section>/)?.[0];
  assert.ok(announcement);
  assert.match(announcement, /¡IMPORTANTE![\s\S]*CONOCIMIENTO DEL MEDIO · ACTUALIZADO/);
  assert.match(announcement, /href="\.\/conocimiento-medio-copernico\.html">Ir a De Aristóteles a Copérnico/);
  assert.doesNotMatch(html, /href="\.\/conocimiento-medio\.html"/);
});

test("El índice de Conocimiento del Medio enlaza la nueva guía y conserva Historia", () => {
  const home = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const newPage = readFileSync(new URL("../aula/conocimiento-medio.html", import.meta.url), "utf8");
  const previousPage = readFileSync(new URL("../aula/historia.html", import.meta.url), "utf8");

  assert.match(home, /<h3>Conocimiento del Medio<\/h3>[\s\S]*href="\.\/conocimiento-medio\/">Ver índice de Conocimiento del Medio/);
  assert.match(newPage, /Taller de Historia de la Ciencia/);
  assert.match(newPage, /¿Qué es la mecánica\?/);
  assert.match(newPage, /¿Quién fue Aristóteles\?/);
  assert.match(newPage, /¿Qué pensaba sobre las esferas\?/);
  assert.match(newPage, /<footer>[\s\S]*href="\.\/conocimiento-medio\/">Índice de Conocimiento del Medio<\/a>/);
  assert.match(previousPage, /<title>Historia · Noé<\/title>/);
});

test("La portada anuncia la hoja de múltiplos del 3 de noviembre en azul", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  const announcement = html.match(/<section class="exam-alert exam-alert-compact exam-alert-math"[\s\S]*?<\/section>/)?.[0];
  assert.ok(announcement);
  assert.match(announcement, /id="math-alert-title"[^>]*>MATEMÁTICAS · MÚLTIPLOS · <time datetime="2026-11-03">3 DE NOVIEMBRE<\/time>/);
  assert.match(announcement, /href="\.\/matematicas-multiplos\.html">Ir a la hoja de múltiplos/);
  assert.match(html, /<h3>Matemáticas<\/h3>[\s\S]*href="\.\/matematicas\/">Ver índice de Matemáticas/);
  assert.match(html, /id="science-alert-title"[^>]*>CONOCIMIENTO DEL MEDIO · ACTUALIZADO · <time datetime="2026-11-03">/);
  assert.match(styles, /\.exam-alert\.exam-alert-math \{/);
  assert.match(html, /styles\.css\?v=20261103-worksheets/);
});
