const alternatives = {
  competition: ["contest"],
  costume: ["fancy dress costume"],
  watch: ["look", "look at"],
  hippo: ["hippopotamus"],
  rhino: ["rhinoceros"],
};

const normalize = text => text.normalize("NFKC").trim().toLowerCase().replace(/\s+/gu, " ");

export function gradeEnglishAnswer(expected, answer) {
  if (typeof expected !== "string" || !expected.trim() || typeof answer !== "string") {
    throw new TypeError("La palabra y la respuesta deben ser textos válidos.");
  }
  return [expected, ...(alternatives[expected] ?? [])].some(value => normalize(value) === normalize(answer));
}
