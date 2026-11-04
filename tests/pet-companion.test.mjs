import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { getPetProfile, petCelebrationForGrade, setPetProfile } from "../pet-companion.mjs";

test("La mascota baila solo por encima de 5 y los cohetes solo por encima de 7", () => {
  assert.deepEqual(petCelebrationForGrade(5), { dance: false, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(5.1), { dance: true, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(7), { dance: true, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(7.1), { dance: true, fireworks: true });
  assert.deepEqual(petCelebrationForGrade(Number.NaN), { dance: false, fireworks: false });
});

test("La mascota elegida y los efectos aparecen en todas las páginas de estudio", () => {
  const historyHome = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const pages = [
    historyHome.includes("pet-companion.mjs") ? "index.html" : "aula/conocimiento-medio/edad-media.html",
    "aula/index.html", "aula/historia.html", "aula/conocimiento-medio.html", "aula/matematicas.html",
    "aula/ingles.html", "aula/lengua.html", "aula/lengua-actual.html",
    "aula/repaso-lengua.html", "aula/test-diptongos.html", "aula/dictado.html",
    "aula/matematicas-multiplos.html", "aula/conocimiento-medio-copernico.html",
  ];
  for (const page of pages)
    assert.match(readFileSync(new URL(`../${page}`, import.meta.url), "utf8"),
      /pet-companion\.mjs\?v=20261104-pets/);

  assert.match(readFileSync(new URL("../pets/parrot.svg", import.meta.url), "utf8"), /<svg/);
  for (const pet of ["cat-preview.jpg", "dog-preview.jpg"]) {
    const image = readFileSync(new URL(`../pets/${pet}`, import.meta.url));
    assert.deepEqual([...image.subarray(0, 3)], [0xff, 0xd8, 0xff]);
  }
  const squirrel = readFileSync(new URL("../aula/ardilla-3d.png", import.meta.url));
  assert.deepEqual([...squirrel.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.equal(squirrel[25], 6, "la imagen de la ardilla debe conservar la transparencia");
  const bee = readFileSync(new URL("../aula/abeja-3d.png", import.meta.url));
  assert.deepEqual([...bee.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.equal(bee[25], 6, "la imagen de la abeja debe conservar la transparencia");

  const companion = readFileSync(new URL("../pet-companion.mjs", import.meta.url), "utf8");
  assert.match(companion, /ardilla: \{\s*label: "Ardilla",\s*image: new URL\("\.\/aula\/ardilla-3d\.png\?v=20261104-squirrel"/);
  assert.match(companion, /abeja: \{\s*label: "Abeja",\s*image: new URL\("\.\/aula\/abeja-3d\.png\?v=20261104-bee"/);
  for (const [type, label] of [["oso", "Oso"], ["mono", "Mono"], ["cocodrilo", "Cocodrilo"]]) {
    const png = readFileSync(new URL(`../pets/${type}-3d.png`, import.meta.url));
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.equal(png[25], 6, `${type}: debe conservar el canal alfa`);
    assert.match(companion, new RegExp(`${type}: \\{\\s*label: "${label}",\\s*image: new URL\\("\\./pets/${type}-3d\\.png\\?v=20261104-pets"`));
  }
  assert.match(companion, /aria-label="Tipo de mascota"/);
  assert.match(companion, /elige una mascota\./);
  assert.match(companion, /Sitting Cat/);
  assert.match(companion, /Shiba/);
  assert.match(companion, /OpenMoji/);
  assert.match(companion, /creativecommons\.org\/licenses\/by\/4\.0/);
  assert.match(companion, /creativecommons\.org\/licenses\/by-sa\/4\.0/);

  const workflow = readFileSync(new URL("../.github/workflows/deploy-pages.yml", import.meta.url), "utf8");
  assert.match(workflow, /cp pet-companion\.mjs site\//);
  assert.match(workflow, /cp -R pets site\//);
});

test("Las ocho mascotas se pueden elegir, guardar y recuperar sin cambiar las anteriores", t => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const values = new Map();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: key => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
    },
  });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else delete globalThis.localStorage;
  });

  assert.equal(getPetProfile(), null);
  for (const animalType of ["loro", "gato", "perro", "ardilla", "abeja", "oso", "mono", "cocodrilo"]) {
    const expected = { petName: "Luna", animalType };
    assert.deepEqual(setPetProfile({ petName: " Luna ", animalType }), expected);
    assert.deepEqual(getPetProfile(), expected);
  }
  assert.throws(() => setPetProfile({ petName: "Luna", animalType: "desconocido" }), /válidos/);
  assert.throws(() => setPetProfile({ petName: "", animalType: "oso" }), /válidos/);
  assert.deepEqual(getPetProfile(), { petName: "Luna", animalType: "cocodrilo" });
});

test("Páginas y actividades comparten la versión de mascotas sin módulos duplicados", () => {
  const version = "20261104-pets";
  const consumers = [
    "app.mjs", "science-quiz.mjs", "language-vowels.mjs", "language-quiz.mjs",
    "english-exercises.mjs", "dictation.mjs", "aula/worksheet-quiz.mjs", "aula/ingles-gramatica.mjs",
  ];
  for (const file of consumers) {
    const source = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
    const imports = [...source.matchAll(/from "([^"]*pet-companion\.mjs[^"]*)"/g)];
    assert.equal(imports.length, 1, file);
    assert.equal(new URL(imports[0][1], "https://example.test/").searchParams.get("v"), version, file);
  }
  const entries = new Set([
    ...consumers.map(file => file.split("/").at(-1)),
    "pet-companion.mjs", "styles.css", "copernico.mjs", "multiplos.mjs",
  ]);
  for (const file of readdirSync(new URL("../aula/", import.meta.url), { recursive: true })) {
    if (!file.endsWith(".html")) continue;
    const html = readFileSync(new URL(`../aula/${file.replaceAll("\\", "/")}`, import.meta.url), "utf8");
    if (!html.includes("pet-companion.mjs")) continue;
    for (const [, path] of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
      const url = new URL(path, "https://example.test/");
      if (entries.has(url.pathname.split("/").at(-1))) {
        assert.equal(url.searchParams.get("v"), version, `${file}: ${path}`);
      }
    }
  }
  for (const file of ["aula/copernico.mjs", "aula/multiplos.mjs"]) {
    assert.match(readFileSync(new URL(`../${file}`, import.meta.url), "utf8"),
      /from "\.\/worksheet-quiz\.mjs\?v=20261104-pets"/);
  }
});

test("Cada actividad calificada usa los umbrales compartidos de baile y cohetes", () => {
  const checks = [
    ["app.mjs", /celebratePet\(grade\)/],
    ["english-exercises.mjs", /celebratePet\(numericGrade\)/],
    ["language-quiz.mjs", /celebratePet\(summarize\(graded\)\.grade\)/],
    ["language-vowels.mjs", /celebratePet\(score \/ questions\.length \* 10\)/],
    ["dictation.mjs", /celebratePet\(review\.correctWords \/ review\.totalWords \* 10\)/],
  ];
  for (const [file, pattern] of checks)
    assert.match(readFileSync(new URL(`../${file}`, import.meta.url), "utf8"), pattern);
});
