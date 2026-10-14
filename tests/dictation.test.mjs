import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dictation, dictationText } from "../dictation-content.mjs";
import { gradeDictation, tokenizeDictation } from "../dictation-grading.mjs";

test("Dictado original de quinto: longitud adecuada y doce audios PCM reales", () => {
  const words = tokenizeDictation(dictationText).filter(token => token.word);
  assert.ok(words.length >= 75 && words.length <= 110);
  assert.equal(dictation.chunks.length, 12);
  let totalDuration = 0;
  for (const chunk of dictation.chunks) {
    assert.ok(chunk.text && chunk.spoken);
    const wav = readFileSync(new URL(chunk.audio));
    assert.equal(wav.toString("ascii", 0, 4), "RIFF");
    assert.equal(wav.toString("ascii", 8, 12), "WAVE");
    assert.equal(wav.toString("ascii", 12, 16), "fmt ");
    assert.equal(wav.readUInt16LE(20), 1);
    assert.equal(wav.readUInt16LE(22), 1);
    assert.equal(wav.readUInt16LE(34), 16);
    assert.equal(wav.toString("ascii", 36, 40), "data");
    const duration = wav.readUInt32LE(40) / wav.readUInt32LE(28);
    assert.ok(duration > 1 && duration < 15);
    assert.ok(wav.subarray(44).some(sample => sample !== 0), "Audio no silencioso");
    totalDuration += duration;
  }
  assert.ok(totalDuration > 30 && totalDuration < 45, "Lectura fluida, sin ralentización adicional");
  assert.equal(dictation.chunks.filter(chunk => /[,.]$/.test(chunk.text)).every(chunk => /coma|Punto/.test(chunk.spoken)), true);
});

test("La velocidad predeterminada no ralentiza la voz y permite ajustar el ritmo", () => {
  const html = readFileSync(new URL("../aula/dictado.html", import.meta.url), "utf8");
  assert.match(html, /<option value="1" selected>Normal<\/option>/);
  assert.match(html, /<option value="0\.9">Despacio<\/option>/);
  assert.match(html, /<option value="1\.15">Más rápido<\/option>/);
  assert.ok(dictation.chunks.every(chunk => new URL(chunk.audio).searchParams.get("v") === "2"));
});

test("Modelo exacto, espacios, saltos de línea y Unicode descompuesto no generan faltas", () => {
  for (const response of [dictationText, `  ${dictationText.replaceAll(" ", "\n  ")}  `, dictationText.normalize("NFD")]) {
    const review = gradeDictation(dictationText, response);
    assert.deepEqual(review.issues, []);
    assert.equal(review.correctWords, review.totalWords);
  }
});

test("Detecta tildes, mayúsculas y letras sin confundir la ñ ni la diéresis", () => {
  const response = dictationText.replace("sábado", "sabado").replace("Hugo", "hugo").replace("hermana", "ermana")
    .replace("pequeño", "pequeno").replace("río", "rio");
  const review = gradeDictation(dictationText, response);
  assert.equal(review.issues.length, 5);
  assert.deepEqual(review.issues.map(issue => issue.kind), ["accent", "capitalization", "spelling", "spelling", "accent"]);
  assert.equal(review.correctWords, review.totalWords - 5);
  assert.equal(gradeDictation("El pingüino.", "El pinguino.").issues[0].kind, "spelling");
  assert.equal(gradeDictation("Después.", "despues.").issues[0].kind, "accent");
  assert.equal(gradeDictation("El año.", "El ano.").issues[0].kind, "spelling");
});

test("Una omisión o inserción no desplaza la corrección del resto del texto", () => {
  const missing = gradeDictation(dictationText, dictationText.replace("su hermana ", ""));
  assert.equal(missing.issues.length, 2);
  assert.ok(missing.issues.every(issue => issue.kind === "missing"));
  assert.deepEqual(missing.issues.map(issue => issue.expected), ["su", "hermana"]);
  const extra = gradeDictation(dictationText, dictationText.replace("un pequeño", "un enorme pequeño"));
  assert.equal(extra.issues.length, 1);
  assert.equal(extra.issues[0].kind, "extra");
  assert.equal(extra.issues[0].actual, "enorme");
  const repeated = gradeDictation("Hugo fue a casa.", "Hugo fue fue a casa.");
  assert.equal(repeated.issues.length, 1);
  assert.equal(repeated.issues[0].kind, "extra");
});

test("Puntuación ausente, cambiada o añadida se revisa aparte de las palabras", () => {
  const noPunctuation = gradeDictation(dictationText, dictationText.replace(/[,.]/g, ""));
  assert.equal(noPunctuation.correctWords, noPunctuation.totalWords);
  assert.equal(noPunctuation.punctuationErrors, (dictationText.match(/[,.]/g) ?? []).length);
  assert.ok(noPunctuation.issues.every(issue => issue.kind === "punctuation"));
  const changed = gradeDictation("Hugo, ven.", "Hugo; ven!");
  assert.equal(changed.issues.length, 2);
  assert.equal(changed.punctuationErrors, 2);
  assert.equal(gradeDictation("Hugo.", "¡Hugo!").punctuationErrors, 2);
});

test("La comparación conserva caracteres peligrosos como texto y rechaza entradas vacías o excesivas", () => {
  const dangerous = gradeDictation("Hugo lee.", "<script>alert(1)</script>");
  assert.ok(dangerous.issues.length > 0);
  for (const response of ["", " \n ", "hola ".repeat(301), "a".repeat(4001)]) {
    assert.throws(() => gradeDictation(dictationText, response), /Escribe|demasiado largo/);
  }
  assert.throws(() => gradeDictation(null, "Hugo"), /deben ser textos/);
  assert.throws(() => gradeDictation("", "Hugo"), /Escribe/);
});

test("Los índices permiten marcar la respuesta y contextualizar omisiones", () => {
  const expected = "El sábado, Hugo lee.";
  const response = "El sabado Hugo lee mucho.";
  const review = gradeDictation(expected, response);
  const actual = tokenizeDictation(response);
  const reference = tokenizeDictation(expected);
  for (const issue of review.issues) {
    if (issue.actual) assert.equal(actual[issue.actualIndex].text, issue.actual);
    if (issue.expected) assert.equal(reference[issue.expectedIndex].text, issue.expected);
  }
  assert.equal(review.issues.length, 3);
});
