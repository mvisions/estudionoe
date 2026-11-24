# Farmacias de Guardia — MVP

Mapa interactivo de farmacias de guardia en España, con datos oficiales del Consejo General de Colegios Farmacéuticos.

«Toda España» muestra por defecto todas las farmacias conocidas y restablece
la vista nacional del mapa. Las guardias del calendario seleccionado tienen
su distintivo y color; aparecer en el catálogo no implica estar de guardia.
Al elegir una provincia se mantiene el modo de visualización seleccionado:
por defecto aparecen las farmacias conocidas con cruces azules y las guardias con cruces verdes de borde rojo.
Las guardias de noche o de 24 h se pintan con una cruz morada de borde violeta
(ver «Guardias de noche y 24 h»).
La casilla «Mostrar todas las farmacias» permite filtrar solo las guardias.

### Guardias de noche y 24 h

`src/horarios.js` clasifica cada guardia a partir de los horarios publicados:

- **Noche / 24 h (cruz morada):** la guardia cubre por completo la madrugada
  (03:00–06:00) del día de guardia o del siguiente, o su texto indica
  noche, nocturna, madrugada, 24 horas o permanente. Incluye las de 24 h y
  las que abren hasta la mañana siguiente (p. ej. 22:00–09:30).
- **Día (cruz verde de borde rojo):** horarios que terminan antes de la madrugada
  (p. ej. «hasta las 22:00»). Las guardias sin horario publicado también
  usan la cruz verde; nunca se suponen nocturnas.
- Valencia (MICOF), Almería y Cádiz recortan los horarios a medianoche
  («09:00-23:59»); sin hora final original se interpreta que la guardia
  continúa y se pide confirmar por teléfono.

Bajo el resumen de guardias hay tres filtros:

- **Todas:** comportamiento normal.
- **Noche y 24 h:** solo las guardias moradas; oculta las farmacias sin guardia.
- **Abiertas ahora:** solo con la fecha de hoy y según la hora peninsular
  (Europe/Madrid). Incluye las guardias de ayer que siguen abiertas, porque
  muchas provincias publican la madrugada en el calendario del día anterior,
  y las que no publican horas exactas («24 horas», «toda la noche»), marcadas
  «Horario por confirmar». Se reevalúa cada minuto sin cerrar la ficha abierta.

La leyenda bajo el mapa muestra ambos tipos de cruz con su número de guardias
ubicadas.

Los avisos de cobertura (provincias con calendario cargado, consultas
incompletas por provincia, horarios dudosos o errores de carga) se agrupan
en el desplegable **Informe** del panel lateral, plegado por defecto. Su
cabecera resume cuántas provincias tienen calendario y cuántos avisos hay;
al abrirlo se ve un aviso por provincia. Los errores de ubicación del usuario
y de carga del catálogo, que requieren acción, siguen visibles fuera.

La interfaz está solo en español. Las traducciones a euskera, catalán, gallego,
valenciano, portugués y andaluz se harán al final con textos propios; la web no
usa traductores automáticos ni carga scripts, publicidad ni marcas de Google.
El único enlace a Google es «Cómo llegar», que se abre en otra pestaña al pulsarlo.

Todas las farmacias con coordenadas se muestran como cruces individuales
en cualquier zoom, sin agrupación ni círculos numerados. Las guardias
confirmadas se dibujan sobre las farmacias ordinarias.
Los nombres y detalles aparecen al pulsar una cruz. Al llegar al zoom máximo
(18), aparece además una lista automática con la información de todas las
farmacias dentro de la vista actual, según los filtros activos. La lista se
actualiza al mover el mapa y desaparece al alejar el zoom.
Si el informe de cobertura de una provincia falla o tiene un formato incorrecto,
el mapa conserva su calendario de guardias válido y muestra el error en
«Informe», en lugar de ocultar las guardias de esa provincia.
Cada ficha incluye «Cómo llegar», que abre Google Maps en otra pestaña
(o su aplicación en dispositivos compatibles) con las coordenadas de la
farmacia como destino. Si se ha usado «Usar mi ubicación», se incluye ese
origen; en caso contrario Google Maps solicita o utiliza la ubicación del
usuario. No se usa el centro del mapa como origen ni se solicita ubicación
al abrir la ficha.
El selector **Auto / Día / Noche / Satélite** permite oscurecer el mapa como un GPS
o cambiar a vista aérea.
En la vista general (zoom 6 o inferior), el mapa utiliza la cartografía IGN
`IGNBaseTodo` sobre España para que las islas se distingan correctamente;
al acercarse utiliza OpenStreetMap. Se mantiene la atribución de ambas fuentes.
**Satélite** usa la ortofoto PNOA del Instituto Geográfico Nacional con su capa
de rótulos (calles, carreteras y poblaciones) encima, mediante los servicios WMTS
`pnoa-ma` (`OI.OrthoimageCoverage`) e `ign-base` (`IGNBaseOrto`). Son gratuitos y
con licencia CC BY 4.0; la atribución obligatoria «CC BY 4.0 scne.es» aparece al pie
del mapa junto a © OpenStreetMap, que sigue aportando datos de farmacias. Los
rótulos solo se piden dentro de su extensión (lat 27–44, lon −19 a 5: península,
Baleares, Canarias, Ceuta y Melilla), porque fuera de ella el servicio responde 400.
En Satélite no se aplica el filtro nocturno, las cruces usan los colores de día y el
zoom máximo sigue siendo 18, de modo que tamaños, cruces grandes y parpadeo no cambian.
En móvil se oculta visualmente el texto de estado del selector para que no tape el zoom.
Auto calcula la posición solar estimada (ecuaciones NOAA y horizonte
aparente de -0,833°) según el centro visible y la hora real, no la fecha
del calendario de guardias. Se actualiza al mover el mapa, cada 30 segundos
y al volver a la pestaña; no solicita ubicación ni servicios externos.
El filtro nocturno solo afecta al mapa base OSM. Las cruces usan azul
apagado o verde suave con borde rojo para las guardias;
conservan tamaños y orden. Al volver a Día recuperan los colores originales.
El cambio actualiza los puntos existentes sin reconstruir las capas.
Día y Noche permiten anular Auto.
Las ventanas de información y la ayuda de la leyenda usan texto claro
de alto contraste sobre el fondo nocturno.
Solo en modo noche, cada cruz Canvas incorpora un punto blanco central de 2 px de diámetro,
sin borde y sin aumentar el tamaño del marcador. El punto central no
intercepta clics; se mantienen los detalles al pulsar la farmacia.
La leyenda y el resumen indican cuántas guardias confirmadas tienen
ubicación; si no hay guardias para los filtros/fecha, se advierte sin inventarlas.
El tamaño se adapta al zoom: en zoom 6 los puntos normales miden 4 px y las
guardias 4 px. Hasta zoom 9 tienen el mismo tamaño; desde zoom 10 las guardias
son 2 px mayores. Crecen hasta 9/11 px en zoom 14, sin seguir
creciendo en los niveles siguientes, excepto al llegar al zoom máximo:
entonces las cruces azules duplican su tamaño a 18 px. Al alejar un nivel
recuperan 9/11 px; el punto blanco central nocturno sigue midiendo 2 px.
En modo día no se muestra, también cuando Auto cambia a día.
En los últimos cinco niveles de zoom, solo las guardias se representan con una cruz verde de
36 px con contorno rojo (morada con contorno violeta si es de noche / 24 h), tanto de día como de noche.
Las guardias quedan fijas y pequeñas en los niveles anteriores:
en los últimos cinco niveles parpadean cada 1,4 segundos entre opacidad 1 y 0,2, sin desaparecer; no animan con
`prefers-reduced-motion`. Conserva la información al pulsar y vuelve a
cruz verde pequeña al alejarse. La leyenda indica el símbolo activo.
Las cruces grandes tienen una capa propia por encima de las cruces Canvas para
que estos no intercepten el clic que abre los datos de la farmacia.

Las cruces individuales se dibujan en Canvas y se crean solo para el área
visible. Al desplazar el mapa se conservan los puntos y grupos presentes,
sin borrar y reconstruir todos los marcadores; los eventos de zoom y
movimiento se combinan en una actualización por fotograma. Las guardias
tienen una capa superior propia para seguir destacando.

Al combinar el catálogo con las guardias de la fecha elegida, la web descarta
los campos de turno (`guardia_*`, `fecha_guardia`) que el catálogo conserve de
importaciones anteriores: la franja, el horario, «Sin reconfirmar» y «Guardia
iniciada ayer» salen solo del archivo de guardias de esa fecha.

El mapa no bloquea puntos por país ni por límites geográficos de España:
admite coordenadas mundiales válidas, pero rechaza valores ausentes y `(0,0)`.
El catálogo OSM se descarga por regiones, sin filtro de país; puede incluir
farmacias de países vecinos. Para recuperar o actualizar el norte:

```bash
python3 scripts/download_osm.py --region norte
python3 scripts/merge_espana.py
npm run build
```

La descarga conserva las demás regiones y no reemplaza el catálogo si
Overpass falla, devuelve resultados vacíos o indica una consulta incompleta.

El catálogo nacional asigna provincia a los puntos OSM mediante polígonos,
no rectángulos aproximados, y no descarta una zona porque su catálogo oficial
sea parcial. Mantiene también los puntos extranjeros sin provincia española.
Solo une fuentes con identidad inequívoca por teléfono o dirección completa,
no por una distancia de 50 metros. También une un registro oficial con el punto
OSM que el localizador enlazó a 15 m o menos (`osm_id`), salvo que sus teléfonos
difieran. El cron reconstruye este catálogo antes
de compilar el mapa. Son todas las farmacias **conocidas por las fuentes**,
no un censo certificado de todas las existentes.

