import { summarize, shuffle } from "../grading.mjs";

/**
 * Banco de 72 preguntas. Cada test elige 24 al azar (ver pickGrammarQuestions),
 * así que dos intentos seguidos casi nunca repiten las mismas preguntas.
 */
export const grammarQuestions = [
  { id: "be-i", topic: "be-affirmative", question: "Completa: I ___ a student.", options: ["is", "am", "are"], answer: 1, explanation: "Con I, la forma de to be es am: I am a student." },
  { id: "be-she", topic: "be-affirmative", question: "Completa: She ___ happy.", options: ["are", "am", "is"], answer: 2, explanation: "Con he, she e it usamos is: She is happy." },
  { id: "be-you", topic: "be-affirmative", question: "Completa: You ___ my friend.", options: ["am", "is", "are"], answer: 2, explanation: "Con you (tú o vosotros) usamos are: You are my friend." },
  { id: "be-they", topic: "be-affirmative", question: "Completa: They ___ at home.", options: ["is", "are", "am"], answer: 1, explanation: "Con they (ellos o ellas) usamos are: They are at home." },
  { id: "be-it", topic: "be-affirmative", question: "Completa: It ___ a big dog.", options: ["are", "am", "is"], answer: 2, explanation: "Con he, she e it usamos is: It is a big dog." },
  { id: "be-we", topic: "be-affirmative", question: "Completa: We ___ in class.", options: ["are", "is", "am"], answer: 0, explanation: "Con we (nosotros) usamos are: We are in class." },
  { id: "be-we-not", topic: "be-negative", question: "Pasa a negativa: We are tired.", options: ["We are not tired.", "We not are tired.", "We do not are tired."], answer: 0, explanation: "Con to be colocamos not después del verbo, sin do: We are not tired." },
  { id: "be-isnt", topic: "be-negative", question: "¿Qué significa He isn’t at school?", options: ["Él está en el colegio.", "Él no está en el colegio.", "¿Está él en el colegio?"], answer: 1, explanation: "Isn’t significa is not. La frase es negativa: él no está en el colegio." },
  { id: "be-i-not", topic: "be-negative", question: "Pasa a negativa: I am tired.", options: ["I not am tired.", "I am not tired.", "I don’t am tired."], answer: 1, explanation: "Con to be la negativa es am + not. Nunca se usa don’t con to be." },
  { id: "be-they-not", topic: "be-negative", question: "Pasa a negativa: They are at school.", options: ["They aren’t at school.", "They don’t are at school.", "They not are at school."], answer: 0, explanation: "Aren’t es la contracción de are not. La negativa de to be no lleva do." },
  { id: "be-she-isnt", topic: "be-negative", question: "Completa: She ___ at home. (Ella no está en casa.)", options: ["isn’t", "aren’t", "doesn’t"], answer: 0, explanation: "Con she usamos isn’t (is not): She isn’t at home." },
  { id: "be-question", topic: "be-interrogative", question: "Pregunta si ella es tu profesora.", options: ["Does she is your teacher?", "She is your teacher?", "Is she your teacher?"], answer: 2, explanation: "En las preguntas de to be se invierte el orden: Is + she + your teacher?" },
  { id: "be-they-question", topic: "be-interrogative", question: "Pasa a interrogativa: They are ready.", options: ["Are they ready?", "Do they are ready?", "Is they ready?"], answer: 0, explanation: "They lleva are. Para preguntar lo ponemos delante: Are they ready?" },
  { id: "be-you-question", topic: "be-interrogative", question: "Pasa a interrogativa: You are ready.", options: ["Do you are ready?", "Are you ready?", "You are ready?"], answer: 1, explanation: "Con to be cambiamos el orden: Are + you + ready?" },
  { id: "be-he-question", topic: "be-interrogative", question: "Pregunta si él es tu hermano.", options: ["Is he your brother?", "Does he is your brother?", "He is your brother?"], answer: 0, explanation: "Con he usamos is y lo ponemos delante: Is he your brother?" },
  { id: "be-it-question", topic: "be-interrogative", question: "Pasa a interrogativa: It is cold today.", options: ["Does it is cold today?", "It is cold today?", "Is it cold today?"], answer: 2, explanation: "El verbo to be va delante del sujeto: Is it cold today?" },
  { id: "be-short", topic: "be-short", question: "Responde afirmativamente: Are you happy?", options: ["Yes, I do.", "Yes, I am.", "Yes, I’m."], answer: 1, explanation: "Con to be respondemos con to be: Yes, I am. No contraemos I am al final de esta respuesta corta." },
  { id: "be-short-negative", topic: "be-short", question: "Responde negativamente: Is he tired?", options: ["No, he doesn’t.", "No, he aren’t.", "No, he isn’t."], answer: 2, explanation: "La pregunta usa is, así que la respuesta es No, he isn’t (he is not)." },
  { id: "be-short-yes-she", topic: "be-short", question: "Responde afirmativamente: Is she your sister?", options: ["Yes, she does.", "Yes, she is.", "Yes, she’s."], answer: 1, explanation: "La pregunta usa is: Yes, she is. En la respuesta corta no se contrae: «yes, she’s» no se usa aquí." },
  { id: "be-short-no-they", topic: "be-short", question: "Responde negativamente: Are they ready?", options: ["No, they don’t.", "No, they isn’t.", "No, they aren’t."], answer: 2, explanation: "La pregunta usa are: No, they aren’t (they are not)." },
  { id: "be-short-no-i", topic: "be-short", question: "Responde negativamente: Are you tired?", options: ["No, I don’t.", "No, I’m not.", "No, I amn’t."], answer: 1, explanation: "Con to be la respuesta corta negativa es No, I’m not. «Amn’t» no existe en inglés." },
  { id: "have-she", topic: "have-affirmative", question: "Completa: She ___ a dog.", options: ["has", "have", "haves"], answer: 0, explanation: "En afirmativa, she lleva has: She has a dog." },
  { id: "have-we", topic: "have-affirmative", question: "Completa: We ___ two pencils.", options: ["has", "have", "having"], answer: 1, explanation: "Con I, you, we y they usamos have: We have two pencils." },
  { id: "have-i", topic: "have-affirmative", question: "Completa: I ___ a new bike.", options: ["has", "have", "haves"], answer: 1, explanation: "Con I usamos have, nunca has: I have a new bike." },
  { id: "have-he", topic: "have-affirmative", question: "Completa: He ___ two sisters.", options: ["have", "has", "haves"], answer: 1, explanation: "Con he, she e it usamos has: He has two sisters." },
  { id: "have-they", topic: "have-affirmative", question: "Completa: They ___ a big house.", options: ["has", "have", "having"], answer: 1, explanation: "Con they usamos have: They have a big house." },
  { id: "have-it", topic: "have-affirmative", question: "Completa: It ___ a long tail.", options: ["have", "has", "is"], answer: 1, explanation: "Con it usamos has, igual que con she: It has a long tail." },
  { id: "have-negative", topic: "have-negative", question: "Pasa a negativa: He has a bike. Usa don’t o doesn’t.", options: ["He don’t have a bike.", "He doesn’t has a bike.", "He doesn’t have a bike."], answer: 2, explanation: "Con he usamos doesn’t y después el verbo base have, no has." },
  { id: "have-neg-i", topic: "have-negative", question: "Pasa a negativa: I have a dog. Usa don’t o doesn’t.", options: ["I don’t have a dog.", "I doesn’t have a dog.", "I haven’t a dog."], answer: 0, explanation: "Con I usamos don’t y el verbo base have: I don’t have a dog." },
  { id: "have-neg-they", topic: "have-negative", question: "Pasa a negativa: They have a car. Usa don’t o doesn’t.", options: ["They doesn’t have a car.", "They don’t have a car.", "They don’t has a car."], answer: 1, explanation: "Con they usamos don’t + have: They don’t have a car." },
  { id: "have-neg-she", topic: "have-negative", question: "Completa: She ___ have a bike. (Ella no tiene bici.)", options: ["don’t", "doesn’t", "isn’t"], answer: 1, explanation: "Con she usamos doesn’t y después have: She doesn’t have a bike." },
  { id: "have-neg-doesnt", topic: "have-negative", question: "¿Cuál es correcta?", options: ["He doesn’t has a cat.", "He don’t have a cat.", "He doesn’t have a cat."], answer: 2, explanation: "Después de doesn’t el verbo va en forma base: have, nunca has." },
  { id: "have-question", topic: "have-interrogative", question: "Pregunta si ella tiene un gato. Usa do o does.", options: ["Does she have a cat?", "Does she has a cat?", "Do she have a cat?"], answer: 0, explanation: "La estructura es Does + she + have. Has solo aparece en la afirmativa sin does." },
  { id: "have-int-you", topic: "have-interrogative", question: "Pregunta si tienes un lápiz. Usa do o does.", options: ["Do you have a pencil?", "Does you have a pencil?", "Have you a pencil?"], answer: 0, explanation: "Con you la pregunta empieza por Do: Do you have a pencil?" },
  { id: "have-int-he", topic: "have-interrogative", question: "Pregunta si él tiene un perro. Usa do o does.", options: ["Do he have a dog?", "Does he has a dog?", "Does he have a dog?"], answer: 2, explanation: "Con he usamos Does + he + have. El verbo va en forma base." },
  { id: "have-int-they", topic: "have-interrogative", question: "Pregunta si ellos tienen hermanos.", options: ["Do they have brothers?", "Does they have brothers?", "Do they has brothers?"], answer: 0, explanation: "Con they usamos Do + they + have: el verbo va en forma base." },
  { id: "have-int-we", topic: "have-interrogative", question: "Pregunta si tenemos una mascota.", options: ["Do we have a pet?", "Does we have a pet?", "Have we a pet?"], answer: 0, explanation: "Con we usamos Do + we + have: Do we have a pet?" },
  { id: "have-short", topic: "have-short", question: "Responde negativamente: Do they have a ball?", options: ["No, they aren’t.", "No, they don’t.", "No, they hasn’t."], answer: 1, explanation: "La pregunta empieza con Do: respondemos No, they don’t." },
  { id: "have-short-yes-i", topic: "have-short", question: "Responde afirmativamente: Do you have a pen?", options: ["Yes, I am.", "Yes, I do.", "Yes, I have."], answer: 1, explanation: "La pregunta empieza por Do, así que respondemos Yes, I do." },
  { id: "have-short-no-he", topic: "have-short", question: "Responde negativamente: Does he have a bike?", options: ["No, he doesn’t.", "No, he don’t.", "No, he isn’t."], answer: 0, explanation: "La pregunta empieza por Does: No, he doesn’t." },
  { id: "have-short-yes-they", topic: "have-short", question: "Responde afirmativamente: Do they have a dog?", options: ["Yes, they are.", "Yes, they have.", "Yes, they do."], answer: 2, explanation: "Con Do respondemos do, no have: Yes, they do." },
  { id: "have-short-no-she", topic: "have-short", question: "Responde negativamente: Does she have a cat?", options: ["No, she isn’t.", "No, she doesn’t.", "No, she don’t."], answer: 1, explanation: "Does se responde con doesn’t: No, she doesn’t." },
  { id: "got-affirmative", topic: "got-affirmative", question: "Completa: He ___ got a sister.", options: ["have", "is", "has"], answer: 2, explanation: "Con he usamos has got para expresar posesión: He has got a sister." },
  { id: "got-i", topic: "got-affirmative", question: "Completa: I ___ got a new phone.", options: ["has", "have", "am"], answer: 1, explanation: "Con I usamos have got: I have got a new phone." },
  { id: "got-she", topic: "got-affirmative", question: "Completa: She ___ got long hair.", options: ["have", "has", "is"], answer: 1, explanation: "Con she usamos has got: She has got long hair." },
  { id: "got-we", topic: "got-affirmative", question: "Completa: We ___ got two cats.", options: ["has", "have", "are"], answer: 1, explanation: "Con we usamos have got: We have got two cats." },
  { id: "got-they", topic: "got-affirmative", question: "Completa: They ___ got a big garden.", options: ["has", "have", "is"], answer: 1, explanation: "Con they usamos have got: They have got a big garden." },
  { id: "got-negative", topic: "got-negative", question: "Pasa a negativa: They have got a car.", options: ["They haven’t got a car.", "They doesn’t got a car.", "They aren’t got a car."], answer: 0, explanation: "Con have got, la negativa es have not got, o haven’t got. No se añade do." },
  { id: "got-neg-i", topic: "got-negative", question: "Pasa a negativa: I have got a bike.", options: ["I haven’t got a bike.", "I don’t got a bike.", "I am not got a bike."], answer: 0, explanation: "Con I usamos haven’t got. No se usa don’t con got." },
  { id: "got-neg-she", topic: "got-negative", question: "Pasa a negativa: She has got a bag.", options: ["She doesn’t got a bag.", "She hasn’t got a bag.", "She isn’t got a bag."], answer: 1, explanation: "Con she: hasn’t got (has not got), sin do." },
  { id: "got-neg-he", topic: "got-negative", question: "Completa: He ___ got a car. (Él no tiene coche.)", options: ["hasn’t", "haven’t", "doesn’t"], answer: 0, explanation: "Con he usamos hasn’t got: He hasn’t got a car." },
  { id: "got-neg-we", topic: "got-negative", question: "Completa: We ___ got a garden. (Nosotros no tenemos jardín.)", options: ["hasn’t", "haven’t", "aren’t"], answer: 1, explanation: "Con we usamos haven’t got: We haven’t got a garden." },
  { id: "got-question", topic: "got-interrogative", question: "Pregunta si ella tiene una mochila. Usa have got.", options: ["Does she has got a bag?", "Has she got a bag?", "Have she got a bag?"], answer: 1, explanation: "Con she usamos has. En la pregunta va delante: Has she got a bag?" },
  { id: "got-int-you", topic: "got-interrogative", question: "Pregunta si tienes una bici. Usa have got.", options: ["Do you have got a bike?", "Have you got a bike?", "Are you got a bike?"], answer: 1, explanation: "Con have got la pregunta es Have + you + got...? Nunca se usa do." },
  { id: "got-int-he", topic: "got-interrogative", question: "Pregunta si él tiene un perro. Usa have got.", options: ["Does he has got a dog?", "Has he got a dog?", "Have he got a dog?"], answer: 1, explanation: "Con he usamos Has + he + got...? No se usa does." },
  { id: "got-int-they", topic: "got-interrogative", question: "Pregunta si ellos tienen hermanos. Usa have got.", options: ["Have they got brothers?", "Do they got brothers?", "Has they got brothers?"], answer: 0, explanation: "Con they usamos Have + they + got...? No se usa do con got." },
  { id: "got-int-she", topic: "got-interrogative", question: "¿Cuál es correcta para preguntar si ella tiene una mochila?", options: ["Does she got a bag?", "Have she got a bag?", "Has she got a bag?"], answer: 2, explanation: "Has + she + got: Has she got a bag? Con she el verbo auxiliar es has." },
  { id: "poss-my", topic: "possessive-adjective", question: "Completa: This is ___ book. (Es mi libro.)", options: ["mine", "I", "my"], answer: 2, explanation: "Delante del nombre book necesitamos el adjetivo my. Mine sustituye al nombre." },
  { id: "poss-mine", topic: "possessive-pronoun", question: "Completa: This book is ___. (Este libro es mío.)", options: ["mine", "my", "me"], answer: 0, explanation: "No hay un nombre después: usamos el pronombre mine, no el adjetivo my." },
  { id: "poss-hers", topic: "possessive-pronoun", question: "The bag belongs to Anna. The bag is ___.", options: ["her", "hers", "she"], answer: 1, explanation: "La mochila es de Anna: usamos hers para sustituir a her bag." },
  { id: "poss-his", topic: "possessive-pronoun", question: "The pen belongs to Tom. The pen is ___.", options: ["he", "him", "his"], answer: 2, explanation: "His significa suyo, de él. Tiene la misma forma con nombre (his pen) y sin nombre (the pen is his)." },
  { id: "poss-ours", topic: "possessive-pronoun", question: "Completa: These books are ___. (Son nuestros.)", options: ["ours", "our", "we"], answer: 0, explanation: "Ours sustituye a our books. El pronombre no cambia porque haya varios libros." },
  { id: "poss-theirs", topic: "possessive-pronoun", question: "The bikes belong to my friends. The bikes are ___.", options: ["their", "theirs", "they"], answer: 1, explanation: "Theirs significa suyas, de ellos o ellas. Their necesita un nombre después." },
  { id: "poss-yours", topic: "possessive-pronoun", question: "Elige la frase correcta para decir «La regla es tuya».", options: ["The ruler is your.", "The ruler is your’s.", "The ruler is yours."], answer: 2, explanation: "El pronombre es yours, sin apóstrofo. Your acompaña al nombre: your ruler." },
  { id: "poss-its", topic: "possessive-adjective", question: "Completa: The cat is moving ___ tail. (El gato mueve su cola.)", options: ["its", "it’s", "it"], answer: 0, explanation: "Its es el posesivo que acompaña a tail. It’s es una contracción de it is o it has, no un posesivo." },
  { id: "poss-your", topic: "possessive-adjective", question: "Completa: Is this ___ pencil? (¿Es tu lápiz?)", options: ["you", "your", "yours"], answer: 1, explanation: "Delante del nombre usamos your: your pencil. Yours va solo: the pencil is yours." },
  { id: "poss-their", topic: "possessive-adjective", question: "Completa: The children love ___ school. (Los niños quieren su colegio.)", options: ["their", "theirs", "they"], answer: 0, explanation: "Delante de school usamos their. Theirs sustituye al nombre: the school is theirs." },
  { id: "poss-her", topic: "possessive-adjective", question: "Completa: Anna loves ___ dog. (Anna quiere a su perro.)", options: ["hers", "her", "she"], answer: 1, explanation: "Delante del nombre usamos her: her dog. Hers va sin nombre: the dog is hers." },
  { id: "poss-mine-notebook", topic: "possessive-pronoun", question: "Completa: This notebook is ___. (Es mío.)", options: ["my", "mine", "me"], answer: 1, explanation: "Sin nombre después del verbo usamos mine: This notebook is mine." },
  { id: "poss-yours-ruler", topic: "possessive-pronoun", question: "Completa: The ruler is ___. (Es tuya.)", options: ["your", "yours", "you"], answer: 1, explanation: "Yours sustituye a your ruler: The ruler is yours." },
  { id: "poss-ours-seats", topic: "possessive-pronoun", question: "Completa: These seats are ___. (Son nuestros.)", options: ["our", "ours", "us"], answer: 1, explanation: "Ours sustituye a our seats: These seats are ours." },
  { id: "poss-theirs-posters", topic: "possessive-pronoun", question: "Completa: Those posters are ___. (Son suyos, de ellos.)", options: ["their", "theirs", "them"], answer: 1, explanation: "Theirs sustituye a their posters: Those posters are theirs." },
];

