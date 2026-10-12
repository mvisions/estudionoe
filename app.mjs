import { questions, matchingPairs } from "./questions.mjs";
import { gradeChoice, gradeWritten, shuffle, summarize } from "./grading.mjs";
import { API_BASE } from "./config.mjs";

const app = document.querySelector("#app");
const notice = document.querySelector("#notice");
const storageKey = "noe-history-exam-v2";
const modes = {
  easy: { title: "Test fácil", icon: "✓", tag: "El primer paso", description: "Una respuesta correcta y dos falsas. Lee con calma y elige la mejor opción." },
  matching: { title: "Unir con flechas", icon: "↔", tag: "Conecta las ideas", description: "Une cada concepto con su respuesta. Haz clic en ambos lados para dibujar una flecha." },
  written: { title: "Respuesta escrita", icon: "✎", tag: "El reto de explicar", description: "Responde con tus palabras. Recibirás una valoración: bien, regular o mal." },
};
let state = null;
let selectedLeft = null;
let results = [];
let noticeTimer;
let storageFailed = false;
let rankingMode = "easy";
let rankingRequest = 0;
const receiptKey = "noe-ranking-receipts-v1";

const duration = milliseconds => {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s`;
};
const elapsed = () => state?.durationMs ?? Math.max(0, Date.now() - (state?.startedAt ?? Date.now()));

async function api(path, method = "GET", body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method, headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(90000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Error del servidor (${response.status}).`);
  return data;
}

function rememberReceipt(remote) {
  const receipts = JSON.parse(localStorage.getItem(receiptKey) ?? "[]");
  receipts.push({ id: remote.id, token: remote.token });
  localStorage.setItem(receiptKey, JSON.stringify(receipts));
}

const escape = value => String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const format = number => new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(number);
const bank = mode => mode === "matching" ? matchingPairs : questions;
const examItems = () => state.ids.map(id => bank(state.mode).find(item => item.id === id));
const isAnswered = item => state.answers[item.id] !== undefined && String(state.answers[item.id]).trim() !== "";

function announce(text, persistent = false) {
  clearTimeout(noticeTimer);
  notice.textContent = text;
  if (!persistent) noticeTimer = setTimeout(() => { notice.textContent = ""; }, 6000);
}

function save() {
  try {
    if (state) localStorage.setItem(storageKey, JSON.stringify(state));
    else localStorage.removeItem(storageKey);
  } catch (error) {
    if (!storageFailed) {
      storageFailed = true;
      console.error("No se pudo guardar el examen localmente.", error);
      announce("No se puede guardar el progreso en este navegador. Puedes seguir, pero no cierres la pestaña.", true);
    }
  }
}

function resetAll() {
  confirmAction("¿Borrar todo y empezar de nuevo?",
    "Se borrarán tus respuestas, el progreso y tus resultados del ranking vinculados a este navegador. No se borran los resultados de otras personas. Esta acción no se puede deshacer.",
    "Sí, borrar todo", async () => {
      try {
        const receipts = JSON.parse(localStorage.getItem(receiptKey) ?? "[]");
        if (state?.remote && !receipts.some(receipt => receipt.id === state.remote.id)) receipts.push(state.remote);
        for (const receipt of receipts) await api(`/api/exams/${receipt.id}`, "DELETE", { token: receipt.token });
        localStorage.removeItem(receiptKey);
        localStorage.removeItem(storageKey);
        localStorage.removeItem("noe-history-exam-v1");
      } catch (error) {
        console.error("No se pudieron borrar los datos del examen.", error);
        announce(`No se ha completado el borrado: ${error.message} Conservamos los datos para que puedas reintentarlo.`, true);
        return;
      }
      state = null;
      results = [];
      selectedLeft = null;
      storageFailed = false;
      home();
      focusHeading();
      announce("Datos borrados. Elige un modo para empezar de nuevo.");
    });
}

function resetButton() {
  return `<button class="secondary danger" data-action="reset-all">Borrar todo y empezar de nuevo</button>`;
}

