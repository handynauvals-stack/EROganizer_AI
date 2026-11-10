"""
Probe keputusan tool call (tanpa database) untuk BEBERAPA adapter sekaligus, greedy seperti di produksi.
  venv\\Scripts\\python.exe training\\scripts\\probe_calls.py <run_a> <run_b>   (nama folder di training\\output)
"""
import sys
import os
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import SYSTEM_PROMPT  # noqa: E402

MODEL_DIR = Path(os.environ.get("CHATBOT_MODEL_DIR") or HERE.parents[1] / "models" / "Qwen2.5-0.5B-Instruct")
OUT = HERE.parent / "output"
QUESTIONS = [
    "Ada berapa ruangan lantai 1 yang bisa saya booking?",
    "Ruangan apa saja yang ada di lantai 2?",
    "Ada ruangan kosong di Gedung A lantai 1?",
    "Ruang di Gedung B yang tersedia apa saja?",
    "Cari ruangan di lt 1",
    "ruangan lantai satu yang bisa dipakai?",
    "Ada ruang diskusi di lantai 2 gedung A?",
    "Ada berapa ruangan yang saya booking?",
    "Booking saya yang sudah lewat apa saja?",
    "Booking saya yang sudah selesai apa saja?",
]

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
eos = [tok.convert_tokens_to_ids("<|im_end|>"), tok.eos_token_id]
dev = "cuda" if torch.cuda.is_available() else "cpu"

for name in sys.argv[1:]:
    base = AutoModelForCausalLM.from_pretrained(MODEL_DIR, dtype=torch.bfloat16 if dev == "cuda" else torch.float32).to(dev)
    model = PeftModel.from_pretrained(base, str(OUT / name / "adapter")).merge_and_unload().eval()
    print(f"\n######## {name}")
    for q in QUESTIONS:
        text = tok.apply_chat_template([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": q}], tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(dev)
        with torch.inference_mode():
            out = model.generate(**ids, max_new_tokens=120, do_sample=False, repetition_penalty=1.0, eos_token_id=eos, pad_token_id=tok.eos_token_id)
        print(f"- {q}\n    -> {tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()}")
    del model, base
    torch.cuda.empty_cache()
