# EROganizer

Aplikasi peminjaman ruangan fakultas (*Faculty Room Organizer*) berbasis **Laravel 12 + MySQL**, dengan **asisten chatbot AI** (Qwen2.5 + LoRA) yang menjawab dan bertindak langsung di database:

- **Member** memesan ruangan, melihat dan membatalkan bookingnya sendiri.
- **Admin** mengelola ruangan, ketersediaan, dan status booking.
- **Chatbot** memahami kalimat seperti *"Ada berapa ruangan lantai 1 yang kosong?"*, *"Pinjam Aula Utama besok jam 9 sampai 11 buat rapat"*, atau *"Batalkan booking saya di Lab Komputer 1"*, lalu menjalankannya ke database atas nama pengguna yang login.

## Cara kerja chatbot

```
Browser ──► Laravel (login, widget chat) ──► MySQL
               │  ChatbotService + ToolExecutor
               ▼
        ai-model (FastAPI :8001)  ── Qwen2.5 + adapter LoRA
```

1. Pengguna mengetik di widget chat; Laravel merakit prompt dari `ai-model/training/system_prompt.txt` + nama ruangan di database.
2. Model **hanya mengusulkan** tool call berbentuk JSON, mis. `{"tool": "list_rooms", "args": {"location": "Lantai 1"}}`.
3. `ToolExecutor` (Laravel) menjalankannya ke MySQL **atas nama pengguna yang sedang login** (identitas tidak pernah diambil dari keluaran model) dengan aturan bisnis yang sama seperti halaman web, lalu hasilnya dikirim balik ke model.
4. Model menjelaskan hasilnya dengan bahasa natural.

## Mulai cepat

**Prasyarat:** Windows 10/11, PHP 8.2+, Composer, Node.js LTS, MySQL 8, Python 3.10–3.13, dan (untuk training) GPU NVIDIA dengan sekitar 8 GB VRAM. Di Windows paling mudah memakai **Laragon** (PHP, MySQL, Composer, Node sekaligus): buka *Laragon Terminal* agar `php` dan `composer` dikenali.

### 1. Download repo dan siapkan Laravel + MySQL

```bat
git clone https://github.com/handynauvals-stack/EROganizer_AI.git
cd EROganizer_AI
```

Nyalakan MySQL, lalu buat database kosong bernama `eroganizer` (nama dan kredensial lain boleh; sesuaikan `DB_*` di `.env` setelah langkah berikut):

```bat
mysql -u root -e "CREATE DATABASE IF NOT EXISTS eroganizer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
setup_laravel.bat
```

`setup_laravel.bat` menjalankan `composer install`, membuat `.env`, `APP_KEY`, dan aset front-end, lalu menawarkan `php artisan migrate --seed` (mengisi akun demo dan 15 ruangan). Bila MySQL Anda memakai port/kata sandi lain, edit `DB_*` di `.env` **sebelum** menjawab `Y`.

### 2. Pasang model AI

```bat
cd ai-model
setup.bat
download_model.bat
```

