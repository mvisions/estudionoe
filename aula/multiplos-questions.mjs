export function multiplesOf(number, { from = 1, to = 100 } = {}) {
  const multiples = [];
  for (let value = Math.ceil(from / number) * number; value <= to; value += number) multiples.push(value);
  return multiples;
}

const WRITE = "Escribe los múltiplos";
const MARK = "Marca los múltiplos";
const YES_NO = "¿Es múltiplo? Sí o no";
const CHOOSE = "Elige la respuesta";
const COMPLETE = "Completa";
const PROBLEMS = "Problemas";

export const multiplesQuestions = [
  {
    id: "primeros-7", group: WRITE, type: "list",
    question: "Escribe los cinco primeros múltiplos de 7 sin contar el 0.",
    answer: [7, 14, 21, 28, 35],
    explanation: "Son los resultados de la tabla del 7: 7 × 1 = 7, 7 × 2 = 14, 7 × 3 = 21, 7 × 4 = 28 y 7 × 5 = 35.",
  },
  {
    id: "entre-4", group: WRITE, type: "list",
    question: "Escribe los múltiplos de 4 que hay entre 10 y 30.",
    answer: [12, 16, 20, 24, 28],
    explanation: "En la tabla del 4, los resultados entre 10 y 30 son 4 × 3 = 12, 4 × 4 = 16, 4 × 5 = 20, 4 × 6 = 24 y 4 × 7 = 28. El 8 y el 32 se quedan fuera.",
  },
  {
    id: "entre-9", group: WRITE, type: "list",
    question: "Escribe los múltiplos de 9 que hay entre 50 y 100.",
    answer: [54, 63, 72, 81, 90, 99],
    explanation: "9 × 6 = 54, 9 × 7 = 63, 9 × 8 = 72, 9 × 9 = 81, 9 × 10 = 90 y 9 × 11 = 99. La tabla sigue después del 10; 9 × 12 = 108 ya pasa de 100.",
  },
  {
    id: "marca-3", group: MARK, type: "mark",
    question: "Marca todos los múltiplos de 3.",
    options: [12, 17, 21, 25, 30, 32],
    answer: [12, 21, 30],
    explanation: "12 = 3 × 4, 21 = 3 × 7 y 30 = 3 × 10. Al dividir 17, 25 o 32 entre 3 sobra algo, así que no son múltiplos de 3.",
  },
  {
    id: "marca-6", group: MARK, type: "mark",
    question: "Marca todos los múltiplos de 6.",
    options: [16, 24, 30, 40, 42, 50],
    answer: [24, 30, 42],
    explanation: "24 = 6 × 4, 30 = 6 × 5 y 42 = 6 × 7. Al dividir 16, 40 o 50 entre 6 sobra algo, así que no son múltiplos de 6.",
  },
  {
    id: "48-de-6", group: YES_NO, type: "choice",
    question: "¿Es 48 múltiplo de 6?",
    options: ["Sí", "No"], answer: 0,
    explanation: "Está en la tabla del 6: 6 × 8 = 48. También puedes dividir: 48 : 6 = 8 y el resto es 0.",
  },
  {
    id: "34-de-4", group: YES_NO, type: "choice",
    question: "¿Es 34 múltiplo de 4?",
    options: ["Sí", "No"], answer: 1,
    explanation: "No está en la tabla del 4: 4 × 8 = 32 y 4 × 9 = 36. Al dividir 34 : 4 = 8 sobran 2.",
  },
  {
    id: "50-de-3", group: YES_NO, type: "choice",
    question: "¿Es 50 múltiplo de 3?",
    options: ["Sí", "No"], answer: 1,
    explanation: "3 × 16 = 48 y 3 × 17 = 51, así que el 50 se queda en medio. Al dividir 50 : 3 = 16 sobran 2.",
  },
  {
    id: "0-de-5", group: YES_NO, type: "choice",
    question: "¿Es 0 múltiplo de 5?",
    options: ["Sí", "No"], answer: 0,
    explanation: "5 × 0 = 0. El 0 es múltiplo de todos los números, porque cualquier número multiplicado por 0 da 0.",
  },
  {
    id: "multiplo-8", group: CHOOSE, type: "choice",
    question: "¿Cuál de estos números es múltiplo de 8?",
    options: ["42", "56", "60"], answer: 1,
    explanation: "8 × 7 = 56. En cambio, 42 y 60 no están en la tabla del 8: al dividirlos entre 8 sobra algo.",
  },
  {
    id: "no-multiplo-5", group: CHOOSE, type: "choice",
    question: "¿Cuál de estos números NO es múltiplo de 5?",
    options: ["35", "52", "70"], answer: 1,
    explanation: "Los múltiplos de 5 terminan en 0 o en 5. El 52 termina en 2, así que no es múltiplo de 5; en cambio, 35 = 5 × 7 y 70 = 5 × 14.",
  },
  {
    id: "72-es-multiplo", group: CHOOSE, type: "choice",
    question: "El número 72 es múltiplo de…",
    options: ["7", "8", "5"], answer: 1,
    explanation: "8 × 9 = 72, así que 72 es múltiplo de 8. Si divides 72 entre 7 o entre 5, sobran 2.",
  },
  {
    id: "completa-54", group: COMPLETE, type: "number",
    question: "54 es múltiplo de 6 porque 6 × ___ = 54. ¿Qué número falta?",
    answer: 9,
    explanation: "En la tabla del 6, 6 × 9 = 54. Para encontrarlo también puedes dividir: 54 : 6 = 9.",
  },
  {
    id: "huevos", group: PROBLEMS, type: "choice",
    question: "Los huevos se venden en cajas de 12 y no se pueden comprar sueltos. ¿Cuántos huevos puedes llevar a casa?",
    options: ["30 huevos", "48 huevos", "50 huevos"], answer: 1,
    explanation: "Solo puedes llevar múltiplos de 12, porque cada caja tiene 12 huevos: 12 × 4 = 48, es decir, 4 cajas. El 30 y el 50 no están en la tabla del 12.",
  },
  {
    id: "reto-2-y-3", group: PROBLEMS, type: "choice",
    question: "Reto: ¿qué número es múltiplo de 2 y también de 3?",
    options: ["9", "14", "18"], answer: 2,
    explanation: "18 = 2 × 9 y 18 = 3 × 6. El 9 es múltiplo de 3 pero no de 2, y el 14 es múltiplo de 2 pero no de 3.",
  },
];
