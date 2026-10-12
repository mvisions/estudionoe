# Noé · Test de historia

Web independiente con una API Node en Render y ranking persistente en Firestore.
La publicación de GitHub Pages sirve la web en `/estudionoe/` desde el repositorio
independiente `mvisions/estudionoe`, sin modificar la aplicación principal.

## Abrir

Desde esta carpeta, ejecuta `python3 -m http.server 8080` y abre
<http://localhost:8080>. Se necesita servir los archivos por HTTP porque se usan módulos JavaScript.
También puede publicarse esta carpeta en un alojamiento estático.
Para probar la API: `npm ci` y `RANKING_STORAGE=memory npm start` (puerto 8081).
El modo memoria es solo para desarrollo y pierde el ranking al reiniciar.

## Modos

- **Test fácil:** 30 preguntas, cada una con una respuesta correcta y dos falsas.
- **Unir con flechas:** 39 parejas derivadas de las 30 preguntas, en bloques de hasta cinco.
  Selecciona un concepto y luego una respuesta, mediante clic o teclado. Las letras
  identifican las parejas además de las flechas. Se pueden cambiar o borrar.
- **Respuesta escrita:** las mismas 30 preguntas del test. La corrección local
  busca ideas clave, ignora tildes y admite pequeños errores de escritura.
  No usa IA ni puede interpretar todas las paráfrasis o contradicciones.

Bien suma 1 punto; regular suma 0,5; mal o sin responder suma 0.
La nota sobre 10 es `puntos / número de preguntas × 10`.
La entrega requiere confirmación. El resultado muestra respuestas, fallos,
explicaciones e ideas no reconocidas. Se puede repetir el examen o solo sus fallos.

Antes de empezar se pide nombre o alias y curso. Se puede practicar sin ranking
o aceptar la publicación de alias, curso, nota, tiempo y fecha en el ranking público.
No usar apellidos ni datos personales, especialmente si se trata de menores.
Cada modo tiene su propia clasificación de 50 resultados, ordenada por nota
descendente y tiempo ascendente. Los repasos no entran en el ranking.
El servidor genera el examen y calcula nota y tiempo: no acepta puntuaciones
enviadas por el cliente. El cronómetro incluye pausas y salir de la página.
Los exámenes caducan a las 24 horas. La entrega es idempotente.
Es un ranking de práctica sin identidad verificada, no un examen vigilado.

El examen y su resultado se guardan localmente en el navegador. Si no se puede
guardar o recuperar el progreso, se muestra un aviso. No se envían las respuestas
a ningún servidor en el modo práctica. En modo ranking se envían para corregirlas
en la API, pero no se guardan en Firestore: se conserva solo el resultado.
Si falla la entrega, se muestra el error y se puede reintentar sin perder el resultado.
El tiempo oficial termina cuando el servidor acepta la entrega; incluye demoras de conexión.
Comenzar un examen nuevo sustituye el anterior.
El botón **Borrar todo y empezar de nuevo** está disponible en la portada,
durante el examen y en los resultados. Pide confirmación y elimina únicamente
los datos locales de esta web y sus entradas del ranking asociadas a este navegador.
No elimina los resultados de otros usuarios. Si falla el borrado remoto, avisa y
mantiene los identificadores locales para reintentarlo.

## Publicación

1. GitHub Actions prueba la API y copia únicamente los archivos públicos al sitio.
2. Crear un servicio web Render llamado `estudionoe-api`, conectado a
   `mvisions/estudionoe`, rama `main`, sin carpeta raíz,
   compilación `npm ci`, inicio `npm start`, plan gratuito.
   [render.yaml](./render.yaml) contiene los parámetros.
3. Configurar `GOOGLE_CLOUD_PROJECT=estudionoe-2026`, `NODE_ENV=production`,
   `ALLOWED_ORIGINS=https://mvisions.github.io`,
   `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/estudionoe-firestore-key.json`.
   Añadir ese archivo secreto en Render con credenciales de una cuenta de servicio
   con acceso a Firestore. Nunca incluir la clave en Git ni en el frontend.
4. Crear en Firestore el índice compuesto de [firestore.indexes.json](./firestore.indexes.json)
   para la colección independiente `estudionoeExams`. No modificar las reglas ni
   las colecciones de otras aplicaciones.
5. Si Render asigna una URL diferente, actualizar [config.mjs](./config.mjs).
6. Verificar `/api/health`, completar un examen desde la web publicada y comprobar
   que figura en el ranking desde otro navegador.

La API solo admite los orígenes configurados y aplica límites de tamaño y peticiones.
Las credenciales y el acceso a Firestore están solo en el servidor.
El servicio gratuito de Render puede tardar en arrancar tras inactividad.

## Contenido

Se respetan las respuestas del usuario, incluidas sus simplificaciones e
imprecisiones históricas. Están incluidas las 30 preguntas y la respuesta completa
de la pregunta 21. La numeración original se conserva.
El modo de parejas descompone las preguntas compuestas para evitar opciones
con significados duplicados.

## Validación

Ejecuta `node --test tests/*.test.mjs`.