Límites provinciales: [Click That 'Hood / CartoDB Common Data](https://github.com/codeforgermany/click_that_hood/blob/main/public/data/spain-provinces.geojson),
con códigos provinciales normalizados a `data/provincias.json`.
Archivo local `data/limites-provincias.geojson`; licencia MIT y aviso de
copyright en `data/limites-provincias.LICENSE`.

## Estructura

```
farmacia/
├── data/                    # provincias.json, calendarios
├── public/data/             # JSON estático para el frontend (generado por scrapers)
├── scripts/                 # scrapers y utilidades
│   ├── scrape_province.py   # scraper por provincia → farmacias-{prov}.json
│   ├── scrape_mes.py        # scraper por mes → guardias-{prov}-YYYY-MM-DD.json
│   ├── calendario_pueblo.py # calendario mensual por pueblo
│   ├── daily_update.sh      # actualización diaria (cron)
│   ├── update_all.py        # actualiza todas las provincias
│   └── gen_provincias.py
├── src/                     # React + Vite + Leaflet
└── package.json
```

## Desarrollo

```bash
npm install
npm run dev          # http://localhost:5173
```

## Datos (sin base de datos, solo JSON)

### Prioridad de nuevas fuentes

Se incorporan primero las fuentes públicas oficiales con descargas estructuradas
o calendarios HTML reutilizables. La facilidad de descarga no acredita cobertura
completa: se verifican fechas, identidad, franjas y ubicaciones por separado.

| Prioridad | Fuente comprobada | Formato y situación |
| --- | --- | --- |
| Primera incorporación | [COF Alicante](https://cofalicante.com/farmacias-de-guardia/) | Excel anual público; integrado. |
| Segunda incorporación | [COF Baleares](https://www.cofib.es/es/llistat_guardies.aspx) | HTML diario por 68 municipios, con horarios y coordenadas oficiales en las fichas del mapa; integrado con cobertura parcial. |
| Segunda incorporación | [CGCOF](https://farmaciasguardia.farmaceuticos.com/web_guardias/) Badajoz, La Rioja, Zaragoza, Ceuta y Melilla | HTML por zona/población con el recolector compartido `cgcof_catalog.py`; integrado. |
| Pendiente | [CGCOF Ávila](https://farmaciasguardia.farmaceuticos.com/web_guardias/publico/Provincia_pNew.asp?id=05) | Para el 2-11-2026 responde «Datos no disponibles»; no se infiere que no haya guardias. |
| Incorporación parcial | [COF Soria](https://www.cofsoria.es/ciudadanos/farmacias-de-guardia/) | Listado diario público de capital y provincia (sol = hasta las 22:00; sol y luna = 24 horas) con fichas y mapa oficial; horario exacto solo en la capital (9:00 a 9:00). Los calendarios 2026 en PDF responden HTTP 401 y no se eluden. |
| Incorporación parcial | [COF Zamora](https://cofzamora.es/) | Calendario mensual de Zamora Capital; otras zonas y horarios exactos pendientes. |
| Incorporación provisional | [COF Cáceres](https://farmacias.cofcaceres.es/) | Consulta «Solo abiertas» por municipio; se importan solo las tarjetas «En Servicio de Urgencias», con cobertura parcial y sin calendario fechado. |
| Pendiente | [COF Lugo](https://www.coflugo.org/farmacia-guardia) | Formulario por municipio y fecha con reCAPTCHA; su respuesta aún no se ha validado. |
| Incorporación parcial | [COF A Coruña](https://www.cofc.es/farmacia/index) | Buscador provincial fechado (`scrape_a_coruna.py`) con horario oficial del día, incluida la madrugada de la noche anterior; solo se dibujan las coordenadas del Colegio contrastadas con una farmacia OSM a 15 m o menos. |
| Incorporación parcial | [Govern d'Andorra](https://www.govern.ad/ca/tematiques/salut/assistencia-sanitaria/farmacies-de-guardia) | PDF mensual oficial (`scrape_andorra.py`) con turnos DIA 9:30–22 y NIT 22–9:30, incluida la madrugada del día anterior. La tabla semanal del Pas de la Casa no publica horas y no se importa. Coordenadas solo desde OSM cuando nombre y dirección coinciden de forma única. |
| Incorporación parcial | [COF Pontevedra](https://cofpo.org/inicio/farmacias/farmacias-de-guardia/) | Listados mensuales de Vigo y Pontevedra; horario exacto y otros municipios pendientes. |
| Incorporación parcial | [COF Ourense](https://www.cofourense.es/buscador-de-farmacias-de-guardia/) | Listado provincial fechado, incluye los turnos de la víspera que siguen durante la madrugada; municipios pendientes de confirmar. |
| Incorporada | [COF Asturias](https://www.farmasturias.org/GESCOF/cms/Guardias/FarmaciaBuscar.asp?IdMenu=111) | Consulta fechada de toda la provincia (todos los municipios en una petición) con turnos oficiales y madrugada heredada de la víspera. |
| Incorporación parcial | [Datos abiertos del Gobierno de Navarra](https://datosabiertos.navarra.es/es/dataset/farmacias-de-guardia) | Guardias fechadas de Pamplona, Tudela y Estella-Lizarra, licencia CC BY 4.0; horarios y otros municipios pendientes de interpretar. |
| Incorporación parcial | [COF Segovia](https://cofsegovia.com/farmacias-de-guardia/) | PDF anual de Segovia capital, rotaciones semanales de Cuéllar y El Espinar y calendario rural 2026; cobertura rural parcial. |
| Investigación más profunda | Barcelona | El acceso manual con CAPTCHA sigue pendiente. |

Esta clasificación es inicial, no una afirmación de que las provincias pendientes
estén integradas ni de que sus calendarios cubran todos los pueblos.

### Cobertura de Andorra

La página oficial del [Govern d'Andorra](https://www.govern.ad/ca/tematiques/salut/assistencia-sanitaria/farmacies-de-guardia)
enlaza un PDF mensual con el calendario de guardias: una farmacia por día con
dos turnos, `DIA/ DAY 9’30→22` y `NIT/ NIGHT 22→9’30`. El recolector lee el mes
completo, comprueba el título, los días de la semana y las dos columnas de cada
día, y recorta los intervalos al día solicitado. La madrugada (00:00–9:30) se
toma del turno nocturno de la víspera; el día 1 no se puede acreditar porque el
documento empieza ese día.

La tabla semanal del Pas de la Casa se lee pero no se publica: el PDF no indica
horas para esa rotación. Las coordenadas solo se toman de OpenStreetMap cuando
el nombre y la dirección coinciden de forma única con el PDF; el resto queda en
la lista sin marcador y con `ubicacion_pendiente_verificacion`, que también
impide que `locate_guardias.py` consulte CartoCiudad (solo cubre España).

```bash
python3 scripts/scrape_andorra.py --fecha 2026-11-03
```

### Cobertura de Alicante

El colegio publica un enlace a `guardias2026.xlsx`, con **26.376 filas de
asignaciones**, **664 farmacias** y **92 localidades** observadas en 2026.
El recolector comprueba la hoja, cabeceras, año e identidad de cada farmacia.
Interpreta las franjas impresas, incluidas jornadas partidas, turnos de 24 horas
y la madrugada del día anterior; no importa banderas de apertura actuales como guardias.
El 1 de enero se advierte que falta acreditar la noche del año anterior.

Para 2026-11-01 hay **87 farmacias confirmadas durante alguna franja del día**,
incluido el relevo nocturno anterior; **9 tienen coordenadas verificadas**.
No significa que las 87 estén abiertas simultáneamente ni que sea un censo completo.
El Excel no contiene coordenadas ni teléfonos: las ubicaciones se reutilizan
por identidad inequívoca o dirección exacta; las pendientes no se dibujan.
Las guardias localizadas y los posibles cambios del calendario requieren
confirmación telefónica en la fuente oficial.
El catálogo añade las farmacias observadas en el calendario, no todas las
farmacias existentes en la provincia. El cron descarga de nuevo el Excel cada día.
Una cobertura parcial devuelve salida 1, manteniendo los datos publicados.

```bash
python3 scripts/scrape_alicante.py --fecha 2026-11-01 --geocode --permitir-direccion-exacta
python3 scripts/merge_espana.py
npm run build
```

`--reanudar` reutiliza el Excel anual guardado; `--sin-red` permite reproducirlo
sin consultas externas y no admite geocodificación.

### Cobertura de Baleares

El scraper COFIB consulta los 68 municipios publicados en los selectores de
Mallorca, Menorca e Ibiza/Formentera para la fecha elegida y la víspera. Conserva
los turnos diurnos, nocturnos y de 24 horas, recortando los intervalos a la fecha
mostrada; así incluye la madrugada que empezó el día anterior. El identificador
de farmacia enlaza cada guardia con el mapa oficial COFIB, del que se leen las
coordenadas exactas. Los calendarios siguen marcados como parciales: las consultas
municipales no acreditan todas las derivaciones ni un censo completo. Para
2026-11-01 se confirmaron 61 farmacias y 58 tienen coordenadas verificadas;
tres entradas sin enlace al mapa no pudieron asociarse a una ubicación segura.

```bash
python3 scripts/scrape_baleares.py --fecha 2026-11-01 --cache-documentos ~/.local/state/farmacia/baleares
python3 scripts/merge_espana.py
npm run build
```

`--reanudar` reutiliza las respuestas diarias guardadas; las fichas de coordenadas
oficiales se conservan en caché. `--sin-red` requiere que estén guardadas todas
las consultas y fichas necesarias.

### Cáceres: consulta actual, sin horario de guardia

El buscador publica 197 municipios y permite marcar «Solo abiertas», pero no
incluye fecha. Las tarjetas distinguen las farmacias «Abierta» de las que están
«En Servicio de Urgencias»; solo se incorporan estas últimas para el día actual
como **guardias sin horario**. Los horarios comerciales de la ficha no se copian
como horas de guardia. El mapa oficial de cada farmacia aporta las coordenadas.
La cobertura se marca parcial y cada aviso indica que la fuente no publica un
calendario fechado ni el intervalo horario de la guardia.
El 2026-11-01 se encontraron 20 fichas «En Servicio de Urgencias» en las 197
consultas; las 20 tenían coordenadas oficiales.

El scraper solo acepta la fecha local actual: no se inventan calendarios pasados
ni futuros. Consulta los municipios secuencialmente con una pausa entre peticiones.

```bash
python3 scripts/scrape_caceres.py
python3 scripts/merge_espana.py
npm run build
```

### Segovia: capital, Cuéllar y El Espinar

El COF publica un PDF anual para la capital, con turnos diurnos (10:15–22:00)
y nocturnos (22:00–10:15), además de calendarios semanales para Cuéllar y El
Espinar. Se valida el calendario, la fecha y las etiquetas de cada rotación.
La Junta de Castilla y León aporta el registro oficial de farmacias de Segovia
([licencia CC BY 4.0](https://analisis.datosabiertos.jcyl.es/explore/dataset/registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/)):
se usa para identificar inequívocamente las farmacias y completar sus direcciones
y teléfonos, no para inventar horarios.

Las rotaciones semanales no publican la hora del relevo, por lo que las guardias
se muestran sin intervalo horario y la cobertura queda parcial. Si el número de
la dirección difiere entre el calendario y el registro, se conserva el publicado
por el COF y se anota la discrepancia; en El Espinar, Hontanilla figura como 18
en el calendario y 12 en el registro JCyL.
El calendario rural 2026 aporta turnos de 10:00–22:00 y 10:00–20:00, que se
publican con sus intervalos oficiales y se identifican con el registro JCyL.
Los nombres abreviados solo se expanden cuando el registro identifica una única
farmacia con dirección utilizable; las asignaciones ambiguas permanecen sin
resolver en el informe. La cobertura sigue parcial: el turno rural de 24 horas
de Cantalejo no señala cuál de sus dos farmacias está asignada. No se elige una
por aproximación.
Las guardias de Maello se contrastan con el registro de Ávila y se publican en
su provincia, sin mezclarlas con el calendario de Segovia.
Las coordenadas se reutilizan por identidad oficial o se confirman con la regla
de proximidad de 15 m; las direcciones sin pruebas suficientes no se dibujan.

Se han generado calendarios para Segovia del 1 de noviembre al 31 de diciembre
de 2026 a partir de las fuentes oficiales disponibles; los turnos semanales sin
hora de relevo y las asignaciones no identificables se señalan como cobertura
parcial.

```bash
python3 scripts/scrape_segovia.py --fecha 2026-11-02
python3 scripts/locate_guardias.py --provincia Segovia
python3 scripts/merge_espana.py
npm run build
```

El cron ejecuta el scraper a diario. `--reanudar` reutiliza el PDF e índice
guardados y `--sin-red` permite repetir la extracción desde esa caché.

### Cobertura CGCOF: Badajoz, La Rioja, Zaragoza, Ceuta y Melilla

Usan el mismo recolector que Salamanca y Burgos (`scripts/scrape_<provincia>.py`).
Resultado para 2026-11-01 (guardias confirmadas en alguna franja / con coordenadas):

| Provincia | Rutas | Confirmadas | Ubicadas |
| --- | --- | --- | --- |
| Badajoz | 226 | 71 | 52 |
| La Rioja | 188 | 19 | 4 |
| Zaragoza | 216 | 43 | 1 |
| Ceuta | 2 | 2 | 1 |
| Melilla | 2 | 3 | 2 |

Las fichas de Zaragoza y La Rioja no publican teléfono y el catálogo OSM de
Zaragoza casi no tiene localidad, así que dependen de la geocodificación de
dirección exacta. Si Nominatim responde HTTP 429, el cron deja de geocodificar
en esa ejecución, conserva las coincidencias por identidad y lo reintenta al día siguiente.
Varias zonas responden «Datos no disponibles»: no se interpreta como ausencia de guardias.

Los calendarios diarios se publican como `public/data/guardias-{provincia}-{YYYY-MM-DD}.json`.
El nombre de provincia usa minúsculas, sin tildes y con guiones (por ejemplo,
`Santa Cruz de Tenerife` → `santa-cruz-de-tenerife`).
El mapa consulta los archivos de todas las provincias para combinar la cobertura disponible
y señala cuáles tienen calendario publicado para la fecha elegida. Así se puede ampliar
paulatinamente al incorporar scrapers de nuevas fuentes locales.

Antes de reconstruir el catálogo nacional, `daily_update.sh` procesa las guardias
guardadas que aún no tienen coordenadas. Solo acepta una farmacia OSM contrastada
con una fuente independiente a 15 m o menos, un punto de dirección confirmado por
una farmacia conocida a 15 m o menos, o dos fuentes independientes (OpenStreetMap
y CartoCiudad) que coincidan dentro de 15 m. Las ubicaciones confirmadas se guardan en los catálogos
provinciales y en `public/data/farmacias-coordenadas-verificadas.json`; también
se reutilizan en los calendarios guardados y no se vuelven a consultar. Las
consultas tienen una caché persistente y un límite de 120 peticiones por ejecución
para respetar los servicios públicos; las pendientes continúan en las siguientes
actualizaciones. Sin confirmación suficiente, la farmacia permanece sin marcador.

Para geocodificar las farmacias de Málaga capital incluidas en los calendarios guardados,
ejecuta `python3 scripts/fix_coords.py`. El resultado se guarda en
`public/data/coordenadas-malaga-capital.json` y el scraper mensual lo reutiliza.
Estas coordenadas incluyen estimaciones de calles, no todas son posiciones exactas.

### Cobertura de Málaga

El scraper mensual consulta **zonas y poblaciones por separado** (284 opciones en
la fuente de Málaga), conserva las franjas de día/noche/24 horas y genera un
informe `public/data/cobertura-malaga-YYYY-MM-DD.json`. «Datos no disponibles»
no significa que no exista una farmacia de guardia: se marca como `sin_datos`.
Los errores de consulta no sobrescriben un calendario anterior. Los errores o
la indisponibilidad de todo el día provocan una salida distinta de cero.
El mapa muestra la cobertura parcial.
Las consultas reproducen el formato exacto del formulario público,
`D/M/YYYY` sin ceros iniciales: la fuente devuelve «Datos no disponibles»
para `01/11/2026` pero sí las guardias de noviembre para `1/11/2026`.
Se contrasta también la fecha impresa cuando está presente en la respuesta.

Para actualizar solo un día y completar las ubicaciones provinciales:

```bash
python3 scripts/scrape_mes.py 29 Malaga 10 2026 --dia 31
python3 scripts/complete_malaga.py --geocode
# Para limitar la geocodificación a la fecha consultada:
python3 scripts/complete_malaga.py --geocode --fecha 2026-10-31
```

`complete_malaga.py` construye `public/data/farmacias-malaga.json` a partir de
farmacias **observadas en calendarios**, no de un censo completo. Las coordenadas
se buscan en OpenStreetMap/Nominatim comprobando la localidad, con peticiones
espaciadas. Las coincidencias no exactas se identifican como aproximadas; las
no resueltas permanecen sin coordenadas, nunca se colocan en `(0,0)`.
También se reutiliza el catálogo OSM guardado cuando coinciden inequívocamente
municipio, calle y número; esto permite localizar Coín sin inventar un punto.
Se normalizan `NUM.`/`NÚM.` y las direcciones alternativas de esquinas para Nerja,
y el sufijo compuesto `Torrox - Torrox Costa` no se confunde con parte de la calle.
Torre de Benagalbón se conserva como sector buscable de Rincón de la Victoria.
El mapa incorpora también las farmacias nuevas del calendario aunque no existan
en el catálogo anterior.

Pizarra y San Pedro Alcántara requieren otra fuente oficial cuando el servicio
del Consejo devuelve «Datos no disponibles». El buscador público de ICOFMA
consultado tampoco devolvió un calendario utilizable. No se inventan guardias
ni se reutilizan las de otra fecha.
En la auditoría del 31/10/2026, Algarrobo, Macharaviaya, Totalán y Almogía
también devolvieron `sin_datos`. Benagalbón, Chilches y La Cala del Moral
no tienen selectores independientes en esta fuente; no se confirma su guardia
solo por disponer de información de Rincón de la Victoria o Vélez-Málaga.

Validación:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
node --test src/farmacias.test.js src/mapTheme.test.js src/horarios.test.js
npm run lint
npm run build
```

### Scrapear una provincia
```bash
python3 scripts/scrape_province.py 29 Malaga
```

### Scrapear un mes completo (genera JSON por día)
```bash
python3 scripts/scrape_mes.py 29 Malaga 10 2026
```

### Calendario de un pueblo
```bash
python3 scripts/calendario_pueblo.py 29 29000019 "Alhaurin de la Torre" 10 2026
```

### Scrapear todas las provincias
```bash
python3 scripts/update_all.py
```

## Actualización diaria (cron)
```bash
crontab -e
# Añadir:
0 12 * * * /home/mega/Documentos/farmacia/scripts/daily_update.sh
5 0 * * * /home/mega/Documentos/farmacia/scripts/daily_update.sh --hoy
0 8 * * * /home/mega/Documentos/farmacia/scripts/daily_update.sh --hoy
```

La actualización completa tarda horas, así que no se ejecuta para el día en curso:
a las 12:00 prepara en segundo plano las guardias de **mañana** (`--fecha` del día
siguiente) y las publica antes de medianoche. Al cambiar de día ya están en el mapa.
A las 00:05, `--hoy` consulta las fuentes que solo publican el día actual y
reintenta las provincias sin archivo para hoy. A las 08:00, `--hoy` repite solo
lo que siga faltando; si no falta nada, termina sin compilar. Si otra ejecución
sigue activa, `--hoy` espera hasta una hora y la de las 12:00 hasta cuatro.

Comprobado el 3/11/2026 a las 02:20 pidiendo el 4/11 a cada fuente: publican el
día siguiente todas las demás; solo publican el día en curso Madrid, Barcelona y
Cáceres (sin selector de fecha), Valladolid («los tres cuadros no confirman la
fecha») y León (la página muestra el turno nocturno vigente). Estas cinco van en
`--hoy`. La web se compila en
`dist.next` y sustituye a `dist` con un intercambio atómico (`mv --exchange`): si
la compilación falla, se mantiene la web anterior. Los JSON se escriben con un
archivo temporal y `os.replace`, de modo que nunca se sirven a medias.

La actualización inicia Valencia, Murcia y Baleares en paralelo: consultan
fuentes independientes y conservan sus propios límites de peticiones. El
resto de provincias se procesa en serie. Después, solo en la ejecución de las
12:00, se regenera el registro JCyL de Castilla y León y se intenta ubicar sus
farmacias; a las 00:05 el localizador solo trata guardias para publicar antes.
La geolocalización final, la fusión
nacional y la compilación de `dist/` esperan a que terminen los tres procesos;
si alguno falla, se registra el error sin saltarse las fases finales.
La geolocalización final omite los borradores no integrados de Las Palmas y
Tenerife, pendientes de verificar y de aclarar las condiciones de reutilización.
Las ubicaciones marcadas explícitamente como pendientes de verificación no se
restauran a partir de coordenadas antiguas.

### Valencia

El scraper consulta el [buscador público MICOF](https://www.micof.es/ver/124/).
Recoge las localidades del autocompletado oficial y consulta cada catálogo
y las búsquedas fechadas de las 00:00, 12:00 y 22:00. Valida la fecha/hora
devuelta y las coordenadas oficiales. No necesita permisos de ubicación.

```bash
python3 scripts/scrape_valencia.py --fecha 2026-11-01
```

El buscador mezcla farmacias abiertas habitualmente con servicios de urgencia.
Solo se publican como guardias los horarios marcados explícitamente
«incluye horario de urgencias». Las demás se mantienen en el catálogo azul.
Los resultados cercanos no acreditan una derivación oficial al municipio
consultado. Tres horas de consulta tampoco garantizan todos los turnos del
día; la cobertura es parcial y el proceso devuelve salida 1.
Los resultados y los municipios pendientes se guardan tras cada localidad,
por lo que una interrupción no pierde todo el recorrido. `--sin-red` permite
reproducir las páginas guardadas; `--limite N` limita el recorrido y deja el
resto explícitamente pendiente. El scraper está conectado al cron y al mapa.
`--reanudar` reutiliza las páginas fechadas ya consultadas para continuar un
recorrido interrumpido; el cron no usa esta opción y consulta datos nuevos.

### Valladolid

Fuente: [Colegio de Valladolid](https://ciudadanos.farmaceuticosdevalladolid.es/FarmaciasGuardia.aspx).

```bash
python3 scripts/scrape_valladolid.py --fecha 2026-11-01 --geocode
```

Importa los tres cuadros públicos (capital diurna, capital nocturna y
provincia), comprobando sus tres fechas impresas. El directorio provincial
aporta las farmacias ordinarias y las coordenadas del mapa oficial se cruzan
por dirección y localidad exactas. Los identificadores del directorio y los
de guardias no se confunden: pertenecen a registros distintos.
Se mantienen los avisos de guardia localizada y los horarios oficiales.
Las fichas sin dirección y las posiciones inválidas se notifican, sin
inventar puntos. Las fuentes no acreditan todos los municipios ni la
madrugada anterior, por lo que la cobertura permanece parcial.
La página consultada muestra el día actual; pedir otra fecha que no coincida
con las cabeceras produce un error y conserva el calendario anterior.
`--sin-red` reproduce las páginas guardadas para su fecha.
Está conectado al mapa y al cron; Valencia se consulta en paralelo.

### Santander y Cantabria

Fuente: [COF Cantabria](https://cofcantabria.org/cofguardiasclient/).
El calendario público `data/guardias.json` contiene todas las zonas de la
aplicación. Se consultan las fechas exactas solicitada y anterior; nunca
se sustituye una fecha ausente por la más cercana. Las horas iguales se
consideran 24 horas únicamente con el indicador nocturno oficial.

```bash
python3 scripts/scrape_cantabria.py --fecha 2026-11-01 --geocode
```

Las farmacias repetidas en varias zonas se fusionan conservando todos los
intervalos y las zonas atendidas. Los nombres de zona no se convierten en
derivaciones municipales inventadas. Las posiciones se obtienen del maestro público del COF por nombre y dirección
exactos, del mapa sanitario del Gobierno de Cantabria por teléfono inequívoco,
y de coincidencias de identidad con los catálogos existentes.
No se usan los centros de zona para ubicar farmacias.
Si falla la cartografía sanitaria secundaria, el calendario oficial sigue
publicándose con las posiciones verificadas disponibles y un error de
cobertura; no se sustituyen las coordenadas ausentes por ubicaciones supuestas.

El catálogo recoge las oficinas observadas en los calendarios y mantiene la
base OSM nacional; no acredita todas las oficinas ni el censo de los 102
municipios. Por eso la cobertura permanece parcial y la salida es 1 aunque
se publiquen guardias válidas. `--sin-red` reproduce los archivos guardados.
Los avisos de fuente/ubicaciones pendientes se conservan y un fallo no borra
los datos anteriores. Está conectado al mapa y al cron, después de Valladolid.

### Galicia: Vigo, Pontevedra y Ourense

El listado mensual del COF Pontevedra se consulta para Vigo y Pontevedra
capital. El Colegio distingue turnos diurnos y nocturnos pero en este listado
no especifica sus horas: se muestran sin inventarlas y se recomienda llamar.
La madrugada anterior y los demás municipios permanecen pendientes. Se comprueba
la ubicación mediante teléfono único en OSM y portal de CartoCiudad coincidente
en municipio, calle y número, a una distancia máxima de 15 metros.

El buscador del COF Ourense proporciona intervalos fechados, incluyendo
guardias iniciadas la víspera. Solo se dibujan sus coordenadas oficiales
cuando una farmacia OSM con el mismo teléfono se encuentra a 15 m o menos.
El resto de posiciones y la cobertura completa municipal quedan pendientes.
Ambos recolectores participan en la actualización diaria y devuelven estado
parcial mientras no se verifique toda la provincia.

### Asturias

El buscador del COF Asturias devuelve en una sola consulta («Todos») las
guardias de todos los municipios que las publican para la fecha: unas 100
farmacias en 60 municipios. Se respetan los turnos oficiales (madrugada, día,
noche, 24 horas de 9:30 a 9:30 o de 9:00 a 9:00 y guardias no presenciales,
que se marcan con «llamar antes de acudir»). La madrugada de los turnos
iniciados la víspera se añade consultando también el día anterior, salvo en
los municipios que ya publican su propio turno desde las 00:00 (Oviedo,
Avilés). Las posiciones se contrastan con portales y farmacias a 15 metros
o menos; las que no superan esa comprobación aparecen en la lista sin
marcador.

### Navarra: Pamplona, Tudela y Estella-Lizarra

Fuente: [Gobierno de Navarra, Farmacias de guardia](https://datosabiertos.navarra.es/es/dataset/farmacias-de-guardia),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Los datos se
adaptan al formato de la aplicación y se limitan a registros de Pamplona,
Tudela y Estella-Lizarra fechados en el día consultado. El recurso identifica
sus zonas como de guardias diarias. No se incluyen otras localidades de esas
zonas. El recurso no explica formalmente los campos
`desde` y `hasta` ni el cambio de fecha, por lo que se conservan literalmente:
no se calculan intervalos ni se asegura la madrugada anterior. El resto de
Navarra queda pendiente, incluidos los turnos semanales. Es necesario
confirmar el horario por teléfono; el mapa muestra la atribución y licencia.

### Salamanca

El Colegio de Salamanca enlaza el [calendario público CGCOF](https://farmaciasguardia.farmaceuticos.com/web_guardias/publico/Provincia_pNew.asp?id=37).
Se consultan todas las rutas de zona y población, con la fecha española sin
ceros iniciales y comprobación de la fecha impresa. Se conservan los turnos
nocturnos y de día completo del día anterior como madrugada, con aviso de
confirmar la hora de cierre. No se importan horarios predeterminados de otra
provincia ni se atribuye una derivación municipal por el nombre de la zona.

```bash
python3 scripts/scrape_salamanca.py --fecha 2026-11-01 --geocode --permitir-direccion-exacta
```

Las fichas oficiales se cruzan por dirección y localidad para añadir nombres
y teléfonos; los números inválidos se notifican, no se corrigen por conjetura.
Solo se aceptan ubicaciones inequívocas; los edificios autorizados llevan
aviso de verificación pendiente. `--reanudar` reutiliza páginas ya guardadas,
`--sin-red` reproduce la caché y `--limite N` deja el resto de rutas pendientes.
Se guarda cada avance y se preservan calendarios ante fallos. El catálogo
incluye las farmacias observadas y la base OSM, no un directorio completo.
La cobertura y los horarios siguen siendo parciales y la salida es 1.
El colector está conectado al mapa y al cron.

### Burgos

El [calendario público CGCOF de Burgos](https://farmaciasguardia.farmaceuticos.com/web_guardias/publico/Provincia_pNew.asp?id=09)
publica rutas de zona y población. Comparte el colector `cgcof_catalog.py`
con Salamanca, conservando separados los códigos provinciales, cachés,
catálogos y calendarios.

```bash
python3 scripts/scrape_burgos.py --fecha 2026-11-01 --geocode --permitir-direccion-exacta
```

Consulta el día solicitado y la madrugada del anterior. Los horarios no
completamente interpretados se anuncian como pendientes: no se aplican las
horas predeterminadas de Málaga. Las rutas aún no consultadas, los errores y
las ubicaciones pendientes permanecen visibles en el informe de cobertura.
Las fichas se validan por dirección y localidad antes de reutilizar contactos.
No se inventan derivaciones ni centros de población. `--reanudar`, `--sin-red`
y `--limite N` funcionan como en Salamanca. El catálogo conserva la base OSM y
las farmacias observadas; no se afirma un directorio provincial completo.
Está conectado al mapa y al cron, después de Salamanca.

### Palencia

El [Colegio Oficial de Farmacéuticos de Palencia](https://www.cofpalencia.org/)
enlaza los [carteles oficiales de capital y provincia](https://www.cofpalencia.org/PUBLICO/CALENDARIOS%20DE%20GUARDIA/menu_calendarios_guardia.htm).
El colector recorre los PDF enlazados y publica los turnos verificables de
capital, Carrión de los Condes y Saldaña, incluyendo la madrugada anterior.
Lee las celdas por coordenadas de palabras para no mezclar columnas del PDF.
El directorio oficial aporta 39 farmacias capitalinas observadas, sin convertir
sus horarios ordinarios en guardias.

```bash
python3 scripts/scrape_palencia.py --fecha 2026-11-01 --geocode --permitir-direccion-exacta
```

`--cache-documentos`, `--reanudar` y `--sin-red` permiten caché y reproducción.
`--sin-red` no admite geocodificación. Requiere las herramientas Poppler
`pdftotext` y `pdfinfo`, ya utilizadas por otros colectores.

Los carteles capitalinos sin año impreso se contrastan con el año de creación
del PDF y el día de semana. Sus horas diurnas quedan pendientes cuando el
encabezado solo especifica lunes a viernes. Los intervalos nocturnos y semanales
explícitos se conservan por separado. La derivación oficial a Sahagún conserva
su provincia real, León, pero aparece al filtrar guardias que atienden Palencia.
Los colores de Aguilar de Campoo, Guardo y la zona de Cervera de Pisuerga se leen mediante `pdftoppm`:
se verifica el mes entero, los bordes de cada fila y una correspondencia única
con la leyenda. Se admite la variación de tonos observada entre cuadrícula y
leyenda (máximo 40 unidades por canal RGB); un color ausente o ambiguo se
rechaza, sin asignar la farmacia más próxima. Un color compartido conserva
todas sus farmacias, incluida Barruelo de Santullán. Las guardias de 24 horas
sin hora explícita de relevo se publican con aviso, sin inventar intervalos.
El cartel de Cervera distingue sus dos farmacias y las de Salinas de Pisuerga,
San Salvador de Cantamuda y Castrejón de la Peña por sus localidades impresas,
no por el nombre de la zona. Las farmacias de todas las leyendas interpretadas
se incorporan también al catálogo ordinario, sin marcar como guardia las que
no correspondan a la fecha consultada. Las coordenadas siguen requiriendo
identidad o dirección exacta; nunca se usan centros de pueblo ni carreteras sin número.
Las asignaciones de otros calendarios por colores y las columnas especiales restantes
siguen pendientes, con avisos explícitos: nunca significan ausencia de guardia.
En Venta de Baños y Villada se interpretan también las columnas de sábados
y domingos: Venta conserva 09:30–20:00, 20:00–22:00 y 22:00–09:30; Villada
mantiene el aviso de relevo desconocido por la contradicción del encabezado
«24 horas / 22:00 a 10:00». Sus festivos y subturnos entre semana siguen pendientes.
La cobertura es parcial y el colector termina con código 1 mientras persistan
estos límites. Está conectado al mapa y al cron, después de Burgos.

### León y su provincia

Fuente: [COF León, calendario de farmacias de guardia](https://www.cofleon.es/index.php/farmacias-de-guardia/).
El importador contrasta las localidades y los registros con el
[registro oficial de establecimientos farmacéuticos de Castilla y León](https://analisis.datosabiertos.jcyl.es/explore/dataset/registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/).

```bash
python3 scripts/scrape_leon.py --fecha 2026-11-02
```

La página publica la madrugada anterior, la guardia diurna y la nocturna.
Solo las nocturnas con fecha y horas impresas se convierten en intervalos;
la diurna queda pendiente de confirmar por teléfono. No se inventan
derivaciones a otros municipios. Las posiciones permanecen sin marcador
hasta que el localizador independiente las verifica a 15 metros o menos.
El informe declara cobertura parcial mientras no se acrediten todas las
derivaciones y el horario diurno. El colector está conectado al mapa y al cron.

El calendario incluye farmacias de zonas limítrofes registradas en otras
provincias (Carrión de los Condes, Palencia; La Unión de Campos, Valladolid).
Se omiten solo si el registro oficial las identifica de forma única: por
teléfono o, si el registro no tiene teléfono, por localidad, titular y número
de la calle. Cualquier otra localidad desconocida detiene la importación.

### Zamora: solo capital

El [COF Zamora](https://cofzamora.es/) publica un calendario mensual por zona.
El importador comprueba la zona, el mes y el año seleccionados y concilia cada
turno con el registro oficial de establecimientos de Castilla y León. Para el
2 de noviembre de 2026 confirma dos turnos en Zamora Capital, uno diurno y otro
nocturno. La fuente no publica horas exactas: se indica confirmar por teléfono,
sin inventar intervalos. Solo una ubicación está contrastada a 5,5 m; la otra
permanece sin marcador. La provincia tiene 15 zonas seleccionables y las otras
14 no se han confirmado, por lo que la cobertura es parcial.

```bash
python3 scripts/scrape_zamora.py --fecha 2026-11-02
python3 scripts/locate_guardias.py --provincia Zamora
```

El importador está conectado al cron y el mapa muestra el aviso de cobertura
incompleta. Para la misma fecha, el CGCOF de Ávila respondió «Datos no
disponibles» y el calendario rural 2026 de Segovia no asignó una guardia a
Maello; esto no acredita la cobertura del resto de Ávila.

### Soria: listado diario del COF

La página pública de [farmacias de guardia del COF Soria](https://www.cofsoria.es/ciudadanos/farmacias-de-guardia/)
se consulta por día, mes y año. El importador comprueba que la fecha
seleccionada coincide con la pedida y lee dos bloques: Soria Capital y
Provincia de Soria. Cada farmacia lleva iconos: sol y luna significan 24 horas;
solo sol, hasta las 22:00. La capital publica el horario exacto, de 9:00 del
día indicado a 9:00 del siguiente; por eso también se consulta el día anterior
y su guardia aparece como madrugada (00:00–09:00). En la provincia no se publica
la hora de inicio: esas guardias se muestran como «Horario por confirmar».

Cada ficha aporta titular y teléfono, y se concilia con el registro oficial de
Castilla y León. Para aceptarla deben coincidir al menos dos datos (dirección,
teléfono o titular) con una sola farmacia del municipio; si no, la importación
falla en lugar de adivinar. La página advierte de que las guardias pueden ser
localizadas (Orden de 2/3/1998): si la farmacia está cerrada, hay que llamar al
teléfono de la fachada. El aviso se muestra en cada guardia.

El punto del mapa oficial del COF no se dibuja directamente. Se pasa al
localizador como `referencia_ubicacion` y solo cuenta si OpenStreetMap o
CartoCiudad coinciden con él a 15 metros o menos. Si discrepan, la farmacia
queda sin marcador. El informe es parcial porque la provincia no publica la hora
de inicio.

```bash
python3 scripts/scrape_soria.py --fecha 2026-11-02
python3 scripts/locate_guardias.py --provincia soria
```

Los calendarios 2026 en PDF de la web del COF responden HTTP 401 y no se
intenta eludir el acceso.

Estado regional para el 2 de noviembre de 2026 (guardias confirmadas / con
coordenadas):

| Provincia | Confirmadas | Ubicadas | Alcance |
| --- | ---: | ---: | --- |
| Ávila | — | — | Sin calendario verificable; CGCOF sin datos y Maello no aparece asignado en el calendario rural consultado. |
| Burgos | 35 | 11 | Parcial. |
| León | 37 | 5 | Parcial; horario diurno y derivaciones pendientes. |
| Palencia | 13 | 3 | Parcial. |
| Salamanca | 40 | 12 | Parcial. |
| Segovia | 9 | 2 | Parcial; calendarios locales con límites documentados. |
| Soria | 9 | 4 | Capital y provincia; 8 guardias del día y la madrugada de la capital. Horario exacto solo en la capital. |
| Valladolid | 17 | 16 | Parcial. |
| Zamora | 2 | 1 | Solo Zamora Capital; sin horas exactas. |

### Castilla y León: registro oficial como catálogo base

Para elegir la fuente con más farmacias se compararon, el 2 de noviembre de 2026, el
[registro oficial de establecimientos farmacéuticos de Castilla y León](https://analisis.datosabiertos.jcyl.es/explore/dataset/registro-de-establecimientos-farmaceuticos-de-castilla-y-leon/)
(CC BY 4.0) y OpenStreetMap:

| Provincia | Registro JCyL | OSM |
| --- | ---: | ---: |
| Ávila | 126 | 66 |
| Burgos | 196 | 214 |
| León | 320 | 203 |
| Palencia | 95 | 47 |
| Salamanca | 250 | 192 |
| Segovia | 99 | 59 |
| Soria | 61 | 46 |
| Valladolid | 282 | 51 |
| Zamora | 159 | 114 |
| **Total** | **1.588** | **992** |

El registro es el catálogo base de la región y se fusiona justo después de OSM;
los catálogos provinciales posteriores lo sustituyen cuando comparten id, `osm_id`
o una identidad única. Los puntos OSM sin correspondencia se conservan; en Burgos,
OSM tiene más puntos que el registro. El registro no publica coordenadas: cada
farmacia hereda el punto OSM solo si el teléfono o la dirección completa coinciden.
Si no, aparece en la lista («Mostrar todas»), pero sin marcador hasta que el
localizador la contrasta a 15 m o menos. Los artículos que el registro escribe al
final entre paréntesis se pasan al principio: «CALLE TABLADA (LA)» se escribe
«Calle la Tablada».

```bash
python3 scripts/registro_jcyl.py
python3 scripts/locate_guardias.py --catalogo farmacias-registro-jcyl.json --provincia soria
python3 scripts/merge_espana.py
```

El cron de las 12:00 sitúa primero las guardias y dedica el resto de las 120 consultas diarias
a las farmacias del registro. El acierto es bajo: en Soria, 7 de 46 direcciones,
porque Nominatim y CartoCiudad no tienen el número exacto de portal, sobre todo
en los pueblos. Las demás se quedan sin marcador; no se usan centros de pueblo ni
portales cercanos. Si el registro llega con menos del 90 % de las farmacias o le
falta alguna provincia, se conserva el catálogo anterior.

### Murcia y sus pueblos

El [buscador enlazado por el COFRM](https://web.cofrm.com/buscador-de-farmacias/)
redirige al [calendario oficial](https://guardias.cofrm.com/). Su API pública
aporta el catálogo y los 45 municipios: en la captura inicial se observaron
582 farmacias y 159 etiquetas de localidad, incluidas pedanías.
Para el 1 de noviembre de 2026 se recorrieron los 582 calendarios sin errores
de consulta: 55 guardias confirmadas y ubicadas, en 37 municipios y 44
localidades. El catálogo tiene 581 coordenadas oficiales válidas; una ubicación
permanece pendiente. Los ocho municipios sin turno propio confirmado no se
consideran desatendidos: sus posibles derivaciones siguen pendientes.

```bash
python3 scripts/scrape_murcia.py --fecha 2026-11-01
```

El colector consulta el calendario de cada farmacia. Solo eventos explícitos
`On-Call - TITULAR` (incluida la extensión ` (Weekend)`) con intervalo
coincidente con la fecha se publican como guardias; no convierte aperturas,
festivos `CLOSED` ni banderas sin fecha en guardias. Conserva la madrugada
anterior, las horas exactas y los intervalos independientes. El titular debe
coincidir con la ficha y los calendarios sin eventos del año consultado se
señalan como pendientes, no como ausencia de guardia.

Las coordenadas oficiales se transforman de WGS84 UTM 30 norte, como hace
el mapa COFRM. Se rechazan valores inválidos y posiciones fuera de Murcia;
no se desplazan farmacias coincidentes ni se usan centros de población.
No se importan los correos personales del directorio.
`--limite N`, `--reanudar`, `--sin-red` y `--cache-documentos` permiten consultas
acotadas y reproducción. Se guarda el progreso tras cada farmacia.
La cobertura permanece parcial mientras no estén verificadas todas las
derivaciones y pedanías; el código de salida 1 expresa esa limitación.
El mapa y la actualización diaria están conectados al colector.

### Granada y Cádiz

```bash
python3 scripts/scrape_granada.py --fecha 2026-11-01 --geocode
python3 scripts/scrape_cadiz.py --fecha 2026-11-01
```

Granada consulta las 197 localidades del formulario oficial con una sesión
HTTP normal. Importa fichas con coordenadas oficiales, columnas de los
carteles de la capital y tablas semanales, incluyendo las derivaciones a
otros municipios. Los teléfonos adicionales se conservan por separado.
No convierte coordenadas oficiales `(0,0)` en marcadores. Para los PDF sin
coordenadas cruza direcciones OSM; `--geocode` solo acepta un POI de farmacia
con calle, número y localidad coincidentes, nunca un centro de municipio.
Los documentos anuales con excepciones no completamente interpretadas,
calendarios gráficos, escaneados o con otra fecha producen avisos de
cobertura parcial, no un resultado vacío aparentemente correcto. Los carteles
escaneados transcritos y contrastados manualmente se reconocen exclusivamente
por la huella SHA-256 del PDF oficial: si cambia el documento, queda pendiente
de una nueva interpretación. Las guardias localizadas incluyen su intervalo
fechado y deben confirmarse por teléfono. En los carteles semanales de atención
localizada que indican cambios los lunes a las 9:30 se conserva también la
guardia de la madrugada del día de cambio, sin suponer quién cubre el relevo.
Para la capital se reconocen los carteles diurnos y nocturnos fechados; la
madrugada anterior queda pendiente. El cartel mensual de Loja identifica la
farmacia diurna y las nocturnas anterior y actual, pero deja sus horas por
confirmar cuando depende de festivos. Las ubicaciones de estos dos carteles
solo se muestran con contraste de farmacia y portal a 15 metros o menos.

Cádiz consulta todas las páginas de la API oficial para el día entero,
no solo la hora de ejecución del cron. Conserva los intervalos que empiezan
la noche anterior, recortados a la fecha solicitada, y las coordenadas del
Colegio. El informe completo confirma la respuesta de la API provincial,
no un censo independiente de todas las farmacias del territorio.

Ambos publican `guardias-PROVINCIA-YYYY-MM-DD.json`,
`farmacias-PROVINCIA.json` y `cobertura-PROVINCIA-YYYY-MM-DD.json`.
Están conectados al mapa y al cron existente, en el orden Granada → Cádiz;
un fallo no impide ejecutar las provincias siguientes ni compilar el mapa.
Granada conserva los calendarios ya publicados si la nueva consulta es
parcial, añadiendo únicamente farmacias nuevas de carteles de la capital y
Loja, carteles escaneados verificados o bloques semanales localizados
interpretados con fecha y hora de cambio,
sin reemplazar una guardia anterior ni restringir su horario desconocido;
Cádiz los conserva si la API falla o devuelve cero guardias.
Huelva y Córdoba están integradas con informes de cobertura parcial.

### Castilla-La Mancha: sus cinco provincias

Fuente pública: [COFCAM](https://farmaciasdeguardia.cofcam.es/),
enlazada por el Colegio de Toledo. El colector compartido consulta
`api.php?action=list&fecha=YYYY-MM-DD&provincia=PROVINCIA` sin filtro por
hora ni cercanía, y valida la fecha, provincia y total de registros.
Los intervalos oficiales se recortan al día solicitado, conservando
la madrugada y todos los turnos de una misma farmacia. Las guardias
localizadas llevan aviso de llamar antes de acudir.

```bash
python3 scripts/scrape_toledo.py --fecha 2026-11-01
python3 scripts/scrape_guadalajara.py --fecha 2026-11-01
python3 scripts/scrape_albacete.py --fecha 2026-11-01
python3 scripts/scrape_ciudad_real.py --fecha 2026-11-01
python3 scripts/scrape_cuenca.py --fecha 2026-11-01
```

Las cinco están conectadas al mapa y a la actualización diaria. Se conservan
las coordenadas oficiales; los centros genéricos no generan puntos.
El catálogo azul mantiene las farmacias OSM y las observadas en guardias;
la respuesta provincial no acredita un censo municipal completo ni
derivaciones a otros pueblos, por lo que la cobertura se declara parcial
y el comando devuelve salida 1. Un fallo conserva los datos anteriores.
`--sin-red` reproduce la caché fechada; `--geocode --permitir-direccion-exacta`
admite únicamente coincidencias inequívocas,
con aviso si son edificios y no puntos de farmacia.

### Barcelona: catálogo oficial y guardias protegidas

Fuente: [cercador COFB](https://www.cofb.org/ca/qui-som/el-collegi/cercador-de-farmacies/).
Su selector contiene los **311 municipios**. Se descargan los seis PDF
regionales mediante el formulario público, comprobando todos sus totales.
Las localidades submunicipales se vinculan únicamente cuando una consulta
municipal oficial confirma el mismo identificador y dirección.
La captura del 01/11/2026 contiene **2.403 farmacias**, 1.024 de la capital;
1.479 tienen coordenadas inequívocas reutilizadas del catálogo, sin centros
urbanos inventados. Los otros registros permanecen sin marcador.

```bash
python3 scripts/scrape_barcelona.py --fecha 2026-11-01 --cache-documentos data/barcelona-cache
python3 scripts/scrape_barcelona.py --fecha 2026-11-01 --sin-red --cache-documentos data/barcelona-cache
```

[El COFB enlaza Farmaguia](https://www.cofb.org/ca/que-oferim/ciutadans/farmacies-obertes/)
para consultar las guardias. Su
[formulario oficial](https://mobi.farmaguia.net/advanced_search) exige
**reCAPTCHA** antes de buscar. El colector comprueba esa protección leyendo
solo las páginas y el cliente públicos; no intenta resolverla ni acceder
a la API protegida. La intervención manual por la interfaz no autoriza
automatizarla en el cron.

Publica `farmacias-barcelona.json` y `cobertura-barcelona-YYYY-MM-DD.json`,
integrados en el mapa y el cron. **No hay guardias fechadas confirmadas ni
cobertura municipal completa**: los 311 municipios están censados, no
consultados para guardias, y 240 tienen registros propios en estos PDF.
Los horarios habituales, incluso 24 horas, no se convierten en guardias.
Se conservan calendarios previos con aviso de no reconfirmación; la salida
1 señala el bloqueo sin impedir las provincias siguientes ni el build.
La caché diaria reside en `$state_dir/barcelona`; no se lanza geocodificación
masiva por defecto. La opción manual `--geocode --permitir-direccion-exacta`
solo admite farmacias o edificios con calle, número y municipio exactos,
manteniendo el aviso de ubicación pendiente de verificar.

### Girona

La [tabla oficial del Colegio de Girona](https://www.cofgi.org/farmacies/farmacies-de-guardia)
permite consultar por fecha las farmacias y sus franjas. Se indica cuándo la
guardia no es presencial y requiere llamar. La cobertura se señala como
parcial: la tabla no acredita que estén cubiertos todos los municipios.

```bash
python3 scripts/scrape_girona.py --fecha 2026-11-02
```

El cron consulta la fecha actual. Los puntos del Colegio solo se muestran
cuando coinciden con una farmacia OSM identificada por teléfono o dirección
a 15 metros o menos; los demás permanecen sin marcador. La salida 1 indica
cobertura parcial o error; si falla la lectura no se reemplaza el calendario.

### Jaén

Fuente: [Colegio de Jaén](https://www.farmaceuticosdejaen.es/Paginas/Farmacias_Guardia.asp).

```bash
python3 scripts/scrape_jaen.py --fecha 2026-11-01 --geocode
# Reproducir sin consultar la web (solo caché de la misma fecha):
python3 scripts/scrape_jaen.py --fecha 2026-11-01 --sin-red
```

El cron consulta diariamente todas las opciones del formulario, selecciona
los carteles del mes y año solicitados (o los anuales vigentes) y vuelve a
descargar los PDF. Solo reutiliza la conversión cuando el contenido SHA-256
no ha cambiado. La caché reside en `~/.local/state/farmacia/jaen`;
`--cache-documentos` permite especificar otra ubicación.

Contrasta las identidades con todas las páginas del directorio oficial.
Interpreta columnas diurnas/nocturnas de la capital, listas fechadas,
tablas semanales con cambios de mes y calendarios mensuales con texto.
Conserva municipios atendidos, varias franjas, teléfonos y enlaces oficiales.
Las discrepancias de dirección se muestran en el mapa. Solo sitúa
farmacias mediante teléfono/dirección OSM inequívocos o POI de farmacia
con calle, número y localidad exactos; nunca coordenadas del centro urbano.

Publica catálogo, calendario e informe de cobertura y está conectado al
mapa y al cron después de Cádiz. **La cobertura es parcial**: carteles
por colores, formatos pendientes, farmacias ambiguas y poblaciones sin
documentos vigentes aparecen como consultas no confirmadas. No significan
ausencia de guardias. Una actualización parcial incorpora las consultas
confirmadas y conserva las antiguas para las no reconfirmadas; el informe
advierte de ello. Un fallo global conserva el calendario y produce salida
de error, sin impedir ejecutar el resto del cron.

### Almería

Fuente: [buscador oficial del Colegio de Almería](https://www.cofalmeria.com/buscador-de-farmacias/?activo_guardias=on).

```bash
python3 scripts/scrape_almeria.py --fecha 2026-11-01 --geocode
python3 -m unittest discover -s scripts -p 'test_scrape_almeria.py'
```

Consulta el formulario público con una sesión normal y su configuración
renovada en cada ejecución. Solicita guardias para la fecha completa, sin
filtro de municipio, y el día anterior para incorporar la madrugada.
Comprueba las fechas de los intervalos y el total de la paginación;
una respuesta truncada, fallida o sin guardias conserva el calendario anterior.
Nunca sustituye una fecha vacía por las guardias de hoy.

Une farmacias e intervalos repetidos y recorta los horarios válidos al día
solicitado. Los intervalos oficiales con fin anterior o igual al inicio
no se convierten en guardias de 24 horas: conserva la farmacia publicada
para ese día, señala el horario inválido y solicita confirmación telefónica.
En esos casos el informe de cobertura es parcial y el proceso termina con
salida de error. Tampoco supone que un intervalo inválido del día anterior
continúe de madrugada.
Si esa farmacia ya figuraba en el calendario de la misma fecha, conserva
la entrada anterior como no reconfirmada y lo indica expresamente.

Publica catálogo, calendario e informe de cobertura, conectados al mapa
y al cron después de Jaén. Solo utiliza coincidencias inequívocas de
teléfono/dirección con OSM, o un POI de farmacia con calle, número y localidad
exactos. Las ubicaciones pendientes no generan marcadores ni coordenadas
del centro urbano. La cobertura del buscador no certifica por sí sola un
censo municipal completo.

### Huelva y Córdoba

Fuentes: [COFH](https://cofhuelva.org/cuadro-de-guardias) y
[COFCO](https://www.cofco.org/aplicaciones/guardias/farmacias2026.php).

```bash
python3 scripts/scrape_huelva.py --fecha 2026-11-01 --geocode
python3 scripts/scrape_cordoba.py --fecha 2026-11-01 --geocode
# Reproducir la caché de la misma fecha, sin consultas externas:
python3 scripts/scrape_huelva.py --fecha 2026-11-01 --sin-red
python3 scripts/scrape_cordoba.py --fecha 2026-11-01 --sin-red
```

Huelva recorre todas las opciones municipales del selector oficial y
selecciona exclusivamente los PDF del mes y año solicitados. Descarga los
documentos cada día y reutiliza la conversión solo si su SHA-256 no cambia.
Interpreta las casillas con texto, comprueba el día de la semana y conserva
las localidades atendidas cuando la guardia corresponde a otro municipio.
La capital incorpora el cuadro diurno según día laborable/sábado/domingo
o festivo explícito y las farmacias publicadas como 24 horas. **Ese cuadro
no certifica otros servicios nocturnos**; se informa de cobertura parcial.
No supone horarios de 24 horas para el resto de calendarios municipales.
Consulta también todos los municipios del localizador oficial y utiliza
sus coordenadas cuando la calle, número y municipio coinciden sin ambigüedad
con el cartel. El directorio se conserva en la caché para `--sin-red`.
El cuadro de Lepe conserva Lepe como municipio y respeta sus excepciones
fechadas: una farmacia indicada para otro domingo no se marca hoy.
Las direcciones discrepantes entre cartel y localizador quedan pendientes:
no se equiparan números diferentes de una misma calle.
El localizador normaliza sus abreviaturas oficiales `CL/PL/C/PS`, los
`s/n` explícitos y los centros comerciales identificados por nombre,
sin relajar la comparación de números. El 1/11/2026 se confirmaron
44 guardias de Huelva, 41 con ubicación; las tres discrepancias reales
de numeración quedaron pendientes.

Córdoba consulta el formulario público del año solicitado con fecha y
municipio explícitos, contrastados con la respuesta. Las peticiones son
secuenciales y espaciadas para respetar el servidor. Conserva las franjas
diurnas/nocturnas del colegio y une farmacias repetidas por su identificador
oficial. No inventa un nombre o municipio ausentes en el resultado. El
colegio advierte que no garantiza consultas con más de 30 días de antelación.

Ambos publican catálogo, calendario e informe de cobertura, están conectados
al mapa y al cron después de Almería, y mantienen las farmacias OSM conocidas
en azul. Solo sitúan guardias con coincidencias inequívocas por teléfono o
dirección completa, o un POI de farmacia con calle, número y localidad
exactos. Las ubicaciones pendientes no se dibujan en el centro del pueblo.
En Córdoba, `--permitir-direccion-exacta` (activado en el cron por decisión
del usuario) admite también edificios con calle, número y municipio
exactos, etiquetados «Ubicación por dirección; pendiente de verificar».
Nunca admite una calle sin número ni un municipio como ubicación.
Los sectores «Zona Centro», «Zona Sector Sur», etc. de la capital se
conservan como sector y se geocodifican bajo el municipio Córdoba.
Un fallo no borra calendarios anteriores; las actualizaciones parciales
conservan guardias de consultas no reconfirmadas y lo indican expresamente.
La caché está en `~/.local/state/farmacia/huelva` y `cordoba`;
`--cache-documentos` permite cambiarla. `--sin-red` no admite `--geocode`.

### Comunidad de Madrid: catálogo provincial y guardias fechadas COFM

Fuente: [buscador público del COFM](https://www.cofm.es/es/buscador-de-farmacias/).
`scrape_madrid.py` obtiene en cada ejecución la aplicación pública actual y
comprueba sus recursos `/rest/poblaciones/` y `/rest/farmacias/es?direccion=`.
No requiere credenciales, claves de Google, tokens guardados ni resolver
CAPTCHA. Usa un agente identificable y peticiones secuenciales espaciadas;
ante bloqueo o cambio del esquema informa del fallo y conserva lo publicado.

```bash
python3 scripts/scrape_madrid.py --fecha 2026-11-01 --cache-documentos data/madrid-cache
# Reproducir únicamente una captura obtenida ese mismo día:
python3 scripts/scrape_madrid.py --fecha 2026-11-01 --sin-red --cache-documentos data/madrid-cache
python3 scripts/merge_espana.py
npm run build
```

La API devuelve el **catálogo entero**, no una búsqueda por radio: no se
necesitan 179 descargas idénticas ni coordenadas de centros municipales.
El censo de cobertura evalúa todos sus municipios sobre esa respuesta
provincial. Las 180 opciones del selector corresponden a 179 municipios:
`LAS ROZAS` y `ROZAS DE MADRID, LAS` son dos nombres del mismo municipio.
Se normalizan también acentos y la variante oficial `San Agustín de Guadalix`.
Un municipio nuevo, desconocido o un censo distinto exige revisar el esquema.

El 1/11/2026 se obtuvieron 2.957 registros del catálogo oficial y **169
guardias, todas con coordenadas oficiales**: 71 en la capital y 98 en otros
municipios. Hay intervalos confirmados en 59 de los 179 municipios.
Los otros 120 se señalan `sin_datos`: esta API no publica derivaciones
comarcales y no se supone ausencia de servicio. **Cobertura parcial**, no
censo certificado de todas las guardias ni de todas las farmacias existentes.
El catálogo incorpora además farmacias previamente conocidas y OSM en azul.
En esa captura, 19 municipios no tienen registros en el catálogo COFM
(no certifica que carezcan de farmacia); los otros 101 sí tienen registros,
pero ninguno publica `horarioGuardia`. Ningún hueco se debe a un intervalo
descartado por fecha ni a un fallo de la descarga provincial.
El informe distingue estos motivos de indisponibilidad explícitamente.
Ejemplos: La Acebeda no tiene registros; Ajalvir tiene uno (1064) sin
horario de guardia y Chinchón dos (542 y 2844), también sin ese campo.
La aplicación oficial descarga la misma lista completa una sola vez.
La selección municipal filtra esa lista en el navegador; la búsqueda por
dirección puede ampliar a códigos postales numéricamente adyacentes y
ordenar por distancia, pero **eso no es una derivación oficial** y no añade
farmacias externas a la respuesta. La antigua URL de guardias redirige a
este mismo buscador. No se crean asociaciones de servicio por proximidad.

Solo `horarioGuardia`, con fechas explícitas, confirma una guardia:
`guardia`, `abierta`, `servicio24h` y el horario habitual no se convierten
por sí solos en guardias. Se conservan descripción e intervalos originales,
incluida la madrugada del día anterior (74 farmacias en esta captura), y se
recortan los intervalos al día solicitado. La API publica **hoy**, no admite
una fecha histórica/futura; `--sin-red` exige una captura de ese día.
Los calendarios parciales o fallidos conservan las guardias anteriores no
reconfirmadas con aviso, sin trasladarlas a otro día.

Publica `farmacias-madrid.json`, `guardias-madrid-YYYY-MM-DD.json` y
`cobertura-madrid-YYYY-MM-DD.json`, integrados en el mapa y el cron existente
de las 02:00, después de Córdoba y antes de la fusión y compilación.
El cron guarda la captura en `$state_dir/madrid`; el comando manual usa
`data/madrid-cache`. `--geocode --permitir-direccion-exacta` admite, solo si
faltan coordenadas oficiales, un POI OSM exacto o un edificio con calle,
número y municipio exactos, etiquetado `precision_ubicacion='direccion'`
y con aviso de verificación pendiente. Esa etiqueta y su nota se conservan
al reutilizar el catálogo y fusionar fuentes. Nunca se usa una calle sin
número ni el centro de una población. El diseño de puntos Canvas, los
modos Auto/Día/Noche y las cruces verdes de zoom máximo no se modifican.

### Sevilla: listado oficial del iframe

Fuente: [localizador del Colegio de Sevilla](https://www.farmaceuticosdesevilla.es/ciudadanos/utilidades/localizador-de-farmacias/).
El formulario de búsqueda mostraba un error de API al comprobarlo; la sección
«Carteles de servicios de urgencias» sí permite consultar el índice provincial.
El scraper obtiene dinámicamente ese iframe, usa una sesión HTTP normal y pide
todos los municipios, en lugar de quedarse en la primera página.
No guarda credenciales ni el parámetro de acceso público del iframe.

```bash
# Requiere pdftotext y pdftoppm (Poppler) instalados.
python3 scripts/scrape_sevilla.py --fecha 2026-11-01 --geocode
# Todas las fechas del cuarto trimestre, descargando cada documento una sola vez:
python3 scripts/scrape_sevilla.py --trimestre 4 --anio 2026
# Para las siguientes ejecuciones, sin fijar año ni trimestre:
python3 scripts/scrape_sevilla.py --trimestre-actual --geocode --cache-documentos "$HOME/.local/state/farmacia/sevilla"
```

Publica `guardias-sevilla-YYYY-MM-DD.json`, `farmacias-sevilla.json` y un informe
`cobertura-sevilla-YYYY-MM-DD.json` con los municipios y documentos consultados.
Interpreta las columnas de los carteles comarcales, semanas municipales y los
horarios de día/noche de Sevilla capital. Conserva horarios especiales y no
utiliza un cartel de otra fecha. `completa` se refiere a los documentos del
índice publicados para la fecha, **no a que todos los municipios tengan una
farmacia propia de guardia ni a que todas las ubicaciones sean exactas**.

Las páginas de El Viso y Mairena del Alcor sin texto del 1/11/2026 se revisaron
visualmente. Su transcripción está en `data/sevilla-carteles-revisados.json`,
vinculada a la fecha, página y SHA-256 del PDF: si cambia el documento se exige
revisión nueva. Los documentos sin texto no revisados se señalan explícitamente.
El PDF de modificaciones vacío se comprueba renderizando la página; no se
interpreta un PDF ilegible como «sin modificaciones».

La geocodificación usa primero coincidencias inequívocas del catálogo OSM
guardado y después Nominatim, con validación de localidad y pausas entre consultas.
Las ubicaciones no exactas se marcan como aproximadas; los servicios localizables
o registros sin dirección resoluble permanecen en el listado sin marcador.
`data/coordenadas-sevilla-revisadas.json` conserva los puntos contrastados con
POIs de farmacia OSM o fichas con teléfono coincidente, junto con la evidencia.
El scraper los aplica automáticamente, antes del catálogo y Nominatim, solo si
la dirección del cartel y el teléfono siguen coincidiendo; avisa si cambian.
Cada ejecución actualiza también las ubicaciones de los calendarios guardados
y los contadores de cobertura, sin cambiar sus horarios ni fechas. Puede
ejecutarse sin descargar carteles con
`python3 scripts/scrape_sevilla.py --actualizar-coordenadas`.
Las discrepancias de numeración y la derivación de Pruna a Olvera se explican
en el popup. No se inventa una farmacia para las derivaciones de Peñaflor a
Palma del Río ni para el servicio localizable de El Garrobo sin dirección.
El listado tiene un botón «Mostrar más» para acceder a todos los resultados.
El modo trimestral reutiliza la conversión de cada PDF y las coordenadas por
identificador; no geocodifica repetidamente la misma farmacia por cada día.
Genera un informe diario para las 92 fechas de octubre a diciembre, más
`cobertura-sevilla-2026-T4.json`. La columna «4ºT» no garantiza que cada PDF
contenga todo ese periodo: se comprueban las fechas internas y se marcan los
huecos como `sin_fecha`. Los días totalmente sin datos no generan calendarios
vacíos, y las consultas incompletas no reemplazan calendarios ya publicados.
La salida es distinta de cero si alguna fecha del trimestre tiene cobertura
incompleta, aunque se hayan publicado las fechas parciales disponibles.
La actualización diaria ejecuta Málaga y Sevilla aunque una fuente falle, y
devuelve un error si cualquiera de las dos consultas falla.
`daily_update.sh` consulta automáticamente el trimestre y año vigentes, vuelve
a descargar los carteles para detectar cambios y solo reutiliza su conversión
cuando coincide el SHA-256. Después reconstruye la aplicación para incluir los
JSON actualizados en `dist/`. La tarea existente de cron la ejecuta a las 02:00
(zona horaria local del servidor; el scraper usa `Europe/Madrid`).
El equipo y el servicio cron deben estar encendidos; cron no recupera por sí
solo una ejecución perdida mientras el equipo estaba apagado.

El script usa `flock` para impedir solapamientos. Registra errores y salida en
`${XDG_STATE_HOME:-$HOME/.local/state}/farmacia/daily-update.log`, y el resultado
de la última ejecución en `last-update.json` dentro de ese mismo directorio.
Una salida 1 puede indicar huecos en el trimestre publicado, no necesariamente
un fallo del scraper; los detalles quedan en los informes de cobertura.
Los carteles sin texto que cambien no reutilizan una transcripción antigua.

## Monetización (futuro)
- Afiliados (PromoFarma, DosFarma)
- Patrocinios locales por zona
- API premium / widget embed