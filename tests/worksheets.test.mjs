import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { multiplesOf, multiplesQuestions } from "../aula/multiplos-questions.mjs";
import { copernicusQuestions } from "../aula/copernico-questions.mjs";
import { feedbackText, gradeWorksheet, parseNumberList, renderWorksheetQuestions } from "../aula/worksheet-quiz.mjs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const isMultiple = (value, number) => value % number === 0;
const range = (from, to) => Array.from({ length: to - from + 1 }, (_, index) => from + index);
const correctAnswers = questions => Object.fromEntries(questions.map(question => [
  question.id,
  question.type === "list" ? question.answer.join(", ")
    : question.type === "mark" ? question.answer.map(String)
      : String(question.answer),
]));

test("Las soluciones de la hoja de múltiplos son correctas", () => {
  const byId = Object.fromEntries(multiplesQuestions.map(question => [question.id, question]));
  assert.equal(multiplesQuestions.length, 15);
  assert.equal(new Set(multiplesQuestions.map(question => question.id)).size, 15);

  assert.deepEqual(byId["primeros-7"].answer, range(1, 35).filter(value => isMultiple(value, 7)).slice(0, 5));
  assert.deepEqual(byId["entre-4"].answer, range(10, 30).filter(value => isMultiple(value, 4)));
  assert.deepEqual(byId["entre-9"].answer, range(50, 100).filter(value => isMultiple(value, 9)));
  assert.deepEqual(byId["marca-3"].answer, byId["marca-3"].options.filter(value => isMultiple(value, 3)));
  assert.deepEqual(byId["marca-6"].answer, byId["marca-6"].options.filter(value => isMultiple(value, 6)));

  const yesNo = { "48-de-6": [48, 6], "34-de-4": [34, 4], "50-de-3": [50, 3], "0-de-5": [0, 5] };
  for (const [id, [value, number]] of Object.entries(yesNo))
    assert.equal(byId[id].answer, isMultiple(value, number) ? 0 : 1, id);

  const options = id => byId[id].options.map(option => Number.parseInt(option, 10));
  assert.deepEqual(options("multiplo-8").map((value, index) => isMultiple(value, 8) === (index === byId["multiplo-8"].answer)), [true, true, true]);
  assert.deepEqual(options("no-multiplo-5").map((value, index) => isMultiple(value, 5) !== (index === byId["no-multiplo-5"].answer)), [true, true, true]);
  assert.deepEqual(options("72-es-multiplo").map((number, index) => isMultiple(72, number) === (index === byId["72-es-multiplo"].answer)), [true, true, true]);
  assert.deepEqual(options("huevos").map((value, index) => isMultiple(value, 12) === (index === byId.huevos.answer)), [true, true, true]);
  assert.deepEqual(options("reto-2-y-3").map((value, index) => (isMultiple(value, 2) && isMultiple(value, 3)) === (index === byId["reto-2-y-3"].answer)), [true, true, true]);
  assert.equal(6 * byId["completa-54"].answer, 54);

  for (const question of multiplesQuestions) assert.ok(question.explanation.length > 40, question.id);
  assert.deepEqual(multiplesOf(4, { from: 10, to: 30 }), [12, 16, 20, 24, 28]);
  assert.equal(multiplesOf(7).length, 14);
});

test("El test de Copérnico tiene tres preguntas por tema con explicaciones", () => {
  assert.equal(copernicusQuestions.length, 9);
  assert.equal(new Set(copernicusQuestions.map(question => question.id)).size, 9);
  for (const topic of ["edad-moderna", "copernico", "experimento"])
    assert.equal(copernicusQuestions.filter(question => question.topic === topic).length, 3, topic);
  for (const question of copernicusQuestions) {
    assert.equal(question.type, "choice");
    assert.equal(new Set(question.options).size, 3);
    assert.ok(Number.isInteger(question.answer) && question.answer >= 0 && question.answer < 3);
    assert.ok(question.explanation.length > 40, question.id);
  }
});

