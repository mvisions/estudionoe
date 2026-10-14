import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { isPetProfile, isRankingProfile, rankingIdentity } from "../ranking-profile.mjs";
import { createExamService, createMemoryStore, getBank } from "../exam-service.mjs";
import { createGitHubRankingStore, parseLog } from "../github-ranking-store.mjs";
import { readRanking, saveResult, sortedRanking, exportRanking, importRanking } from "../local-ranking.mjs";

const pet = { petName: " Luna ", animalType: " gato " };
const legacy = { name: "Alias antiguo", course: "5.º A" };
const storage = () => {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
};

test("Valida mascotas y distingue los registros antiguos sin convertir cursos en animales", () => {
  assert.equal(isPetProfile(pet), true);
  assert.deepEqual(rankingIdentity(pet), { name: "Luna", detail: "gato", legacy: false });
  assert.deepEqual(rankingIdentity(legacy), { name: "Alias antiguo", detail: "Resultado antiguo · Curso: 5.º A", legacy: true });
  for (const invalid of [null, "texto", [], {}, { ...pet, petName: " " },
    { ...pet, petName: "x".repeat(41) }, { ...pet, animalType: "x".repeat(31) },
    { ...pet, animalType: "<gato>" }, { ...pet, petName: "Luna\n" },
    { ...legacy, petName: "Luna" }]) {
    assert.equal(isRankingProfile(invalid), false);
  }
});

test("Guarda mascotas y resultados antiguos juntos, ordena y conserva las copias locales", () => {
  const store = storage();
  const base = { mode: "easy", grade: 10, durationMs: 1000, finishedAt: 2000 };
  saveResult(store, { ...base, ...legacy, id: "old" });
  saveResult(store, { ...base, ...pet, id: "new", durationMs: 500 });
  const entries = sortedRanking(readRanking(store), "easy");
  assert.deepEqual(entries.map(entry => entry.id), ["new", "old"]);
  assert.equal(entries[0].name, undefined);
  assert.equal(entries[0].course, undefined);
  assert.equal(rankingIdentity(entries[1]).legacy, true);
  const restored = storage();
  importRanking(restored, exportRanking(store));
  assert.deepEqual(readRanking(restored), entries);
  assert.throws(() => saveResult(store, { ...base, id: "bad", petName: "Luna" }), /no es válido/);
});

test("API: mascotas en ambos temas y los tres modos, sin guardar nombre ni curso", async () => {
  const store = createMemoryStore();
  const service = createExamService(store);
  for (const topic of ["history", "powers"]) {
    for (const mode of ["easy", "matching", "written"]) {
      const ids = getBank(mode, topic).map(item => item.id);
      const payload = {
        ...pet, ...legacy, topic, mode, consent: true, id: randomUUID(), token: "a".repeat(64),
        startedAt: Date.now() - 1000, finishedAt: Date.now(), ids,
        answers: Object.fromEntries(getBank(mode, topic).map(item => [item.id, mode === "matching" ? item.id : item.answer])),
      };
      const result = await service.submit(payload);
      assert.equal(result.grade, 10);
      assert.equal(result.petName, "Luna");
      assert.equal(result.animalType, "gato");
      assert.equal(result.name, undefined);
      assert.equal(result.course, undefined);
      const [stored] = await store.ranking(mode, topic);
      assert.equal(stored.name, undefined);
      assert.equal(stored.course, undefined);
      assert.equal((await service.ranking(mode, topic))[0].petName, "Luna");
      await service.remove(result.id, payload.token);
      assert.deepEqual(await service.ranking(mode, topic), []);
    }
  }
  const input = { ...pet, mode: "easy", consent: true };
  const started = await service.start(input);
  assert.equal((await service.finish(started.id, started.token, {})).animalType, "gato");
  await assert.rejects(service.start({ ...input, animalType: "" }), { status: 400 });
  await assert.rejects(service.submit({ ...input, animalType: "" }), { status: 400 });
});

test("GitHub: el TXT conserva campos de mascota y sigue leyendo resultados antiguos", async () => {
  let text = "";
  let sha = 0;
  const fetcher = async (url, options = {}) => {
    if (options.method === "PUT") {
      text = Buffer.from(JSON.parse(options.body).content, "base64").toString("utf8");
      sha++;
      return new Response("{}", { status: 200 });
    }
    return Response.json({ sha: String(sha), encoding: "base64", content: Buffer.from(text).toString("base64") });
  };
  const service = createExamService(createGitHubRankingStore({ token: "test", repository: "example/study", fetcher }));
  for (const profile of [legacy, pet]) {
    const exam = await service.start({ ...profile, mode: "easy", consent: true });
    await service.finish(exam.id, exam.token, {});
  }
  const records = [...parseLog(text).values()];
  assert.equal(records[0].name, legacy.name);
  assert.equal(records[1].petName, "Luna");
  assert.equal(records[1].animalType, "gato");
  assert.equal(records[1].name, undefined);
  assert.equal(records[1].course, undefined);
  const identities = (await service.ranking("easy")).map(rankingIdentity);
  assert.equal(identities.filter(identity => identity.legacy).length, 1);
  assert.equal(identities.filter(identity => !identity.legacy).length, 1);
});
