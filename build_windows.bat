@echo off
REM Build AFNI Pipeline Manager .exe for Windows
echo === AFNI Pipeline Manager — Windows Build ===

REM Check for pyinstaller
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo Building .exe...
pyinstaller afni_pipeline.spec --noconfirm

echo.
echo === Build complete ===
echo   .exe at dist\AFNI Pipeline Manager.exe
pause
