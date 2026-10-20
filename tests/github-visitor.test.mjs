import test from "node:test";
import assert from "node:assert/strict";
import { createGitHubVisitorStore, parseVisitorLog } from "../github-visitor-store.mjs";

function mockGitHub() {
  let text = "", version = 1, exists = true, conflicts = 0;
  return {
    get text() { return text; },
    set conflicts(value) { conflicts = value; },
    set exists(value) { exists = value; },
    fetcher: async (_url, options) => {
      if (!options.method) {
        if (!exists) return new Response("{}", { status: 404 });
        return new Response(JSON.stringify({ encoding: "base64", content: Buffer.from(text).toString("base64"), sha: String(version) }));
      }
      const input = JSON.parse(options.body);
      if (!exists && input.sha) return new Response("{}", { status: 409 });
      if (exists && (conflicts-- > 0 || input.sha !== String(version))) return new Response("{}", { status: 409 });
      text = Buffer.from(input.content, "base64").toString("utf8");
      version++;
      exists = true;
      return new Response("{}");
    },
  };
}

const hashA = "a".repeat(64), hashB = "b".repeat(64);

test("Cuenta visitantes únicos por día, reintenta conflictos y persiste tras reiniciar", async () => {
  const mock = mockGitHub();
  const options = { token: "test-token", repository: "owner/repo", fetcher: mock.fetcher };
  const store = createGitHubVisitorStore(options);
  mock.conflicts = 1;
  assert.equal(await store.record(hashA, "2026-10-16"), true);
  assert.equal(await store.record(hashA, "2026-10-16"), false);
  assert.equal(await store.record(hashB, "2026-10-16"), true);
  assert.equal(await store.record(hashA, "2026-10-17"), true);
  assert.equal(await store.count("2026-10-16"), 2);
  assert.equal(await store.count("2026-10-17"), 1);
  assert.equal(await store.count("2026-10-18"), 0);
  const restarted = createGitHubVisitorStore(options);
  assert.equal(await restarted.count("2026-10-16"), 2);
  assert.equal(parseVisitorLog(mock.text).size, 3);
});

test("Crea el log al primer visitante y valida datos y errores de GitHub", async () => {
  const mock = mockGitHub();
  mock.exists = false;
  const store = createGitHubVisitorStore({ token: "test", repository: "a/b", fetcher: mock.fetcher });
  assert.equal(await store.record(hashA, "2026-10-16"), true);
  assert.equal(await store.count("2026-10-16"), 1);
  await assert.rejects(store.record("not-a-hash", "2026-10-16"), /no válidos/);
  await assert.rejects(store.record(hashA, "16-10-2026"), /no válidos/);
  assert.throws(() => parseVisitorLog('{"day":"2026-10-16"}'), /inválida/);
  const failing = createGitHubVisitorStore({ token: "test", repository: "a/b", fetcher: async () => new Response("{}", { status: 403 }) });
  await assert.rejects(failing.count("2026-10-16"), /403/);
  assert.throws(() => createGitHubVisitorStore({ repository: "a/b" }), /GITHUB_TOKEN/);
});

test("Elimina los días antiguos al escribir para mantener el log pequeño", async () => {
  const mock = mockGitHub();
  const store = createGitHubVisitorStore({ token: "test", repository: "a/b", fetcher: mock.fetcher, retentionDays: 2 });
  await store.record(hashA, "2026-10-10");
  assert.equal(await store.count("2026-10-10"), 1);
  await store.record(hashB, "2026-10-13");
  assert.equal(await store.count("2026-10-10"), 0);
  assert.equal(await store.count("2026-10-13"), 1);
  assert.equal(parseVisitorLog(mock.text).size, 1);
});
