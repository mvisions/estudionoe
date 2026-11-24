import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  frenchNumberQuiz,
  frenchNumbers,
  gradeFrenchQuiz,
  gradeFrenchWriting,
} from "../aula/frances-numeros-questions.mjs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");

test("La lección de Francés ofrece las tres prácticas y separa la pantalla de escritura", () => {
  const html = read("../aula/frances-numeros.html");
  assert.match(html, /data-open-french-test="matching"/);
  assert.match(html, /data-open-french-test="writing"/);
  assert.match(html, /data-open-french-test="quiz"/);
  assert.match(html, /youtube-nocookie\.com\/embed\/qfsMXxTcY-I/);
  assert.match(html, /href="https:\/\/www\.youtube\.com\/watch\?v=qfsMXxTcY-I"[^>]*target="_blank"[^>]*rel="noopener noreferrer"/);
  assert.match(html, /id="french-test-screen"/);
  assert.match(read("../aula/frances-numeros.mjs"), /Las palabras de ayuda están en otra pantalla/);
  assert.match(read("../aula/frances-numeros.mjs"), /scrollTo\(\{ top: 0, behavior: "smooth" \}\)/);
});

test("El banco del test tiene una única forma correcta y opciones mal escritas", () => {
  for (const question of frenchNumberQuiz) {
    const number = Number(question.id.replace("french-quiz-", ""));
    assert.equal(question.options[question.answer], frenchNumbers[number - 1].word);
    assert.equal(new Set(question.options).size, question.options.length);
    assert.ok(question.options.slice(1).every(option => !frenchNumbers.some(item => item.word === option)));
  }
});

test("La corrección de Francés distingue respuestas correctas y errores", () => {
  const writingQuestions = frenchNumbers.map(item => ({ ...item, id: `french-number-${item.number}` }));
  const writingAnswers = Object.fromEntries(writingQuestions.map(question => [question.id, question.word.toUpperCase()]));
  writingAnswers["french-number-5"] = "sinque";
  assert.deepEqual(gradeFrenchWriting(writingQuestions, writingAnswers), {
    results: writingQuestions.map(question => ({
      question,
      answer: writingAnswers[question.id],
      correct: question.id !== "french-number-5",
    })),
    points: 9,
    total: 10,
  });
  const quizAnswers = Object.fromEntries(frenchNumberQuiz.map(question => [question.id, question.answer]));
  quizAnswers[frenchNumberQuiz[0].id] = 1;
  assert.equal(gradeFrenchQuiz(frenchNumberQuiz, quizAnswers).points, 9);
});
