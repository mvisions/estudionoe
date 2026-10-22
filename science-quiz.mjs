export const scienceQuestions = [
  {
    id: "mecanica", topic: "mecanica",
    question: "¿Qué estudia la mecánica?",
    options: ["Solo los seres vivos.", "El movimiento, el reposo y las fuerzas.", "La escritura de los pueblos antiguos."],
    answer: 1,
    explanation: "La mecánica es una parte de la física que estudia cómo se mueven los objetos, cuándo están quietos y las fuerzas que intervienen.",
  },
  {
    id: "pelota", topic: "mecanica",
    question: "¿Cuál de estos ejemplos podemos estudiar con la mecánica?",
    options: ["Una pelota que empieza a moverse al empujarla.", "El significado de una palabra.", "La fecha de nacimiento de un escritor."],
    answer: 0,
    explanation: "Al empujar una pelota ejercemos una fuerza que puede cambiar su movimiento.",
  },
  {
    id: "fuerzas", topic: "mecanica",
    question: "¿Qué puede hacer una fuerza sobre un objeto?",
    options: ["Hacer que siempre se mueva más deprisa.", "Cambiar su movimiento, por ejemplo al frenarlo.", "No puede afectar a su movimiento."],
    answer: 1,
    explanation: "Una fuerza puede poner un objeto en movimiento, frenarlo o cambiar su dirección. No siempre lo acelera.",
  },
  {
    id: "aristoteles", topic: "aristoteles",
    question: "¿Quién fue Aristóteles?",
    options: ["Un astronauta de nuestro tiempo.", "Un rey de la Edad Media.", "Un filósofo griego de la Antigüedad."],
    answer: 2,
    explanation: "Aristóteles fue un filósofo griego que vivió hace más de 2.300 años e intentó explicar la naturaleza.",
  },
  {
    id: "intereses", topic: "aristoteles",
    question: "¿Qué temas interesaban a Aristóteles?",
    options: ["Los animales, las plantas, el cielo y el movimiento.", "Solo los ordenadores.", "Únicamente las camisetas."],
    answer: 0,
    explanation: "Aristóteles estudió muchos temas relacionados con la naturaleza, no una única materia.",
  },
  {
    id: "ideas", topic: "aristoteles",
    question: "¿Qué pasó con las ideas de Aristóteles?",
    options: ["Todas se aceptan hoy sin comprobarlas.", "No influyeron en nadie.", "Influyeron durante siglos, pero algunas fueron corregidas con nuevas pruebas."],
    answer: 2,
    explanation: "Sus ideas tuvieron mucha influencia. La ciencia revisa las explicaciones con observaciones y experimentos.",
  },
  {
    id: "centro", topic: "esferas",
    question: "Según Aristóteles, ¿dónde estaba la Tierra?",
    options: ["Quieta en el centro del universo.", "Girando alrededor del Sol.", "Sobre la superficie de la Luna."],
    answer: 0,
    explanation: "En su modelo, la Tierra estaba quieta en el centro. Es una idea histórica, no lo que sabemos hoy.",
  },
  {
    id: "esferas", topic: "esferas",
    question: "¿Qué eran las esferas celestes en aquella explicación?",
    options: ["Pelotas utilizadas en sus experimentos.", "Capas alrededor de la Tierra que transportaban los astros.", "Satélites artificiales para observar el cielo."],
    answer: 1,
    explanation: "Las esferas eran capas que, según aquel modelo antiguo, llevaban la Luna, el Sol, los planetas y las estrellas alrededor de la Tierra.",
  },
  {
    id: "actualidad", topic: "esferas",
    question: "¿Qué sabemos hoy sobre la Tierra?",
    options: ["Está quieta en el centro del universo.", "El Sol gira a su alrededor en una esfera celeste.", "Gira sobre sí misma y se mueve alrededor del Sol."],
    answer: 2,
    explanation: "Las observaciones muestran que la Tierra gira sobre sí misma y orbita alrededor del Sol. El modelo de las esferas no describe correctamente el universo.",
  },
];

export function gradeScienceQuiz(questions, answers) {
  const results = questions.map(question => ({
    question,
    selected: answers[question.id],
    correct: answers[question.id] === question.answer,
  }));
  const score = results.filter(result => result.correct).length;
  return { results, score, total: questions.length, grade: questions.length ? score / questions.length * 10 : 0 };
}

const form = globalThis.document?.querySelector("#science-quiz");
if (form) {
  const container = document.querySelector("#science-questions");
  const result = document.querySelector("#science-result");
  const retry = form.querySelector('[data-action="mistakes"]');
  let questions = scienceQuestions;
  let mistakes = [];

  function render() {
    container.innerHTML = questions.map((question, index) => `
      <fieldset class="question-card" data-question="${question.id}">
        <legend>${index + 1}. ${question.question}</legend>
        <div class="options">
          ${question.options.map((option, optionIndex) => `
            <label><input type="radio" name="${question.id}" value="${optionIndex}"> ${option}</label>
          `).join("")}
        </div>
        <p class="science-feedback" hidden></p>
      </fieldset>
    `).join("");
    mistakes = [];
    retry.hidden = true;
    result.textContent = "";
  }

  render();
  form.hidden = false;

  form.addEventListener("submit", event => {
    event.preventDefault();
    const answers = Object.fromEntries([...new FormData(form)].map(([id, value]) => [id, Number(value)]));
    const graded = gradeScienceQuiz(questions, answers);
    mistakes = graded.results.filter(item => !item.correct).map(item => item.question);
    for (const item of graded.results) {
      const feedback = container.querySelector(`[data-question="${item.question.id}"] .science-feedback`);
      feedback.hidden = false;
      feedback.textContent = `${item.correct ? "¡Correcto!" : "Revisa esta pregunta."} Tu respuesta: ${item.question.options[item.selected] ?? "Sin responder"}. Respuesta correcta: ${item.question.options[item.question.answer]} Por qué: ${item.question.explanation}`;
    }
    retry.hidden = mistakes.length === 0;
    result.textContent = `Has acertado ${graded.score} de ${graded.total}. Nota: ${graded.grade.toLocaleString("es", { maximumFractionDigits: 1 })}/10. ${mistakes.length ? "Revisa las explicaciones o practica solo los fallos." : "¡Muy bien, has acertado todas!"}`;
  });

  retry.addEventListener("click", () => {
    questions = mistakes;
    render();
    result.textContent = `Repaso de ${questions.length} preguntas erróneas o sin responder.`;
    container.querySelector("input").focus();
  });

  form.addEventListener("change", () => {
    retry.hidden = true;
    result.textContent = "";
    for (const feedback of container.querySelectorAll(".science-feedback")) feedback.hidden = true;
  });

  form.addEventListener("reset", event => {
    event.preventDefault();
    questions = scienceQuestions;
    render();
    container.querySelector("input").focus();
  });
}
