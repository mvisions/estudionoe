import { celebratePet } from "../pet-companion.mjs?v=20261104-pets";

const listFormat = new Intl.ListFormat("es", { style: "long", type: "conjunction" });

export const formatNumbers = numbers => listFormat.format(numbers.map(String));

export function parseNumberList(text) {
  const numbers = String(text ?? "").match(/\d+/g)?.map(Number) ?? [];
  return [...new Set(numbers)].sort((a, b) => a - b);
}

export function gradeWorksheetQuestion(question, given) {
  if (question.type === "choice") {
    const selected = given === undefined || given === null || given === "" ? undefined : Number(given);
    return { selected, empty: selected === undefined, correct: selected === question.answer };
  }
  if (question.type === "number") {
    const text = String(given ?? "").trim();
    return { text, empty: !text, correct: /^\d+$/.test(text) && Number(text) === question.answer };
  }
  if (question.type === "list" || question.type === "mark") {
    const numbers = question.type === "list"
      ? parseNumberList(given)
      : [...new Set([given ?? []].flat().map(Number))].sort((a, b) => a - b);
    const missing = question.answer.filter(number => !numbers.includes(number));
    const extra = numbers.filter(number => !question.answer.includes(number));
    return { text: String(given ?? "").trim(), numbers, missing, extra, empty: numbers.length === 0, correct: !missing.length && !extra.length };
  }
  throw new Error(`Tipo de ejercicio desconocido: ${question.type}`);
}

export function gradeWorksheet(questions, answers) {
  const results = questions.map(question => ({ question, ...gradeWorksheetQuestion(question, answers[question.id]) }));
  const score = results.filter(result => result.correct).length;
  return {
    results, score,
    total: questions.length,
    unanswered: results.filter(result => result.empty).length,
    grade: questions.length ? score / questions.length * 10 : 0,
  };
}

const sentence = text => /[.!?…]$/.test(text) ? text : `${text}.`;

export function describeResult(result) {
  const { question } = result;
  if (question.type === "choice") {
    return {
      given: question.options[result.selected] ?? "Sin responder",
      solution: question.options[question.answer],
      detail: "",
    };
  }
  if (question.type === "number") {
    return { given: result.text || "Sin responder", solution: String(question.answer), detail: "" };
  }
  const marking = question.type === "mark";
  const detail = result.correct || result.empty ? "" : [
    result.missing.length ? `${marking ? "Te faltó marcar" : "Te faltan"}: ${formatNumbers(result.missing)}.` : "",
    result.extra.length ? `${marking ? "No son múltiplos" : "Sobran"}: ${formatNumbers(result.extra)}.` : "",
  ].filter(Boolean).join(" ");
  return {
    given: marking ? (result.numbers.length ? formatNumbers(result.numbers) : "Sin marcar") : result.text || "Sin responder",
    solution: formatNumbers(question.answer),
    detail,
  };
}

export function feedbackText(result) {
  const { given, solution, detail } = describeResult(result);
  return [
    `Tu respuesta: ${sentence(given)}`,
    detail,
    `Respuesta correcta: ${sentence(solution)}`,
    `Por qué: ${result.question.explanation}`,
  ].filter(Boolean).join(" ");
}

const escapeHtml = text => String(text).replace(/[&<>"']/g, character => `&#${character.charCodeAt(0)};`);
const isShort = options => options.every(option => String(option).length <= 10);

function renderAnswerArea(question) {
  const name = escapeHtml(question.id);
  if (question.type === "list" || question.type === "number") {
    const hint = question.type === "list"
      ? "Escribe los números separados por comas. El orden no importa."
      : "Escribe solo el número.";
    return `
      <label class="written-answer">
        <span>${hint}</span>
        <input type="text" name="${name}" inputmode="${question.type === "number" ? "numeric" : "text"}" autocomplete="off" spellcheck="false">
      </label>`;
  }
  const type = question.type === "mark" ? "checkbox" : "radio";
  return `
    <div class="options${isShort(question.options) ? " options-inline" : ""}">
      ${question.options.map((option, index) => `
        <label><input type="${type}" name="${name}" value="${type === "checkbox" ? escapeHtml(option) : index}"> ${escapeHtml(option)}</label>
      `).join("")}
    </div>`;
}

export function renderWorksheetQuestions(questions) {
  let group;
  return questions.map((question, index) => {
    const heading = question.group && question.group !== group ? `<h3 class="worksheet-group">${escapeHtml(question.group)}</h3>` : "";
    group = question.group;
    return `${heading}
      <fieldset class="question-card" data-question="${escapeHtml(question.id)}">
        <legend>${index + 1}. ${escapeHtml(question.question)}</legend>
        ${renderAnswerArea(question)}
        <p class="science-feedback" hidden></p>
      </fieldset>`;
  }).join("");
}

function readAnswers(form, questions) {
  const data = new FormData(form);
  return Object.fromEntries(questions.map(question => [
    question.id,
    question.type === "mark" ? data.getAll(question.id) : data.get(question.id) ?? undefined,
  ]));
}

export function mountWorksheetQuiz({ form, container, result, questions: allQuestions, itemName = "ejercicios" }) {
  const retry = form.querySelector('[data-action="mistakes"]');
  let questions = allQuestions;
  let mistakes = [];
  let practice = false;
  let startedAt = Date.now();
  let celebratedStart = 0;

  function render() {
    container.innerHTML = renderWorksheetQuestions(questions);
    mistakes = [];
    retry.hidden = true;
    result.textContent = "";
    startedAt = Date.now();
  }

  function focusFirstAnswer() {
    container.querySelector("input")?.focus();
  }

  render();
  form.hidden = false;

  form.addEventListener("submit", event => {
    event.preventDefault();
    const graded = gradeWorksheet(questions, readAnswers(form, questions));
    mistakes = graded.results.filter(item => !item.correct).map(item => item.question);
    for (const item of graded.results) {
      const card = container.querySelector(`[data-question="${CSS.escape(item.question.id)}"]`);
      const feedback = card.querySelector(".science-feedback");
      const verdict = document.createElement("strong");
      verdict.textContent = item.correct ? "¡Correcto!" : "Revisa esta pregunta.";
      feedback.replaceChildren(verdict, ` ${feedbackText(item)}`);
      feedback.hidden = false;
      card.dataset.result = item.correct ? "correct" : "wrong";
    }
    retry.hidden = mistakes.length === 0;
    const grade = graded.grade.toLocaleString("es", { maximumFractionDigits: 1 });
    result.textContent = `Has acertado ${graded.score} de ${graded.total}. Nota: ${grade}/10. ${graded.unanswered
      ? `Te faltan ${graded.unanswered} por responder; cuentan como fallo.`
      : mistakes.length ? "Revisa las explicaciones o practica solo los fallos." : "¡Muy bien, has acertado todas!"}`;
    if (!graded.unanswered && !practice && celebratedStart !== startedAt) {
      celebratePet(graded.grade);
      celebratedStart = startedAt;
    }
  });

  retry.addEventListener("click", () => {
    practice = true;
    questions = mistakes;
    render();
    result.textContent = `Repaso de ${questions.length} ${itemName} con errores o sin responder.`;
    focusFirstAnswer();
  });

  form.addEventListener("input", event => {
    const card = event.target.closest("[data-question]");
    if (!card?.dataset.result) return;
    delete card.dataset.result;
    card.querySelector(".science-feedback").hidden = true;
    retry.hidden = true;
    result.textContent = "";
  });

  form.addEventListener("reset", event => {
    event.preventDefault();
    practice = false;
    questions = allQuestions;
    render();
    focusFirstAnswer();
  });
}
