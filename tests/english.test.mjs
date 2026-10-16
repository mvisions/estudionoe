import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gradeEnglishAnswer } from "../english-grading.mjs";

test("Los ejercicios cubren las 29 palabras de ambos temas sin duplicar el banco", () => {
  for (const [topic, count] of [[3, 12], [4, 17]]) {
    const html = readFileSync(new URL(`../aula/ingles-tema-${topic}.html`, import.meta.url), "utf8");
    const words = [...html.matchAll(/<dt>([^<]+)<\/dt><dd>([^<]+)<\/dd>/g)];
    assert.equal(words.length, count);
    assert.equal(new Set(words.map(word => word[1])).size, count);
    assert.ok(html.includes('id="english-exercises"'));
    assert.ok(html.includes('src="../english-exercises.mjs"'));
    for (const [, english] of words) {
      assert.equal(gradeEnglishAnswer(english, english), true);
      assert.equal(gradeEnglishAnswer(english, `  ${english.toUpperCase().replaceAll(" ", "   ")}  `), true);
      assert.equal(gradeEnglishAnswer(english, ""), false);
      assert.equal(gradeEnglishAnswer(english, "   "), false);
      assert.equal(gradeEnglishAnswer(english, `${english}x`), false);
    }
  }
});

test("Se aceptan variantes válidas sin aceptar errores de ortografía ni número", () => {
  for (const [expected, answer] of [["hippo", "hippopotamus"], ["rhino", "rhinoceros"], ["competition", "contest"]]) {
    assert.equal(gradeEnglishAnswer(expected, answer), true);
  }
  for (const [expected, answer] of [["claws", "claw"], ["camel", "camels"], ["cheetah", "cheeta"], ["food stall", "foodstall"], ["mask", "<script>"]]) {
    assert.equal(gradeEnglishAnswer(expected, answer), false);
  }
  assert.throws(() => gradeEnglishAnswer("camel", null), TypeError);
  assert.throws(() => gradeEnglishAnswer("", "camel"), TypeError);
});
