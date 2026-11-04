import { multiplesOf, multiplesQuestions } from "./multiplos-questions.mjs";
import { formatNumbers, mountWorksheetQuiz } from "./worksheet-quiz.mjs";

const explorer = document.querySelector("#multiples-explorer");
if (explorer) {
  const board = explorer.querySelector("#multiples-board");
  const table = explorer.querySelector("#times-table");
  const summary = explorer.querySelector("#multiples-summary");
  const fullList = explorer.querySelector("#multiples-list");
  board.innerHTML = Array.from({ length: 100 }, (_, index) => `<span>${index + 1}</span>`).join("");
  const cells = [...board.children];

  function show(number) {
    const multiples = multiplesOf(number);
    for (const [index, cell] of cells.entries()) {
      const value = index + 1;
      cell.classList.toggle("is-multiple", value % number === 0 && value <= number * 10);
      cell.classList.toggle("is-beyond", value % number === 0 && value > number * 10);
    }
    table.setAttribute("aria-label", `Tabla del ${number}`);
    table.innerHTML = Array.from({ length: 10 }, (_, index) =>
      `<li>${number} × ${index + 1} = <strong>${number * (index + 1)}</strong></li>`).join("");
    summary.textContent = `Entre el 1 y el 100 hay ${multiples.length} múltiplos de ${number}. La tabla no se acaba en ${number} × 10: sigue con ${number} × 11 = ${number * 11}, ${number} × 12 = ${number * 12}… El 0 también es múltiplo de ${number}.`;
    fullList.textContent = `Múltiplos de ${number} del 1 al 100: ${formatNumbers(multiples)}.`;
  }

  explorer.addEventListener("change", event => {
    if (event.target.name === "times-table") show(Number(event.target.value));
  });
  show(Number(explorer.querySelector('input[name="times-table"]:checked').value));
  explorer.hidden = false;
}

const form = document.querySelector("#multiples-quiz");
if (form) {
  mountWorksheetQuiz({
    form,
    container: document.querySelector("#multiples-questions"),
    result: document.querySelector("#multiples-result"),
    questions: multiplesQuestions,
  });
}
