@echo off
rem ============================================================================
rem  setup.bat - SEKALI SAJA: buat virtual environment (venv) dan pasang semua paket Python.
rem
rem    setup.bat            PyTorch build cu118 (default; jalan di hampir semua driver NVIDIA)
rem    setup.bat cu126      driver NVIDIA baru (build cu126 / cu128 lebih cepat di GPU baru)
rem    setup.bat cpu        tanpa GPU NVIDIA (server jalan, training sangat lambat)
rem
rem  Uji tanpa memasang apa pun:  set DRY_RUN=1 ^& setup.bat
rem ============================================================================
setlocal
cd /d "%~dp0"
call config.bat
call env.bat
set "RUN="
if defined DRY_RUN set "RUN=echo [dry-run]"
set "TORCH_BUILD=%~1"
if "%TORCH_BUILD%"=="" set "TORCH_BUILD=cu118"

echo ============================================================
echo  ai-model - setup   PyTorch build: %TORCH_BUILD%
echo ============================================================
echo  Pilihan build: cu118 default, cu126, cu128, cpu
echo.

where python >nul 2>nul
if errorlevel 1 goto :no_python
python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
if errorlevel 1 goto :bad_python

if exist "venv\Scripts\python.exe" goto :have_venv
echo [1/3] Membuat virtual environment: venv
%RUN% python -m venv venv
if errorlevel 1 goto :fail
goto :install
:have_venv
echo [1/3] venv sudah ada - dilewati.

:install
echo [2/3] Memasang PyTorch %TORCH_BUILD% - unduhan besar, 1 sampai 3 GB
%RUN% "%PY%" -m pip install --upgrade pip
%RUN% "%PY%" -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/%TORCH_BUILD%
if errorlevel 1 goto :fail
echo [3/3] Memasang paket lain dari requirements.txt
%RUN% "%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Selesai. Berikutnya:
echo   1. download_model.bat   unduh model dasar
echo   2. train.bat            latih model
echo   3. run_server.bat       jalankan layanan AI
exit /b 0

:no_python
echo [ERROR] Python tidak ditemukan di PATH.
echo         Pasang Python 3.10 sampai 3.13 dari python.org dan centang "Add python.exe to PATH".
exit /b 1
:bad_python
echo [ERROR] Dibutuhkan Python 3.10 sampai 3.13. Versi Anda:
python --version
exit /b 1
:fail
echo.
echo [ERROR] Setup gagal. Baca pesan di atas.
exit /b 1
