#!/usr/bin/env zsh

# =================================================================
# Script de Orquestación: Etiquetador de Gastos
# Ubicación: ~/dev/pc/scripts/start_contabilidad.sh
# =================================================================

# Colores para el log
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "${BLUE}============================================${NC}"
echo "${BLUE}    Iniciando Entorno de Contabilidad       ${NC}"
echo "${BLUE}============================================${NC}"

# Función para limpiar procesos al salir (CTRL+C)
cleanup() {
    echo "\n${BLUE}Deteniendo servicios...${NC}"
    kill $(jobs -p)
    exit
}
trap cleanup SIGINT

# 1. Iniciar Backend (FastAPI)
echo "${GREEN}[1/2] Levantando Backend (FastAPI)...${NC}"
cd ~/dev/projects/ContabilidadPersonal/contabilidad/backend
source .venv/bin/activate
# Ejecutamos en segundo plano (&)
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Esperar a que el puerto esté disponible
sleep 2

# 2. Iniciar Frontend (React)
echo "${GREEN}[2/2] Levantando Frontend (Vite/React)...${NC}"
cd ~/dev/projects/ContabilidadPersonal/contabilidad/pagina
# fnm ya debería estar configurado en tu .zshrc
npm run dev &
FRONTEND_PID=$!

echo "${BLUE}============================================${NC}"
echo "Servidores corriendo:"
echo "  - Backend:  http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Frontend: http://localhost:5173"
echo "${BLUE}Presiona CTRL+C para detener ambos servidores${NC}"
echo "${BLUE}============================================${NC}"

# Mantener el script vivo para escuchar el trap
wait