`setup.bat` membuat lingkungan Python (`setup.bat cpu` bila tanpa GPU NVIDIA). `download_model.bat` mengunduh **Qwen2.5-0.5B-Instruct** (±1 GB); model lain: `download_model.bat Qwen/Qwen2.5-1.5B-Instruct` ([panduan model lain](ai-model/README.md#memakai-model-lain)).

### 3. Latih model

```bat
train.bat
```

Membangun dataset (otomatis, sintetis), melatih adapter LoRA (±20 menit di RTX 3070 Laptop 8 GB), lalu mengevaluasi. Pengaturan (epoch, ukuran batch, model, nama hasil) ada di `ai-model/config.bat`; untuk konfigurasi model/GPU yang berbeda, ada jalur manual lewat CMD di [`ai-model/README.md`](ai-model/README.md#jalur-manual-lewat-cmd-tanpa-bat). **Tutup layanan AI sebelum training.**

### 4. Jalankan semuanya

```bat
cd ..
start_all.bat
```

Memeriksa MySQL, lalu membuka Laravel (`http://127.0.0.1:8000`) dan layanan AI (`http://127.0.0.1:8001`) di jendela masing-masing. MySQL sendiri dinyalakan lewat Laragon/XAMPP/Docker. Tanpa AI: `start_all.bat noai` (chatbot menampilkan *Offline*).

**Akun demo** (dari seeder; **ganti sebelum dipasang di server publik**): admin `admin@eroganizer.com` / `password123`, member `john@example.com` / `password`.

## Struktur repo

```
EROganizer/
├── app/ config/ database/ resources/ routes/ public/ tests/   # aplikasi Laravel
│   ├── app/Services/Chatbot/      # ChatbotService (alur chat) + ToolExecutor (menjalankan tool call ke DB)
│   ├── config/chatbot.php         # pengaturan chatbot (URL layanan AI, zona waktu, ...)
│   └── database/seeders/RoomSeeder.php   # isi ruangan dari ai-model/training/data/rooms.json
├── ai-model/                      # layanan AI + training  → lihat ai-model/README.md
├── setup_laravel.bat              # sekali: dependensi, .env, key, aset, migrate+seed
├── start_all.bat                  # jalankan Laravel + layanan AI
└── Dockerfile                     # build deployment web (tanpa layanan AI)
```

## Pengujian

Tidak butuh MySQL maupun GPU kecuali disebutkan:

```bat
php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_executor_sqlite.php
php ai-model\tests\test_location_filter.php
php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_room_seeder.php
cd ai-model & venv\Scripts\python.exe tests\test_modelutil.py
```

Uji alur penuh dengan model sungguhan (butuh GPU dan layanan AI menyala): `ai-model\tests\e2e_sqlite.php` (database SQLite sementara) atau `e2e_laravel.php` (ke MySQL Anda; semua perubahan di-*rollback*).

## Pemecahan masalah

| Gejala | Penyebab / solusi |
|---|---|
| Chat: "Asisten AI sedang tidak aktif" | Layanan AI belum jalan atau port beda. Jalankan `ai-model\run_server.bat`; `CHATBOT_URL` di `.env` harus sama dengan `SERVER_PORT` (bawaan 8001). |
| `run_server.bat`: "Adapter belum ada" | Belum training, atau `RUN_NAME` tidak cocok dengan folder di `ai-model\training\output\`. |
| `php` / `composer` tidak dikenali | Buka lewat Laragon Terminal atau tambahkan PHP ke `PATH`. |
| `start_all.bat`: MySQL tidak terdeteksi | Nyalakan MySQL; cek `DB_HOST`/`DB_PORT` di `.env` (Laragon sering memakai 3306, bisa juga 3307). |
| Training: out of memory | Di `config.local.bat`: `TOKENS_PER_BATCH=1200` dan `ACCUM=6` (batch efektif sama, VRAM turun dari ±7 GB ke ±4 GB). |
| Disk C membengkak saat training | Jangan jalankan training bersamaan dengan layanan AI (Windows membengkakkan *pagefile*). Semua cache sudah dialihkan ke `ai-model\.workdir` oleh `env.bat`. |
| Jawaban chatbot janggal | Model 0,5B tetap bisa keliru; lihat [`ai-model/training/README.md`](ai-model/training/README.md) bagian *Celah yang diketahui*. Kesalahan argumen yang umum (mis. lantai) sudah ditambal di `ToolExecutor`. |

## Catatan penting

- **Keamanan:** layanan AI (`:8001`) tidak punya autentikasi dan hanya boleh dipanggil dari server Laravel (di-*bind* ke `127.0.0.1`). Jangan membukanya ke jaringan publik. Endpoint chat di Laravel mensyaratkan login.
- **Aturan aplikasi yang dicerminkan chatbot:** satu booking aktif membuat seluruh ruangan berstatus *booked*, sehingga jumlah ruangan "kosong" cepat turun. Chatbot hanya mengikuti aturan ini, bukan menciptakannya.
- **Zona waktu:** `config/app.php` memakai UTC, sedangkan jam booking disimpan sebagai jam dinding WIB; chatbot memakai `CHATBOT_TIMEZONE=Asia/Jakarta`.
- **Deployment:** `Dockerfile` hanya membangun aplikasi web. Layanan AI dijalankan terpisah di mesin ber-Python/GPU.

Dibangun dengan [Laravel](https://laravel.com) (MIT).
