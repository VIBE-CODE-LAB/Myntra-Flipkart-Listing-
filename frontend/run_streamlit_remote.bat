@echo off
REM Flipkart Listing Generator - Streamlit Web App for Remote Access
REM Run this file to start the web interface accessible from other devices on your network

echo.
echo ======================================================
echo  🌐 Myntra Listing AI - Remote Access Mode
echo ======================================================
echo.

REM Check if Streamlit is installed
python -m pip show streamlit > nul 2>&1
if errorlevel 1 (
    echo Installing Streamlit (required for web interface)...
    pip install -r requirements_streamlit.txt
)

REM Get local IP address
echo Getting your system IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo.
echo ✅ Main System IP: %IP%
echo.
echo 📱 Remote workers can access at: http://%IP%:8501
echo.
echo Starting Streamlit app in remote access mode...
echo Press Ctrl+C to stop the server
echo.

streamlit run app_streamlit.py --server.address 0.0.0.0 --server.port 8501

pause
