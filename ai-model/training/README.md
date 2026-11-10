# Training chatbot EROganizer (LoRA; model dasar bawaan Qwen2.5-0.5B-Instruct)

Cara tercepat: `train.bat` di folder `ai-model` (panduan ringkas ada di `ai-model/README.md`). Dokumen ini berisi detail data dan training. Perintah manual dijalankan dari folder `ai-model` memakai Python di `venv`; jalankan `call env.bat` dulu supaya cache tidak masuk ke disk C.

## Struktur

```
training/
  system_prompt.txt        prompt sistem (HARUS sama saat training, evaluasi, dan di aplikasi)
  data/rooms.json          data ruangan (sumber tunggal; di-seed ke tabel `rooms`)
  datasets/
    train/  <kategori>.jsonl     data latih, dipisah per tipe pertanyaan
    eval/   <kategori>.jsonl     data uji (kerangka kalimat BERBEDA dari train)
    eval/10_adhoc_natural.jsonl  pertanyaan alami tulisan tangan (tidak pernah dipakai training)
  scripts/                 pembangkit dataset, train.py, evaluate.py, peek.py, stats.py, modelutil.py, check_model.py, download_model.py, probe.py, probe_calls.py
  output/<run>/adapter     hasil training (adapter LoRA) + train.log + train_log.json
  reports/<tag>/           hasil evaluasi: report.md (daftar kegagalan), summary.json, results.jsonl
```

## Kategori dataset (tiap file = satu tipe pertanyaan)

| File | Isi | Keluaran model |
|---|---|---|
| `01_room_search` | cari ruangan (kapasitas/lokasi/fasilitas/jenis) & info satu ruangan | `list_rooms` / `room_info` |
| `02_room_availability` | "ruangan X kosong tanggal/jam ..." | `check_availability` |
| `03_booking_create` | membuat booking (info lengkap, termasuk catatan) | `book_room` |
| `04_my_bookings` | "apa saja ruangan yang saya pinjam" (filter status/periode) | `my_bookings` |
| `05_booking_cancel` | membatalkan booking | `cancel_booking` |
| `06_slot_filling` | multi-giliran: model bertanya satu hal yang kurang, lalu memanggil tool | pertanyaan / tool call |
| `07_tool_results` | hasil tool (role `tool`) -> jawaban jujur sesuai data & pesan error aplikasi | teks |
| `08_faq` | panduan penggunaan, status, aturan, sapaan | teks |
| `09_out_of_scope` | fitur admin, data orang lain, di luar topik, fitur belum ada, prompt injection | teks (menolak sopan) |

Format satu baris JSONL: `{"id", "category", "messages": [system, user, assistant, tool, ...], "meta": {"expect": ...}}`.
Tool call = satu JSON: `{"tool": "book_room", "args": {"room": "Aula Utama", "date_text": "besok", "start_time": "09:00", "end_time": "11:00", "purpose": "Rapat himpunan"}}`.

Aturan penting: `date_text` TIDAK dihitung model (diambil dari ucapan pengguna, dinormalisasi: "bsk" -> "besok", "tgl 5 nov" -> "5 november");
tanggal sebenarnya dihitung kode backend. Jam dinormalisasi ke `HH:MM` (24 jam) atau `duration_minutes`.

## Siklus training

1. Ubah/tambah data di `scripts/gen_*.py` (kerangka kalimat TRAIN saja; jangan menyalin kalimat eval/adhoc ke train).
2. `venv\Scripts\python.exe training\scripts\build.py`   -> membangun ulang `datasets/` (+ membuang train yang identik dengan eval)
3. `venv\Scripts\python.exe training\scripts\train.py --run-name runNN --epochs 3`
4. `venv\Scripts\python.exe training\scripts\evaluate.py --tag runNN --adapter training\output\runNN\adapter`
5. Baca `reports/runNN/report.md` (bagian "Kegagalan / tanda halusinasi") -> kembali ke langkah 1.

Alat bantu: `peek.py 03 6 train` (lihat sampel), `stats.py` (statistik token & uji render), `php artisan db:seed --class=RoomSeeder` (isi tabel rooms dari rooms.json),
`demo.py` (percakapan end-to-end dengan backend TIRUAN: `demo.py --adapter training\output\runNN\adapter --out training\reports\demo_runNN.md`).

## Menjalankan training/evaluasi agar tahan sesi & hemat disk C

- `env.bat` (di folder ai-model) mengalihkan TEMP, cache HuggingFace/PyTorch/Triton/CUDA/pip ke `ai-model\.workdir`, bukan ke disk C. Semua file `.bat` memanggilnya otomatis.
  Untuk perintah manual: `call env.bat` sebelum menjalankan python.
- `scripts\diskmon.ps1` mencatat ruang kosong C dan D tiap 3 detik ke `.workdir\diskmon.csv` (untuk mencari tahu siapa yang menghabiskan disk C).
- Proses yang dijalankan dari sesi chat ikut mati saat sesi habis. Untuk training panjang, jalankan lewat Windows Task Scheduler
  (`Register-ScheduledTask` dengan `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries`), lalu hapus task-nya setelah selesai.
