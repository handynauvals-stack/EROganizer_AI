"""
Uji deteksi penanda giliran asisten / token berhenti (modelutil.py) dan check_model.py. Tanpa GPU.

  venv\\Scripts\\python.exe tests\\test_modelutil.py
"""
import os
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "training" / "scripts"))
from check_model import check_model  # noqa: E402
from modelutil import detect_markers, eos_ids  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

MODEL = Path(os.environ.get("CHATBOT_MODEL_DIR") or AI / "models" / "Qwen2.5-0.5B-Instruct")
if not (MODEL / "config.json").exists():
    sys.exit(f"Model tidak ditemukan di {MODEL}: jalankan download_model.bat dulu.")

LLAMA3 = (
    "{{ bos_token }}{% for m in messages %}<|start_header_id|>{{ m['role'] }}<|end_header_id|>\n\n{{ m['content'] }}<|eot_id|>{% endfor %}"
    "{% if add_generation_prompt %}<|start_header_id|>assistant<|end_header_id|>\n\n{% endif %}"
)
GEMMA = (
    "{% for m in messages %}<start_of_turn>{{ 'model' if m['role'] == 'assistant' else m['role'] }}\n{{ m['content'] }}<end_of_turn>\n{% endfor %}"
    "{% if add_generation_prompt %}<start_of_turn>model\n{% endif %}"
)
MISTRAL_LAMA = "{% for m in messages %}{% if m['role'] == 'user' %}[INST] {{ m['content'] }} [/INST]{% else %}{{ m['content'] }}</s>{% endif %}{% endfor %}"

fail = 0


def check(title, ok, detail=""):
    global fail
    fail += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  {title:<62} {detail}")


tok = AutoTokenizer.from_pretrained(MODEL)
s, e = detect_markers(tok)
check("Qwen/ChatML: sama persis dengan konstanta lama (tanpa regresi)", (s, e) == ("<|im_start|>assistant\n", "<|im_end|>"), f"{s!r} {e!r}")
ids = eos_ids(tok)
check("Qwen: token stop mencakup <|im_end|>", tok.convert_tokens_to_ids("<|im_end|>") in ids, str(ids))
check("check_model(Qwen) lulus", check_model(MODEL) is True)

tok.chat_template = LLAMA3
s, e = detect_markers(tok)
check("Llama-3 (simulasi): penanda terdeteksi", (s, e) == ("<|start_header_id|>assistant<|end_header_id|>\n\n", "<|eot_id|>"), f"{s!r} {e!r}")

tok.chat_template = GEMMA
s, e = detect_markers(tok)
check("Gemma (simulasi): penanda terdeteksi", (s, e) == ("<start_of_turn>model\n", "<end_of_turn>"), f"{s!r} {e!r}")

tok.chat_template = MISTRAL_LAMA
s, e = detect_markers(tok)
check("template tanpa generation prompt: START kosong -> ditolak jelas", s == "", f"{s!r} {e!r}")

print("\n" + ("SEMUA LULUS" if fail == 0 else f"{fail} GAGAL"))
sys.exit(0 if fail == 0 else 1)
