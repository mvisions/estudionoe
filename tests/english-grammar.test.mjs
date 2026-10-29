import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { grammarQuestions, gradeGrammarQuiz, pickGrammarQuestions, GRAMMAR_QUIZ_SIZE } from "../aula/ingles-gramatica-questions.mjs";
import { flechasPairs, gradeFlechas } from "../aula/ingles-flechas-questions.mjs";
import { gradeActivity } from "../activity-definitions.mjs";
import { activityRankings } from "../activity-ranking.mjs";
import { createExamService, createMemoryStore } from "../exam-service.mjs";

const ids = grammarQuestions.map(question => question.id);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");

// Azar repetible para que las pruebas siempre hagan lo mismo.
function seededRandom(seed = 1) {
  let value = seed;
  return () => {
    value = (value * 1664525 + 1013904223) % 4294967296;
    return value / 4294967296;
  };
}

test("El banco tiene 72 preguntas correctas y cubre todos los temas", () => {
  assert.equal(grammarQuestions.length, 72);
  assert.equal(GRAMMAR_QUIZ_SIZE, 24);
  assert.equal(new Set(ids).size, 72);
  for (const topic of [
    "be-affirmative", "be-negative", "be-interrogative", "be-short",
    "have-affirmative", "have-negative", "have-interrogative", "have-short",
    "got-affirmative", "got-negative", "got-interrogative",
    "possessive-adjective", "possessive-pronoun",
  ]) {
    assert.ok(grammarQuestions.filter(question => question.topic === topic).length >= 5, topic);
  }
  for (const question of grammarQuestions) {
    assert.equal(question.options.length, 3, question.id);
    assert.equal(new Set(question.options).size, 3, question.id);
    assert.ok(Number.isInteger(question.answer) && question.answer >= 0 && question.answer < 3, question.id);
    assert.ok(question.explanation.length > 40, question.id);
  }
});

test("Cada test saca 24 preguntas al azar, sin repetir y con todos los temas", () => {
  const first = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(7));
  const second = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(99));
  assert.equal(first.length, 24);
  assert.equal(new Set(first.map(question => question.id)).size, 24);
  assert.equal(new Set(first.map(question => question.topic)).size, 13);
  assert.notDeepEqual(first.map(question => question.id), second.map(question => question.id));
  assert.ok(first.some(question => !second.includes(question)), "dos tests no son iguales");
  assert.deepEqual(
    pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(7)).map(question => question.id),
    first.map(question => question.id),
    "con la misma semilla sale el mismo test",
  );
  assert.equal(pickGrammarQuestions(500, seededRandom(3)).length, 72, "nunca repite preguntas");
  assert.deepEqual(pickGrammarQuestions(0, seededRandom(3)), []);
});

test("La corrección puntúa aciertos, fallos y respuestas vacías y conserva el detalle", () => {
  const questions = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(11));
  const answers = Object.fromEntries(questions.map(question => [question.id, question.answer]));
  assert.equal(gradeGrammarQuiz(questions, answers).grade, 10);
  assert.equal(gradeGrammarQuiz(questions, {}).grade, 0);
  const mixed = { ...answers, [questions[0].id]: (questions[0].answer + 1) % 3 };
  delete mixed[questions[1].id];
  const graded = gradeGrammarQuiz(questions, mixed);
  assert.equal(graded.correct, 22);
  assert.equal(graded.grade, 9.2);
  const mistakes = graded.results.filter(result => !result.correct).map(result => result.question);
  assert.equal(mistakes.length, 2);
  assert.equal(graded.results[1].selected, undefined);
  assert.equal(gradeGrammarQuiz(mistakes, answers).grade, 10);
});

test("El servidor recalcula la nota de las 24 preguntas que recibe", () => {
  const questions = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(5));
  const testIds = questions.map(question => question.id);
  const answers = Object.fromEntries(questions.map(question => [question.id, String(question.answer)]));
  assert.deepEqual(gradeActivity("english-grammar", testIds, answers), { points: 24, total: 24 });
  assert.deepEqual(gradeActivity("english-grammar", testIds, {}), { points: 0, total: 24 });
  answers[testIds[0]] = "0.0";
  answers[testIds[1]] = "99";
  assert.deepEqual(gradeActivity("english-grammar", testIds, answers), { points: 22, total: 24 });
  assert.throws(() => gradeActivity("english-grammar", testIds.slice(1), {}), /formato válido/);
  assert.throws(() => gradeActivity("english-grammar", [...testIds.slice(1), testIds[1]], {}), /formato válido/);
  assert.throws(() => gradeActivity("english-grammar", ["unknown", ...testIds.slice(1)], {}), /formato válido/);
  const extra = grammarQuestions.find(question => !testIds.includes(question.id)).id;
  assert.throws(() => gradeActivity("english-grammar", [...testIds, extra], {}), /formato válido/);
  assert.throws(() => gradeActivity("english-grammar", ids, {}), /formato válido/, "ya no se exige el banco entero");

  const other = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(6));
  const otherAnswers = Object.fromEntries(other.map(question => [question.id, String(question.answer)]));
  assert.deepEqual(gradeActivity("english-grammar", other.map(question => question.id), otherAnswers), { points: 24, total: 24 });
  assert.ok(activityRankings.some(item => item.topic === "english-grammar" && item.mode === "activity"));
});