/** Cuántas preguntas tiene cada test. */
export const GRAMMAR_QUIZ_SIZE = 24;

/**
 * Elige preguntas al azar repartidas entre todos los temas, para que ningún
 * test se quede sin, por ejemplo, posesivos o preguntas con have got.
 */
export function pickGrammarQuestions(count = GRAMMAR_QUIZ_SIZE, random = Math.random) {
  const byTopic = new Map();
  for (const question of grammarQuestions) {
    if (!byTopic.has(question.topic)) byTopic.set(question.topic, []);
    byTopic.get(question.topic).push(question);
  }
  for (const list of byTopic.values()) {
    const shuffled = shuffle(list, random);
    list.length = 0;
    list.push(...shuffled);
  }
  const topics = shuffle([...byTopic.keys()], random);
  const total = Math.min(count, grammarQuestions.length);
  const picked = [];
  for (let round = 0; picked.length < total; round++) {
    let added = false;
    for (const topic of topics) {
      const question = byTopic.get(topic)[round];
      if (!question) continue;
      if (picked.length < total) picked.push(question);
      added = true;
    }
    if (!added) break;
  }
  return shuffle(picked, random);
}

export function gradeGrammarQuiz(questions, answers) {
  const results = questions.map(question => {
    const selected = answers[question.id];
    const correct = selected === question.answer;
    return { question, selected, correct, score: correct ? 1 : 0 };
  });
  return { results, ...summarize(results) };
}
