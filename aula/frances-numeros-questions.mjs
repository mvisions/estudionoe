export const frenchNumbers = Object.freeze([
  { number: 1, word: "un" },
  { number: 2, word: "deux" },
  { number: 3, word: "trois" },
  { number: 4, word: "quatre" },
  { number: 5, word: "cinq" },
  { number: 6, word: "six" },
  { number: 7, word: "sept" },
  { number: 8, word: "huit" },
  { number: 9, word: "neuf" },
  { number: 10, word: "dix" },
]);

export const frenchNumberPairs = Object.freeze(
  frenchNumbers.map(item => Object.freeze({
    id: `french-number-${item.number}`,
    left: item.word,
    right: String(item.number),
    answer: item.number,
  })),
);

export const frenchNumberQuiz = Object.freeze(
  frenchNumbers.map((item, index) => Object.freeze({
    id: `french-quiz-${item.number}`,
    question: `¿Cómo se escribe ${item.number} en francés?`,
    options: Object.freeze([
      item.word,
      `${item.word.slice(0, -1)}${item.word.endsWith("s") ? "e" : "z"}`,
      `${item.word}${index % 2 ? "e" : "t"}`,
    ]),
    answer: 0,
  })),
);

const normalize = value => String(value ?? "").trim().toLocaleLowerCase("fr-FR");

export function gradeFrenchWriting(questions, answers) {
  const results = questions.map(question => ({
    question,
    answer: String(answers[question.id] ?? ""),
    correct: normalize(answers[question.id]) === question.word,
  }));
  return {
    results,
    points: results.filter(result => result.correct).length,
    total: questions.length,
  };
}

export function gradeFrenchQuiz(questions, answers) {
  const results = questions.map(question => ({
    question,
    selected: Number.isInteger(answers[question.id]) ? answers[question.id] : undefined,
    correct: answers[question.id] === question.answer,
  }));
  return {
    results,
    points: results.filter(result => result.correct).length,
    total: questions.length,
  };
}

export function gradeFrenchMatching(pairs, answers) {
  const results = pairs.map(pair => ({
    pair,
    chosen: Number(answers[pair.id]),
    correct: Number(answers[pair.id]) === pair.answer,
  }));
  return {
    results,
    points: results.filter(result => result.correct).length,
    total: pairs.length,
  };
}
