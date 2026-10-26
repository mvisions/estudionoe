import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { grammarQuestions, gradeGrammarQuiz } from "../aula/ingles-gramatica-questions.mjs";
import { gradeActivity } from "../activity-definitions.mjs";
import { activityRankings } from "../activity-ranking.mjs";
import { createExamService, createMemoryStore } from "../exam-service.mjs";

const ids = grammarQuestions.map(question => question.id);
const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const allCorrect = Object.fromEntries(grammarQuestions.map(question => [question.id, question.answer]));

test("Las 24 preguntas cubren las formas verbales y los dos tipos de posesivos", () => {
  assert.equal(grammarQuestions.length, 24);
  assert.equal(new Set(ids).size, 24);
  for (const topic of [
    "be-affirmative", "be-negative", "be-interrogative", "be-short",
    "have-affirmative", "have-negative", "have-interrogative", "have-short",
    "got-affirmative", "got-negative", "got-interrogative",
    "possessive-adjective", "possessive-pronoun",
  ]) assert.ok(grammarQuestions.some(question => question.topic === topic), topic);
  for (const question of grammarQuestions) {
    assert.equal(question.options.length, 3);
    assert.equal(new Set(question.options).size, 3);
    assert.ok(Number.isInteger(question.answer) && question.answer >= 0 && question.answer < 3);
    assert.ok(question.explanation.length > 40, question.id);
  }
});

test("La corrección puntúa aciertos, fallos y respuestas vacías y conserva el detalle", () => {
  assert.equal(gradeGrammarQuiz(grammarQuestions, allCorrect).grade, 10);
  assert.equal(gradeGrammarQuiz(grammarQuestions, {}).grade, 0);
  const mixed = { ...allCorrect, [ids[0]]: (allCorrect[ids[0]] + 1) % 3 };
  delete mixed[ids[1]];
  const graded = gradeGrammarQuiz(grammarQuestions, mixed);
  assert.equal(graded.correct, 22);
  assert.equal(graded.grade, 9.2);
  const mistakes = graded.results.filter(result => !result.correct).map(result => result.question);
  assert.equal(mistakes.length, 2);
  assert.equal(graded.results[1].selected, undefined);
  assert.equal(gradeGrammarQuiz(mistakes, allCorrect).grade, 10);
});

test("El servidor recalcula el resultado y solo acepta el banco completo para el ranking", () => {
  const answers = Object.fromEntries(Object.entries(allCorrect).map(([id, value]) => [id, String(value)]));
  assert.deepEqual(gradeActivity("english-grammar", ids, answers), { points: 24, total: 24 });
  assert.deepEqual(gradeActivity("english-grammar", ids, {}), { points: 0, total: 24 });
  answers[ids[0]] = "0.0";
  answers[ids[1]] = "99";
  assert.deepEqual(gradeActivity("english-grammar", ids, answers), { points: 22, total: 24 });
  assert.throws(() => gradeActivity("english-grammar", ids.slice(1), {}), /formato válido/);
  assert.throws(() => gradeActivity("english-grammar", [...ids.slice(1), ids[1]], {}), /formato válido/);
  assert.throws(() => gradeActivity("english-grammar", ["unknown", ...ids.slice(1)], {}), /formato válido/);
  assert.ok(activityRankings.some(item => item.topic === "english-grammar" && item.mode === "activity"));
});

test("El resultado entra en el ranking general con consentimiento y puede retirarse", async () => {
  const service = createExamService(createMemoryStore());
  const input = {
    activity: "english-grammar", ids,
    answers: Object.fromEntries(Object.entries(allCorrect).map(([id, value]) => [id, String(value)])),
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
