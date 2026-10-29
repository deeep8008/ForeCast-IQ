@echo off
title ForecastIQ - Multi-Horizon Demand Forecasting (Full Stack)
echo ======================================================================
echo Starting ForecastIQ Backend (FastAPI + Pandas Engine) on Port 8000
echo ======================================================================
start "ForecastIQ Backend" cmd /k "cd /d "%~dp0" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend"

echo ======================================================================
echo Starting ForecastIQ Frontend (Vite + React) on Port 5173
echo ======================================================================
cd /d "%~dp0frontend"
npm run dev -- --host
pause
