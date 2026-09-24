#!/usr/bin/env bash
# Commitea el trabajo de Deudas v2 en la rama `feat/deudas-v2` SIN cambiar de rama.
#
#   scripts/v2/rama_v2.sh estado                 # qué difiere entre la copia de trabajo y la rama
#   scripts/v2/rama_v2.sh commitear archivo.txt  # commit nuevo en la rama con ese mensaje
#
# Por qué existe (deudas/PLAN_MULTIUSUARIO.md §0.3 y §0.4): el dueño trabaja en otra rama
# (`refactor/filtros-transacciones`) con cambios suyos sin commitear, y los archivos de v2
# viven en esa misma copia de trabajo, sin seguimiento. `git switch feat/deudas-v2` falla
# ("los archivos sin seguimiento serían sobrescritos"), y mezclarlos en su rama no se debe.
# Este script arma el commit con un índice temporal: no toca la rama actual, ni el índice
# real, ni la copia de trabajo.
#
# Solo mira las rutas de v2 (RUTAS). Ojo con `contabilidad/debts/reading.py` y
# `escritura.py`: si el dueño también los cambió por otra cosa, esos cambios entrarían.
# Revisa `estado` antes de commitear.
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
RAMA="feat/deudas-v2"
RUTAS=(
    deudas/PLAN_MULTIUSUARIO.md
    deudas/v2
    scripts/v2
    contabilidad/debts/cliente.py
    contabilidad/debts/reading.py
    contabilidad/debts/escritura.py
    tests/test_deudas_rechazadas.py
)

INDICE="$(mktemp)"
trap 'rm -f "$INDICE"' EXIT
g() { GIT_INDEX_FILE="$INDICE" git -C "$RAIZ" "$@"; }

g read-tree "$RAMA"

case "${1:-}" in
    estado)
        echo "Rama $RAMA: $(git -C "$RAIZ" log --oneline -1 "$RAMA")"
        echo "Cambios de la copia de trabajo respecto de la rama (solo rutas de v2):"
        g add -A -- "${RUTAS[@]}"
        g diff --cached --stat "$RAMA" -- "${RUTAS[@]}" || true
        ;;
    commitear)
        MENSAJE="${2:?Falta el archivo con el mensaje del commit}"
        g add -A -- "${RUTAS[@]}"
        if g diff --cached --quiet "$RAMA" -- "${RUTAS[@]}"; then
            echo "Nada que commitear: la rama ya tiene todo."
            exit 0
        fi
        ANTES="$(git -C "$RAIZ" rev-parse "$RAMA")"
        ARBOL="$(g write-tree)"
        NUEVO="$(git -C "$RAIZ" commit-tree "$ARBOL" -p "$ANTES" -F "$MENSAJE")"
        # Con el valor viejo: si la rama se movió mientras tanto, no se pisa.
        git -C "$RAIZ" update-ref "refs/heads/$RAMA" "$NUEVO" "$ANTES"
        git -C "$RAIZ" log --oneline -1 "$RAMA"
        ;;
    *)
        sed -n '2,6p' "$0"
        exit 1
        ;;
esac
