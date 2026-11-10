@echo off
rem ============================================================================
rem  start_all.bat - jalankan Laravel dan layanan AI, masing-masing di jendela sendiri.
rem  MySQL TIDAK dijalankan di sini (nyalakan lewat Laragon/XAMPP/Docker); skrip hanya memeriksa bahwa MySQL bisa dihubungi.
rem
rem    start_all.bat            Laravel (http://127.0.0.1:8000) + layanan AI (http://127.0.0.1:8001)
rem    start_all.bat noai       Laravel saja (chatbot menampilkan Offline)
rem    set FORCE=1              lanjut walau MySQL tidak terdeteksi    set DRY_RUN=1   hanya cetak perintah
rem ============================================================================
setlocal
cd /d "%~dp0"
set "START=start"
if defined DRY_RUN set "START=echo [dry-run] start"

where php >nul 2>nul
if errorlevel 1 goto :no_php
if not exist ".env" goto :no_env

rem --- baca alamat MySQL dari .env
set "DB_HOST=127.0.0.1"
set "DB_PORT=3306"
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"DB_HOST=" ".env"') do set "DB_HOST=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"DB_PORT=" ".env"') do set "DB_PORT=%%B"

if defined FORCE goto :launch
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $a = $c.BeginConnect('%DB_HOST%', %DB_PORT%, $null, $null); if ($a.AsyncWaitHandle.WaitOne(2000) -and $c.Connected) { exit 0 } else { exit 1 } } catch { exit 1 } finally { $c.Close() }"
if errorlevel 1 goto :no_mysql

:launch
if defined FORCE goto :skipmsg
echo MySQL terdeteksi di %DB_HOST%:%DB_PORT%
goto :go
:skipmsg
echo Pemeriksaan MySQL dilewati - FORCE=1
:go
%START% "EROganizer - Laravel" cmd /k php artisan serve --host=127.0.0.1 --port=8000
if /i "%~1"=="noai" goto :done_noai
%START% "EROganizer - AI model" cmd /k "ai-model\run_server.bat"

echo.
echo Laravel : http://127.0.0.1:8000
echo AI      : http://127.0.0.1:8001  (jendela terpisah; model butuh beberapa detik untuk siap)
echo Tutup jendela masing-masing atau tekan Ctrl+C di dalamnya untuk menghentikan.
exit /b 0

:done_noai
echo.
echo Laravel : http://127.0.0.1:8000   (tanpa layanan AI: chatbot akan menampilkan Offline)
exit /b 0

:no_php
echo [ERROR] PHP tidak ditemukan di PATH. Buka lewat Laragon Terminal atau tambahkan PHP ke PATH.
exit /b 1
:no_env
echo [ERROR] File .env belum ada. Jalankan setup_laravel.bat dulu.
exit /b 1
:no_mysql
echo [ERROR] MySQL tidak bisa dihubungi di %DB_HOST%:%DB_PORT% (sesuai .env).
echo         Nyalakan MySQL dulu lewat Laragon atau XAMPP, atau Docker. Contoh Docker:
echo         docker run -d --name eroganizer-mysql -p 3306:3306 -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=eroganizer mysql:8
echo         Lanjut tanpa pemeriksaan: set FORCE=1
exit /b 1
