import { gradeGrammarQuiz, pickGrammarQuestions, GRAMMAR_QUIZ_SIZE } from "./ingles-gramatica-questions.mjs";
import { flechasPairs, gradeFlechas } from "./ingles-flechas-questions.mjs";
import { offerActivityRanking } from "../activity-ranking.mjs";
import { celebratePet } from "../pet-companion.mjs";
import { shuffle } from "../grading.mjs";

const screen = document.querySelector("#test-screen");
const content = document.querySelector("#test-screen-content");
const screenTitle = document.querySelector("#test-screen-title");
const screenProgress = document.querySelector("#test-screen-progress");
const backButton = screen.querySelector('[data-action="back"]');
const launchers = [...document.querySelectorAll("[data-open-test]")];
const LETTERS = "ABCDEFGH";

const modes = {
  test: { title: "Test · To be, to have y posesivos", render: () => renderQuiz() },
  flechas: { title: "Unir con flechas · has y have", render: () => renderFlechas() },
};

let current = null;
let quiz = null;
let flechas = null;

/* ------------------------------------------------------------------ *
 * Pantalla del test: se abre encima de la lección, con su propia barra.
 * ------------------------------------------------------------------ */

function openScreen(name) {
  if (!modes[name] || current === name) return;
  if (location.hash !== `#${name}`) history.pushState({ testScreen: name }, "", `#${name}`);
  showScreen(name);
}

function showScreen(name) {
  current = name;
  screenTitle.textContent = modes[name].title;
  screenProgress.textContent = "";
  content.replaceChildren();
  screen.hidden = false;
  document.body.classList.add("test-screen-open");
  modes[name].render();
  titleFocus();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function hideScreen() {
  if (!current) return;
  const closed = current;
  current = null;
  quiz = null;
  flechas = null;
  screen.hidden = true;
  content.replaceChildren();
  screenProgress.textContent = "";
  document.body.classList.remove("test-screen-open");
  if (modes[location.hash.slice(1)]) history.replaceState(null, "", location.pathname + location.search);
  launchers.find(button => button.dataset.openTest === closed)?.focus();
}

function requestClose() {
  hideScreen();
}

function titleFocus() {
  screenTitle.focus({ preventScroll: true });
}

for (const button of launchers) button.addEventListener("click", () => openScreen(button.dataset.openTest));
backButton.addEventListener("click", requestClose);

window.addEventListener("popstate", () => {
  const name = location.hash.slice(1);
  if (modes[name]) {
    if (current !== name) showScreen(name);
  } else if (current) {
    hideScreen();
  }
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && current) {
    event.preventDefault();
    requestClose();
  }
});

if (modes[location.hash.slice(1)]) showScreen(location.hash.slice(1));

/* ------------------------------------------------------------------ *
 * Test de 24 preguntas
 * ------------------------------------------------------------------ */