function restore() {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;
    const candidate = JSON.parse(raw);
    if (!candidate || candidate.version !== 2 || !Object.hasOwn(modes, candidate.mode)) throw new Error("Formato de examen desconocido.");
    const items = bank(candidate.mode);
    if (!Array.isArray(candidate.ids) || !candidate.ids.length || new Set(candidate.ids).size !== candidate.ids.length
      || candidate.ids.some(id => !items.some(item => item.id === id))
      || !candidate.answers || typeof candidate.answers !== "object" || Array.isArray(candidate.answers)
      || !Number.isInteger(candidate.page) || candidate.page < 0
      || candidate.page >= Math.ceil(candidate.ids.length / (candidate.mode === "matching" ? 5 : 1))
      || typeof candidate.finished !== "boolean"
      || !candidate.options || typeof candidate.options !== "object") throw new Error("El progreso guardado no es válido.");
    for (const [id, value] of Object.entries(candidate.answers)) {
      if (!candidate.ids.some(itemId => String(itemId) === id) || typeof value !== "string") throw new Error("Respuesta guardada no válida.");
      if (candidate.mode === "matching") {
        const leftIndex = candidate.ids.indexOf(id);
        const rightIndex = candidate.ids.indexOf(value);
        if (rightIndex < 0 || Math.floor(leftIndex / 5) !== Math.floor(rightIndex / 5)) throw new Error("Pareja guardada no válida.");
      }
      if (candidate.mode === "easy") {
        const question = questions.find(item => String(item.id) === id);
        if (![question.answer, ...question.wrong].includes(value)) throw new Error("Opción guardada no válida.");
      }
    }
    if (candidate.mode === "matching" && new Set(Object.values(candidate.answers)).size !== Object.values(candidate.answers).length) throw new Error("Parejas guardadas duplicadas.");
    if (candidate.mode === "easy") {
      for (const id of candidate.ids) {
        const question = questions.find(item => item.id === id);
        const options = candidate.options[id];
        if (!Array.isArray(options) || options.length !== 3 || new Set(options).size !== 3
          || options.some(option => ![question.answer, ...question.wrong].includes(option))) throw new Error("Opciones guardadas no válidas.");
      }
    }
    if (candidate.mode === "matching") {
      for (let page = 0; page < Math.ceil(candidate.ids.length / 5); page++) {
        const expected = candidate.ids.slice(page * 5, page * 5 + 5);
        const options = candidate.options[page];
        if (!Array.isArray(options) || options.length !== expected.length || new Set(options).size !== expected.length
          || options.some(id => !expected.includes(id))) throw new Error("Orden de parejas no válido.");
      }
    }
    state = candidate;
  } catch (error) {
    console.error("No se pudo recuperar el examen.", error);
    announce("No se pudo recuperar el examen guardado. Puedes comenzar uno nuevo.", true);
  }
}

function sourceNote() {
  return `<details class="source-note"><summary>Sobre las preguntas y la corrección</summary>
    <p>Están incluidas las ${questions.length} preguntas de tus apuntes, con su numeración original del 1 al 30.
    Las respuestas se mantienen según tus apuntes, por tu elección; algunas fechas y explicaciones son simplificaciones o contienen imprecisiones históricas.</p>
    <p>El modo de flechas transforma el temario en ${matchingPairs.length} parejas cortas para evitar respuestas duplicadas.
    En el modo escrito buscamos ideas clave, ignoramos tildes y toleramos pequeños errores. No es IA: no comprende todas las formas de expresar una idea.
    Bien = 1 punto; regular = 0,5; mal o sin responder = 0. La nota es puntos obtenidos ÷ preguntas del examen × 10.</p></details>`;
}

