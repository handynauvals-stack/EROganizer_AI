# ai-model — chatbot EROganizer (Qwen + LoRA)

Layanan AI yang dipanggil Laravel. Model bahasa kecil dilatih (LoRA) agar **mengusulkan tool call** (`list_rooms`, `check_availability`, `book_room`, `my_bookings`, `cancel_booking`, ...). Laravel yang menjalankannya ke database atas nama pengguna yang login, lalu hasilnya dikirim balik ke model untuk dijelaskan dengan bahasa natural. Dataset dibangkitkan otomatis (sintetis), **tidak ada data eksternal yang perlu disiapkan**.

## Empat langkah

Jalankan dari folder `ai-model` (klik dua kali atau lewat CMD):

| # | Perintah | Fungsi | Perlu internet |
|---|---|---|---|
| 1 | `setup.bat` | membuat `venv` dan memasang PyTorch + paket Python | ya |
| 2 | `download_model.bat` | mengunduh model dasar ke `models\` lalu memeriksa kecocokannya | ya |
| 3 | `train.bat` | cek model → bangun dataset → training LoRA → evaluasi | tidak |
| 4 | `run_server.bat` | menjalankan layanan AI di `http://127.0.0.1:8001` | tidak |

Setelah itu jalankan `start_all.bat` di folder induk (Laravel + AI sekaligus). Detail Laravel/MySQL ada di `README.md` utama.

`setup.bat` menerima pilihan PyTorch: `setup.bat cu118` (bawaan, cocok untuk hampir semua driver NVIDIA), `cu126`, `cu128`, atau `cpu`.

## Kebutuhan

| | Training | Menjalankan server |
|---|---|---|
| OS | Windows 10/11 (skrip `.bat`; skrip Python bisa dijalankan manual di OS lain) | sama |
| Python | 3.10 – 3.13 | sama |
| GPU | NVIDIA, disarankan 8 GB VRAM (6 GB: turunkan batch, lihat bawah). CPU sangat lambat | opsional; ±2 GB VRAM, bisa di CPU (`set CHATBOT_DEVICE=cpu`) |
| Waktu (acuan) | ±20 menit untuk Qwen2.5-0.5B di RTX 3070 Laptop | model siap dalam beberapa detik |

> **Jangan menjalankan training bersamaan dengan layanan AI.** Keduanya berebut VRAM dan RAM; di Windows ini membuat *pagefile* membengkak di disk C dan training melambat sekitar 2,5 kali. `train.bat` menolak berjalan bila port layanan AI sedang aktif.

## Pengaturan

Semua pengaturan ada di `config.bat`. **Jangan diedit untuk pengaturan pribadi**: salin `config.local.bat.example` menjadi `config.local.bat` (tidak ikut git). Prioritas: variabel yang Anda `set` di CMD → `config.local.bat` → default `config.bat`.

| Variabel | Bawaan | Fungsi |
|---|---|---|
| `MODEL_REPO` / `MODEL_NAME` | `Qwen/Qwen2.5-0.5B-Instruct` / `Qwen2.5-0.5B-Instruct` | model dasar di Hugging Face / nama folder di `models\` |
| `RUN_NAME` | `run1` | nama hasil training → `training\output\<RUN_NAME>\adapter`; **adapter ini juga yang dimuat `run_server.bat`** |
| `EPOCHS`, `LR` | `3`, `2e-4` | jumlah epoch, learning rate |
| `LORA_RANK`, `LORA_ALPHA` | `32`, `64` | ukuran adapter LoRA |
| `TARGET_MODULES` | `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj` | modul yang diberi LoRA; arsitektur lain: `all-linear` |
| `TOKENS_PER_BATCH` × `ACCUM` | `2400` × `3` | batch efektif. Acuan: 2400×3 butuh ±7 GB VRAM; **1200×6 butuh ±4 GB** dengan hasil setara |
| `SERVER_PORT` | `8001` | port layanan AI (samakan dengan `CHATBOT_URL` di `.env` Laravel) |

Contoh sekali pakai tanpa mengubah file (**pakai tanda kutip**; tanpa kutip, `set A=1 & ...` menyimpan spasi di akhir nilai): `set "RUN_NAME=percobaan2" & set "TOKENS_PER_BATCH=1200" & set "ACCUM=6" & train.bat`

Opsi `train.bat` (variabel lingkungan): `SKIP_BUILD=1` (pakai dataset yang ada), `SKIP_EVAL=1`, `OVERWRITE=1`, `FORCE=1`, `DRY_RUN=1` (hanya cetak perintah). Argumen tambahan diteruskan ke `train.py`, mis. `train.bat --epochs 5`.

> **Adapter tidak akan tertimpa.** `train.py` menolak memakai `RUN_NAME` yang sudah berisi adapter, kecuali `--overwrite` / `OVERWRITE=1`. Untuk uji coba, pakai nama baru.

## Memakai model lain

1. `download_model.bat Qwen/Qwen2.5-1.5B-Instruct` — mengunduh dan **langsung memeriksa** model (lihat bawah), lalu menampilkan baris `MODEL_NAME` yang perlu Anda tambahkan ke `config.local.bat`. Model yang butuh persetujuan (mis. Llama): `set HF_TOKEN=hf_xxx` dulu.
2. `set "RUN_NAME=uji" & train.bat --max-steps 5` — **uji cepat 5 langkah**: memastikan model dan GPU Anda cocok sebelum training penuh yang lama.
3. `train.bat` penuh, lalu `run_server.bat`.

Pemeriksaan otomatis (`training\scripts\check_model.py`) memastikan: model punya *chat template*, template menerima role `tool` (hasil database harus terlihat model), penanda giliran asisten terdeteksi, dan struktur model cocok (`decoder-only` dengan `.model` + `.lm_head`: Qwen, Llama, Mistral, Gemma, ...). Penanda giliran asisten (untuk *loss masking*) dan token berhenti **diturunkan dari chat template model**, bukan ditulis khusus untuk Qwen. Bila template tidak punya *generation prompt* dan tidak terdeteksi, beri manual: `train.bat --assistant-start "..." --assistant-end "..."`.

> **Jujur soal pengujian:** hanya **Qwen2.5-0.5B-Instruct** yang diuji end-to-end (training, evaluasi, server). Untuk model lain, deteksi template diuji dengan template Llama-3 dan Gemma *simulasi* (`tests\test_modelutil.py`), belum dengan bobot aslinya. Jalankan langkah 2 dulu dan periksa hasil `evaluate.py`.

## Jalur manual lewat CMD (tanpa `.bat`)

Berguna bila konfigurasi model Anda berbeda. Dari folder `ai-model`:

```bat
call env.bat
rem -- sekali: lingkungan Python
python -m venv venv
venv\Scripts\python.exe -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu118
venv\Scripts\python.exe -m pip install -r requirements.txt

