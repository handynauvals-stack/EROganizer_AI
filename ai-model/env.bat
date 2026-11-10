@echo off
rem ============================================================================
rem  env.bat - mengalihkan SEMUA file sementara dan cache ke folder lokal ai-model\.workdir
rem  (bukan ke profil pengguna / disk C). Dipanggil oleh setup, download_model, train, run_server.
rem  Aman dipanggil berkali-kali. Folder .workdir tidak ikut git.
rem ============================================================================
set "WORK=%~dp0.workdir"
for %%D in (tmp hf torch cuda triton pycache pip cache) do if not exist "%WORK%\%%D" mkdir "%WORK%\%%D"
set "TEMP=%WORK%\tmp"
set "TMP=%WORK%\tmp"
set "TMPDIR=%WORK%\tmp"
set "HF_HOME=%WORK%\hf"
set "HF_HUB_CACHE=%WORK%\hf\hub"
set "TORCH_HOME=%WORK%\torch"
set "XDG_CACHE_HOME=%WORK%\cache"
set "TRITON_CACHE_DIR=%WORK%\triton"
set "CUDA_CACHE_PATH=%WORK%\cuda"
set "PYTORCH_KERNEL_CACHE_PATH=%WORK%\torch"
set "PIP_CACHE_DIR=%WORK%\pip"
set "PYTHONPYCACHEPREFIX=%WORK%\pycache"
set "PYTHONUTF8=1"