function renderQuiz() {
  quiz = { questions: pickGrammarQuestions(GRAMMAR_QUIZ_SIZE), practice: false, mistakes: [], startedAt: Date.now(), celebratedStart: null };
  content.innerHTML = `
    <p class="muted">24 preguntas <strong>elegidas al azar</strong> de un banco de 72, así que cada test es distinto. Entran todos los temas (to be, to have / have got y posesivos). Cada acierto vale un punto; los errores y las preguntas sin responder valen cero. Al corregir verás tu respuesta, la solución y su explicación.</p>
    <form id="quiz-form">
      <div id="quiz-questions" class="grammar-questions"></div>
      <div class="nav">
        <button class="primary" type="submit">Corregir test</button>
        <button class="secondary" type="button" data-action="mistakes" hidden>Practicar solo los fallos</button>
        <button class="secondary" type="reset">Hacer otro test</button>
      </div>
    </form>
    <p id="quiz-result" class="quiz-result" role="status" aria-live="polite" tabindex="-1"></p>
    <div class="test-screen-end">
      <button class="primary" type="button" data-action="finish" hidden>Terminar y volver</button>
    </div>
    <div data-ranking-slot></div>`;

  const form = content.querySelector("#quiz-form");
  const list = content.querySelector("#quiz-questions");
  const result = content.querySelector("#quiz-result");
  const slot = content.querySelector("[data-ranking-slot]");
  const retry = form.querySelector('[data-action="mistakes"]');
  const finish = content.querySelector('[data-action="finish"]');

  const updateProgress = () => {
    const answered = new Set([...new FormData(form).keys()]).size;
    screenProgress.textContent = `${answered} de ${quiz.questions.length} contestadas`;
  };

  const clearFeedback = () => {
    retry.hidden = true;
    result.textContent = "";
    slot.replaceChildren();
    for (const feedback of list.querySelectorAll(".grammar-feedback")) feedback.hidden = true;
  };

  const renderQuestions = () => {
    list.innerHTML = quiz.questions.map((question, position) => `
      <fieldset data-question="${question.id}" aria-describedby="feedback-${question.id}">
        <legend>${position + 1}. ${question.question}</legend>
        <div class="options">
          ${question.options.map((option, index) => `
            <label><input type="radio" name="${question.id}" value="${index}"><span>${option}</span></label>
          `).join("")}
        </div>
        <p id="feedback-${question.id}" class="grammar-feedback" hidden></p>
      </fieldset>
    `).join("");
    updateProgress();
  };

  form.addEventListener("submit", event => {
    event.preventDefault();
    const answers = Object.fromEntries([...new FormData(form)].map(([id, value]) => [id, Number(value)]));
    const graded = gradeGrammarQuiz(quiz.questions, answers);
    quiz.mistakes = graded.results.filter(item => !item.correct).map(item => item.question);
    for (const item of graded.results) {
      const feedback = list.querySelector(`#feedback-${item.question.id}`);
      feedback.textContent = `${item.correct ? "¡Correcto!" : "Para repasar."} Tu respuesta: ${item.question.options[item.selected] ?? "Sin responder"}. Respuesta correcta: ${item.question.options[item.question.answer]} Por qué: ${item.question.explanation}`;
      feedback.hidden = false;
    }
    retry.hidden = quiz.mistakes.length === 0;
    finish.hidden = false;
    const unanswered = graded.results.filter(item => item.selected === undefined).length;
    result.textContent = `Has acertado ${graded.correct} de ${quiz.questions.length}. Nota: ${graded.grade.toLocaleString("es-ES", { maximumFractionDigits: 1 })}/10. ${quiz.mistakes.length ? "Revisa las explicaciones o practica solo los fallos; las preguntas sin responder también cuentan como fallo." : "¡Muy bien, has acertado todas!"}${unanswered && !quiz.practice ? " Contesta todas las preguntas para poder participar en el ranking." : ""}`;
    slot.replaceChildren();
    if (!unanswered && !quiz.practice) {
      if (quiz.celebratedStart !== quiz.startedAt) {
        celebratePet(graded.grade);
        quiz.celebratedStart = quiz.startedAt;
      }
      offerActivityRanking(slot, {
        activity: "english-grammar",
        ids: quiz.questions.map(question => question.id),
        answers: Object.fromEntries(quiz.questions.map(question => [question.id, String(answers[question.id])])),
        startedAt: quiz.startedAt, finishedAt: Date.now(),
      });
    }
    result.focus();
  });

  retry.addEventListener("click", () => {
    quiz.practice = true;
    quiz.questions = quiz.mistakes;
    quiz.startedAt = Date.now();
    renderQuestions();
    clearFeedback();
    finish.hidden = true;
    result.textContent = `Repaso de ${quiz.questions.length} ${quiz.questions.length === 1 ? "pregunta errónea o sin responder" : "preguntas erróneas o sin responder"}. Este repaso no participa en el ranking.`;
    list.querySelector("input")?.focus();
  });

  form.addEventListener("change", () => {
    clearFeedback();
    updateProgress();
  });

  form.addEventListener("reset", event => {
    event.preventDefault();
    quiz.practice = false;
    quiz.questions = pickGrammarQuestions(GRAMMAR_QUIZ_SIZE);
    quiz.startedAt = Date.now();
    quiz.celebratedStart = null;
    renderQuestions();
    clearFeedback();
    finish.hidden = true;
    result.textContent = "Test nuevo: otras 24 preguntas al azar del banco de 72.";
    list.querySelector("input")?.focus();
  });

  finish.addEventListener("click", requestClose);

  renderQuestions();
}

/* ------------------------------------------------------------------ *
 * Unir con flechas: has / have
 * ------------------------------------------------------------------ */

