@echo off
rem ============================================================================
rem  setup_laravel.bat - SEKALI SAJA setelah clone: dependensi Laravel, .env, APP_KEY, aset front-end, database.
rem
rem    setup_laravel.bat            lalu menanyakan apakah migrate + seed dijalankan sekarang
rem    setup_laravel.bat migrate    langsung migrate + seed tanpa bertanya
rem    set DRY_RUN=1                hanya mencetak perintah (uji)
rem
rem  Prasyarat: PHP 8.2+, Composer, Node.js. Di Windows paling mudah lewat Laragon (buka Laragon Terminal).
rem  Untuk langkah database: MySQL sudah menyala, .env sudah benar, dan database kosong sudah dibuat.
rem ============================================================================
setlocal
cd /d "%~dp0"
set "RUN="
if defined DRY_RUN set "RUN=echo [dry-run]"

where php >nul 2>nul
if errorlevel 1 goto :no_php
where composer >nul 2>nul
if errorlevel 1 goto :no_composer
where npm >nul 2>nul
if errorlevel 1 goto :no_npm

echo [1/5] composer install
%RUN% call composer install --no-interaction
if errorlevel 1 goto :fail

if exist ".env" goto :have_env
echo [2/5] Membuat .env dari .env.example
%RUN% copy ".env.example" ".env" >nul
goto :key
:have_env
echo [2/5] .env sudah ada - dilewati.

:key
findstr /B /C:"APP_KEY=base64:" ".env" >nul 2>nul
if not errorlevel 1 goto :have_key
echo [3/5] Membuat APP_KEY
%RUN% php artisan key:generate --ansi
if errorlevel 1 goto :fail
goto :assets
:have_key
echo [3/5] APP_KEY sudah ada - dilewati, tidak dibuat ulang.

:assets
echo [4/5] npm ci dan build aset front-end
%RUN% call npm ci
if errorlevel 1 goto :fail
%RUN% call npm run build
if errorlevel 1 goto :fail

echo [5/5] Database
echo       Pastikan MySQL menyala, DB_* di .env benar, dan database sudah dibuat. Contoh perintahnya:
echo       mysql -u root -e "CREATE DATABASE IF NOT EXISTS eroganizer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
if /i "%~1"=="migrate" goto :migrate
choice /c YN /m "Jalankan migrate dan seed sekarang"
if errorlevel 2 goto :skip_db
:migrate
%RUN% php artisan migrate --seed
if errorlevel 1 goto :fail_db
goto :done
:skip_db
echo       Dilewati. Jalankan nanti:  php artisan migrate --seed

:done
echo.
echo Selesai. Akun demo setelah seed:
echo   admin  admin@eroganizer.com / password123
echo   member john@example.com / password
echo Berikutnya: siapkan AI di folder ai-model lalu jalankan start_all.bat. Ganti kredensial demo bila dipasang di server publik.
exit /b 0

:no_php
echo [ERROR] PHP tidak ditemukan di PATH. Buka lewat Laragon Terminal atau tambahkan PHP 8.2+ ke PATH.
exit /b 1
:no_composer
echo [ERROR] Composer tidak ditemukan di PATH. Pasang dari getcomposer.org atau pakai Laragon Terminal.
exit /b 1
:no_npm
echo [ERROR] Node.js/npm tidak ditemukan di PATH. Pasang Node.js LTS dari nodejs.org.
exit /b 1
:fail_db
echo.
echo [ERROR] migrate/seed gagal. Biasanya MySQL belum menyala, DB_* di .env salah, atau database belum dibuat.
exit /b 1
:fail
echo.
echo [ERROR] Langkah di atas gagal. Baca pesan error-nya.
exit /b 1
