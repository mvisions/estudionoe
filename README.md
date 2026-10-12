# Noé · Test de historia

Web publicada en https://mvisions.github.io/estudionoe/ desde el repositorio
independiente `mvisions/estudionoe`.

## Uso

Se pide nombre o alias y curso antes de comenzar. Incluye las 30 preguntas de
los apuntes originales y tres modos:

- Test fácil: una respuesta correcta y dos falsas.
- Unir con flechas: 39 parejas derivadas de las 30 preguntas, en bloques de cinco.
- Respuesta escrita: corrección orientativa por ideas clave, no por IA.

Bien suma 1 punto, regular 0,5 y mal o sin respuesta 0. La nota final es
`puntos / preguntas × 10`. El resultado muestra fallos, respuestas modelo e
ideas que faltan. Los apuntes se conservan según lo solicitado, incluidas sus
simplificaciones e imprecisiones históricas.

## Ranking local

No requiere Render, Google Cloud ni claves. El frontend no llama a ninguna API.
Guarda nombre, curso, nota, duración y fecha en `localStorage` de este navegador.
Cada modo conserva sus 50 mejores resultados: nota descendente, tiempo ascendente,
y fecha ascendente en caso de empate. El cronómetro incluye pausas y salir de la página.
Al finalizar un examen completo se guarda su resultado una sola vez.
Los repasos de fallos no participan en la clasificación.

El ranking persiste al recargar, pero no se comparte entre dispositivos, perfiles
de navegador ni direcciones web diferentes. Borrar datos del navegador también
lo elimina. «Borrar todo y empezar de nuevo» borra el progreso y todo el ranking
local, con confirmación. Los errores de almacenamiento se notifican y permiten
reintentar guardar el resultado. No se envían nombres ni respuestas a un servidor.

## Desarrollo y publicación

Para abrir en local: `python3 -m http.server 8080`.
Para validar: `npm test`.
GitHub Actions ejecuta las pruebas y publica únicamente los archivos estáticos.
La API experimental y su configuración permanecen en el repositorio, pero no
se usan ni se publican con esta versión local.
