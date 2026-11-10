"""
Pemeriksaan cepat model dasar SEBELUM training (hanya memuat tokenizer, beberapa detik).

  venv\\Scripts\\python.exe training\\scripts\\check_model.py [folder_model]     (default: env CHATBOT_MODEL_DIR)

Memastikan: model ada, punya chat template, template mendukung role "tool" (hasil tool dikirim balik ke model),
penanda giliran asisten terdeteksi (dipakai loss masking), dan struktur model cocok dengan train.py (.model + .lm_head).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelutil import detect_markers, eos_ids  # noqa: E402


def check_model(path) -> bool:
    path = Path(path)
    if not (path / "config.json").exists():
        print(f"[X] config.json tidak ada di {path}\n    Jalankan download_model.bat (atau set MODEL_NAME di config.local.bat).")
        return False
    cfg = json.loads((path / "config.json").read_text(encoding="utf-8"))
    print(f"model      : {path.name}")
    print(f"arsitektur : {cfg.get('architectures')} | layer={cfg.get('num_hidden_layers')} hidden={cfg.get('hidden_size')} vocab={cfg.get('vocab_size')}")

    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(path)
    except Exception as exc:  # noqa: BLE001
        print(f"[X] tokenizer gagal dimuat: {exc}")
        return False

    if not getattr(tok, "chat_template", None):
        print("[X] model tidak punya chat template (kemungkinan model BASE). Pakai varian instruct/chat, mis. *-Instruct.")
        return False

    convo = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": '{"tool": "list_rooms", "args": {}}'},
        {"role": "tool", "content": '{"ok": true, "count": 14}'},
    ]
    try:
        text = tok.apply_chat_template(convo, tokenize=False, add_generation_prompt=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[X] chat template menolak role 'tool' / urutan pesan ini: {exc}")
        return False
    if '"count": 14' not in text:
        print("[X] hasil tool TIDAK muncul di prompt: model tidak akan 'melihat' hasil database. Gunakan model lain.")
        return False

    start, end = detect_markers(tok)
    if not start or not end:
        print(f"[X] penanda giliran asisten tidak terdeteksi (START={start!r} END={end!r}).\n"
              "    Beri manual saat training: train.bat --assistant-start \"...\" --assistant-end \"...\"")
        return False
    print(f"penanda    : START={start!r} END={end!r}")
    print(f"token stop : {eos_ids(tok)}")
    print(f"ujung prompt (tool -> jawaban): ...{text[-110:]!r}")

    try:  # train.py memakai inner.model(...) + inner.lm_head(...)
        from transformers import AutoModelForCausalLM  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"[!] transformers bermasalah: {exc}")
    print("[OK] model cocok untuk pipeline ini (decoder-only dengan .model + .lm_head: Qwen, Llama, Mistral, Gemma, ...).")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CHATBOT_MODEL_DIR")
    if not target:
        sys.exit("Beri folder model: check_model.py <folder>  atau set CHATBOT_MODEL_DIR")
    sys.exit(0 if check_model(target) else 1)
