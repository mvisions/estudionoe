import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { scienceQuestions, gradeScienceQuiz } from "../science-quiz.mjs";

test("El test cubre las tres preguntas de la profesora con opciones y explicaciones", () => {
  assert.equal(scienceQuestions.length, 9);
  assert.equal(new Set(scienceQuestions.map(question => question.id)).size, 9);
  for (const topic of ["mecanica", "aristoteles", "esferas"]) {
    assert.equal(scienceQuestions.filter(question => question.topic === topic).length, 3);
  }
  for (const question of scienceQuestions) {
    assert.equal(new Set(question.options).size, 3);
    assert.ok(Number.isInteger(question.answer) && question.answer >= 0 && question.answer < 3);
    assert.ok(question.explanation.length > 40);
  }
});

test("La corrección puntúa aciertos, errores y respuestas vacías y permite repasar fallos", () => {
  const answers = Object.fromEntries(scienceQuestions.map(question => [question.id, question.answer]));
  assert.equal(gradeScienceQuiz(scienceQuestions, answers).grade, 10);
  const empty = gradeScienceQuiz(scienceQuestions, {});
  assert.equal(empty.score, 0);
  assert.equal(empty.results.filter(result => !result.correct).length, 9);
  answers[scienceQuestions[0].id] = (scienceQuestions[0].answer + 1) % 3;
  delete answers[scienceQuestions[1].id];
  const mixed = gradeScienceQuiz(scienceQuestions, answers);
  assert.equal(mixed.score, 7);
  assert.equal(mixed.total, 9);
  const mistakes = mixed.results.filter(result => !result.correct).map(result => result.question);
  assert.equal(mistakes.length, 2);
  assert.equal(gradeScienceQuiz(mistakes, Object.fromEntries(mistakes.map(question => [question.id, question.answer]))).grade, 10);
});

test("El enlace Página anterior está al final y el test se publica con la página", () => {
  const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
  const html = read("../aula/conocimiento-medio.html");
  assert.match(html, /<footer>[\s\S]*href="\.\/historia\.html">Página anterior<\/a>[\s\S]*<\/footer>/);
  assert.equal((html.match(/href="\.\/historia\.html"/g) ?? []).length, 1);
  assert.match(html, /id="science-quiz" hidden/);
  assert.match(html, /src="\.\.\/science-quiz\.mjs"/);
  assert.match(read("../.github/workflows/deploy-pages.yml"), /cp science-quiz\.mjs site\//);
});

test("El vídeo aparece incrustado directamente y ofrece un enlace alternativo", () => {
  const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
  const html = read("../aula/conocimiento-medio.html");
  assert.match(html, /4 minutos y 5 segundos/);
  assert.match(html, /href="https:\/\/www.youtube.com\/watch\?v=Wr3p0U2_nqU"/);
  assert.match(html, /<div class="science-video">\s*<iframe src="https:\/\/www.youtube-nocookie.com\/embed\/Wr3p0U2_nqU"[^>]*referrerpolicy="strict-origin-when-cross-origin"/);
  assert.doesNotMatch(html, /load-aristotle-video|science-video\.mjs/);
});

test("El test completo de Conocimiento del Medio ofrece participar en el ranking", () => {
  const source = readFileSync(new URL("../science-quiz.mjs", import.meta.url), "utf8");
  assert.match(source, /offerActivityRanking\(section, \{\s*activity: "science-forces"/);
  assert.match(source, /if \(!unanswered && !practice\)/);
});
