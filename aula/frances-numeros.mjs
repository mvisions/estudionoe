import {
  frenchNumberPairs,
  frenchNumberQuiz,
  frenchNumbers,
  gradeFrenchMatching,
  gradeFrenchQuiz,
  gradeFrenchWriting,
} from "./frances-numeros-questions.mjs";
import { offerActivityRanking } from "../activity-ranking.mjs";
import { celebratePet } from "../pet-companion.mjs?v=20261124-french";
import { shuffle } from "../grading.mjs";

const screen = document.querySelector("#french-test-screen");
const content = document.querySelector("#french-test-screen-content");
const title = document.querySelector("#french-test-screen-title");
const progress = document.querySelector("#french-test-screen-progress");
const back = screen.querySelector('[data-action="back"]');
const launchers = [...document.querySelectorAll("[data-open-french-test]")];
const letters = "ABCDEFGHIJ";
const modes = {
  matching: { title: "Francés · Unir con flechas", render: renderMatching },
  writing: { title: "Francés · Escribir los números", render: renderWriting },
  quiz: { title: "Francés · Elegir la forma correcta", render: renderQuiz },
};
let current;
let activity;

function openScreen(name) {
  if (!modes[name] || current === name) return;
  history.pushState({ frenchTest: name }, "", `#${name}`);
  showScreen(name);
}

