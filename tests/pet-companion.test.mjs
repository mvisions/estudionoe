import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { petCelebrationForGrade } from "../pet-companion.mjs";

test("La mascota baila solo por encima de 5 y los cohetes solo por encima de 7", () => {
  assert.deepEqual(petCelebrationForGrade(5), { dance: false, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(5.1), { dance: true, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(7), { dance: true, fireworks: false });
  assert.deepEqual(petCelebrationForGrade(7.1), { dance: true, fireworks: true });
  assert.deepEqual(petCelebrationForGrade(Number.NaN), { dance: false, fireworks: false });
});

test("La mascota elegida y los efectos aparecen en todas las páginas de estudio", () => {
  const pages = [
    "index.html", "aula/index.html", "aula/historia.html", "aula/matematicas.html",
    "aula/ingles.html", "aula/lengua.html", "aula/lengua-actual.html",
    "aula/repaso-lengua.html", "aula/test-diptongos.html", "aula/dictado.html",
  ];
  for (const page of pages)
    assert.match(readFileSync(new URL(`../${page}`, import.meta.url), "utf8"), /pet-companion\.mjs/);

  for (const pet of ["parrot.svg", "cat.svg", "dog.svg"])
    assert.match(readFileSync(new URL(`../pets/${pet}`, import.meta.url), "utf8"), /<svg/);

  const workflow = readFileSync(new URL("../.github/workflows/deploy-pages.yml", import.meta.url), "utf8");
  assert.match(workflow, /cp pet-companion\.mjs site\//);
  assert.match(workflow, /cp -R pets site\//);
});

test("Cada actividad calificada usa los umbrales compartidos de baile y cohetes", () => {
  const checks = [
    ["app.mjs", /celebratePet\(grade\)/],
    ["english-exercises.mjs", /celebratePet\(numericGrade\)/],
    ["language-quiz.mjs", /celebratePet\(summarize\(graded\)\.grade\)/],
    ["language-vowels.mjs", /celebratePet\(score \/ vowelQuestions\.length \* 10\)/],
    ["dictation.mjs", /celebratePet\(review\.correctWords \/ review\.totalWords \* 10\)/],
  ];
  for (const [file, pattern] of checks)
    assert.match(readFileSync(new URL(`../${file}`, import.meta.url), "utf8"), pattern);
});
