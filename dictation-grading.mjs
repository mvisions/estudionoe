export function tokenizeDictation(text) {
  return Array.from(text.normalize("NFC").matchAll(/[\p{L}\p{N}]+|[^\s\p{L}\p{N}]/gu),
    match => ({ text: match[0], word: /^[\p{L}\p{N}]/u.test(match[0]), start: match.index, end: match.index + match[0].length }));
}

const withoutAcute = text => text.normalize("NFD").replace(/\u0301/g, "").normalize("NFC");

function replacementKind(expected, actual) {
  if (!expected.word && !actual.word) return "punctuation";
  if (expected.text.toLocaleLowerCase("es") === actual.text.toLocaleLowerCase("es")) return "capitalization";
  if (withoutAcute(expected.text).toLocaleLowerCase("es") === withoutAcute(actual.text).toLocaleLowerCase("es")) return "accent";
  return "spelling";
}

export function gradeDictation(reference, response) {
  if (typeof reference !== "string" || typeof response !== "string") throw new Error("El dictado y la respuesta deben ser textos.");
  const expected = tokenizeDictation(reference);
  const actual = tokenizeDictation(response);
  if (!expected.length || !actual.length) throw new Error("Escribe tu dictado antes de corregir.");
  if (expected.length > 300 || actual.length > 300 || response.length > 4000) throw new Error("El texto es demasiado largo para este dictado. Usa como máximo 300 palabras y signos, y 4000 caracteres.");
  const costs = Array.from({ length: expected.length + 1 }, () => new Float64Array(actual.length + 1));
  const changes = Array.from({ length: expected.length + 1 }, () => new Uint8Array(actual.length + 1));
  for (let i = 1; i <= expected.length; i++) { costs[i][0] = i; changes[i][0] = 2; }
  for (let j = 1; j <= actual.length; j++) { costs[0][j] = j; changes[0][j] = 3; }
  for (let i = 1; i <= expected.length; i++) {
    for (let j = 1; j <= actual.length; j++) {
      const same = expected[i - 1].text === actual[j - 1].text;
      const replace = expected[i - 1].word === actual[j - 1].word ? 1 : 2.5;
      const candidates = [costs[i - 1][j - 1] + (same ? 0 : replace), costs[i - 1][j] + 1, costs[i][j - 1] + 1];
      const best = Math.min(...candidates);
      costs[i][j] = best;
      changes[i][j] = candidates.indexOf(best) + 1;
    }
  }
  const issues = [];
  let correctWords = 0;
  let i = expected.length, j = actual.length;
  while (i || j) {
    const change = changes[i][j];
    if (change === 1) {
      const left = expected[--i], right = actual[--j];
      if (left.text === right.text) { if (left.word) correctWords++; }
      else issues.push({ kind: replacementKind(left, right), expected: left.text, actual: right.text, expectedIndex: i, actualIndex: j });
    } else if (change === 2) {
      const left = expected[--i];
      issues.push({ kind: left.word ? "missing" : "punctuation", expected: left.text, actual: "", expectedIndex: i, actualIndex: j });
    } else {
      const right = actual[--j];
      issues.push({ kind: right.word ? "extra" : "punctuation", expected: "", actual: right.text, expectedIndex: i, actualIndex: j });
    }
  }
  const totalWords = expected.filter(token => token.word).length;
  return { issues: issues.reverse(), correctWords, totalWords, punctuationErrors: issues.filter(issue => issue.kind === "punctuation").length };
}

export function dictationMistakeChunks(chunks, response) {
  const reference = chunks.map(chunk => chunk.text).join(" ");
  const { issues } = gradeDictation(reference, response);
  const totalTokens = tokenizeDictation(reference).length;
  let offset = 0;
  return chunks.flatMap((chunk, index) => {
    const start = offset;
    offset += tokenizeDictation(chunk.text).length;
    const incorrect = issues.some(issue => {
      const position = Math.min(issue.expectedIndex, totalTokens - 1);
      return position >= start && position < offset;
    });
    return incorrect ? [{ ...chunk, index }] : [];
  });
}