function showScreen(name) {
  current = name;
  activity = { startedAt: Date.now(), offered: false };
  title.textContent = modes[name].title;
  progress.textContent = "";
  content.replaceChildren();
  screen.hidden = false;
  document.body.classList.add("test-screen-open");
  modes[name].render();
  title.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function closeScreen() {
  if (!current) return;
  const closed = current;
  current = null;
  activity = null;
  content.replaceChildren();
  screen.hidden = true;
  document.body.classList.remove("test-screen-open");
  if (modes[location.hash.slice(1)]) history.replaceState(null, "", location.pathname + location.search);
  launchers.find(button => button.dataset.openFrenchTest === closed)?.focus();
}

function finishActivity(slot, result, ids, answers, grade) {
  const score = `${result.points} de ${result.total}`;
  const message = slot.closest(".french-test-content")?.querySelector("[data-french-result]");
  if (message) {
    message.textContent = `Has acertado ${score}. ${result.points === result.total ? "¡Perfecto!" : "Repasa las respuestas marcadas y vuelve a intentarlo."}`;
    message.focus();
  }
  if (activity.offered) return;
  activity.offered = true;
  celebratePet((result.points / result.total) * 10);
  offerActivityRanking(slot, { activity: `french-numbers-${current}`, ids, answers, startedAt: activity.startedAt, finishedAt: Date.now() });
}

function renderMatching() {
  activity.answers = {};
  activity.selected = null;
  activity.order = shuffle(frenchNumberPairs.map(pair => pair.id));
  content.innerHTML = `
    <div class="french-test-content">
      <p class="match-help" id="french-matching-help">Elige una palabra de la izquierda y después el número que le corresponde. La letra marca cada unión.</p>
      <div class="matching french-matching" id="french-matching-board" aria-describedby="french-matching-help"></div>
      <p data-french-result class="quiz-result" role="status" aria-live="polite" tabindex="-1"></p>
      <div class="nav"><button class="secondary" type="button" data-action="clear">Borrar uniones</button><button class="secondary" type="button" data-action="shuffle">Otra ronda</button><button class="primary" type="button" data-action="check">Comprobar</button><button class="primary" type="button" data-action="finish" hidden>Terminar y volver</button></div>
      <div data-ranking-slot></div>
    </div>`;
  const board = content.querySelector("#french-matching-board");
  const result = content.querySelector("[data-french-result]");
  const finish = content.querySelector('[data-action="finish"]');
  const paint = focus => {
    board.innerHTML = `<svg class="arrows" aria-hidden="true"><defs><marker id="french-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="currentColor"/></marker></defs><g id="french-lines"></g></svg>
      <div class="match-column">${frenchNumberPairs.map((pair, index) => `<button type="button" class="match-item ${activity.answers[pair.id] ? "connected" : ""} ${activity.selected === pair.id ? "active" : ""}" data-left="${pair.id}" aria-pressed="${activity.selected === pair.id}"><span class="match-badge">${letters[index]}</span><span lang="fr">${pair.left}</span></button>`).join("")}</div><div></div>
      <div class="match-column">${activity.order.map(id => { const pair = frenchNumberPairs.find(item => item.id === id); const owner = frenchNumberPairs.findIndex(item => activity.answers[item.id] === id); return `<button type="button" class="match-item ${owner >= 0 ? "connected" : ""}" data-right="${id}"><span class="match-badge">${owner >= 0 ? letters[owner] : "·"}</span><span>${pair.right}</span></button>`; }).join("")}</div>`;
    progress.textContent = `${Object.keys(activity.answers).length} de ${frenchNumberPairs.length} unidas`;
    if (focus) board.querySelector(focus)?.focus();
    requestAnimationFrame(() => drawLines(board));
  };
  board.addEventListener("click", event => {
    const left = event.target.closest("[data-left]");
    if (left) {
      activity.selected = activity.selected === left.dataset.left ? null : left.dataset.left;
      delete activity.answers[activity.selected];
      result.textContent = "";
      paint(`[data-left="${left.dataset.left}"]`);
      return;
    }
    const right = event.target.closest("[data-right]");
    if (!right || !activity.selected) return;
    for (const pair of frenchNumberPairs) if (activity.answers[pair.id] === right.dataset.right) delete activity.answers[pair.id];
    activity.answers[activity.selected] = right.dataset.right;
    activity.selected = null;
    result.textContent = "";
    paint(`[data-right="${right.dataset.right}"]`);
  });
  content.querySelector('[data-action="clear"]').addEventListener("click", () => { activity.answers = {}; activity.selected = null; finish.hidden = true; result.textContent = ""; paint(); });
  content.querySelector('[data-action="shuffle"]').addEventListener("click", () => { activity.answers = {}; activity.selected = null; activity.order = shuffle(frenchNumberPairs.map(pair => pair.id)); finish.hidden = true; result.textContent = ""; paint(); });
  content.querySelector('[data-action="check"]').addEventListener("click", () => {
    if (Object.keys(activity.answers).length < frenchNumberPairs.length) {
      result.textContent = `Faltan uniones: llevas ${Object.keys(activity.answers).length} de ${frenchNumberPairs.length}.`;
      result.focus();
      return;
    }
    const graded = gradeFrenchMatching(frenchNumberPairs, activity.answers);
    board.querySelectorAll(".match-item").forEach(item => {
      const pair = frenchNumberPairs.find(candidate => candidate.id === (item.dataset.left ?? item.dataset.right));
      const correct = graded.results.find(itemResult => itemResult.pair.id === pair.id)?.correct;
      item.classList.toggle("is-ok", correct);
      item.classList.toggle("is-bad", !correct);
    });
    result.textContent = `Has unido bien ${graded.points} de ${graded.total}.`;
    finish.hidden = false;
    finishActivity(content.querySelector("[data-ranking-slot]"), graded, frenchNumberPairs.map(pair => pair.id), activity.answers, graded.points);
  });
  finish.addEventListener("click", closeScreen);
  paint();
}

function renderWriting() {
  content.innerHTML = `<div class="french-test-content"><p>Escribe en francés el nombre de cada número. Las palabras de ayuda están en otra pantalla para que puedas hacerlo de memoria.</p>
    <form id="french-writing-form" class="french-writing-form"><div class="french-writing-grid">${frenchNumbers.map(item => `<label><span>${item.number}</span><input name="french-number-${item.number}" autocomplete="off" spellcheck="false" required aria-label="Número ${item.number} en francés"></label>`).join("")}</div>
      <div class="nav"><button class="primary" type="submit">Corregir respuestas</button><button class="secondary" type="reset">Intentarlo de nuevo</button><button class="primary" type="button" data-action="finish" hidden>Terminar y volver</button></div>
    </form><p data-french-result class="quiz-result" role="status" aria-live="polite" tabindex="-1"></p><div data-ranking-slot></div></div>`;
  const form = content.querySelector("form");
  const result = content.querySelector("[data-french-result]");
  const finish = content.querySelector('[data-action="finish"]');
  form.addEventListener("submit", event => {
    event.preventDefault();
    const answers = Object.fromEntries(new FormData(form));
    const graded = gradeFrenchWriting(frenchNumbers.map(item => ({ ...item, id: `french-number-${item.number}` })), answers);
    result.textContent = `Has acertado ${graded.points} de ${graded.total}. ${graded.points === graded.total ? "¡Perfecto!" : "Revisa las respuestas marcadas."}`;
    form.querySelectorAll("input").forEach(input => {
      const item = graded.results.find(entry => entry.question.id === input.name);
      input.classList.toggle("is-correct", item.correct);
      input.classList.toggle("is-incorrect", !item.correct);
    });
    finish.hidden = false;
    finishActivity(content.querySelector("[data-ranking-slot]"), graded, frenchNumbers.map(item => `french-number-${item.number}`), answers, graded.points);
    result.focus();
  });
  form.addEventListener("reset", () => { window.setTimeout(() => { result.textContent = ""; form.querySelectorAll("input").forEach(input => input.classList.remove("is-correct", "is-incorrect")); }, 0); });
  finish.addEventListener("click", closeScreen);
  form.querySelector("input")?.focus();
}

function renderQuiz() {
  content.innerHTML = `<div class="french-test-content"><p>Lee el número y elige la única forma bien escrita en francés.</p>
    <form id="french-quiz-form" class="french-quiz-form"><div class="grammar-questions">${frenchNumberQuiz.map((question, index) => `<fieldset><legend>${index + 1}. ${question.question}</legend><div class="options">${question.options.map((option, optionIndex) => `<label><input type="radio" name="${question.id}" value="${optionIndex}" required><span lang="fr">${option}</span></label>`).join("")}</div></fieldset>`).join("")}</div>
      <div class="nav"><button class="primary" type="submit">Corregir test</button><button class="secondary" type="reset">Otro test</button><button class="primary" type="button" data-action="finish" hidden>Terminar y volver</button></div>
    </form><p data-french-result class="quiz-result" role="status" aria-live="polite" tabindex="-1"></p><div data-ranking-slot></div></div>`;
  const form = content.querySelector("form");
  const result = content.querySelector("[data-french-result]");
  const finish = content.querySelector('[data-action="finish"]');
  form.addEventListener("submit", event => {
    event.preventDefault();
    const answers = Object.fromEntries([...new FormData(form)].map(([id, value]) => [id, Number(value)]));
    const graded = gradeFrenchQuiz(frenchNumberQuiz, answers);
    result.textContent = `Has acertado ${graded.points} de ${graded.total}. ${graded.points === graded.total ? "¡Perfecto!" : "Busca las opciones marcadas para repasar."}`;
    finish.hidden = false;
    finishActivity(content.querySelector("[data-ranking-slot]"), graded, frenchNumberQuiz.map(question => question.id), Object.fromEntries(Object.entries(answers).map(([id, value]) => [id, String(value)])), graded.points);
    result.focus();
  });
  form.addEventListener("reset", () => { window.setTimeout(() => { result.textContent = ""; finish.hidden = true; }, 0); });
  finish.addEventListener("click", closeScreen);
}

function drawLines(board) {
  const svg = board.querySelector(".arrows");
  const lines = board.querySelector("#french-lines");
  if (!svg || !lines) return;
  const bounds = board.getBoundingClientRect();
  lines.replaceChildren();
  for (const pair of frenchNumberPairs) {
    const rightId = activity.answers[pair.id];
    if (!rightId) continue;
    const left = board.querySelector(`[data-left="${pair.id}"]`).getBoundingClientRect();
    const right = board.querySelector(`[data-right="${rightId}"]`).getBoundingClientRect();
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", String(left.right - bounds.left));
    line.setAttribute("y1", String(left.top + left.height / 2 - bounds.top));
    line.setAttribute("x2", String(right.left - bounds.left));
    line.setAttribute("y2", String(right.top + right.height / 2 - bounds.top));
    line.setAttribute("stroke", "currentColor");
    line.setAttribute("stroke-width", "2");
    line.setAttribute("marker-end", "url(#french-arrow)");
    lines.append(line);
  }
}

for (const launcher of launchers) launcher.addEventListener("click", () => openScreen(launcher.dataset.openFrenchTest));
back.addEventListener("click", closeScreen);
window.addEventListener("popstate", () => {
  const name = location.hash.slice(1);
  if (modes[name]) showScreen(name);
  else if (current) closeScreen();
});
window.addEventListener("resize", () => current === "matching" && drawLines(content.querySelector("#french-matching-board")));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && current) { event.preventDefault(); closeScreen(); }
});
if (modes[location.hash.slice(1)]) showScreen(location.hash.slice(1));
