"""Statistik token & uji render chat template. Pakai: stats.py"""
import json
import statistics
import os
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
MODEL = Path(os.environ.get("CHATBOT_MODEL_DIR") or ROOT.parent / "models" / "Qwen2.5-0.5B-Instruct")
tok = AutoTokenizer.from_pretrained(MODEL)

for split in ("train", "eval"):
    lens, bad = [], 0
    per_cat = {}
    for path in sorted((ROOT / "datasets" / split).glob("*.jsonl")):
        cat_lens = []
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            try:
                text = tok.apply_chat_template(r["messages"], tokenize=False)
                n = len(tok(text)["input_ids"])
            except Exception as e:  # noqa
                bad += 1
                print("RENDER GAGAL:", path.name, e)
                continue
            lens.append(n)
            cat_lens.append(n)
        per_cat[path.stem] = cat_lens
    lens_sorted = sorted(lens)
    print(f"\n[{split}] contoh={len(lens)} gagal_render={bad} rata2={statistics.mean(lens):.0f} median={statistics.median(lens):.0f} "
          f"p95={lens_sorted[int(len(lens) * .95)]} maks={max(lens)} total_token={sum(lens):,}")
    for k, v in per_cat.items():
        print(f"   {k:<24} n={len(v):<4} rata2={statistics.mean(v):.0f} maks={max(v)}")

sample = json.loads(next(iter((ROOT / "datasets" / "train" / "07_tool_results.jsonl").open(encoding="utf-8"))))
print("\n=== Contoh hasil render chat template (kategori 07) ===")
print(tok.apply_chat_template(sample["messages"], tokenize=False))
