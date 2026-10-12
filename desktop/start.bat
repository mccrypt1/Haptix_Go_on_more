@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw xbox_to_lovense.py
) else (
    REM No pythonw: fall back to python so errors stay visible
    python xbox_to_lovense.py
    pause
)
