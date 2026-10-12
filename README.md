# Noé · Test de historia

Web: https://mvisions.github.io/estudionoe/

30 preguntas, tres modos (test, flechas y respuesta escrita), formulario de
alias y curso, cronómetro, nota sobre 10 y revisión de fallos.
Bien suma 1, regular 0,5 y mal 0. La corrección escrita es orientativa por
ideas clave, no IA. Los apuntes mantienen las respuestas aportadas.

## Ranking automático en GitHub

No hay exportación ni subida manual. Al finalizar un examen completo:

1. Se guarda una copia local.
2. Si se aceptó participar en el ranking público, se envían las respuestas a Render.
3. La API calcula la puntuación y añade una línea JSON al archivo `ranking.txt`
   de la rama `ranking-data` de `mvisions/estudionoe`.
4. El script del servidor interpreta el TXT y devuelve los 50 mejores resultados
   por modo: mayor nota, menor tiempo, fecha más antigua en caso de empate.

El tiempo se mide en el navegador e incluye pausas: no es un examen vigilado
ni una clasificación resistente a trampas. Las respuestas no se guardan en GitHub.
El log conserva alias, curso, modo, nota, duración y metadatos del examen.
La prueba de autorización para retirar una entrada se almacena solo como hash
SHA-256 de un valor aleatorio de 256 bits; nunca se registra el token del usuario
ni el token de escritura de GitHub.

Los resultados pendientes se conservan localmente aunque se comience otro examen
y se reintentan al abrir la web, recuperar conexión y cada dos minutos.
Si falla la API se avisa explícitamente y se muestra el ranking local como respaldo.
Los repasos no compiten. Borrar todo retira las entradas asociadas a este navegador
con eventos de borrado y limpia los datos locales. GitHub conserva el historial
de commits, por lo que esa retirada no elimina los datos del historial.
No usar datos personales ni apellidos; menores con permiso de su responsable.

## Configurar Render (paso imprescindible)

Servicio `estudionoe-api`, repositorio `mvisions/estudionoe`, rama `main`,
sin carpeta raíz, plan gratuito, `npm ci`, `npm start`, salud `/api/health`.
Variables:

- `NODE_VERSION=22.22.1`
- `NODE_ENV=production`
- `RANKING_STORAGE=github`
- `GITHUB_REPOSITORY=mvisions/estudionoe`
- `GITHUB_DATA_BRANCH=ranking-data`
- `ALLOWED_ORIGINS=https://mvisions.github.io`
- `GITHUB_TOKEN`: token de acceso **fine-grained** configurado directamente
  por el propietario en Render. Seleccionar solo `estudionoe`, permiso
  **Contents: Read and write** y fecha de caducidad. Nunca incluirlo en el chat,
  Git, frontend ni este documento.

No requiere Google Cloud ni archivos secretos de Firestore. Eliminar del
servicio las variables y el archivo secreto anteriores. El servidor no arranca
sin el token: no se simula un guardado exitoso.

La rama `ranking-data` debe existir con un `ranking.txt` vacío. Los commits
del log no publican Pages ni redespliegan Render: ambos usan solo `main`.
Ante entregas simultáneas se usa el SHA del archivo y se reintentan conflictos.
El log está limitado a 900 KB; el administrador debe archivarlo al llenarse.
El límite de solicitudes de GitHub y el arranque lento de Render gratuito
pueden demorar la sincronización.

## Desarrollo

Web: `python3 -m http.server 8080`.
API sin credenciales para pruebas: `RANKING_STORAGE=memory npm start`.
Pruebas: `npm test`.
GitHub Actions prueba y publica solo archivos estáticos.