test("La corrección acepta listas en cualquier orden y explica qué falta o sobra", () => {
  assert.deepEqual(parseNumberList("35, 7 y 14 21-28 7"), [7, 14, 21, 28, 35]);
  assert.deepEqual(parseNumberList(""), []);

  const all = gradeWorksheet(multiplesQuestions, correctAnswers(multiplesQuestions));
  assert.equal(all.grade, 10);
  assert.equal(all.unanswered, 0);

  const empty = gradeWorksheet(multiplesQuestions, {});
  assert.equal(empty.score, 0);
  assert.equal(empty.unanswered, 15);

  const list = multiplesQuestions.find(question => question.id === "entre-4");
  const [wrongList] = gradeWorksheet([list], { "entre-4": "28 12 16 32" }).results;
  assert.equal(wrongList.correct, false);
  assert.deepEqual(wrongList.missing, [20, 24]);
  assert.deepEqual(wrongList.extra, [32]);
  assert.match(feedbackText(wrongList), /Te faltan: 20 y 24\. Sobran: 32\./);
  assert.equal(gradeWorksheet([list], { "entre-4": "28, 24, 20, 16 y 12" }).score, 1);

  const mark = multiplesQuestions.find(question => question.id === "marca-3");
  const [wrongMark] = gradeWorksheet([mark], { "marca-3": ["12", "17"] }).results;
  assert.match(feedbackText(wrongMark), /Te faltó marcar: 21 y 30\. No son múltiplos: 17\./);

  const number = multiplesQuestions.find(question => question.id === "completa-54");
  assert.equal(gradeWorksheet([number], { "completa-54": " 9 " }).score, 1);
  assert.equal(gradeWorksheet([number], { "completa-54": "9.0" }).score, 0);

  const copernicus = gradeWorksheet(copernicusQuestions, correctAnswers(copernicusQuestions));
  assert.equal(copernicus.grade, 10);
  const mistakes = gradeWorksheet(copernicusQuestions, { "quien-fue": "0" }).results.filter(result => !result.correct);
  assert.equal(mistakes.length, 9);
  assert.match(feedbackText(mistakes[0]), /Tu respuesta: Sin responder\. Respuesta correcta: En 1492/);
});

test("Las preguntas se muestran agrupadas y escapan el texto", () => {
  const html = renderWorksheetQuestions(multiplesQuestions);
  assert.equal((html.match(/class="worksheet-group"/g) ?? []).length, 6);
  assert.equal((html.match(/<fieldset class="question-card"/g) ?? []).length, 15);
  assert.match(html, /type="checkbox" name="marca-3" value="12"/);
  assert.match(html, /inputmode="numeric"/);
  assert.doesNotMatch(renderWorksheetQuestions([{ id: "x", type: "number", question: "<b>", answer: 1 }]), /<b>/);
});

test("Las nuevas páginas siguen la estructura de sus asignaturas y se publican", () => {
  const math = read("../aula/matematicas-multiplos.html");
  assert.match(math, /<html lang="es" data-subject="math">/);
  assert.match(math, /id="theme-toggle"/);
  assert.match(math, /<h1 id="multiples-title">Los múltiplos<\/h1>/);
  assert.equal((math.match(/<article class="mode-card">/g) ?? []).length, 3);
  assert.match(math, /id="multiples-explorer" class="multiples-explorer" hidden/);
  assert.match(math, /id="multiples-quiz" hidden/);
  assert.match(math, /<footer>[\s\S]*href="\.\/matematicas\/">Índice de Matemáticas<\/a>[\s\S]*<\/footer>/);
  assert.match(math, /src="\.\/subject-index\.mjs"[\s\S]*src="\.\/multiplos\.mjs(?:\?v=[^"]+)?"/);
  assert.match(math, /youtube-nocookie\.com\/embed\/xHdoCI-lz44/);
  assert.match(math, /href="https:\/\/www\.youtube\.com\/watch\?v=xHdoCI-lz44"[^>]*target="_blank"[^>]*rel="noopener noreferrer"/);
  assert.match(math, /id="multiples-video-title">Los múltiplos, explicados en vídeo<\/h2>/);

  const science = read("../aula/conocimiento-medio-copernico.html");
  for (const heading of ["¿Qué es la Edad Moderna?", "¿Qué se descubrió?", "¿Quién fue Nicolás Copérnico?", "Experimentamos con Aristóteles"])
    assert.ok(science.includes(heading), heading);
  assert.equal((science.match(/<article class="mode-card">/g) ?? []).length, 3);
  assert.match(science, /id="copernicus-quiz" hidden/);
  assert.match(science, /<footer>[\s\S]*href="\.\/conocimiento-medio\/">Índice de Conocimiento del Medio<\/a>[\s\S]*<\/footer>/);
  assert.match(science, /src="\.\/copernico\.mjs(?:\?v=[^"]+)?"/);
  assert.match(science, /youtube-nocookie\.com\/embed\/dwigKvjyPoM/);
  assert.match(science, /href="https:\/\/www\.youtube\.com\/watch\?v=dwigKvjyPoM"[^>]*target="_blank"[^>]*rel="noopener noreferrer"/);
  assert.match(science, /id="copernicus-video-title">Copérnico y la idea del Sol en el centro<\/h2>/);

  assert.match(read("../.github/workflows/deploy-pages.yml"), /cp -R aula site\//);
});
