export const classroomVocabulary = [
  { english: "scissors", spanish: "tijeras", explanation: "Scissors nombra el utensilio para cortar papel. Se escribe con sc al principio, doble s en medio y s final porque se usa en plural." },
  { english: "desk", spanish: "pupitre", explanation: "Desk es la mesa de trabajo del alumno, es decir, el pupitre. No es board, que es la pizarra." },
  { english: "calculator", spanish: "calculadora", explanation: "Calculator es el aparato para hacer cálculos. Aunque se parece a «calculadora», en inglés termina en -tor, no en -dora." },
  { english: "folder", spanish: "carpeta", explanation: "Folder sirve para guardar hojas sueltas: es una carpeta. No es notebook, que es un cuaderno con las hojas unidas." },
  { english: "notebook", spanish: "cuaderno", explanation: "Notebook une note (nota) y book (libro): es el cuaderno donde escribes. Se escribe como una sola palabra." },
  { english: "board", spanish: "pizarra", explanation: "Board es la pizarra donde escribe la profesora. En esta práctica no se refiere al pupitre del alumno, que es desk." },
  { english: "diary", spanish: "agenda", explanation: "En este vocabulario escolar, diary es la agenda para anotar tareas y fechas. No es dictionary, que sirve para consultar palabras." },
  { english: "bin", spanish: "papelera", explanation: "Bin es el recipiente donde tiras los papeles: la papelera. No es una carpeta para guardarlos." },
  { english: "dictionary", spanish: "diccionario", explanation: "Dictionary es el libro para consultar el significado de las palabras. Recuerda su terminación -ary; no es diary, la agenda." },
  { english: "sharpener", spanish: "sacapuntas", explanation: "Sharpener es el objeto que afila la punta del lápiz. Se relaciona con sharp (afilado) y termina en -ener." },
];

export const classroomPhrases = [
  { english: "Can you speak more slowly?", spanish: "¿Puedes hablar más despacio?", explanation: "Can you…? pide a otra persona que haga algo; speak es hablar y more slowly significa más despacio." },
  { english: "How do you spell calculator?", spanish: "¿Cómo se escribe «calculator»?", explanation: "How do you spell…? sirve para preguntar las letras de una palabra. Spell significa deletrear, no hablar." },
  { english: "Can I borrow a sharpener?", spanish: "¿Puedo pedir prestado un sacapuntas?", explanation: "Can I…? pide permiso para ti. Borrow es recibir algo prestado, y a sharpener es un sacapuntas." },
  { english: "Can I go to the toilet?", spanish: "¿Puedo ir al baño?", explanation: "Can I…? pide permiso; go to significa ir a. En esta expresión usamos the delante de toilet." },
  { english: "Sorry, I'm late.", spanish: "Perdona, llego tarde.", explanation: "Sorry expresa disculpa y I'm es la contracción de I am. En inglés se dice I am late (estoy llegando tarde), no se traduce «llego» palabra por palabra." },
  { english: "Don't forget to say please!", spanish: "¡No olvides decir «please»!", explanation: "Don't forma una orden negativa; forget significa olvidar. Después de forget se usa to say: no olvides decir por favor." },
];

export const classroomPractice = [
  ...classroomVocabulary.map(({ english, spanish, explanation }) => ({
    id: `classroom-word-${english}`,
    display: `Traduce al inglés: ${spanish}`,
    answer: english,
    explanation,
  })),
  ...classroomPhrases.map(({ english, spanish, explanation }) => ({
    id: `classroom-phrase-${english}`,
    display: `Di en inglés: ${spanish}`,
    answer: english,
    explanation,
  })),
];
