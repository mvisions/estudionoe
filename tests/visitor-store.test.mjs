import test from "node:test";
import assert from "node:assert/strict";
import { createFirestoreVisitorStore, createMemoryVisitorStore } from "../visitor-store.mjs";

test("El almacén de memoria deduplica por navegador y por día", async () => {
  const store = createMemoryVisitorStore();
  assert.equal(await store.record("visitor-hash", "2026-10-16"), true);
  assert.equal(await store.record("visitor-hash", "2026-10-16"), false);
  assert.equal(await store.record("visitor-hash", "2026-10-17"), true);
  assert.equal(await store.count("2026-10-16"), 1);
  assert.equal(await store.count("2026-10-17"), 1);
});

test("Firestore almacena y cuenta visitantes únicos por día", async () => {
  const documents = new Map();
  const database = {
    collection(name) {
      return {
        doc(id) {
          const key = `${name}/${id}`;
          return {
            key,
            async get() {
              const data = documents.get(key);
              return { exists: data !== undefined, data: () => data };
            },
          };
        },
      };
    },
    async runTransaction(callback) {
      const writes = [];
      const result = await callback({
        async get(document) {
          const data = documents.get(document.key);
          return { exists: data !== undefined, data: () => data };
        },
        create(document, data) {
          writes.push([document.key, data]);
        },
        set(document, data) {
          writes.push([document.key, data]);
        },
      });
      for (const [key, data] of writes) documents.set(key, data);
      return result;
    },
  };
  const store = createFirestoreVisitorStore(database);
  assert.equal(await store.record("hash-a", "2026-10-16"), true);
  assert.equal(await store.record("hash-a", "2026-10-16"), false);
  assert.equal(await store.record("hash-b", "2026-10-16"), true);
  assert.equal(await store.record("hash-a", "2026-10-17"), true);
  assert.equal(await store.count("2026-10-16"), 2);
  assert.equal(await store.count("2026-10-17"), 1);
  assert.equal(await store.count("2026-10-18"), 0);
});