- Tutup layanan AI (port 8001) sebelum training (`train.bat` menolak berjalan bila port itu aktif): VRAM 8 GB habis terpakai (`--tokens-per-batch 2400 --accum 3` menjaga puncak di ±7,2 GB).

## Catatan evaluasi

- Perbandingan antar-run hanya adil jika diuji pada set uji yang SAMA (jalankan ulang `evaluate.py` untuk run lama setelah `build.py` mengubah set uji).
- Set uji berisi 276 soal, jadi selisih 1-2 poin persentase masih dalam batas derau; baca daftar kegagalan di `reports\<run>\report.md`, jangan hanya angka total.
- Kriteria penilaian otomatis (`must`/`must_not`) bisa terlalu kaku atau salah; periksa kegagalan secara manual sebelum menyimpulkan.


## Penting

- Isi FAQ/penolakan mengikuti perilaku aplikasi SAAT INI (mis. ruangan berstatus `booked` tidak bisa dipesan lagi, tidak ada fitur edit booking
  atau reset password). Jika aplikasi berubah, perbarui data lalu training ulang.
- Jika daftar ruangan di database berubah, perbarui `data/rooms.json` dan `system_prompt.txt` (daftar nama), lalu bangun ulang dan latih ulang.
## Status layanan chatbot & hasil terakhir

- Terpasang: `server.py` memuat adapter (default `run05`, ganti lewat `CHATBOT_ADAPTER_DIR`); `app/Services/Chatbot/ChatbotService.php` menyusun prompt dari `system_prompt.txt` + nama ruangan di DB dan mengatur putaran tool call; `ToolExecutor.php` menjalankan tool call ke database atas nama pengguna yang login (model hanya MENGUSULKAN tool call). Bentuk hasil tool (kunci, kode error, urutan kunci, gaya JSON Python) HARUS sama dengan `scripts/gen_results.py`.
- Generasi di produksi harus sama dengan saat evaluasi: greedy (`temperature 0`), `repetition_penalty 1.0`. Sampling/penalti merusak JSON tool call.
- Hasil pada set uji yang sama (286 soal, kriteria `must` diperketat): run04 266/286 (93,0%), run05 277/286 (96,9%). Adhoc 58/63 -> 61/63; `booking_saya` 2/4 -> 4/4. Sisa kegagalan run05 ada di `reports\run05\report.md`.
- Uji (jalankan setelah mengubah `ToolExecutor` atau data):
  - `php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_executor_sqlite.php` (30 uji aturan bisnis, SQLite sementara, tanpa model)
  - `php ai-model\tests\test_location_filter.php` (filter lokasi/lantai, tanpa DB)
  - `php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_room_seeder.php` (RoomSeeder + perakitan system prompt dari DB)
  - `venv\Scripts\python.exe tests\test_modelutil.py` (deteksi penanda giliran asisten lintas-model; tanpa GPU, dijalankan dari folder ai-model)
  - `venv\Scripts\python.exe training\scripts\probe.py` dan `probe_calls.py` (jawaban dari hasil tool rekayasa; keputusan tool call per adapter)
  - `php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\e2e_sqlite.php http://127.0.0.1:8001 [user_id]` (alur penuh dengan model + SQLite) atau `e2e_laravel.php` (ke MySQL, semua perubahan di-rollback)
- Celah yang diketahui (bahan run06):
  - Data training tidak mengenal LANTAI (nilai `location` hanya Gedung A/B/Perpustakaan): model mengarang argumen (`floor`, `building`, `keyword: "lantai 1"`, `min_capacity: 1` untuk "lt 1"). Ditambal di `ToolExecutor` (parseListFilters + membaca lantai/gedung dari pesan pengguna), bukan di model. Tambahkan contoh lantai (nilai "Lt.1") ke `gen_tools.py`.
  - `filters_text()` membocorkan nama field ("location") pada jawaban hasil kosong; buat bahasa natural.
  - Aplikasi tidak pernah mengubah booking menjadi `completed`; `ToolExecutor` memperlakukan "selesai" sebagai approved yang sudah berakhir.
  - Satu booking aktif membuat SELURUH ruangan `booked` (aturan aplikasi), sehingga jumlah ruangan tersedia cepat turun; chatbot hanya mencerminkan aturan itu.
- JANGAN menjalankan training bersamaan dengan layanan AI: RAM 16 GB dan VRAM 8 GB habis, memori virtual tinggal sekitar 1 GB, Windows membengkakkan pagefile di disk C (sekitar 8 GB) dan training melambat 2,5x. Tutup layanan dulu dan pakai `--tokens-per-batch 2400 --accum 3`.
- `config/app.php` memakai timezone UTC, sedangkan jam booking disimpan sebagai jam dinding WIB. Chatbot memakai `CHATBOT_TIMEZONE=Asia/Jakarta`; pengecekan "waktu sudah lewat" pada form web masih memakai UTC.

