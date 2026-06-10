@echo off
REM Flipkart Listing Generator - Streamlit Web App Launcher
REM Run this file to start the web interface

echo.
echo ======================================================
echo  🎀 Flipkart Listing Generator - Web Interface
echo ======================================================
echo.

REM Check if Streamlit is installed
python -m pip show streamlit > nul 2>&1
if errorlevel 1 (
    echo Installing Streamlit (required for web interface)...
    pip install -r requirements_streamlit.txt
)

echo.
echo Starting Streamlit app...
echo Browser will open automatically at http://localhost:8501
echo Press Ctrl+C to stop the server
echo.

streamlit run app_streamlit.py

pause