function home() {
  app.innerHTML = `<section class="hero"><div><span class="eyebrow">Un poquito cada día, un gran avance</span>
    <h1>La historia se aprende<br><span class="accent">practicando.</span></h1>
    <p>Del Imperio Romano a los reinos cristianos. Elige cómo quieres estudiar y descubre todo lo que ya sabes.</p></div>
    <div class="hero-art" aria-hidden="true"><div class="book"><span>MI CUADERNO</span><strong>La Edad<br>Media</strong><span>HISTORIA</span></div><span class="art-note">✓ Hoy es un buen día para aprender</span></div></section>
    <section aria-labelledby="modes-title"><div class="section-heading"><h2 id="modes-title">Elige tu modo de estudio</h2><span class="muted">Tres formas de aprender</span></div>
    <div class="mode-grid">${Object.entries(modes).map(([key, mode]) => `<article class="mode-card">
    <span class="mode-icon" aria-hidden="true">${mode.icon}</span><span class="pill">${mode.tag}</span><h3>${mode.title}</h3><p>${mode.description}</p>
    <button class="primary" data-start="${key}">Empezar a practicar <span aria-hidden="true">→</span></button></article>`).join("")}</div></section>
    <div class="info-strip"><span>✓ Nota final sobre 10</span><span>✓ Revisión de todos los fallos</span><span>✓ Explicaciones para mejorar</span></div>
    ${state ? `<div class="review"><strong>${state.finished ? "Tu último resultado está guardado" : "Tienes un examen en curso"}</strong>
    <p>${modes[state.mode].title} · ${state.ids.length} preguntas</p><button class="secondary" data-action="resume">${state.finished ? "Ver resultado" : "Continuar examen"}</button></div>` : ""}
    ${rankingMarkup()}<div class="reset-area">${resetButton()}</div>${sourceNote()}`;
  loadRanking();
}

function profileForm(mode, ids) {
  const profile = state?.profile ?? { name: "", course: "" };
  const dialog = document.createElement("dialog");
  dialog.innerHTML = `<h2>Antes de empezar</h2><form id="student-form">
    <label class="input-label" for="student-name">Nombre o alias (sin apellidos)</label>
    <input id="student-name" name="name" maxlength="40" required autocomplete="off" value="${escape(profile.name)}">
    <label class="input-label" for="student-course">Curso</label>
    <input id="student-course" name="course" maxlength="30" required placeholder="Por ejemplo: 5.º A" value="${escape(profile.course)}">
    <p class="muted">Tu resultado mostrará la nota final y el tiempo, incluyendo pausas. ${ids ? "Este repaso no entra en el ranking." : "El ranking es público y se guarda en Google Cloud mediante Render. Usa un alias y un curso genérico; no incluyas datos personales."}</p>
    ${ids ? "" : `<label class="consent"><input type="checkbox" name="consent"> Acepto publicar mi alias, curso, nota y tiempo en el ranking. Si eres menor, pide permiso a tu responsable.</label>`}
    <p class="form-error" role="alert"></p><div class="nav"><button type="button" class="secondary" data-cancel>Cancelar</button>
    <button type="submit" class="secondary" name="practice" value="yes">Practicar sin ranking</button>
    ${ids ? "" : `<button type="submit" class="primary" name="ranked" value="yes">Empezar con ranking</button>`}</div></form>`;
  document.body.append(dialog);
  dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.querySelector("form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const ranked = event.submitter?.name === "ranked";
    const profile = { name: String(data.get("name")).trim(), course: String(data.get("course")).trim() };
    const errorLabel = form.querySelector(".form-error");
    if (!profile.name || !profile.course) { errorLabel.textContent = "Completa el nombre o alias y el curso."; return; }
    if (ranked && data.get("consent") !== "on") { errorLabel.textContent = "Debes aceptar la publicación para participar; también puedes practicar sin ranking."; return; }
    const buttons = form.querySelectorAll("button");
    buttons.forEach(button => { button.disabled = true; });
    errorLabel.textContent = ranked ? "Conectando con el ranking… Render puede tardar en arrancar." : "";
    try {
      const remote = ranked ? await api("/api/exams", "POST", { ...profile, mode, consent: true }) : null;
      if (remote) {
        try { rememberReceipt(remote); }
        catch (error) {
          await api(`/api/exams/${remote.id}`, "DELETE", { token: remote.token });
          throw new Error(`No se puede guardar el acceso a tu resultado: ${error.message}`);
        }
      }
      dialog.close();
      start(mode, ids, profile, remote);
    } catch (error) {
      console.error("No se pudo iniciar el examen con ranking.", error);
      errorLabel.textContent = `No se ha iniciado: ${error.message} Puedes reintentar o practicar sin ranking.`;
      buttons.forEach(button => { button.disabled = false; });
    }
  });
  dialog.showModal();
}

