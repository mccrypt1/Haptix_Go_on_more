@echo off
REM Build a standalone XboxToLovense.exe into dist\
cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo PyInstaller not found - installing...
    python -m pip install pyinstaller || goto :fail
)

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name XboxToLovense ^
    --clean ^
    --noconfirm ^
    xbox_to_lovense.py || goto :fail

echo.
echo Done: dist\XboxToLovense.exe
echo Copy it anywhere - config.json is created next to the exe on first run.
pause
exit /b 0

:fail
echo.
echo Build FAILED.
pause
exit /b 1
