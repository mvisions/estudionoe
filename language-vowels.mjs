import { offerActivityRanking } from "./activity-ranking.mjs";
import { celebratePet } from "./pet-companion.mjs";

export const vowelQuestions = [
  { word: "cielo", answer: "Diptongo", explanation: "ie se pronuncia en una misma sílaba: cie-lo." },
  { word: "ciudad", answer: "Diptongo", explanation: "iu son dos vocales cerradas distintas en una misma sílaba: ciu-dad." },
  { word: "causa", answer: "Diptongo", explanation: "au se pronuncia en una misma sílaba: cau-sa." },
  { word: "buey", answer: "Triptongo", explanation: "uey reúne cerrada + abierta + cerrada en una sílaba." },
  { word: "limpiáis", answer: "Triptongo", explanation: "iái reúne cerrada átona + abierta + cerrada átona en una sílaba." },
  { word: "miau", answer: "Triptongo", explanation: "iau se pronuncia en una misma sílaba." },
  { word: "mesa", answer: "Ninguno", explanation: "No hay dos o tres vocales juntas que formen un diptongo o un triptongo." },
  { word: "libro", answer: "Ninguno", explanation: "Sus vocales no forman una unión de dos o tres vocales en la misma sílaba." },
];

const categories = ["Diptongo", "Triptongo", "Ninguno"];
const form = globalThis.document?.querySelector("#vowel-quiz");
const questionsContainer = globalThis.document?.querySelector("#vowel-questions");
const result = globalThis.document?.querySelector("#vowel-quiz-result");
let startedAt = Date.now();
let celebratedStart = 0;

if (form && questionsContainer && result) {
  questionsContainer.innerHTML = vowelQuestions.map((question, index) => `
    <fieldset class="vowel-question" data-question="${index}">
      <legend><span class="vowel-question-number">${index + 1}</span> ¿Qué hay en <strong>${question.word}</strong>?</legend>
      <div class="vowel-options">
        ${categories.map(category => `
          <label>
            <input type="radio" name="word-${index}" value="${category}">
            <span>${category}</span>
          </label>
        `).join("")}
      </div>
      <p class="vowel-feedback" hidden></p>
    </fieldset>
  `).join("");

  form.addEventListener("submit", event => {
    event.preventDefault();
    let score = 0;
    let unanswered = 0;

    vowelQuestions.forEach((question, index) => {
      const fieldset = questionsContainer.querySelector(`[data-question="${index}"]`);
      const selected = form.querySelector(`input[name="word-${index}"]:checked`);
      const feedback = fieldset.querySelector(".vowel-feedback");
      if (!selected) unanswered += 1;
      const correct = selected?.value === question.answer;
      if (correct) score += 1;
      fieldset.dataset.correct = String(correct);
      feedback.hidden = false;
      feedback.textContent = `${correct ? "¡Correcto!" : `Respuesta: ${question.answer}.`} ${question.explanation}`;
    });

    result.textContent = unanswered
      ? `Has acertado ${score} de ${vowelQuestions.length}. Te faltan ${unanswered} por responder; puedes completarlas y corregir de nuevo.`
      : `Resultado: ${score} de ${vowelQuestions.length}. ${score === vowelQuestions.length ? "¡Excelente, ya dominas la clasificación!" : "Revisa las explicaciones y vuelve a intentarlo."}`;
    const section = form.closest(".language-practice");
    section.querySelector(".activity-ranking-invite")?.remove();
    if (!unanswered) {
      if (celebratedStart !== startedAt) {
        celebratePet(score / vowelQuestions.length * 10);
        celebratedStart = startedAt;
      }
      offerActivityRanking(section, {
        activity: "language-vowels",
        ids: vowelQuestions.map(question => `vowel-${question.word}`),
        answers: Object.fromEntries(vowelQuestions.map((question, index) => [
          `vowel-${question.word}`, form.querySelector(`input[name="word-${index}"]:checked`).value,
        ])),
        startedAt, finishedAt: Date.now(),
      });
    }
  });

  form.addEventListener("reset", () => {
    startedAt = Date.now();
    form.closest(".language-practice").querySelector(".activity-ranking-invite")?.remove();
    for (const fieldset of questionsContainer.querySelectorAll(".vowel-question")) {
      delete fieldset.dataset.correct;
      const feedback = fieldset.querySelector(".vowel-feedback");
      feedback.hidden = true;
      feedback.textContent = "";
    }
    result.textContent = "";
  });
}
