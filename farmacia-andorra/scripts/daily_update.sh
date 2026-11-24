#!/bin/bash
# Modo por defecto («manana», 12:00): prepara en segundo plano las guardias de MAÑANA
# para que estén publicadas antes de medianoche. Modo «--hoy» (00:05 y reintento de las
# 08:00): fuentes que solo publican el día en curso (Madrid, Barcelona, Cáceres,
# Valladolid, León) y las provincias a las que aún les falte el archivo de hoy.
# La web se publica con un intercambio atómico.
set -euo pipefail
cd "$(dirname "$0")/.."
export TZ=Europe/Madrid
mode=manana
case "${1:-}" in
  "") ;;
  --hoy) mode=hoy ;;
  *) echo "Uso: $0 [--hoy]" >&2; exit 2 ;;
esac
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/farmacia"
data_dir="${FARMACIA_DATA_DIR:-public/data}"
dist_dir="${FARMACIA_DIST_DIR:-dist}"
mkdir -p "$state_dir"
log_file="$state_dir/daily-update.log"
exec >> "$log_file" 2>&1
exec 9>"$state_dir/daily-update.lock"
# Si otra ejecución sigue activa, se espera en lugar de omitirse: la de hoy hasta 1 h
# (debe publicar pronto) y la de mañana hasta 4 h (tiene margen hasta medianoche).
lock_wait=14400
[[ $mode == hoy ]] && lock_wait=3600
lock_option=(-w "${FARMACIA_LOCK_WAIT:-$lock_wait}")
if ! flock "${lock_option[@]}" 9; then
  echo "Actualización omitida: ya hay otra ejecución activa ($(date --iso-8601=seconds))."
  exit 75
