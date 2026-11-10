@echo off
rem ============================================================================
rem  download_model.bat - unduh model dasar dari Hugging Face ke ai-model\models\ lalu periksa kecocokannya.
rem
rem    download_model.bat                                   model dari config.bat (Qwen/Qwen2.5-0.5B-Instruct)
rem    download_model.bat Qwen/Qwen2.5-1.5B-Instruct        model lain (folder = nama repo)
rem    download_model.bat Qwen/Qwen2.5-1.5B-Instruct nama   model lain, folder bernama "nama"
rem
rem  Model yang butuh persetujuan (gated, mis. Llama): set HF_TOKEN=hf_xxx  sebelum menjalankan.
rem  Setelah mengunduh model BARU, tambahkan MODEL_NAME di config.local.bat (skrip akan menampilkan barisnya).
rem  Hanya langkah ini yang butuh internet; training dan server berjalan offline.
rem ============================================================================
setlocal
cd /d "%~dp0"
call config.bat
call env.bat
set "RUN="
if defined DRY_RUN set "RUN=echo [dry-run]"
if not exist "%PY%" goto :no_venv

set "HF_HUB_OFFLINE=0"
%RUN% "%PY%" training\scripts\download_model.py "%~1" "%~2"
if errorlevel 1 goto :fail
exit /b 0

:no_venv
echo [ERROR] venv belum ada. Jalankan setup.bat dulu.
exit /b 1
:fail
echo.
echo [ERROR] Unduh/pemeriksaan model gagal. Baca pesan di atas.
exit /b 1
