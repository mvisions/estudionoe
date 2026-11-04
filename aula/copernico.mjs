import { copernicusQuestions } from "./copernico-questions.mjs";
import { mountWorksheetQuiz } from "./worksheet-quiz.mjs?v=20261104-pets2";

const form = document.querySelector("#copernicus-quiz");
if (form) {
  mountWorksheetQuiz({
    form,
    container: document.querySelector("#copernicus-questions"),
    result: document.querySelector("#copernicus-result"),
    questions: copernicusQuestions,
    itemName: "preguntas",
  });
}
