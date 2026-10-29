import { summarize } from "../grading.mjs";

/**
 * Parejas para el test de unir con flechas: cuándo se usa has y cuándo have.
 * Cada respuesta correcta aparece una sola vez, así que cada flecha solo puede
 * ir a un sitio y no hay dos soluciones posibles para la misma frase.
 */
export const flechasPairs = [
  {
    id: "she-cat",
    left: "She ___ a cat. (afirmativa)",
    right: "has",
    explanation: "Con he, she e it el verbo tiene la forma has: She has a cat. Es la misma -s del presente de otros verbos (she plays, she likes).",
  },
  {
    id: "they-car",
    left: "They ___ a car. (afirmativa)",
    right: "have",
    explanation: "Con I, you, we y they usamos have: They have a car. Nunca «they has».",
  },
  {
    id: "ask-her",
    left: "___ she have a cat?",
    right: "Does",
    explanation: "En las preguntas con he, she o it ponemos Does delante y el verbo vuelve a have: Does she have a cat? No se dice «Does she has».",
  },
  {
    id: "ask-them",
    left: "___ they have a car?",
    right: "Do",
    explanation: "Con I, you, we y they la pregunta empieza por Do y el verbo sigue en have: Do they have a car?",
  },
  {
    id: "neg-her",
    left: "She ___ got a bag. (negativa)",
    right: "hasn’t",
    explanation: "Con have got, la negativa de she es hasn’t got: She hasn’t got a bag. Con got no se usa doesn’t.",
  },
  {
    id: "neg-them",
    left: "They ___ got a bike. (negativa)",
    right: "haven’t",
    explanation: "Con they, la negativa de have got es haven’t got: They haven’t got a bike.",
  },
];

export function gradeFlechas(pairs, answers) {
  const results = pairs.map(pair => {
    const chosen = answers[pair.id];
    const correct = chosen === pair.id;
    return { pair, chosen, correct, score: correct ? 1 : 0 };
  });
  return { results, ...summarize(results) };
}
