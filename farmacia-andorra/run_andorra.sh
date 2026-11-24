#!/usr/bin/env bash
# Runs a free OpenCode model on this isolated copy until it writes ANDORRA2_INFORME.txt.
cd "$(dirname "$0")" || exit 1
log=opencode-andorra2.log
finished() { head -1 ANDORRA2_INFORME.txt 2>/dev/null | grep -q -E '^ESTADO: (TERMINADO|BLOQUEADO)'; }
echo "INICIO $(date -Is)" >>"$log"
for model in opencode/big-pickle opencode/deepseek-v4.1-flash-free; do
  echo "== Modelo $model $(date -Is)" >>"$log"
  timeout 3600 opencode run -m "$model" "$(cat PROMPT_ANDORRA2.md)" >>"$log" 2>&1
  for i in 1 2; do
    finished && break 2
    echo "== Continuación $i ($model) $(date -Is)" >>"$log"
    timeout 2400 opencode run -c -m "$model" "Continúa la tarea de PROMPT_ANDORRA2.md donde la dejaste. Aún no existe ANDORRA2_INFORME.txt con ESTADO: TERMINADO o ESTADO: BLOQUEADO en la primera línea. Termina los pasos pendientes, verifica y escribe el informe." >>"$log" 2>&1
  done
  finished && break
done
echo "FIN $(date -Is)" >>"$log"
