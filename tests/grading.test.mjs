import test from "node:test";
import assert from "node:assert/strict";
import { questions, matchingPairs } from "../questions.mjs";
import { gradeWritten, gradeChoice, normalize, shuffle, summarize } from "../grading.mjs";

test("Las 30 preguntas recibidas están incluidas y cubiertas por parejas", () => {
  assert.equal(questions.length, 30);
  assert.deepEqual(questions.map(q => q.id), Array.from({ length: 30 }, (_, i) => i + 1));
  assert.equal(matchingPairs.length, 39);
  for (const question of questions) {
    assert.equal(question.wrong.length, 2);
    assert.equal(new Set([question.answer, ...question.wrong]).size, 3);
    assert.ok(question.explanation.length > 50, `Explicación de Historia ${question.id}`);
    assert.notEqual(question.explanation, question.answer);
    assert.ok(matchingPairs.some(pair => pair.source === question.id));
  }
  for (const pair of matchingPairs) {
    assert.equal(pair.explanation, questions.find(question => question.id === pair.source).explanation);
  }
  assert.equal(new Set(matchingPairs.map(p => p.answer)).size, matchingPairs.length);
});

test("Todos los modelos escritos obtienen bien", () => {
  for (const question of questions) {
    assert.equal(gradeWritten(question, question.answer).status, "bien", `Pregunta ${question.id}`);
  }
});

test("Tres estados, tolerancia de tildes y una errata", () => {
  const question = questions.find(q => q.id === 12);
  assert.equal(gradeWritten(question, "Siglo VII, peninsula arabiga. Mahomaa.").score, 1);
  assert.equal(gradeWritten(question, "En Arabia, fundado por Mahoma.").score, 0.5);
  assert.equal(gradeWritten(question, "En Roma.").score, 0);
  assert.equal(gradeWritten(question, "   ").score, 0);
  assert.equal(normalize("Al-Ándalus"), "al andalus");
});

test("Fechas y números romanos no se confunden", () => {
  const q = questions.find(item => item.id === 12);
  assert.equal(gradeWritten(q, "Siglo VIII, Arabia, Mahoma").score, 0.5);
  assert.equal(gradeWritten(questions.find(item => item.id === 29), "1493").score, 0);
  assert.equal(gradeWritten(questions.find(item => item.id === 29), "1.492").score, 1);
  assert.notEqual(gradeWritten(questions.find(item => item.id === 18), "Abderramán III, emir independiente, dependía religiosamente del califa, no políticamente").score, 1);
});

test("Negaciones y opciones dudosas no consiguen bien", () => {
  const question = questions.find(q => q.id === 15);
  assert.notEqual(gradeWritten(question, "No fue Guadalete").score, 1);
  assert.notEqual(gradeWritten(question, "Guadalete o Covadonga").score, 1);
});

test("Elección correcta, incorrecta y pregunta sin respuesta", () => {
  for (const q of questions) {
    assert.equal(gradeChoice(q, q.answer).score, 1);
    for (const wrong of q.wrong) assert.equal(gradeChoice(q, wrong).score, 0);
    assert.equal(gradeChoice(q, "").score, 0);
  }
});

test("Nota y contadores exactos, incluidos los regulares", () => {
  assert.deepEqual(summarize([{ score: 1 }, { score: 0.5 }, { score: 0 }, { score: 1 }]),
    { points: 2.5, grade: 6.3, correct: 2, partial: 1, wrong: 1 });
  assert.equal(summarize(questions.map(() => ({ score: 1 }))).grade, 10);
  assert.equal(summarize([]).grade, 0);
});

test("Barajar conserva los elementos y no modifica el original", () => {
  const input = [1, 2, 3];
  const output = shuffle(input, () => 0);
  assert.deepEqual(input, [1, 2, 3]);
  assert.deepEqual(output, [2, 3, 1]);
});
