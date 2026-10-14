import test from "node:test";
import assert from "node:assert/strict";
import { createExamService, createMemoryStore } from "../exam-service.mjs";
import { createApi } from "../server.mjs";
import { questions, matchingPairs } from "../questions.mjs";

const profile = { name: "Prueba", course: "5.º A", consent: true, mode: "easy" };

test("El servidor calcula nota y tiempo, ordena y evita duplicar entregas", async () => {
  let now = 1000;
  const service = createExamService(createMemoryStore(), () => now);
  const first = await service.start(profile);
  const answers = Object.fromEntries(questions.map(q => [q.id, q.answer]));
  now += 120000;
  const result = await service.finish(first.id, first.token, answers);
  assert.equal(result.grade, 10);
  assert.equal(result.total, 30);
  assert.equal(result.durationMs, 120000);
  now += 10000;
  assert.deepEqual(await service.finish(first.id, first.token, {}), result);
  const second = await service.start({ ...profile, name: "Otro" });
  now += 60000;
  await service.finish(second.id, second.token, answers);
  const ranking = await service.ranking("easy");
  assert.equal(ranking.length, 2);
  assert.equal(ranking[0].name, "Otro");
  assert.equal(ranking[0].tokenHash, undefined);
  await service.remove(second.id, second.token);
  await service.remove(second.id, second.token);
  assert.equal((await service.ranking("easy")).length, 1);
});

test("Los tres modos reciben 10 con sus respuestas correctas", async () => {
  const service = createExamService(createMemoryStore());
  for (const mode of ["easy", "written", "matching"]) {
    const exam = await service.start({ ...profile, mode });
    const answers = mode === "matching" ? Object.fromEntries(matchingPairs.map(p => [p.id, p.id]))
      : Object.fromEntries(questions.map(q => [q.id, q.answer]));
    assert.equal((await service.finish(exam.id, exam.token, answers)).grade, 10);
  }
});

test("Rechaza perfiles inválidos, tokens, respuestas ajenas y parejas duplicadas", async () => {
  const service = createExamService(createMemoryStore());
  await assert.rejects(service.start({ ...profile, consent: false }), { status: 400 });
  await assert.rejects(service.start({ ...profile, name: "<script>" }), { status: 400 });
  const exam = await service.start(profile);
  await assert.rejects(service.finish(exam.id, "0".repeat(64), {}), { status: 404 });
  await assert.rejects(service.finish(exam.id, exam.token, { 31: "texto" }), { status: 400 });
  await assert.rejects(service.finish(exam.id, exam.token, { 1: "opción inventada" }), { status: 400 });
  await assert.rejects(service.remove(exam.id, "0".repeat(64)), { status: 404 });
  const pairs = await service.start({ ...profile, mode: "matching" });
  await assert.rejects(service.finish(pairs.id, pairs.token, { [pairs.ids[0]]: pairs.ids[0], [pairs.ids[1]]: pairs.ids[0] }), { status: 400 });
});

test("HTTP: salud, CORS, inicio, entrega, ranking y borrado", async t => {
  const petProfile = { petName: "Coco", animalType: "loro", consent: true, mode: "easy" };
  const service = createExamService(createMemoryStore());
  const server = createApi(service, { origins: ["http://localhost:8080"], development: true });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const url = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(`${url}/api/health`)).status, 200);
  assert.equal((await fetch(`${url}/api/ranking?mode=easy`, { headers: { Origin: "https://invalid.example" } })).status, 403);
  const post = (path, body, method = "POST") => fetch(`${url}${path}`, {
    method, headers: { "Content-Type": "application/json", Origin: "http://localhost:8080" }, body: JSON.stringify(body),
  });
  const response = await post("/api/exams", petProfile);
  assert.equal(response.status, 201);
  const exam = await response.json();
  const finished = await post(`/api/exams/${exam.id}/finish`, { token: exam.token, answers: {} });
  assert.equal((await finished.json()).grade, 0);
  const ranked = await (await fetch(`${url}/api/ranking?mode=easy`)).json();
  assert.equal(ranked.entries.length, 1);
  assert.equal(ranked.entries[0].petName, "Coco");
  assert.equal(ranked.entries[0].animalType, "loro");
  assert.equal(ranked.entries[0].name, undefined);
  assert.equal(ranked.entries[0].course, undefined);
  assert.equal((await post(`/api/exams/${exam.id}`, { token: exam.token }, "DELETE")).status, 200);
  assert.equal((await (await fetch(`${url}/api/ranking?mode=easy`)).json()).entries.length, 0);
  const automatic = await post("/api/results", {
    ...petProfile, id: exam.id, token: exam.token, startedAt: Date.now() - 1000, finishedAt: Date.now(),
    ids: questions.map(q => q.id), answers: Object.fromEntries(questions.map(q => [q.id, q.answer])),
  });
  assert.equal(automatic.status, 201);
  const automaticResult = await automatic.json();
  assert.equal(automaticResult.grade, 10);
  assert.equal(automaticResult.storage, "memory-development");
  assert.equal(automaticResult.petName, "Coco");
  assert.equal(automaticResult.course, undefined);
});