test("El resultado entra en el ranking general con consentimiento y puede retirarse", async () => {
  const service = createExamService(createMemoryStore());
  const questions = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE, seededRandom(21));
  const input = {
    activity: "english-grammar", ids: questions.map(question => question.id),
    answers: Object.fromEntries(questions.map(question => [question.id, String(question.answer)])),
    startedAt: Date.now() - 30000, finishedAt: Date.now(),
    petName: "Coco", animalType: "loro", consent: true,
  };
  await assert.rejects(service.submitActivity({ ...input, consent: false }), { status: 400 });
  const result = await service.submitActivity(input);
  assert.equal(result.grade, 10);
  assert.equal(result.topic, "english-grammar");
  assert.equal(result.answers, undefined);
  const ranking = await service.rankingAll();
  assert.equal(ranking.length, 1);
  assert.equal(ranking[0].topic, "english-grammar");
  assert.equal(ranking[0].grade, 10);
  assert.equal(ranking[0].answers, undefined);
  await service.remove(result.id, result.token);
  assert.equal((await service.rankingAll()).length, 0);
});

test("El test se abre en su propia pantalla desde dos botones de entrada", () => {
  const html = read("../aula/ingles-gramatica.html");
  assert.match(html, /data-open-test="test"/);
  assert.match(html, /data-open-test="flechas"/);
  assert.match(html, /id="test-screen"/);
  assert.match(html, /id="test-screen-content"/);
  assert.ok(!html.includes('id="grammar-quiz"'), "el test ya no vive incrustado en la lección");
  const script = read("../aula/ingles-gramatica.mjs");
  assert.match(script, /event\.key === "Escape"/);
  assert.match(script, /Terminar y volver/);
  assert.match(script, /history\.pushState/);
  assert.match(script, /pickGrammarQuestions\(GRAMMAR_QUIZ_SIZE\)/, "cada test elige 24 preguntas al azar");
});

test("Las flechas de has y have tienen una única respuesta posible", () => {
  assert.equal(flechasPairs.length, 6);
  assert.equal(new Set(flechasPairs.map(pair => pair.id)).size, 6);
  assert.equal(new Set(flechasPairs.map(pair => pair.right)).size, 6);
  for (const pair of flechasPairs) {
    assert.ok(pair.left.includes("___"), pair.id);
    assert.ok(pair.explanation.length > 40, pair.id);
  }
  const rights = flechasPairs.map(pair => pair.right);
  for (const expected of ["has", "have", "hasn’t", "haven’t", "Do", "Does"]) assert.ok(rights.includes(expected), expected);
  const all = Object.fromEntries(flechasPairs.map(pair => [pair.id, pair.id]));
  assert.equal(gradeFlechas(flechasPairs, all).grade, 10);
  assert.equal(gradeFlechas(flechasPairs, all).correct, 6);
  assert.equal(gradeFlechas(flechasPairs, {}).grade, 0);
  const graded = gradeFlechas(flechasPairs, { ...all, [flechasPairs[0].id]: flechasPairs[1].id });
  assert.equal(graded.correct, 5);
  assert.equal(graded.grade, 8.3);
  assert.equal(graded.results[0].correct, false);
});

test("La lección incluye tablas, tres vídeos incrustados y el acceso al ranking", () => {
  const html = read("../aula/ingles-gramatica.html");
  for (const section of ["to-be", "to-have", "possessives", "grammar-test"])
    assert.ok(html.includes(`id="${section}"`));
  assert.equal((html.match(/youtube-nocookie\.com\/embed\//g) ?? []).length, 3);
  assert.equal((html.match(/<iframe[^>]*title="[^"]+"/g) ?? []).length, 3);
  assert.match(html, /Have you got a bike/);
  assert.match(html, /Does she have a bike/);
  assert.match(html, /pronombres posesivos/);
  assert.match(html, /data-activity-rankings/);
  assert.match(html, /href="\.\/ingles\/"/);
  const workflow = read("../.github/workflows/deploy-pages.yml");
  assert.match(workflow, /cp -R aula site\//);
});
