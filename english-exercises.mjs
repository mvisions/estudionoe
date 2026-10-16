import { gradeEnglishAnswer } from "./english-grading.mjs";
import { shuffle } from "./grading.mjs";

const app = document.querySelector("#english-exercises");
const vocabulary = [...document.querySelectorAll(".english-words > div")].map((row, id) => ({
  id, english: row.querySelector("dt").textContent.trim(), spanish: row.querySelector("dd").textContent.trim(),
}));
const studySections = [...document.querySelectorAll("[data-vocabulary]")];
const escape = text => String(text).replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);
let questions = [];
let mistakes = [];

function start(words = vocabulary) {
  questions = shuffle(words);
  studySections.forEach(section => { section.hidden = true; });
  app.innerHTML = `<form id="english-form" autocomplete="off">
    <h2 tabindex="-1">Escribe en inglés</h2>
    <p>Traduce estas ${questions.length} palabras. Cada acierto vale un punto; las respuestas vacías cuentan como fallo.
    No importan las mayúsculas ni los espacios de más, pero sí la ortografía y el singular o plural.</p>
    <p class="muted">Este ejercicio no se guarda al cerrar o recargar la página. Sin ranking público.</p>
    ${questions.map((word, index) => `<div class="english-exercise">
      <label class="input-label" for="word-${word.id}">${index + 1}. ${escape(word.spanish)}</label>
      <input id="word-${word.id}" name="word-${word.id}" type="text" lang="en" placeholder="Escribe la palabra en inglés"
        autocapitalize="none" autocorrect="off" spellcheck="false" autocomplete="off">
    </div>`).join("")}
    <div class="result-actions"><button class="primary" type="submit">Corregir ejercicios</button>
    <button class="secondary" type="button" data-action="study">Volver al vocabulario</button></div>
  </form>`;
  app.querySelector("h2").focus();
}

function showStudy() {
  studySections.forEach(section => { section.hidden = false; });
  app.innerHTML = `<section class="question-card"><h2 tabindex="-1">Del español al inglés</h2>
    <p>Verás las palabras en español y tendrás que escribirlas en inglés. El vocabulario se oculta mientras practicas.</p>
    <button class="primary" type="button" data-action="start">Practicar ${vocabulary.length} palabras</button></section>`;
}

app.addEventListener("submit", event => {
  event.preventDefault();
  const answers = new FormData(event.target);
  const results = questions.map(word => {
    const answer = String(answers.get(`word-${word.id}`) ?? "");
    return { ...word, answer, correct: gradeEnglishAnswer(word.english, answer) };
  });
  mistakes = results.filter(word => !word.correct);
  const correct = results.length - mistakes.length;
  const grade = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(correct / results.length * 10);
  app.innerHTML = `<section class="result-hero"><h2 tabindex="-1">¡Sigue aprendiendo nuevas palabras!</h2>
    <div class="grade-circle"><strong>${grade}</strong><span>NOTA SOBRE 10</span></div>
    <p>${correct} aciertos de ${results.length}. ${mistakes.length} palabras para repasar.</p>
    <div class="result-actions"><button class="primary" data-action="start">Repetir todas</button>
    ${mistakes.length ? '<button class="secondary" data-action="mistakes">Practicar solo los fallos</button>' : ""}
    <button class="secondary" data-action="study">Ver vocabulario</button></div></section>
    <h2>Revisa tus respuestas</h2>
    ${results.map(word => `<article class="review"><span class="status ${word.correct ? "bien" : "mal"}">${word.correct ? "Bien" : "Para repasar"}</span>
      <h3>${escape(word.spanish)}</h3><p>Tu respuesta: <span lang="en">${escape(word.answer.trim() || "Sin responder")}</span></p>
      <div class="model-answer">En inglés: <strong lang="en">${escape(word.english)}</strong></div></article>`).join("")}`;
  app.querySelector("h2").focus();
  app.scrollIntoView({ block: "start" });
});

app.addEventListener("click", event => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "start") start();
  if (button.dataset.action === "mistakes") start(mistakes);
  if (button.dataset.action === "study") {
    showStudy();
    app.querySelector("h2").focus();
  }
});

showStudy();
