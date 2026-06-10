#!/usr/bin/env powershell
# Flipkart Listing Generator - Streamlit Web App Launcher
# Run this file to start the web interface

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  🎀 Flipkart Listing Generator - Web Interface" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Streamlit is installed
try {
    python -m pip show streamlit > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Streamlit (required for web interface)..." -ForegroundColor Yellow
        pip install -r requirements_streamlit.txt
    }
} catch {
    Write-Host "Warning: Could not check Streamlit installation" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting Streamlit app..." -ForegroundColor Green
Write-Host "Browser will open automatically at http://localhost:8501" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

streamlit run app_streamlit.py

Read-Host "Press Enter to exit"
