import { greekMythQuestions } from "./mitos-griegos-questions.mjs";
import { mountWorksheetQuiz } from "./worksheet-quiz.mjs?v=20261124-french";

const form = document.querySelector("#myths-quiz");
if (form) {
  mountWorksheetQuiz({
    form,
    container: document.querySelector("#myths-questions"),
    result: document.querySelector("#myths-result"),
    questions: greekMythQuestions,
    itemName: "preguntas",
  });
}
