@echo off
title ForecastIQ - Multi-Horizon Demand Forecasting Frontend
cd /d "%~dp0frontend"
echo ======================================================================
echo Starting ForecastIQ Frontend (Vite + React + Tailwind CSS)
echo ======================================================================
npm run dev -- --host
pause
