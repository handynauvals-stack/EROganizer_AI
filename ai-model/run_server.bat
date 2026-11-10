@echo off
rem ============================================================================
rem  run_server.bat - jalankan layanan AI (model + adapter) di http://127.0.0.1:8001  (port: SERVER_PORT di config.bat)
rem  Laravel memanggil layanan ini; alamatnya harus sama dengan CHATBOT_URL di .env.
rem  Adapter yang dimuat = training\output\<RUN_NAME>\adapter  (RUN_NAME di config.bat / config.local.bat).
rem  Tanpa adapter (model dasar, TANPA tool call): set ADAPTER_DIR=none
rem ============================================================================
setlocal
cd /d "%~dp0"
call config.bat
call env.bat
set "HF_HUB_OFFLINE=1"
set "RUN="
if defined DRY_RUN set "RUN=echo [dry-run]"

if not exist "%PY%" goto :no_venv
if not exist "%MODEL_DIR%\config.json" goto :no_model
if /i "%ADAPTER_DIR%"=="none" goto :run
if not exist "%ADAPTER_DIR%\adapter_config.json" goto :no_adapter

:run
set "ADAPTER_LABEL=%RUN_NAME%"
if /i "%ADAPTER_DIR%"=="none" set "ADAPTER_LABEL=TANPA ADAPTER, model dasar tanpa tool call"
echo Layanan AI: model=%MODEL_NAME%  adapter=%ADAPTER_LABEL%  http://127.0.0.1:%SERVER_PORT%
echo Hentikan dengan Ctrl+C.
%RUN% "%PY%" -m uvicorn server:app --host 127.0.0.1 --port %SERVER_PORT%
exit /b %errorlevel%

:no_venv
echo [ERROR] venv belum ada. Jalankan setup.bat dulu.
exit /b 1
:no_model
echo [ERROR] Model belum ada di %MODEL_DIR%
echo         Jalankan download_model.bat dulu.
exit /b 1
:no_adapter
echo [ERROR] Adapter belum ada di %ADAPTER_DIR%
echo         Jalankan train.bat dulu, atau set RUN_NAME di config.local.bat ke nama training yang sudah ada.
exit /b 1