rem -- model
venv\Scripts\python.exe training\scripts\download_model.py Qwen/Qwen2.5-1.5B-Instruct
venv\Scripts\python.exe training\scripts\check_model.py models\Qwen2.5-1.5B-Instruct

rem -- dataset, training, evaluasi
venv\Scripts\python.exe training\scripts\build.py
venv\Scripts\python.exe training\scripts\train.py --run-name percobaan1 --model-dir models\Qwen2.5-1.5B-Instruct --epochs 3 --tokens-per-batch 1200 --accum 6 --target-modules all-linear
venv\Scripts\python.exe training\scripts\evaluate.py --tag percobaan1 --model-dir models\Qwen2.5-1.5B-Instruct --adapter training\output\percobaan1\adapter

rem -- server
set CHATBOT_MODEL_DIR=models\Qwen2.5-1.5B-Instruct
set CHATBOT_ADAPTER_DIR=training\output\percobaan1\adapter
venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8001
```

Semua opsi `train.py`: `venv\Scripts\python.exe training\scripts\train.py --help`.

## Mengubah data ruangan / domain

Daftar ruangan dan system prompt adalah **bagian dari training** (nama ruangan masuk ke prompt):

1. Edit `training\data\rooms.json` (dan `training\system_prompt.txt` bila perlu).
2. `php artisan db:seed --class=RoomSeeder` di folder induk — mengisi ruangan baru ke database dari file yang **sama**, sehingga DB dan model selalu sepakat. Seeder tidak menimpa ruangan yang sudah ada.
3. Latih ulang dengan `RUN_NAME` baru. Prompt yang dilihat model saat dipakai harus identik dengan saat training; Laravel merakitnya dari `system_prompt.txt` + nama ruangan di DB.

## API layanan AI

Hanya untuk Laravel (di-bind ke `127.0.0.1`; **jangan dibuka ke jaringan publik**, tidak ada autentikasi di sini).

- `GET /health` → `{"status":"ok","model":"...","adapter":"<RUN_NAME>","device":"cuda"}`
- `POST /chat` `{"messages":[{"role":"system|user|assistant|tool","content":"..."}], "max_new_tokens":400, "temperature":0}` → `{"reply":"..."}`

`temperature` bawaan **0 (greedy)** dan `repetition_penalty` 1.0, sama seperti saat evaluasi. Sampling atau penalti pengulangan dapat merusak JSON tool call.

## Hasil evaluasi (Qwen2.5-0.5B-Instruct, 286 soal internal)

| | lulus |
|---|---|
| model dasar tanpa training | ±10% |
| `run04` | 266/286 (93,0%) |
| `run05` (dipakai) | 277/286 (96,9%) |

Ini evaluasi internal buatan sendiri (set uji dibangkitkan, bukan benchmark publik). Rincian, celah yang diketahui, dan catatan run berikutnya ada di [`training/README.md`](training/README.md).

## Isi folder

```
ai-model/
├── config.bat  setup.bat  download_model.bat  train.bat  run_server.bat  env.bat
├── config.local.bat.example      # salin → config.local.bat (pribadi, tidak ikut git)
├── requirements.txt   server.py
├── tests/                        # uji PHP dan Python (lihat training/README.md)
├── training/
│   ├── system_prompt.txt  data/rooms.json
│   ├── scripts/                  # pembangkit data, train.py, evaluate.py, check_model.py, ...
│   └── README.md                 # detail data, training, evaluasi
├── models/                       # (tidak ikut git) model dasar hasil download_model.bat
├── training/output/ datasets/ reports/   # (tidak ikut git) adapter, dataset, laporan
├── venv/                         # (tidak ikut git)
└── .workdir/                     # (tidak ikut git) cache & file sementara; semua dialihkan ke sini oleh env.bat
```