function renderFlechas() {
  flechas = {
    answers: {}, selected: null, order: shuffle(flechasPairs.map(pair => pair.id)),
    checked: null, startedAt: Date.now(), offered: false,
  };
  content.innerHTML = `
    <p class="match-help" id="flechas-help">Selecciona una frase de la izquierda (A, B, C…) y después el verbo que le corresponde. La misma letra marca las dos puntas de la flecha. Para cambiar una unión, vuelve a elegir la frase.</p>
    <div class="matching" id="flechas-board" aria-describedby="flechas-help"></div>
    <p id="flechas-result" class="quiz-result" role="status" aria-live="polite" tabindex="-1"></p>
    <div class="nav">
      <button class="secondary" type="button" data-action="clear">Borrar uniones</button>
      <button class="secondary" type="button" data-action="shuffle">Otra ronda</button>
      <button class="primary" type="button" data-action="check">Comprobar uniones</button>
      <button class="primary" type="button" data-action="finish" hidden>Terminar y volver</button>
    </div>
    <div data-ranking-slot></div>`;

  const board = content.querySelector("#flechas-board");
  const result = content.querySelector("#flechas-result");
  const finish = content.querySelector('[data-action="finish"]');
  const rankingSlot = content.querySelector("[data-ranking-slot]");

  // Cada intento (ronda nueva o cambio de flechas) cuenta como una prueba distinta.
  const restartAttempt = () => {
    flechas.startedAt = Date.now();
    flechas.offered = false;
    rankingSlot.replaceChildren();
  };

  const paint = focusSelector => {
    board.innerHTML = `
      <svg class="arrows" aria-hidden="true"><defs>
        <marker id="flechas-tip" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="currentColor"/></marker>
        <marker id="flechas-tip-ok" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#3b6a45"/></marker>
        <marker id="flechas-tip-bad" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#b1594a"/></marker>
      </defs><g id="flechas-lines"></g></svg>
      <div class="match-column">
        ${flechasPairs.map((pair, index) => {
          const state = flechas.checked?.results.find(item => item.pair.id === pair.id);
          return `<button type="button" class="match-item ${flechas.answers[pair.id] ? "connected" : ""} ${flechas.selected === pair.id ? "active" : ""} ${state ? (state.correct ? "is-ok" : "is-bad") : ""}" data-left="${pair.id}" aria-pressed="${flechas.selected === pair.id}">
            <span class="match-badge">${LETTERS[index]}</span><span>${pair.left}</span></button>`;
        }).join("")}
      </div>
      <div></div>
      <div class="match-column">
        ${flechas.order.map(id => {
          const pair = flechasPairs.find(item => item.id === id);
          const ownerIndex = flechasPairs.findIndex(item => flechas.answers[item.id] === id);
          const state = flechas.checked?.results.find(item => item.chosen === id);
          return `<button type="button" class="match-item ${ownerIndex >= 0 ? "connected" : ""} ${state ? (state.correct ? "is-ok" : "is-bad") : ""}" data-right="${id}">
            <span class="match-badge">${ownerIndex >= 0 ? LETTERS[ownerIndex] : "·"}</span><span>${pair.right}</span></button>`;
        }).join("")}
      </div>`;
    screenProgress.textContent = `${Object.keys(flechas.answers).length} de ${flechasPairs.length} unidas`;
    if (focusSelector) board.querySelector(focusSelector)?.focus();
    requestAnimationFrame(drawFlechasArrows);
  };

  board.addEventListener("click", event => {
    const left = event.target.closest("[data-left]");
    if (left) {
      const id = left.dataset.left;
      if (flechas.selected === id) {
        flechas.selected = null;
      } else {
        flechas.selected = id;
        delete flechas.answers[id];
      }
      flechas.checked = null;
      result.textContent = "";
      restartAttempt();
      paint(`[data-left="${id}"]`);
      return;
    }
    const right = event.target.closest("[data-right]");
    if (!right) return;
    const id = right.dataset.right;
    if (!flechas.selected) {
      const owner = flechasPairs.find(pair => flechas.answers[pair.id] === id);
      if (!owner) return;
      flechas.selected = owner.id;
      delete flechas.answers[owner.id];
      flechas.checked = null;
      result.textContent = "";
      restartAttempt();
      paint(`[data-left="${owner.id}"]`);
      return;
    }
    for (const pair of flechasPairs) if (flechas.answers[pair.id] === id) delete flechas.answers[pair.id];
    flechas.answers[flechas.selected] = id;
    flechas.selected = null;
    flechas.checked = null;
    result.textContent = "";
    restartAttempt();
    paint(`[data-right="${id}"]`);
  });

  content.querySelector('[data-action="clear"]').addEventListener("click", () => {
    flechas.answers = {};
    flechas.selected = null;
    flechas.checked = null;
    result.textContent = "";
    finish.hidden = true;
    restartAttempt();
    paint();
  });

  content.querySelector('[data-action="shuffle"]').addEventListener("click", () => {
    flechas.answers = {};
    flechas.selected = null;
    flechas.checked = null;
    flechas.order = shuffle(flechasPairs.map(pair => pair.id));
    result.textContent = "";
    finish.hidden = true;
    restartAttempt();
    paint();
  });

  content.querySelector('[data-action="check"]').addEventListener("click", () => {
    const joined = Object.keys(flechas.answers).length;
    if (joined < flechasPairs.length) {
      result.textContent = `Todavía faltan flechas: llevas ${joined} de ${flechasPairs.length}. Une todas las frases para comprobar.`;
      result.focus();
      return;
    }
    const graded = gradeFlechas(flechasPairs, flechas.answers);
    flechas.checked = graded;
    paint();
    finish.hidden = false;
    const review = graded.results.map(item => `<li class="${item.correct ? "bien" : "mal"}">
      <strong>${item.correct ? "✔" : "✘"}</strong> ${item.pair.left.replace("___", `<strong>${item.pair.right}</strong>`)}
      ${item.correct ? "" : `— la flecha correcta es <strong>${item.pair.right}</strong>`}
      <br><span class="muted">${item.pair.explanation}</span></li>`).join("");
    result.innerHTML = `<strong>Has unido bien ${graded.correct} de ${flechasPairs.length}.</strong> ${graded.correct === flechasPairs.length ? "¡Perfecto, todas las flechas están en su sitio!" : "Revisa las que están en rojo y vuelve a intentarlo."}<ul class="flechas-review">${review}</ul>`;
    if (!flechas.offered) {
      flechas.offered = true;
      offerActivityRanking(rankingSlot, {
        activity: "english-flechas",
        ids: flechasPairs.map(pair => pair.id),
        answers: Object.fromEntries(flechasPairs.map(pair => [pair.id, String(flechas.answers[pair.id])])),
        startedAt: flechas.startedAt, finishedAt: Date.now(),
      });
    }
    result.focus();
  });

  finish.addEventListener("click", requestClose);

  paint();
}