export function explainDictationIssue(issue) {
  const word = issue.expected.toLocaleLowerCase("es");
  if (issue.kind === "accent") {
    const rules = {
      sábado: "Sábado es esdrújula (sá-ba-do); todas las esdrújulas llevan tilde.",
      mostró: "Mostró es aguda y termina en vocal, por eso lleva tilde en ó.",
      dragón: "Dragón es aguda y termina en n, por eso lleva tilde en ó.",
      vivía: "Vivía lleva tilde en la vocal cerrada tónica í para marcar el hiato: vi-ví-a.",
      río: "Río lleva tilde en la vocal cerrada tónica í para marcar el hiato: rí-o.",
      parecía: "Parecía lleva tilde en la vocal cerrada tónica í para marcar el hiato: pa-re-cí-a.",
      después: "Después es aguda y termina en s, por eso lleva tilde en é.",
      niños: "Niños conserva la ñ: no se sustituye por n.",
      descripción: "Descripción es aguda y termina en n, por eso lleva tilde en ó.",
      guardó: "Guardó es aguda y termina en vocal, por eso lleva tilde en ó.",
      enseñárselo: "Enseñárselo es esdrújula (en-se-ñár-se-lo); todas las esdrújulas llevan tilde.",
    };
    return `${rules[word] ?? `La forma «${issue.expected}» del modelo debe conservar sus tildes; cambiarlas puede alterar la pronunciación o el significado.`} Revisa también la mayúscula si ha cambiado.`;
  }
  if (issue.kind === "capitalization") {
    return issue.expected === "Hugo"
      ? "Hugo es un nombre propio de persona y siempre comienza con mayúscula."
      : /^[A-ZÁÉÍÓÚÜÑ]/u.test(issue.expected)
        ? `«${issue.expected}» comienza una oración y por eso lleva mayúscula inicial.`
        : `«${issue.expected}» no es un nombre propio ni comienza aquí una oración; se escribe con minúscula.`;
  }
  if (issue.kind === "punctuation") {
    if (issue.expected === ".") return "El punto cierra la oración y marca una pausa. No se sustituye por otro signo ni se omite.";
    if (issue.expected === ",") return "La coma separa esta parte de la oración y marca la pausa indicada en el audio; la oración continúa después.";
    return "El modelo no lleva un signo en este lugar; añadirlo cambia la puntuación del dictado.";
  }
  if (issue.kind === "missing") return `Falta «${issue.expected}»: forma parte de la frase que se escucha y es necesaria para reproducir el modelo completo.`;
  if (issue.kind === "extra") return `«${issue.actual}» no aparece en este punto del audio; hay que quitarla para no añadir ni repetir palabras.`;
  const spelling = {
    hugo: "Hugo es un nombre propio que se escribe con H inicial, aunque esa h no suene.",
    hermana: "Hermana se escribe con h inicial muda: no se oye, pero no se puede omitir.",
    ayudaba: "Ayudaba es una forma verbal en -aba; estas terminaciones se escriben con b.",
    biblioteca: "Biblioteca empieza por b y conserva el grupo bl.",
    bibliotecaria: "Bibliotecaria pertenece a la familia de biblioteca y conserva b y bl.",
    aventuras: "Aventuras se escribe con v, aunque en español b y v suelen sonar igual.",
    vecinos: "Vecinos se escribe con v inicial y c delante de i.",
    breve: "Breve conserva b en el grupo br y v en su segunda sílaba.",
    pequeño: "Pequeño conserva la ñ y el grupo qu delante de e; la ñ no es una n.",
    niños: "Niños se escribe con ñ; cambiarla por n cambia la palabra.",
    descripción: "Descripción conserva el grupo -pc- y la tilde en ó.",
  };
  return spelling[word] ?? `La palabra del audio es «${issue.expected}». Su escritura completa es ${Array.from(issue.expected).join(" · ")}; compara las letras con «${issue.actual}» para localizar el cambio.`;
}
