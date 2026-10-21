const units = [
  "", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
  "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
  "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
  "nineteenth",
];
const tens = [
  "", "", "twentieth", "thirtieth", "fortieth", "fiftieth", "sixtieth",
  "seventieth", "eightieth", "ninetieth",
];
const cardinalTens = [
  "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
  "eighty", "ninety",
];

export const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function validateDate(day, month) {
  const monthIndex = monthNames.indexOf(month);
  if (!Number.isInteger(day) || monthIndex < 0 || day < 1 || day > daysInMonth[monthIndex]) {
    throw new RangeError("La fecha debe ser válida y usar un mes en inglés.");
  }
}

export function ordinalWords(number) {
  if (!Number.isInteger(number) || number < 1 || number > 100) {
    throw new RangeError("El número ordinal debe estar entre 1 y 100.");
  }
  if (number < 20) return units[number];
  if (number < 100) {
    const ten = Math.floor(number / 10);
    const unit = number % 10;
    return unit === 0 ? tens[ten] : `${cardinalTens[ten]}-${units[unit]}`;
  }
  return "one hundredth";
}

export function ordinalExplanation(number) {
  const words = ordinalWords(number);
  const exceptions = {
    1: "one cambia a first", 2: "two cambia a second", 3: "three cambia a third",
    5: "five pierde ve y añade fth: fifth", 8: "eight añade h: eighth",
    9: "nine pierde la e antes de añadir th: ninth", 12: "twelve cambia ve por f antes de añadir th: twelfth",
  };
  if (exceptions[number]) return `Es un ordinal con escritura especial: ${exceptions[number]}. Indica una posición, no una cantidad.`;
  if (number === 100) return "En one hundredth, hundred recibe la terminación -th para indicar la posición centésima.";
  if (number >= 20 && number % 10 === 0) return `En las decenas, la y del cardinal cambia a ie antes de añadir th: ${cardinalTens[number / 10]} → ${words}.`;
  if (number > 20) return `Se conserva la decena ${cardinalTens[Math.floor(number / 10)]}, se añade un guion y solo la unidad se vuelve ordinal: ${words}. ${ordinalExplanation(number % 10)}`;
  return `Se añade -th al cardinal para expresar una posición: ${words}. No se escribe solo el número cardinal, que indica cantidad.`;
}

export function spokenDate(day, month) {
  validateDate(day, month);
  return `the ${ordinalWords(day)} of ${month}`;
}

export function writtenDate(day, month) {
  validateDate(day, month);
  return `${day}${ordinalSuffix(day)} ${month}`;
}

export function ordinalSuffix(number) {
  if (!Number.isInteger(number) || number < 1 || number > 100) {
    throw new RangeError("El número ordinal debe estar entre 1 y 100.");
  }
  const lastTwoDigits = number % 100;
  if (lastTwoDigits >= 11 && lastTwoDigits <= 13) return "th";
  if (number % 10 === 1) return "st";
  if (number % 10 === 2) return "nd";
  if (number % 10 === 3) return "rd";
  return "th";
}

export const ordinalNumbers = Array.from({ length: 100 }, (_, index) => {
  const number = index + 1;
  return {
    number,
    numeral: `${number}${ordinalSuffix(number)}`,
    words: ordinalWords(number),
  };
});
