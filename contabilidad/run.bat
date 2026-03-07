@echo off
echo ============================================
echo    Etiquetador de Gastos - Starting...
echo ============================================
echo.

REM Check if backend folder exists
if not exist "backend" (
    echo ERROR: Backend folder not found!
    pause
    exit /b 1
)

REM Check if pagina folder exists
if not exist "pagina" (
    echo ERROR: Frontend folder not found!
    pause
    exit /b 1
)

echo Starting Backend (FastAPI)...
start "Backend - FastAPI" cmd /k "cd backend && python -m uvicorn main:app --reload --port 8000"

echo Waiting for backend to start...
timeout /t 3 /nobreak > nul

echo Starting Frontend (React)...
start "Frontend - React" cmd /k "cd pagina && npm run dev"

echo.
echo ============================================
echo    Servers are starting...
echo ============================================
echo.
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Frontend: http://localhost:5173
echo.
echo    Close the terminal windows to stop.
echo ============================================
echo.
pause
