@echo off
REM Launch Device Management Dashboard
echo Starting Device Management Dashboard...
echo.
echo Dashboard will open in your browser
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0.."
.venv\Scripts\python.exe -m streamlit run frontend\device_dashboard.py --server.port 8502
