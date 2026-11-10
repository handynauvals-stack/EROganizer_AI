@echo off
rem ============================================================================
rem  train.bat - periksa model -> bangun dataset -> training LoRA -> evaluasi.
rem  Pengaturan ada di config.bat (timpa lewat config.local.bat). Argumen tambahan diteruskan ke train.py:
rem
rem    train.bat                       training penuh dengan pengaturan config
rem    train.bat --epochs 5            timpa satu parameter
rem    train.bat --max-steps 5         UJI CEPAT 5 langkah (pastikan model/GPU cocok sebelum training penuh)
rem
rem  Opsi lewat variabel lingkungan:  SKIP_BUILD=1 (pakai dataset yang ada)   SKIP_EVAL=1 (tanpa evaluasi)
rem                                   FORCE=1 (abaikan peringatan layanan AI menyala)   DRY_RUN=1 (hanya tampilkan perintah)
rem                                   OVERWRITE=1 (izinkan menimpa adapter RUN_NAME yang sudah ada; bawaan: DITOLAK)
rem  Uji cepat jangan pakai RUN_NAME yang sudah berisi adapter bagus:  set "RUN_NAME=uji" ^& train.bat --max-steps 5
rem
rem  PENTING: tutup layanan AI (run_server.bat) sebelum training. Keduanya berebut VRAM dan RAM; di Windows ini
rem  membuat pagefile membengkak di disk C dan training melambat sekitar 2,5 kali.
rem ============================================================================
setlocal
cd /d "%~dp0"
call config.bat
call env.bat
set "HF_HUB_OFFLINE=1"
set "RUN="
if defined DRY_RUN set "RUN=echo [dry-run]"
set "EXTRA="
if defined OVERWRITE set "EXTRA=--overwrite"
if not exist "%PY%" goto :no_venv

if defined FORCE goto :port_ok
netstat -ano | findstr /R /C:":%SERVER_PORT% .*LISTENING" >nul 2>nul
if not errorlevel 1 goto :server_running
:port_ok

where nvidia-smi >nul 2>nul
if errorlevel 1 echo [PERINGATAN] GPU NVIDIA tidak terdeteksi. Training di CPU sangat lambat; pakai --max-steps untuk uji saja.

echo ============================================================
echo  train.bat   model=%MODEL_NAME%   run=%RUN_NAME%
echo  epochs=%EPOCHS% lr=%LR% lora=%LORA_RANK%/%LORA_ALPHA% batch=%TOKENS_PER_BATCH%x%ACCUM%
echo ============================================================

echo [1/4] Memeriksa model dasar
%RUN% "%PY%" training\scripts\check_model.py "%MODEL_DIR%"
if errorlevel 1 goto :fail

if defined SKIP_BUILD goto :train
echo [2/4] Membangun dataset
%RUN% "%PY%" training\scripts\build.py
if errorlevel 1 goto :fail

:train
echo [3/4] Training
%RUN% "%PY%" training\scripts\train.py --run-name "%RUN_NAME%" --model-dir "%MODEL_DIR%" --epochs %EPOCHS% --lr %LR% --rank %LORA_RANK% --alpha %LORA_ALPHA% --target-modules "%TARGET_MODULES%" --tokens-per-batch %TOKENS_PER_BATCH% --accum %ACCUM% --max-len %MAX_LEN% %EXTRA% %*
if errorlevel 1 goto :fail

if defined SKIP_EVAL goto :done
echo [4/4] Evaluasi
%RUN% "%PY%" training\scripts\evaluate.py --tag "%RUN_NAME%" --model-dir "%MODEL_DIR%" --adapter "%ADAPTER_DIR%"
if errorlevel 1 goto :fail

:done
echo.
echo Selesai. Adapter: %ADAPTER_DIR%
if not defined SKIP_EVAL echo Laporan evaluasi: training\reports\%RUN_NAME%\report.md
echo Jalankan layanan AI dengan run_server.bat  RUN_NAME=%RUN_NAME% dipakai otomatis.
exit /b 0

:no_venv
echo [ERROR] venv belum ada. Jalankan setup.bat dulu.
exit /b 1
:server_running
echo [ERROR] Layanan AI sedang berjalan di port %SERVER_PORT%. Tutup dulu jendelanya dengan Ctrl+C.
echo         Jalan terus tanpa menutup: set FORCE=1 lalu jalankan lagi - tidak disarankan.
exit /b 1
:fail
echo.
echo [ERROR] Tahap gagal. Baca pesan di atas. Bila kehabisan memori GPU: turunkan TOKENS_PER_BATCH dan naikkan ACCUM di config.local.bat.
exit /b 1
