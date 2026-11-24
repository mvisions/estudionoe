#!/usr/bin/env bash
# Runs a free OpenCode model on this isolated copy until it writes BARCELONA_INFORME.txt.
cd "$(dirname "$0")" || exit 1
log=opencode-barcelona.log
finished() { head -1 BARCELONA_INFORME.txt 2>/dev/null | grep -q -E '^ESTADO: (TERMINADO|BLOQUEADO)'; }
echo "INICIO $(date -Is)" >>"$log"
for model in opencode/big-pickle opencode/deepseek-v4.1-flash-free; do
  echo "== Modelo $model $(date -Is)" >>"$log"
  timeout 3600 opencode run -m "$model" "$(cat PROMPT_BARCELONA.md)" >>"$log" 2>&1
  for i in 1 2; do
    finished && break 2
    echo "== Continuación $i ($model) $(date -Is)" >>"$log"
    timeout 2400 opencode run -c -m "$model" "Continúa la tarea de PROMPT_BARCELONA.md donde la dejaste. Aún no existe BARCELONA_INFORME.txt con ESTADO: TERMINADO o ESTADO: BLOQUEADO en la primera línea. Termina los pasos pendientes, verifica y escribe el informe." >>"$log" 2>&1
  done
  finished && break
done
echo "FIN $(date -Is)" >>"$log"
