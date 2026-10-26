import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const indexes = [
  {
    path: "../aula/conocimiento-medio/index.html",
    pages: ["../historia.html", "../conocimiento-medio.html"],
  },
  {
    path: "../aula/matematicas/index.html",
    pages: ["../matematicas.html"],
  },
  {
    path: "../aula/lengua/index.html",
    pages: ["../lengua.html", "../dictado.html", "../repaso-lengua.html", "../lengua-actual.html", "../test-diptongos.html"],
  },
  {
    path: "../aula/ingles/index.html",
    pages: ["../ingles.html", "../ingles-gramatica.html"],
  },
];

test("Cada índice enumera sus páginas en orden cronológico y enlaza cada una", () => {
  for (const { path, pages } of indexes) {
    const html = read(path);
    const dates = [...html.matchAll(/<time datetime="([^"]+)">/g)].map(([, date]) => date);

    assert.deepEqual(dates, [...dates].sort(), path);
    assert.equal((html.match(/<li>/g) ?? []).length, pages.length, path);
    assert.match(html, /<ol class="subject-index-list">/);
    assert.doesNotMatch(html, /class="mode-card"/);
    for (const page of pages) assert.ok(html.includes(`href="${page}"`), `${path} should link ${page}`);
    assert.match(html, /De lo más antiguo a lo más reciente/);
  }
});

test("La portada abre cada índice y las páginas activas ofrecen volver al suyo", () => {
  const homepage = read("../aula/index.html");
  for (const subject of ["conocimiento-medio", "matematicas", "lengua", "ingles"])
    assert.match(homepage, new RegExp(`href="./${subject}/"`));
  assert.doesNotMatch(homepage, /href="\.\/(?:conocimiento-medio|matematicas|lengua(?:-actual)?|ingles)\.html"/);

  const subjectPages = [
    ["../index.html", "./aula/conocimiento-medio/"],
    ["../aula/historia.html", "./conocimiento-medio/"],
    ["../aula/conocimiento-medio.html", "./conocimiento-medio/"],
    ["../aula/matematicas.html", "./matematicas/"],
    ["../aula/lengua.html", "./lengua/"],
    ["../aula/lengua-actual.html", "./lengua/"],
    ["../aula/dictado.html", "./lengua/"],
    ["../aula/repaso-lengua.html", "./lengua/"],
    ["../aula/test-diptongos.html", "./lengua/"],
    ["../aula/ingles.html", "./ingles/"],
    ["../aula/ingles-gramatica.html", "./ingles/"],
  ];
  for (const [path, indexLink] of subjectPages)
    assert.ok(read(path).includes(`href="${indexLink}"`), `${path} should link its subject index`);
});

test("Los accesos antiguos de Inglés redirigen y no duplican páginas en su índice", () => {
  const html = read("../aula/ingles/index.html");
  assert.match(read("../aula/ingles-tema-3.html"), /http-equiv="refresh" content="0; url=\.\/ingles\.html"/);
  assert.match(read("../aula/ingles-tema-4.html"), /http-equiv="refresh" content="0; url=\.\/ingles\.html"/);
  assert.equal((html.match(/<li>/g) ?? []).length, 2);
});
