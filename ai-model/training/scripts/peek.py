"""Melihat sampel dataset. Pakai: peek.py <awalan_kategori> [jumlah] [train|eval] [seed]   contoh: peek.py 03 6 train"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
prefix = sys.argv[1] if len(sys.argv) > 1 else "01"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
split = sys.argv[3] if len(sys.argv) > 3 else "train"
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1

for path in sorted((ROOT / "datasets" / split).glob(f"{prefix}*.jsonl")):
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    print(f"===== {path.name} ({len(rows)} contoh) =====")
    for r in random.Random(seed).sample(rows, min(n, len(rows))):
        print("--")
        for m in r["messages"][1:]:
            tag = {"user": "U", "assistant": "A", "tool": "T"}[m["role"]]
            print(f"  {tag}: {m['content']}")
