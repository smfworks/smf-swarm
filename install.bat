@echo off
rem SMF Swarm — One-line installer for Windows (legacy batch fallback)
rem Usage: curl -fsSL .../install.bat -o install.bat && install.bat
rem Prefer PowerShell: iwr -useb .../install.ps1 | iex

echo.
echo  [SMF Swarm Installer — Windows Batch Fallback]
echo  ==============================================
echo.

rem Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Python not found in PATH.
    echo  Install Python 3.10+ from https://python.org/downloads/windows/
    echo  Enable "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo  [OK] Python found.

rem Check pip
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  Installing pip via ensurepip...
    python -m ensurepip --default-pip
    if %ERRORLEVEL% NEQ 0 (
        echo  ERROR: Failed to install pip.
        pause
        exit /b 1
    )
)

echo  [OK] pip found.
echo.

rem Install
echo  Installing smf-swarm from PyPI...
python -m pip install --upgrade smf-swarm
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Installation failed. Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo  [OK] Installation complete.
echo.

rem Verify
where smf-swarm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  WARNING: smf-swarm command not found. Add Python Scripts to PATH.
)

echo  Run: smf-swarm version
echo  Run: smf-swarm configure
echo.
pause