fi
if [[ $mode == hoy ]]; then fecha=$(date +%F); else fecha=$(date -d tomorrow +%F); fi
anio=${fecha:0:4}
mes=$((10#${fecha:5:2}))
dia=$((10#${fecha:8:2}))
trimestre=$(((mes - 1) / 3 + 1))
started=$(date --iso-8601=seconds)
worker_pids=()
finish() {
  result=$?
  trap - EXIT
  for pid in "${worker_pids[@]}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  printf 'Fin: %s; salida=%s\n' "$(date --iso-8601=seconds)" "$result"
  printf '{"inicio":"%s","fin":"%s","modo":"%s","fecha":"%s","salida":%s}\n' \
    "$started" "$(date --iso-8601=seconds)" "$mode" "$fecha" "$result" > "$state_dir/last-update.json.tmp"
  mv "$state_dir/last-update.json.tmp" "$state_dir/last-update.json"
  exit "$result"
}
trap finish EXIT
echo "Inicio: $started; modo=$mode; fecha=$fecha"
status=0
ran=0

# Fuentes con fecha: en modo «manana» siempre; en modo «hoy» solo si falta su archivo.
pending() {
  [[ $mode == manana || ! -e "$data_dir/guardias-$1-$fecha.json" ]]
}
dated() {
  local slug=$1; shift
  if pending "$slug"; then ran=1; "$@" --fecha "$fecha" || status=1; fi
}
dated_worker() {
  local slug=$1; shift
  if pending "$slug"; then ran=1; "$@" --fecha "$fecha" & worker_pids+=("$!"); fi
}
# Fuentes que solo publican el día en curso: solo en modo «hoy» y si falta su archivo,
# para que el reintento de la mañana no repita las ya obtenidas.
today_only() {
  local slug=$1; shift
  if [[ $mode == hoy ]] && pending "$slug"; then ran=1; "$@" || status=1; fi
}
# Igual, pero aceptan --fecha (comprueban que la página muestre el día pedido).
dated_today_only() {
  local slug=$1; shift
  if [[ $mode == hoy ]] && pending "$slug"; then ran=1; "$@" --fecha "$fecha" || status=1; fi
}

dated_worker valencia python3 scripts/scrape_valencia.py --cache-documentos "$state_dir/valencia"
dated_worker murcia python3 scripts/scrape_murcia.py --cache-documentos "$state_dir/murcia"
dated_worker baleares python3 scripts/scrape_baleares.py --cache-documentos "$state_dir/baleares"
if pending malaga; then
  ran=1
  python3 scripts/scrape_mes.py 29 Malaga "$mes" "$anio" --dia "$dia" || status=1
  python3 scripts/complete_malaga.py --fecha "$fecha" || status=1
fi
if pending sevilla; then
  ran=1
  python3 scripts/scrape_sevilla.py --trimestre "$trimestre" --anio "$anio" --geocode \
    --cache-documentos "$state_dir/sevilla" || status=1
fi
dated granada python3 scripts/scrape_granada.py --geocode
dated cadiz python3 scripts/scrape_cadiz.py
dated jaen python3 scripts/scrape_jaen.py --geocode --cache-documentos "$state_dir/jaen"
dated almeria python3 scripts/scrape_almeria.py --geocode
dated alicante python3 scripts/scrape_alicante.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/alicante"
dated huelva python3 scripts/scrape_huelva.py --geocode --cache-documentos "$state_dir/huelva"
dated cordoba python3 scripts/scrape_cordoba.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/cordoba"
today_only madrid python3 scripts/scrape_madrid.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/madrid"
dated toledo python3 scripts/scrape_toledo.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/toledo"
dated guadalajara python3 scripts/scrape_guadalajara.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/guadalajara"
dated albacete python3 scripts/scrape_albacete.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/albacete"
dated ciudad-real python3 scripts/scrape_ciudad_real.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/ciudad-real"
dated cuenca python3 scripts/scrape_cuenca.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/cuenca"
today_only barcelona python3 scripts/scrape_barcelona.py --cache-documentos "$state_dir/barcelona"
dated girona python3 scripts/scrape_girona.py
dated_today_only valladolid python3 scripts/scrape_valladolid.py --geocode --cache-documentos "$state_dir/valladolid"
dated_today_only leon python3 scripts/scrape_leon.py --cache-documentos "$state_dir/leon"
dated zamora python3 scripts/scrape_zamora.py --cache-documentos "$state_dir/zamora"
dated soria python3 scripts/scrape_soria.py --cache-documentos "$state_dir/soria"
dated cantabria python3 scripts/scrape_cantabria.py --geocode --cache-documentos "$state_dir/cantabria"
dated pontevedra python3 scripts/scrape_pontevedra.py --geocode --cache-documentos "$state_dir/pontevedra"
dated ourense python3 scripts/scrape_ourense.py
dated a-coruna python3 scripts/scrape_a_coruna.py
dated andorra python3 scripts/scrape_andorra.py --cache-documentos "$state_dir/andorra"
dated asturias python3 scripts/scrape_asturias.py --geocode --cache-documentos "$state_dir/asturias"
dated navarra python3 scripts/scrape_navarra.py --geocode --cache-documentos "$state_dir/navarra"
dated salamanca python3 scripts/scrape_salamanca.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/salamanca"
dated burgos python3 scripts/scrape_burgos.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/burgos"
dated palencia python3 scripts/scrape_palencia.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/palencia"
dated badajoz python3 scripts/scrape_badajoz.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/badajoz"
dated la-rioja python3 scripts/scrape_la_rioja.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/la-rioja"
dated zaragoza python3 scripts/scrape_zaragoza.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/zaragoza"
dated ceuta python3 scripts/scrape_ceuta.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/ceuta"
dated melilla python3 scripts/scrape_melilla.py --geocode --permitir-direccion-exacta --cache-documentos "$state_dir/melilla"
today_only caceres python3 scripts/scrape_caceres.py
dated segovia python3 scripts/scrape_segovia.py --cache-documentos "$state_dir/segovia"
for pid in "${worker_pids[@]}"; do
  wait "$pid" || status=1
done
worker_pids=()
if [[ $ran == 0 ]]; then
  echo "Nada pendiente para $fecha: se mantiene la web publicada."
  exit "$status"
fi
# El registro JCyL y la ubicación de sus farmacias (sin guardia) solo se hacen en la víspera;
# a medianoche se ubican únicamente guardias para publicar cuanto antes.
catalog_option=()
if [[ $mode == manana ]]; then
  python3 scripts/registro_jcyl.py --cache-documentos "$state_dir/registro-jcyl" || status=1
  catalog_option=(--catalogo farmacias-registro-jcyl.json)
fi
python3 scripts/locate_guardias.py --cache "$state_dir/geocache-guardias.json" \
  "${catalog_option[@]}" \
  --excluir-provincia laspalmas --excluir-provincia tenerife || status=1
python3 scripts/merge_espana.py || status=1

# Compila aparte y sustituye la web publicada en una sola operación: nunca queda a medias.
next_dir="$dist_dir.next"
rm -rf "$next_dir"
if npm run build -- --outDir "$(realpath -m "$next_dir")" --emptyOutDir && [[ -d $next_dir ]]; then
  if [[ -d $dist_dir ]]; then
    mv -T --exchange "$next_dir" "$dist_dir" && rm -rf "$next_dir"
  else
    mv -T "$next_dir" "$dist_dir"
  fi
  echo "Web publicada: $(date --iso-8601=seconds)."
else
  rm -rf "$next_dir"
  echo "Compilación fallida: se mantiene la web publicada anterior."
  status=1
fi
echo "Consultas finalizadas: $(date). Revisar los informes de cobertura provinciales."
exit "$status"
