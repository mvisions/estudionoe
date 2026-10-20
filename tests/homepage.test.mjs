import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("Los anuncios de exámenes comparten el formato y conservan sus enlaces", () => {
  const html = readFileSync(new URL("../aula/index.html", import.meta.url), "utf8");
  assert.match(html, /class="exam-alert exam-alert-compact" aria-labelledby="english-exam-alert-title"/);
  assert.match(html, /class="exam-alert exam-alert-compact exam-alert-language" aria-labelledby="language-exam-alert-title"/);
  assert.match(html, /class="exam-announcements"/);
  assert.equal((html.match(/class="exam-alert-kicker">¡PRÓXIMO EXAMEN!/g) ?? []).length, 2);
  assert.match(html, /href="\.\/ingles\.html">Empezar a estudiar Inglés/);
  assert.match(html, /href="\.\/lengua-actual\.html">Preparar control de Lengua/);
});
