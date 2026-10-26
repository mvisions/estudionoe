import { grammarQuestions, gradeGrammarQuiz } from "./ingles-gramatica-questions.mjs";
import { offerActivityRanking } from "../activity-ranking.mjs";
import { celebratePet } from "../pet-companion.mjs";

const form = document.querySelector("#grammar-quiz");
const container = document.querySelector("#grammar-questions");
const result = document.querySelector("#grammar-result");
const retry = form.querySelector('[data-action="mistakes"]');
const section = form.closest("section");
let questions = grammarQuestions;
let mistakes = [];
let practice = false;
let startedAt;
let celebratedStart;

function clearFeedback() {
  retry.hidden = true;
  result.textContent = "";
  for (const feedback of container.querySelectorAll(".grammar-feedback")) feedback.hidden = true;
  section.querySelector(".activity-ranking-invite")?.remove();
}

function render() {
  container.innerHTML = questions.map((question, index) => `
    <fieldset data-question="${question.id}" aria-describedby="feedback-${question.id}">
      <legend>${index + 1}. ${question.question}</legend>
      <div class="options">
        ${question.options.map((option, optionIndex) => `
          <label><input type="radio" name="${question.id}" value="${optionIndex}"><span>${option}</span></label>
        `).join("")}
      </div>
      <p id="feedback-${question.id}" class="grammar-feedback" hidden></p>
    </fieldset>
  `).join("");
  mistakes = [];
  clearFeedback();
  startedAt = Date.now();
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const answers = Object.fromEntries([...new FormData(form)].map(([id, value]) => [id, Number(value)]));
  const graded = gradeGrammarQuiz(questions, answers);
  mistakes = graded.results.filter(item => !item.correct).map(item => item.question);
  for (const item of graded.results) {
    const feedback = container.querySelector(`#feedback-${item.question.id}`);
    feedback.textContent = `${item.correct ? "¡Correcto!" : "Para repasar."} Tu respuesta: ${item.question.options[item.selected] ?? "Sin responder"}. Respuesta correcta: ${item.question.options[item.question.answer]} Por qué: ${item.question.explanation}`;
    feedback.hidden = false;
  }
  retry.hidden = mistakes.length === 0;
  const unanswered = graded.results.filter(item => item.selected === undefined).length;
  result.textContent = `Has acertado ${graded.correct} de ${questions.length}. Nota: ${graded.grade.toLocaleString("es-ES", { maximumFractionDigits: 1 })}/10. ${mistakes.length ? "Revisa las explicaciones o practica solo los fallos; las preguntas sin responder también cuentan como fallo." : "¡Muy bien, has acertado todas!"}${unanswered && !practice ? " Contesta todas las preguntas para poder participar en el ranking." : ""}`;
  section.querySelector(".activity-ranking-invite")?.remove();
  if (!unanswered && !practice) {
    if (celebratedStart !== startedAt) {
      celebratePet(graded.grade);
      celebratedStart = startedAt;
    }
    offerActivityRanking(section, {
      activity: "english-grammar",
      ids: questions.map(question => question.id),
      answers: Object.fromEntries(questions.map(question => [question.id, String(answers[question.id])])),
      startedAt, finishedAt: Date.now(),
    });
  }
  result.focus();
});

retry.addEventListener("click", () => {
  practice = true;
  questions = mistakes;
  render();
  result.textContent = `Repaso de ${questions.length} preguntas erróneas o sin responder. Este repaso no participa en el ranking.`;
  container.querySelector("input").focus();
});

form.addEventListener("change", clearFeedback);
form.addEventListener("reset", event => {
  event.preventDefault();
  practice = false;
  questions = grammarQuestions;
  render();
  container.querySelector("input").focus();
});

render();
form.hidden = false;