function drawFlechasArrows() {
  if (current !== "flechas" || !flechas) return;
  const board = document.querySelector("#flechas-board");
  const svg = board?.querySelector("svg");
  if (!board || !svg) return;
  const bounds = board.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
  const rights = [...board.querySelectorAll("[data-right]")];
  const paths = [];
  for (const left of board.querySelectorAll("[data-left]")) {
    const answer = flechas.answers[left.dataset.left];
    const right = rights.find(element => element.dataset.right === answer);
    if (!right) continue;
    const a = left.getBoundingClientRect();
    const b = right.getBoundingClientRect();
    const x1 = a.right - bounds.left;
    const y1 = a.top + a.height / 2 - bounds.top;
    const x2 = b.left - bounds.left;
    const y2 = b.top + b.height / 2 - bounds.top;
    const state = flechas.checked?.results.find(item => item.pair.id === left.dataset.left);
    const stroke = state ? (state.correct ? "#3b6a45" : "#b1594a") : "currentColor";
    const marker = state ? (state.correct ? "flechas-tip-ok" : "flechas-tip-bad") : "flechas-tip";
    paths.push(`<path d="M${x1},${y1} C${x1 + (x2 - x1) / 2},${y1} ${x1 + (x2 - x1) / 2},${y2} ${x2 - 3},${y2}" fill="none" stroke="${stroke}" stroke-width="2" marker-end="url(#${marker})"/>`);
  }
  board.querySelector("#flechas-lines").innerHTML = paths.join("");
}

window.addEventListener("resize", drawFlechasArrows);
