# DriftSystem Backend Executable Builder

This utility packages the FastAPI backend into a single-file Windows executable using PyInstaller.

## Prerequisites

- Windows 10/11 with Python 3.11 or newer on the PATH
- Internet access to install dependencies the first time
- Microsoft Visual C++ Build Tools (required by several Python wheels)

## Build Steps

1. Open **Developer Command Prompt for VS** (or any terminal with Python).
2. Navigate to the repository root:
   ```bat
   cd path\to\DriftSystem
   ```
3. Run the build helper:
   ```bat
   tools\pack_backend_exe\build_backend_exe.bat
   ```

The script creates an isolated virtual environment under `tools\pack_backend_exe\.venv`, installs backend dependencies plus PyInstaller, and then produces `DriftSystemBackend.exe` inside `tools\pack_backend_exe\dist`.

## Result

- **Executable:** `tools\pack_backend_exe\dist\DriftSystemBackend.exe`
- **Behavior:** starts Uvicorn with `app.main:app` on `127.0.0.1:8000`
- **Data:** Backed by the same `backend/data` and `backend/app/static` directories bundled into the executable so gameplay content loads as expected.

Run the executable by double-clicking it or via PowerShell:

```powershell
.\toolsack_backend_exeuild_backend_exe.bat
.\toolsack_backend_exeuild_backend_exeuild_backend_exe.py? wait
```

Hold on? we inserted extra text? Oops. Need to correct.*