function start(mode, ids, profile, remote) {
  const items = ids ? bank(mode).filter(item => ids.includes(item.id)) : bank(mode);
  state = { version: 2, mode, ids: remote?.ids ?? shuffle(items).map(item => item.id), answers: {}, options: {}, page: 0, finished: false,
    profile, remote, startedAt: remote?.startedAt ?? Date.now(), practice: !remote };
  if (mode === "easy") for (const item of items) state.options[item.id] = shuffle([item.answer, ...item.wrong]);
  if (mode === "matching") for (let page = 0; page < Math.ceil(state.ids.length / 5); page++)
    state.options[page] = shuffle(state.ids.slice(page * 5, page * 5 + 5));
  selectedLeft = null;
  save();
  renderExam();
}

function focusHeading() {
  const heading = app.querySelector("h1");
  heading?.setAttribute("tabindex", "-1");
  heading?.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function renderExam(focus = true) {
  selectedLeft = null;
  const items = examItems();
  const matching = state.mode === "matching";
  const totalPages = Math.ceil(items.length / (matching ? 5 : 1));
  const answered = items.filter(isAnswered).length;
  const question = items[state.page];
  app.innerHTML = `<div class="exam-top"><div><span class="eyebrow">Tu sesión de historia</span><h1>${modes[state.mode].title}</h1></div>
    <button class="secondary" data-action="home">Guardar y salir</button></div>
    <div class="student-strip"><span>${escape(state.profile?.name ?? "Estudiante")} · ${escape(state.profile?.course ?? "Sin curso")}</span>
    <span id="exam-timer" role="timer">Tiempo: ${duration(elapsed())}</span><span>${state.remote ? "Examen para el ranking" : "Práctica sin ranking"}</span></div>
    <div class="progress"><div class="progress-label"><span>${matching ? "Bloque" : "Pregunta"} ${state.page + 1} de ${totalPages}</span>
    <span id="answered-count">${answered} de ${items.length} respondidas</span></div><progress id="exam-progress" value="${answered}" max="${items.length}" aria-label="Preguntas respondidas"></progress></div>
    <section class="question-card">${matching ? matchingMarkup(items) : `<span class="eyebrow">Pregunta ${question.id} de tus apuntes</span><h2>${escape(question.title)}</h2>
      ${state.mode === "easy" ? `<div class="options" role="group" aria-label="Elige una respuesta">${state.options[question.id].map((option, index) =>
        `<button class="option ${state.answers[question.id] === option ? "selected" : ""}" aria-pressed="${state.answers[question.id] === option}" data-option="${index}">
        <span class="option-letter">${"ABC"[index]}</span><span>${escape(option)}</span></button>`).join("")}</div>` :
        `<label class="input-label" for="written-answer">Tu respuesta</label><textarea id="written-answer" maxlength="4000" placeholder="Explica lo que recuerdas con tus palabras…">${escape(state.answers[question.id] ?? "")}</textarea>
        <p class="muted">Incluye las fechas, nombres e ideas que pide la pregunta. Corrección orientativa por ideas clave: 1 / 0,5 / 0 puntos.</p>`}`}</section>
    <div class="nav"><button class="secondary" data-action="previous" ${state.page === 0 ? "disabled" : ""}>← Anterior</button>
    <div class="nav-right">${state.page < totalPages - 1 ? `<button class="secondary" data-action="next">Siguiente →</button>` : ""}
    <button class="primary" data-action="finish">Finalizar examen</button></div></div>
    <nav class="jump-list" aria-label="${matching ? "Ir a un bloque" : "Ir a una pregunta"}">${Array.from({ length: totalPages }, (_, page) => {
      const group = matching ? items.slice(page * 5, page * 5 + 5) : [items[page]];
      return `<button class="jump ${page === state.page ? "active" : ""} ${group.every(isAnswered) ? "answered" : ""}"
      data-page="${page}" aria-label="${matching ? "Bloque" : "Pregunta"} ${page + 1}" ${page === state.page ? 'aria-current="step"' : ""}>${page + 1}</button>`;
    }).join("")}</nav><p class="muted">Puedes cambiar tus respuestas antes de terminar. La corrección aparece únicamente al finalizar.</p>
    <div class="reset-area">${resetButton()}</div>`;
  if (focus) focusHeading();
  requestAnimationFrame(drawArrows);
}

function matchingMarkup(items) {
  const group = items.slice(state.page * 5, state.page * 5 + 5);
  return `<span class="eyebrow">Relaciona los conceptos</span><h2>Cada idea tiene su pareja.</h2>
    <p class="match-help" id="match-instructions">Selecciona un concepto a la izquierda y su respuesta a la derecha. La misma letra identifica ambos extremos. Para cambiar una unión, vuelve a elegir; para borrarla, usa «Borrar uniones».</p>
    <div class="matching" aria-describedby="match-instructions"><svg class="arrows" aria-hidden="true"><defs><marker id="arrow-tip" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#78947a"/></marker></defs><g id="arrow-lines"></g></svg>
    <div class="match-column">${group.map((item, index) => `<button class="match-item ${isAnswered(item) ? "connected" : ""}" data-left="${item.id}" aria-pressed="false">
    <span class="match-badge">${"ABCDE"[index]}</span><span>${escape(item.title)}</span></button>`).join("")}</div><div></div>
    <div class="match-column">${state.options[state.page].map(id => {
      const item = matchingPairs.find(pair => pair.id === id);
      const left = group.findIndex(pair => state.answers[pair.id] === id);
      return `<button class="match-item ${left >= 0 ? "connected" : ""}" data-right="${id}">
      <span class="match-badge">${left >= 0 ? "ABCDE"[left] : "·"}</span><span>${escape(item.answer)}</span></button>`;
    }).join("")}</div></div><button class="secondary" data-action="clear-pairs" style="margin-top:20px">Borrar uniones de este bloque</button>`;
}

function drawArrows() {
  const container = app.querySelector(".matching");
  if (!container || state?.mode !== "matching") return;
  const bounds = container.getBoundingClientRect();
  const svg = container.querySelector("svg");
  svg.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
  const paths = [];
  for (const left of container.querySelectorAll("[data-left]")) {
    const answer = state.answers[left.dataset.left];
    const right = [...container.querySelectorAll("[data-right]")].find(element => element.dataset.right === answer);
    if (!right) continue;
    const a = left.getBoundingClientRect(), b = right.getBoundingClientRect();
    const x1 = a.right - bounds.left, y1 = a.top + a.height / 2 - bounds.top;
    const x2 = b.left - bounds.left, y2 = b.top + b.height / 2 - bounds.top;
    paths.push(`<path d="M${x1},${y1} C${x1 + (x2 - x1) / 2},${y1} ${x1 + (x2 - x1) / 2},${y2} ${x2 - 3},${y2}" fill="none" stroke="#78947a" stroke-width="2" marker-end="url(#arrow-tip)"/>`);
  }
  container.querySelector("#arrow-lines").innerHTML = paths.join("");
}

function calculateResults() {
  return examItems().map(item => {
    let answer = state.answers[item.id] ?? "";
    let grade;
    if (state.mode === "written") grade = gradeWritten(item, answer);
    else if (state.mode === "easy") grade = gradeChoice(item, answer);
    else {
      const pair = matchingPairs.find(pair => pair.id === answer);
      answer = pair?.answer ?? "";
      grade = gradeChoice(item, answer);
    }
    return { ...grade, item, answer };
  });
}

function renderResults(focus = true) {
  results = calculateResults();
  const summary = state.remoteResult ? { ...summarize(results), grade: state.remoteResult.grade, points: state.remoteResult.points } : summarize(results);
  const mistakes = results.filter(result => result.score < 1);
  app.innerHTML = `<section class="result-hero"><span class="eyebrow">Examen terminado · ${modes[state.mode].title}</span>
    <h1>${summary.grade >= 9 ? "¡Lo tienes dominado!" : summary.grade >= 5 ? "¡Vas por buen camino!" : "Cada intento te ayuda a aprender."}</h1>
    <p><strong>${escape(state.profile?.name ?? "Estudiante")}</strong> · ${escape(state.profile?.course ?? "Sin curso")} · Tiempo: ${duration(state.remoteResult?.durationMs ?? elapsed())}</p>
    <div class="grade-circle"><strong>${format(summary.grade)}</strong><span>NOTA SOBRE 10</span></div>
    <p class="muted">${format(summary.points)} puntos de ${results.length} posibles. ${state.mode === "written" ? "Corrección automática orientativa por ideas clave." : "Cada acierto suma un punto."}</p>
    <div class="stats"><div class="stat"><strong>${summary.correct}</strong>Bien</div><div class="stat"><strong>${summary.partial}</strong>Regular</div><div class="stat"><strong>${summary.wrong}</strong>Mal / sin responder</div></div>
    <div class="result-actions"><button class="primary" data-action="retry">Repetir examen</button>
    ${mistakes.length ? `<button class="secondary" data-action="retry-mistakes">Practicar solo los fallos</button>` : ""}
    <button class="secondary" data-action="home">Elegir otro modo</button>${resetButton()}</div>
    <p id="submission-status" class="muted">${state.remoteResult ? "Resultado guardado en el ranking compartido." : state.remote ? "Resultado pendiente de guardar en el ranking." : "Práctica: este resultado no participa en el ranking."}</p>
    ${state.remote && !state.remoteResult ? `<button class="secondary" data-action="submit-ranking">Guardar resultado en el ranking</button>` : ""}</section>
    ${rankingMarkup(state.mode)}
    <div class="section-heading"><h2>Lo que puedes mejorar</h2><span class="muted">${mistakes.length} para repasar</span></div>
    ${mistakes.length ? mistakes.map(reviewMarkup).join("") : `<div class="review"><span class="status bien">Todo bien</span><p>No hay fallos. ¡Prueba otro modo para seguir practicando!</p></div>`}
    <details class="source-note"><summary>Ver las respuestas correctas (${summary.correct})</summary>${results.filter(result => result.score === 1).map(reviewMarkup).join("")}</details>
    <div style="margin-top:25px">${sourceNote()}</div>`;
  if (focus) focusHeading();
  loadRanking();
}

function rankingMarkup(mode = rankingMode) {
  rankingMode = mode;
  return `<section class="ranking"><div class="section-heading"><h2>Ranking compartido</h2><button class="secondary" data-action="refresh-ranking">Actualizar</button></div>
    <label for="ranking-mode" class="input-label">Modo de examen</label><select id="ranking-mode">${Object.entries(modes).map(([key, value]) =>
      `<option value="${key}" ${key === rankingMode ? "selected" : ""}>${value.title}</option>`).join("")}</select>
    <p class="muted">Los 50 mejores exámenes completos. Mayor nota primero; en empate, menor tiempo. El tiempo incluye pausas y salir de la página. Ranking de práctica, sin identidad verificada.</p>
    <div id="ranking-entries" aria-live="polite"><p class="muted">Cargando ranking…</p></div></section>`;
}

async function loadRanking() {
  const request = ++rankingRequest;
  const container = app.querySelector("#ranking-entries");
  if (!container) return;
  container.innerHTML = `<p class="muted">Cargando ranking…</p>`;
  try {
    const { entries } = await api(`/api/ranking?mode=${rankingMode}`);
    if (request !== rankingRequest || !container.isConnected) return;
    container.innerHTML = entries.length ? `<div class="table-scroll"><table><caption class="visually-hidden">Clasificación de ${modes[rankingMode].title}</caption>
    <thead><tr><th>Puesto</th><th>Nombre o alias</th><th>Curso</th><th>Nota / 10</th><th>Tiempo</th><th>Fecha</th></tr></thead><tbody>${entries.map((entry, index) =>
      `<tr><td>${index + 1}</td><td>${escape(entry.name)}</td><td>${escape(entry.course)}</td><td><strong>${format(entry.grade)}</strong></td><td>${duration(entry.durationMs)}</td>
      <td>${escape(new Date(entry.finishedAt).toLocaleDateString("es-ES"))}</td></tr>`).join("")}</tbody></table></div>` :
      `<p class="muted">Todavía no hay resultados en este modo. ¡Puedes ser el primero!</p>`;
  } catch (error) {
    console.error("No se pudo cargar el ranking.", error);
    if (request === rankingRequest && container.isConnected) container.innerHTML = `<p class="form-error">Ranking no disponible: ${escape(error.message)}. Usa «Actualizar» para reintentar.</p>`;
  }
}

async function submitRanking() {
  if (!state?.remote || state.remoteResult || !state.finished) return;
  const exam = state;
  const button = app.querySelector('[data-action="submit-ranking"]');
  if (button?.disabled) return;
  if (button) button.disabled = true;
  const status = app.querySelector("#submission-status");
  if (status) status.textContent = "Guardando el resultado…";
  try {
    const result = await api(`/api/exams/${exam.remote.id}/finish`, "POST", { token: exam.remote.token, answers: exam.answers });
    if (state !== exam) return;
    state.remoteResult = result;
    state.durationMs = result.durationMs;
    save();
    if (app.querySelector("#submission-status")) renderResults(false);
    announce("Nota y tiempo guardados en el ranking.");
  } catch (error) {
    console.error("No se pudo guardar el resultado.", error);
    if (state === exam && status?.isConnected) status.textContent = `No se ha guardado: ${error.message} Reintenta con el botón de guardar. Tu resultado local sigue disponible.`;
    if (button?.isConnected) button.disabled = false;
  }
}

function reviewMarkup(result) {
  return `<article class="review"><span class="status ${result.status}">${result.status} · ${format(result.score)} / 1</span>
    <h3>${state.mode === "matching" ? "" : `${result.item.id}. `}${escape(result.item.title)}</h3>
    <p><strong>Tu respuesta:</strong> ${escape(result.answer || "Sin responder")}</p>
    <div class="model-answer"><p><strong>Respuesta de los apuntes:</strong> ${escape(result.item.answer)}</p></div>
    <p><strong>${result.score === 1 ? "Por qué está bien:" : "Por qué no está completa o correcta:"}</strong> ${escape(result.reason)}</p>
    ${result.matched?.length ? `<p><strong>Ideas reconocidas:</strong> ${result.matched.map(escape).join("; ")}.</p>` : ""}
    ${result.missing?.length ? `<p><strong>Debes añadir o revisar:</strong></p><ul>${result.missing.map(label => `<li>${escape(label)}</li>`).join("")}</ul>` : ""}</article>`;
}

function confirmAction(title, text, label, callback) {
  const dialog = document.createElement("dialog");
  dialog.innerHTML = `<h2>${escape(title)}</h2><p>${escape(text)}</p><div class="nav"><button class="secondary" data-cancel>Volver</button><button class="primary" data-confirm>${escape(label)}</button></div>`;
  document.body.append(dialog);
  dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-confirm]").addEventListener("click", () => { dialog.close(); callback(); });
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.showModal();
}

