"""
Mengunduh model dasar dari Hugging Face ke ai-model/models/<nama> lalu memeriksanya (check_model.py).

  venv\\Scripts\\python.exe training\\scripts\\download_model.py                              (default dari config.bat)
  venv\\Scripts\\python.exe training\\scripts\\download_model.py Qwen/Qwen2.5-1.5B-Instruct   (model lain; folder = nama repo)
  venv\\Scripts\\python.exe training\\scripts\\download_model.py <repo> <nama_folder>

Model yang butuh login/persetujuan (gated, mis. Llama): set HF_TOKEN=hf_xxx lebih dulu.
Setelah mengunduh model BARU, tambahkan di config.local.bat:  set "MODEL_NAME=<nama_folder>"
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_model import check_model  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402

AI_DIR = Path(__file__).resolve().parents[2]
arg_repo = sys.argv[1] if len(sys.argv) > 1 else ""
arg_name = sys.argv[2] if len(sys.argv) > 2 else ""

repo = arg_repo or os.environ.get("MODEL_REPO") or "Qwen/Qwen2.5-0.5B-Instruct"
if arg_name:
    name = arg_name
elif arg_repo:
    name = repo.split("/")[-1]  # model lain: folder = nama repo (bukan MODEL_NAME bawaan config)
else:
    name = os.environ.get("MODEL_NAME") or repo.split("/")[-1]
dest = AI_DIR / "models" / name

if (dest / "config.json").exists():
    print(f"Model sudah ada: {dest}  (hapus folder itu bila ingin mengunduh ulang)")
else:
    print(f"Mengunduh {repo} -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo,
        local_dir=str(dest),
        ignore_patterns=["*.gguf", "*.onnx", "*.msgpack", "*.h5", "*.ot", "original/*"],
        token=os.environ.get("HF_TOKEN") or None,
    )
    print("Unduhan selesai.")

print()
ok = check_model(dest)
if name != (os.environ.get("MODEL_NAME") or ""):
    print(f'\nPakai model ini: tambahkan baris berikut di ai-model\\config.local.bat\n    set "MODEL_NAME={name}"')
sys.exit(0 if ok else 1)
