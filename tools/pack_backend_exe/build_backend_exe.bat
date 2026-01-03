@echo off
setlocal ENABLEDELAYEDEXPANSION

set SCRIPT_DIR=%~dp0
rem Normalize to remove trailing backslash if present
for %%I in ("%SCRIPT_DIR%") do set SCRIPT_DIR=%%~fI
pushd "%SCRIPT_DIR%"

set PROJECT_ROOT=%SCRIPT_DIR%\..\..
for %%I in ("%PROJECT_ROOT%") do set PROJECT_ROOT=%%~fI
set BACKEND_DIR=%PROJECT_ROOT%\backend
set VENV_DIR=%SCRIPT_DIR%\.venv

if not exist "%BACKEND_DIR%\requirements.txt" (
    echo DriftSystem backend requirements.txt not found at %BACKEND_DIR%\requirements.txt
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment at %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

echo Activating build virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

echo Installing backend dependencies...
echo Installing PyInstaller...
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto build_error

echo Installing backend dependencies...
python -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 goto build_error

echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto build_error

echo Building DriftSystem backend executable...
python "%SCRIPT_DIR%\build_backend_exe.py"
if errorlevel 1 goto build_error

if exist "%SCRIPT_DIR%\dist\DriftSystemBackend.exe" (
    echo.
    echo ✅ Build complete: %SCRIPT_DIR%\dist\DriftSystemBackend.exe
) else (
    echo.
    echo ⚠️ Build script finished but executable not found in dist directory.
)

goto build_success

:build_error
echo.
echo ❌ Build failed.
exit /b 1

:build_success
popd
exit /b 0
