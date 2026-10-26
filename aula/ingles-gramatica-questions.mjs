import { summarize } from "../grading.mjs";

export const grammarQuestions = [
  { id: "be-i", topic: "be-affirmative", question: "Completa: I ___ a student.", options: ["is", "am", "are"], answer: 1, explanation: "Con I, la forma de to be es am: I am a student." },
  { id: "be-she", topic: "be-affirmative", question: "Completa: She ___ happy.", options: ["are", "am", "is"], answer: 2, explanation: "Con he, she e it usamos is: She is happy." },
  { id: "be-we-not", topic: "be-negative", question: "Pasa a negativa: We are tired.", options: ["We are not tired.", "We not are tired.", "We do not are tired."], answer: 0, explanation: "Con to be colocamos not después del verbo, sin do: We are not tired." },
  { id: "be-isnt", topic: "be-negative", question: "¿Qué significa He isn’t at school?", options: ["Él está en el colegio.", "Él no está en el colegio.", "¿Está él en el colegio?"], answer: 1, explanation: "Isn’t significa is not. La frase es negativa: él no está en el colegio." },
  { id: "be-question", topic: "be-interrogative", question: "Pregunta si ella es tu profesora.", options: ["Does she is your teacher?", "She is your teacher?", "Is she your teacher?"], answer: 2, explanation: "En las preguntas de to be se invierte el orden: Is + she + your teacher?" },
  { id: "be-they-question", topic: "be-interrogative", question: "Pasa a interrogativa: They are ready.", options: ["Are they ready?", "Do they are ready?", "Is they ready?"], answer: 0, explanation: "They lleva are. Para preguntar lo ponemos delante: Are they ready?" },
  { id: "be-short", topic: "be-short", question: "Responde afirmativamente: Are you happy?", options: ["Yes, I do.", "Yes, I am.", "Yes, I’m."], answer: 1, explanation: "Con to be respondemos con to be: Yes, I am. No contraemos I am al final de esta respuesta corta." },
  { id: "be-short-negative", topic: "be-short", question: "Responde negativamente: Is he tired?", options: ["No, he doesn’t.", "No, he aren’t.", "No, he isn’t."], answer: 2, explanation: "La pregunta usa is, así que la respuesta es No, he isn’t (he is not)." },
  { id: "have-she", topic: "have-affirmative", question: "Completa: She ___ a dog.", options: ["has", "have", "haves"], answer: 0, explanation: "En afirmativa, she lleva has: She has a dog." },
  { id: "have-we", topic: "have-affirmative", question: "Completa: We ___ two pencils.", options: ["has", "have", "having"], answer: 1, explanation: "Con I, you, we y they usamos have: We have two pencils." },
  { id: "have-negative", topic: "have-negative", question: "Pasa a negativa: He has a bike. Usa don’t o doesn’t.", options: ["He don’t have a bike.", "He doesn’t has a bike.", "He doesn’t have a bike."], answer: 2, explanation: "Con he usamos doesn’t y después el verbo base have, no has." },
  { id: "have-question", topic: "have-interrogative", question: "Pregunta si ella tiene un gato. Usa do o does.", options: ["Does she have a cat?", "Does she has a cat?", "Do she have a cat?"], answer: 0, explanation: "La estructura es Does + she + have. Has solo aparece en la afirmativa sin does." },
  { id: "have-short", topic: "have-short", question: "Responde negativamente: Do they have a ball?", options: ["No, they aren’t.", "No, they don’t.", "No, they hasn’t."], answer: 1, explanation: "La pregunta empieza con Do: respondemos No, they don’t." },
  { id: "got-affirmative", topic: "got-affirmative", question: "Completa: He ___ got a sister.", options: ["have", "is", "has"], answer: 2, explanation: "Con he usamos has got para expresar posesión: He has got a sister." },
  { id: "got-negative", topic: "got-negative", question: "Pasa a negativa: They have got a car.", options: ["They haven’t got a car.", "They doesn’t got a car.", "They aren’t got a car."], answer: 0, explanation: "Con have got, la negativa es have not got, o haven’t got. No se añade do." },
  { id: "got-question", topic: "got-interrogative", question: "Pregunta si ella tiene una mochila. Usa have got.", options: ["Does she has got a bag?", "Has she got a bag?", "Have she got a bag?"], answer: 1, explanation: "Con she usamos has. En la pregunta va delante: Has she got a bag?" },
  { id: "poss-my", topic: "possessive-adjective", question: "Completa: This is ___ book. (Es mi libro.)", options: ["mine", "I", "my"], answer: 2, explanation: "Delante del nombre book necesitamos el adjetivo my. Mine sustituye al nombre." },
  { id: "poss-mine", topic: "possessive-pronoun", question: "Completa: This book is ___. (Este libro es mío.)", options: ["mine", "my", "me"], answer: 0, explanation: "No hay un nombre después: usamos el pronombre mine, no el adjetivo my." },
  { id: "poss-hers", topic: "possessive-pronoun", question: "The bag belongs to Anna. The bag is ___.", options: ["her", "hers", "she"], answer: 1, explanation: "La mochila es de Anna: usamos hers para sustituir a her bag." },
  { id: "poss-his", topic: "possessive-pronoun", question: "The pen belongs to Tom. The pen is ___.", options: ["he", "him", "his"], answer: 2, explanation: "His significa suyo, de él. Tiene la misma forma con nombre (his pen) y sin nombre (the pen is his)." },
  { id: "poss-ours", topic: "possessive-pronoun", question: "Completa: These books are ___. (Son nuestros.)", options: ["ours", "our", "we"], answer: 0, explanation: "Ours sustituye a our books. El pronombre no cambia porque haya varios libros." },
  { id: "poss-theirs", topic: "possessive-pronoun", question: "The bikes belong to my friends. The bikes are ___.", options: ["their", "theirs", "they"], answer: 1, explanation: "Theirs significa suyas, de ellos o ellas. Their necesita un nombre después." },
  { id: "poss-yours", topic: "possessive-pronoun", question: "Elige la frase correcta para decir «La regla es tuya».", options: ["The ruler is your.", "The ruler is your’s.", "The ruler is yours."], answer: 2, explanation: "El pronombre es yours, sin apóstrofo. Your acompaña al nombre: your ruler." },
  { id: "poss-its", topic: "possessive-adjective", question: "Completa: The cat is moving ___ tail. (El gato mueve su cola.)", options: ["its", "it’s", "it"], answer: 0, explanation: "Its es el posesivo que acompaña a tail. It’s es una contracción de it is o it has, no un posesivo." },
];

export function gradeGrammarQuiz(questions, answers) {
  const results = questions.map(question => {
    const selected = answers[question.id];
    const correct = selected === question.answer;
    return { question, selected, correct, score: correct ? 1 : 0 };
  });
  return { results, ...summarize(results) };
}
