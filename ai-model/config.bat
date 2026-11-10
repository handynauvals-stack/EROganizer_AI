@echo off
rem ============================================================================
rem  config.bat - PENGATURAN TERPUSAT ai-model
rem  Dibaca oleh setup.bat, download_model.bat, train.bat, run_server.bat.
rem
rem  JANGAN edit file ini untuk pengaturan pribadi. Salin  config.local.bat.example  menjadi  config.local.bat
rem  (tidak ikut git). Isinya baris dengan pola "if not defined", contoh:
rem
rem      if not defined MODEL_NAME set "MODEL_NAME=Qwen2.5-1.5B-Instruct"
rem      if not defined RUN_NAME set "RUN_NAME=eksperimen2"
rem
rem  Prioritas:  variabel yang Anda set di CMD  >  config.local.bat  >  default di bawah.
rem  Contoh sekali pakai di CMD (pakai kutip!):  set "RUN_NAME=uji" ^& train.bat --max-steps 5
rem ============================================================================

rem 1) pengaturan pribadi dulu (menimpa default)
if exist "%~dp0config.local.bat" call "%~dp0config.local.bat"

rem 2) MODEL DASAR (Hugging Face). Ganti untuk memakai model lain, mis. Qwen/Qwen2.5-1.5B-Instruct.
rem    MODEL_NAME = nama folder di ai-model\models\ (download_model.bat membuatnya otomatis dari nama repo).
if not defined MODEL_REPO set "MODEL_REPO=Qwen/Qwen2.5-0.5B-Instruct"
if not defined MODEL_NAME set "MODEL_NAME=Qwen2.5-0.5B-Instruct"

rem 3) TRAINING
rem    RUN_NAME            : nama hasil training -> training\output\<RUN_NAME>\adapter (juga dipakai run_server.bat)
rem    TOKENS_PER_BATCH x ACCUM : ukuran batch efektif. Turunkan TOKENS_PER_BATCH (naikkan ACCUM) bila VRAM kurang / out-of-memory.
rem                          Acuan: 2400 x 3 butuh +-7 GB VRAM (Qwen2.5-0.5B). 1200 x 6 butuh +-4 GB dengan hasil setara.
rem    TARGET_MODULES      : modul yang diberi LoRA. Qwen/Llama/Mistral/Gemma: nilai bawaan. Arsitektur lain: all-linear
if not defined RUN_NAME set "RUN_NAME=run1"
if not defined EPOCHS set "EPOCHS=3"
if not defined LR set "LR=2e-4"
if not defined LORA_RANK set "LORA_RANK=32"
if not defined LORA_ALPHA set "LORA_ALPHA=64"
if not defined TARGET_MODULES set "TARGET_MODULES=q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj"
if not defined TOKENS_PER_BATCH set "TOKENS_PER_BATCH=2400"
if not defined ACCUM set "ACCUM=3"
if not defined MAX_LEN set "MAX_LEN=1280"

rem 4) LAYANAN AI (Laravel memanggil alamat ini; samakan dengan CHATBOT_URL di .env)
if not defined SERVER_PORT set "SERVER_PORT=8001"

rem 5) TURUNAN - jangan diubah (boleh ditimpa lewat config.local.bat bila model/adapter ada di folder lain)
set "AI_DIR=%~dp0"
if not defined MODEL_DIR set "MODEL_DIR=%~dp0models\%MODEL_NAME%"
if not defined ADAPTER_DIR set "ADAPTER_DIR=%~dp0training\output\%RUN_NAME%\adapter"
set "CHATBOT_MODEL_DIR=%MODEL_DIR%"
set "CHATBOT_ADAPTER_DIR=%ADAPTER_DIR%"
set "PY=%~dp0venv\Scripts\python.exe"
