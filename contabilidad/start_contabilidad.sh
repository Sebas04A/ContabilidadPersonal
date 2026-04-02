#!/usr/bin/env zsh

# =================================================================
# ContabilidadPersonal — Script de Orquestación
# Uso: ./start_contabilidad.sh [debug]
#   debug → activa LOG_LEVEL=DEBUG en el backend
# =================================================================

# ── Nivel de log ──────────────────────────────────────────────────
LOG_LEVEL="INFO"
[[ "$1" == "debug" ]] && LOG_LEVEL="DEBUG"
export LOG_LEVEL

# ── Paleta de colores ─────────────────────────────────────────────
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'

# Backend → azul
BE_COLOR=$'\033[38;5;117m'
BE_LABEL="${BE_COLOR}${BOLD}[BACKEND ]${RESET}"

# Frontend → verde
FE_COLOR=$'\033[38;5;114m'
FE_LABEL="${FE_COLOR}${BOLD}[FRONTEND]${RESET}"

# Sistema → gris
SYS_COLOR=$'\033[38;5;245m'
SYS_LABEL="${SYS_COLOR}[SISTEMA ]${RESET}"

# Warn / Error
WARN=$'\033[38;5;221m'
ERR=$'\033[38;5;203m'

separator() {
    echo "${DIM}$(printf '─%.0s' {1..64})${RESET}"
}

log_sys()  { echo "${SYS_LABEL}  $*"; }
log_be()   { echo "${BE_LABEL}  $*"; }
log_fe()   { echo "${FE_LABEL}  $*"; }

# ── Header ───────────────────────────────────────────────────────
clear
separator
echo "${BOLD}  ContabilidadPersonal${RESET}  ${DIM}—  Sistema de arranque${RESET}"
separator
log_sys "LOG_LEVEL=${BOLD}${LOG_LEVEL}${RESET}"
log_sys "$(date '+%Y-%m-%d %H:%M:%S')"
separator
echo ""

# ── Limpieza al salir (CTRL+C) ────────────────────────────────────
cleanup() {
    echo ""
    separator
    log_sys "Deteniendo servicios..."
    [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null
    # Matar cualquier proceso hijo restante
    kill $(jobs -p) 2>/dev/null
    log_sys "Servicios detenidos. ${DIM}Bye!${RESET}"
    separator
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── 1. Backend (FastAPI + Uvicorn) ───────────────────────────────
log_be "Iniciando backend FastAPI (puerto 8000)..."

# Directorio raíz del proyecto (relativo a este script, no hardcodeado)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_ACTIVATE="$SCRIPT_DIR/backend/.venv/bin/activate"

(
    cd "$PROJECT_ROOT" || { echo "${ERR}[BACKEND ] Error: directorio raíz no encontrado${RESET}"; exit 1; }
    [[ -f "$VENV_ACTIVATE" ]] && source "$VENV_ACTIVATE"

    # Lanzar desde la raíz del proyecto como módulo para que 'contabilidad.*' resuelva siempre
    python -m uvicorn contabilidad.backend.main:app --reload --port 8000 2>&1 | while IFS= read -r line; do
        if [[ "$line" == *"ERROR"* ]] || [[ "$line" == *"error"* ]]; then
            echo "${BE_COLOR}[BACKEND ]${RESET}  ${ERR}${line}${RESET}"
        elif [[ "$line" == *"WARNING"* ]] || [[ "$line" == *"⚠"* ]]; then
            echo "${BE_COLOR}[BACKEND ]${RESET}  ${WARN}${line}${RESET}"
        else
            echo "${BE_LABEL}  ${line}"
        fi
    done
) &
BACKEND_PID=$!

# Esperar a que el backend esté listo
log_be "Esperando que levante..."
for i in {1..15}; do
    sleep 1
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_be "${FE_COLOR}✓ Backend listo${RESET} en http://localhost:8000"
        break
    fi
    [[ $i -eq 15 ]] && log_be "${WARN}⚠ Backend tardando más de lo esperado — revisa los logs${RESET}"
done

echo ""

# ── 2. Frontend (Vite/React) ─────────────────────────────────────
log_fe "Iniciando frontend Vite/React (puerto 5173)..."

FRONTEND_DIR=~/dev/projects/ContabilidadPersonal/contabilidad/pagina

(
    cd "$FRONTEND_DIR" || { echo "${ERR}[FRONTEND] Error: directorio no encontrado${RESET}"; exit 1; }

    npm run dev 2>&1 | while IFS= read -r line; do
        if [[ "$line" == *"error"* ]] || [[ "$line" == *"Error"* ]]; then
            echo "${FE_COLOR}[FRONTEND]${RESET}  ${ERR}${line}${RESET}"
        elif [[ "$line" == *"warn"* ]] || [[ "$line" == *"WARN"* ]]; then
            echo "${FE_COLOR}[FRONTEND]${RESET}  ${WARN}${line}${RESET}"
        else
            echo "${FE_LABEL}  ${line}"
        fi
    done
) &
FRONTEND_PID=$!

# ── Resumen ───────────────────────────────────────────────────────
sleep 2
echo ""
separator
echo "  ${BOLD}Servicios corriendo:${RESET}"
echo "  ${BE_COLOR}●${RESET} Backend   →  http://localhost:8000"
echo "  ${BE_COLOR}●${RESET} API Docs  →  http://localhost:8000/docs"
echo "  ${FE_COLOR}●${RESET} Frontend  →  http://localhost:5173"
echo ""
echo "  ${DIM}LOG_LEVEL=${LOG_LEVEL}   |   CTRL+C para detener todo${RESET}"
separator
echo ""

# ── Mantener el script vivo ───────────────────────────────────────
wait