app.addEventListener("input", event => {
  if (event.target.id !== "written-answer" || !state || state.finished) return;
  const item = examItems()[state.page];
  state.answers[item.id] = event.target.value;
  save();
  const answered = examItems().filter(isAnswered).length;
  app.querySelector("#answered-count").textContent = `${answered} de ${state.ids.length} respondidas`;
  app.querySelector("#exam-progress").value = answered;
  app.querySelector(`[data-page="${state.page}"]`).classList.toggle("answered", isAnswered(item));
});

app.addEventListener("click", event => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  if (button.dataset.start) {
    const mode = button.dataset.start;
    if (state && !state.finished) confirmAction("¿Comenzar un examen nuevo?", "Se sustituirá el progreso del examen en curso.", "Empezar nuevo", () => profileForm(mode));
    else profileForm(mode);
    return;
  }
  const action = button.dataset.action;
  if (action === "refresh-ranking") { loadRanking(); return; }
  if (action === "submit-ranking") { submitRanking(); return; }
  if (action === "reset-all") { resetAll(); return; }
  if (action === "home") { save(); home(); focusHeading(); return; }
  if (!state) return;
  if (action === "resume") { state.finished ? renderResults() : renderExam(); return; }
  if (action === "retry" || action === "retry-mistakes") {
    const ids = action === "retry-mistakes" ? results.filter(result => result.score < 1).map(result => result.item.id) : undefined;
    profileForm(state.mode, ids); return;
  }
  if (state.finished) return;
  if (button.dataset.page !== undefined || action === "previous" || action === "next") {
    state.page = button.dataset.page !== undefined ? Number(button.dataset.page) : state.page + (action === "next" ? 1 : -1);
    save(); renderExam(); return;
  }
  if (button.dataset.option !== undefined) {
    const item = examItems()[state.page];
    state.answers[item.id] = state.options[item.id][Number(button.dataset.option)];
    save(); renderExam(false);
    app.querySelector(`[data-option="${button.dataset.option}"]`).focus();
    return;
  }
  if (button.dataset.left) {
    selectedLeft = button.dataset.left;
    for (const item of app.querySelectorAll("[data-left]")) {
      item.classList.toggle("active", item.dataset.left === selectedLeft);
      item.setAttribute("aria-pressed", String(item.dataset.left === selectedLeft));
    }
    announce("Concepto seleccionado. Elige su respuesta a la derecha."); return;
  }
  if (button.dataset.right) {
    if (!selectedLeft) { announce("Primero selecciona un concepto a la izquierda."); return; }
    const previous = Object.keys(state.answers).find(id => state.answers[id] === button.dataset.right && id !== selectedLeft);
    if (previous) delete state.answers[previous];
    state.answers[selectedLeft] = button.dataset.right;
    save(); renderExam(false);
    app.querySelector(`[data-right="${button.dataset.right}"]`).focus();
    announce(previous ? "Unión cambiada. El concepto anterior ha quedado libre." : "Unión guardada. Puedes seguir con otra pareja."); return;
  }
  if (action === "clear-pairs") {
    for (const item of examItems().slice(state.page * 5, state.page * 5 + 5)) delete state.answers[item.id];
    save(); renderExam(false);
    app.querySelector('[data-action="clear-pairs"]').focus();
    announce("Uniones de este bloque borradas."); return;
  }
  if (action === "finish") {
    const unanswered = examItems().filter(item => !isAnswered(item)).length;
    confirmAction("¿Entregar el examen?", unanswered
      ? `Quedan ${unanswered} preguntas sin responder; contarán como 0 puntos. Al entregar verás la nota y las explicaciones.`
      : "Al entregar verás tu nota y la revisión. Después podrás practicar los fallos.", "Entregar y corregir",
    () => { state.durationMs = elapsed(); state.finished = true; save(); renderResults(); submitRanking(); });
  }
});

window.addEventListener("resize", drawArrows);
app.addEventListener("change", event => {
  if (event.target.id === "ranking-mode") { rankingMode = event.target.value; loadRanking(); }
});
setInterval(() => {
  const timer = app.querySelector("#exam-timer");
  if (timer && state && !state.finished) timer.textContent = `Tiempo: ${duration(elapsed())}`;
}, 1000);
restore();
if (state?.finished) renderResults(false);
else home();
