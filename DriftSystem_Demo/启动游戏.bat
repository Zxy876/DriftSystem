@echo off
setlocal enableextensions enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PROJECT_DIR=%SCRIPT_DIR%DriftSystem"
if not exist "%PROJECT_DIR%" (
    echo [錯誤] 未找到 DriftSystem 目錄，請確認 Demo 包完整。
    pause
    exit /b 1
)

echo ============================================
echo   DriftSystem Demo 啟動程序
echo   這是一個研究 / 展示 Demo
echo ============================================

echo [1/8] 檢查 Java 可用性...
where java >nul 2>nul
if errorlevel 1 (
    echo 未檢測到 Java，請安裝 Java 17 或以上版本後重試。
    pause
    exit /b 1
)

set "JAVA_VER="
for /f tokens^=2^ delims^=^" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do set "JAVA_VER=%%v"
if not defined JAVA_VER (
    echo 無法讀取 Java 版本資訊。
    pause
    exit /b 1
)
set "JAVA_VER=!JAVA_VER:"=!"
set "JAVA_MAJOR="
set "JAVA_MINOR="
for /f "tokens=1-3 delims=._" %%a in ("!JAVA_VER!") do (
    if not defined JAVA_MAJOR set "JAVA_MAJOR=%%a"
    if not defined JAVA_MINOR set "JAVA_MINOR=%%b"
)
set /a JAVA_MAJOR_NUM=JAVA_MAJOR
if !JAVA_MAJOR_NUM! LSS 17 (
    echo 檢測到的 Java 版本為 !JAVA_VER!，需要 Java 17 或更新版本。
    pause
    exit /b 1
)
echo    Java 版本: !JAVA_VER!

echo [2/8] 檢查 Python 可用性...
set "PYTHON_EXE="
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
)
if not defined PYTHON_EXE (
    echo 未檢測到 Python，請安裝 Python 3.10 或以上版本後重試。
    pause
    exit /b 1
)
echo    已找到 Python 可執行檔: %PYTHON_EXE%

set "PYTHON_VER="
for /f "tokens=2 delims= " %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do if not defined PYTHON_VER set "PYTHON_VER=%%v"
if not defined PYTHON_VER (
    echo 無法讀取 Python 版本資訊。
    pause
    exit /b 1
)
set "PYTHON_VER=%PYTHON_VER:"=%"
set "PY_MAJOR="
set "PY_MINOR="
for /f "tokens=1-3 delims=._" %%a in ("%PYTHON_VER%") do (
    if not defined PY_MAJOR set "PY_MAJOR=%%a"
    if not defined PY_MINOR set "PY_MINOR=%%b"
)
set /a PY_MAJOR_NUM=PY_MAJOR
set /a PY_MINOR_NUM=PY_MINOR
if %PY_MAJOR_NUM% LSS 3 (
    echo 檢測到的 Python 版本為 %PYTHON_VER%，需要 Python 3.10 或更新版本。
    pause
    exit /b 1
)
if %PY_MAJOR_NUM% EQU 3 if %PY_MINOR_NUM% LSS 10 (
    echo 檢測到的 Python 版本為 %PYTHON_VER%，需要 Python 3.10 或更新版本。
    pause
    exit /b 1
)
echo    Python 版本: %PYTHON_VER%

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "BACKEND_REQ=%BACKEND_DIR%\requirements.txt"
if not exist "%BACKEND_REQ%" (
    echo 未找到 backend\requirements.txt，請確認 Demo 包完整。
    pause
    exit /b 1
)

set "VENV_DIR=%BACKEND_DIR%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo [3/8] 準備後端虛擬環境...
if not exist "%VENV_PY%" (
    echo    第一次使用：正在建立虛擬環境，可能需要一點時間。
    "%PYTHON_EXE%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo 建立虛擬環境失敗，請確認 Python 安裝正常。
        pause
        exit /b 1
    )
)
echo    虛擬環境位置: %VENV_DIR%

echo [4/8] 安裝 / 更新後端所需套件...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo pip 更新失敗，請稍後再試或檢查網絡。
    pause
    exit /b 1
)
"%VENV_PY%" -m pip install -r "%BACKEND_REQ%"
if errorlevel 1 (
    echo 套件安裝失敗，請檢查網絡並稍後重試。
    pause
    exit /b 1
)

echo [5/8] 準備啟動 FastAPI 後端...
set "BACKEND_CMD=%VENV_PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
pushd "%BACKEND_DIR%"
start "DriftSystem Backend" cmd /k "%BACKEND_CMD%"
popd

echo [6/8] 準備啟動 Minecraft 服務端...
set "MC_DIR=%BACKEND_DIR%\server"
if not exist "%MC_DIR%" (
    echo 未找到 backend\server 目錄，請確認 Demo 包完整。
    pause
    exit /b 1
)

set "MC_JAR="
if exist "%MC_DIR%\paper-1.20.1.jar" set "MC_JAR=paper-1.20.1.jar"
if not defined MC_JAR if exist "%MC_DIR%\paper.jar" set "MC_JAR=paper.jar"
if not defined MC_JAR (
    for %%j in ("%MC_DIR%\*.jar") do (
        if not defined MC_JAR set "MC_JAR=%%~nxj"
    )
)
if not defined MC_JAR (
    echo 未在 backend\server 中找到 Minecraft 服務端 jar 文件。
    pause
    exit /b 1
)

pushd "%MC_DIR%"
start "DriftSystem MC Server" cmd /k "java -Xms2G -Xmx4G -jar \"%MC_JAR%\" nogui"
popd

echo [7/8] 服務正在啟動中（將於新視窗顯示進度）。
echo [8/8] 當兩個視窗顯示 Ready 後，請使用 Minecraft Java 版 1.20.1 連線到 localhost。
echo --------------------------------------------
echo 體驗結束後，關閉這兩個視窗即可停止所有服務。
echo --------------------------------------------

pause
exit /b 0
