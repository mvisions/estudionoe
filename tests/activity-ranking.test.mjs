import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { activityDefinitions, gradeActivity } from "../activity-definitions.mjs";
import { classroomPractice } from "../english-classroom.mjs";
import { dictationText } from "../dictation-content.mjs";
import { languageQuestions } from "../language-questions.mjs";
import { ordinalNumbers, monthNames, spokenDate } from "../ordinal-numbers.mjs";
import { vowelQuestions } from "../language-vowels.mjs";
import { scienceQuestions } from "../science-quiz.mjs";
import { createExamService, createMemoryStore } from "../exam-service.mjs";
import { createApi } from "../server.mjs";

test("Las actividades con nota calculan sus puntos desde los bancos oficiales", () => {
  const ordinals = ordinalNumbers.slice(0, 10);
  assert.deepEqual(gradeActivity("english-ordinal",
    ordinals.map(item => `ordinal-${item.number}`),
    Object.fromEntries(ordinals.map(item => [`ordinal-${item.number}`, item.words]))),
  { points: 10, total: 10 });

  const dates = Array.from({ length: 10 }, (_, index) => ({
    id: `date-10-${index + 1}`,
    answer: spokenDate(index + 1, monthNames[9]),
  }));
  assert.deepEqual(gradeActivity("english-date", dates.map(item => item.id),
    Object.fromEntries(dates.map(item => [item.id, item.answer]))), { points: 10, total: 10 });

  const classroom = classroomPractice.slice(0, 10);
  assert.deepEqual(gradeActivity("english-classroom", classroom.map(item => item.id),
    Object.fromEntries(classroom.map(item => [item.id, item.answer.toUpperCase()]))), { points: 10, total: 10 });

  assert.deepEqual(gradeActivity("language-review", languageQuestions.map(item => String(item.id)),
    Object.fromEntries(languageQuestions.map(item => [String(item.id), item.answer]))),
  { points: languageQuestions.length, total: languageQuestions.length });

  assert.deepEqual(gradeActivity("language-vowels", vowelQuestions.map(item => `vowel-${item.word}`),
    Object.fromEntries(vowelQuestions.map(item => [`vowel-${item.word}`, item.answer]))),
  { points: vowelQuestions.length, total: vowelQuestions.length });

  assert.deepEqual(gradeActivity("language-dictation", ["dictation-biblioteca"],
    { "dictation-biblioteca": dictationText }), { points: 75, total: 75 });

  const scienceIds = scienceQuestions.map(item => `science-${item.id}`);
  assert.deepEqual(gradeActivity("science-forces", scienceIds,
    Object.fromEntries(scienceQuestions.map(item => [`science-${item.id}`, String(item.answer)]))),
  { points: scienceQuestions.length, total: scienceQuestions.length });
  assert.deepEqual(gradeActivity("science-forces", scienceIds,
    Object.fromEntries(scienceQuestions.map(item => [`science-${item.id}`, String((item.answer + 1) % item.options.length)]))),
  { points: 0, total: scienceQuestions.length });
});

test("Las actividades solo aceptan bancos y cantidades completos válidos", () => {
  assert.equal(Object.keys(activityDefinitions).length, 8);
  assert.throws(() => gradeActivity("english-ordinal", ["ordinal-1"], { "ordinal-1": "first" }), /formato válido/);
  assert.throws(() => gradeActivity("english-ordinal", Array(10).fill("ordinal-1"), {}), /formato válido/);
  assert.throws(() => gradeActivity("language-review", ["1"], { "1": "respuesta ajena" }), /formato válido/);
  assert.throws(() => gradeActivity("not-an-activity", [], {}), /formato válido/);
});

test("La página principal y todas las prácticas independientes muestran acceso a los rankings", () => {
  const root = fileURLToPath(new URL("..", import.meta.url));
  const pages = [
    "aula/index.html", "aula/historia.html", "aula/conocimiento-medio.html", "aula/ingles.html", "aula/lengua.html", "aula/lengua-actual.html",
    "aula/repaso-lengua.html", "aula/test-diptongos.html", "aula/dictado.html", "aula/ingles-gramatica.html",
  ];
  for (const path of pages)
    assert.match(readFileSync(`${root}/${path}`, "utf8"), /data-activity-rankings/);
  const workflow = readFileSync(`${root}/.github/workflows/deploy-pages.yml`, "utf8");
  assert.match(workflow, /cp activity-ranking\.mjs site\//);
});

test("La API publica y retira un resultado de actividad sin devolver respuestas", async t => {
  const store = createMemoryStore();
  const service = createExamService(store);
  const server = createApi(service, { origins: [], development: true });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const url = `http://127.0.0.1:${server.address().port}`;
  const questions = ordinalNumbers.slice(0, 10);
  const ids = questions.map(item => `ordinal-${item.number}`);
  const answers = Object.fromEntries(questions.map(item => [`ordinal-${item.number}`, item.words]));
  const response = await fetch(`${url}/api/activity-results`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      activity: "english-ordinal", ids, answers, startedAt: Date.now() - 30000,
      finishedAt: Date.now(), petName: "Coco", animalType: "loro", consent: true,
    }),
  });
  assert.equal(response.status, 201);
  const submitted = await response.json();
  assert.equal(submitted.grade, 10);
  assert.equal(submitted.topic, "english-ordinal");
  assert.equal(submitted.mode, "activity");
  assert.equal(submitted.answers, undefined);
  assert.match(submitted.token, /^[a-f0-9]{64}$/);

  const rankingResponse = await fetch(`${url}/api/ranking?mode=activity&topic=english-ordinal`);
  const ranking = await rankingResponse.json();
  assert.equal(ranking.entries.length, 1);
  assert.equal(ranking.entries[0].petName, "Coco");
  assert.equal(ranking.entries[0].grade, 10);
  assert.equal(ranking.entries[0].answers, undefined);

  const removed = await fetch(`${url}/api/exams/${submitted.id}`, {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: submitted.token }),
  });
  assert.equal(removed.status, 200);
  const afterRemoval = await fetch(`${url}/api/ranking?mode=activity&topic=english-ordinal`);
  assert.equal((await afterRemoval.json()).entries.length, 0);
});

test("La API rechaza la publicación sin consentimiento y los temas desconocidos", async t => {
  const service = createExamService(createMemoryStore());
  const validPayload = {
    activity: "english-ordinal", ids: ordinalNumbers.slice(0, 10).map(item => `ordinal-${item.number}`),
    answers: {}, startedAt: Date.now() - 1000, finishedAt: Date.now(),
    petName: "Coco", animalType: "loro",
  };
  await assert.rejects(service.submitActivity({ ...validPayload, consent: false }), { status: 400 });
  await assert.rejects(service.submitActivity({ ...validPayload, activity: "otro", consent: true }), { status: 400 });
});
