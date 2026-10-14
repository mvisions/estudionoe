import test from "node:test";
import assert from "node:assert/strict";
import { languageQuestions, languageGuide, gradeLanguageSelection } from "../language-questions.mjs";
import { summarize } from "../grading.mjs";

test("32 ejemplos originales cubren todos los contenidos de los dos temas", () => {
  assert.equal(languageQuestions.length, 32);
  assert.deepEqual(languageQuestions.map(item => item.id), Array.from({ length: 32 }, (_, index) => index + 1));
  assert.equal(new Set(languageQuestions.map(item => item.category)).size, 8);
  assert.equal(languageGuide.length, 6);
  for (const item of languageQuestions) {
    assert.equal(item.wrong.length, 2);
    assert.equal(new Set([item.answer, ...item.wrong]).size, 3);
    assert.ok(item.title.length > 20);
    assert.ok(item.explanation.length > 35);
    assert.equal(gradeLanguageSelection(item, item.answer).score, 1);
    assert.equal(gradeLanguageSelection(item, undefined).score, 0);
    for (const wrong of item.wrong) assert.equal(gradeLanguageSelection(item, wrong).score, 0);
  }
  assert.equal(summarize(languageQuestions.map(item => gradeLanguageSelection(item, item.answer))).grade, 10);
  assert.equal(summarize(languageQuestions.map(item => gradeLanguageSelection(item, undefined))).grade, 0);
});

test("Las parejas incluyen sinónimos y antónimos positivos, negativos y palabras no relacionadas", () => {
  const synonyms = languageQuestions.filter(item => item.category === "Sinónimos");
  const antonyms = languageQuestions.filter(item => item.category === "Antónimos");
  assert.equal(synonyms.filter(item => item.answer === "Sí, son sinónimos.").length, 2);
  assert.equal(synonyms.filter(item => item.answer === "No, tienen significados diferentes.").length, 2);
  assert.equal(antonyms.filter(item => item.answer === "Sí, son antónimos.").length, 2);
  assert.ok(antonyms.some(item => item.answer === "No, son sinónimos."));
  assert.ok(antonyms.some(item => item.answer === "No, son distintos, pero no opuestos."));
});

test("Se incluyen los cinco tipos de determinantes, géneros y artículos", () => {
  const determinants = languageQuestions.filter(item => item.category === "Determinantes");
  assert.deepEqual(determinants.map(item => item.answer), ["Demostrativo.", "Posesivo.", "Numeral.", "Indefinido.", "Artículo determinado."]);
  const literature = languageQuestions.filter(item => item.category === "Literatura");
  for (const genre of ["Narrativa.", "Lírica.", "Teatro."]) assert.ok(literature.some(item => item.answer === genre));
  const articles = languageQuestions.filter(item => item.category === "Artículos");
  assert.ok(articles.some(item => item.answer === "Indeterminado."));
  assert.ok(articles.some(item => item.answer === "el, la, los, las"));
});

test("El corrector rechaza respuestas inventadas y no premia selecciones parciales", () => {
  assert.throws(() => gradeLanguageSelection(languageQuestions[0], "Sí"), /no pertenece/);
  assert.throws(() => gradeLanguageSelection(languageQuestions[0], null), /no pertenece/);
  assert.throws(() => gradeLanguageSelection(undefined, "Respuesta"), /no es válido/);
});
