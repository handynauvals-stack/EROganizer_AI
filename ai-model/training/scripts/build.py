"""
Membangun dataset EROganizer ke training/datasets/{train,eval}/<kategori>.jsonl

Pakai:  venv\\Scripts\\python.exe training\\scripts\\build.py [--seed 7]
Eval dibangun lebih dulu dengan kerangka kalimat/tujuan/catatan yang BERBEDA dari train, lalu contoh train
yang pertanyaannya identik dengan eval otomatis dibuang (tidak ada kebocoran).
"""
import argparse
import json
import random
import re
import shutil

import adhoc
import gen_results as gr
import gen_slots as gs
import gen_text as gx
import gen_tools as gt
from common import ROOT, last_user, write_jsonl

OUT = ROOT / "datasets"

COUNTS = {
    "train": {"room_list": 160, "room_info": 200, "availability": 250, "booking": 600, "my": 260, "cancel": 110, "slots": 850,
              "res": {"list": 200, "info": 170, "avail": 80, "book": 130, "my": 150, "cancel": 70}, "faq": None, "oos": None},
    "eval": {"room_list": 12, "room_info": 14, "availability": 18, "booking": 28, "my": 14, "cancel": 14, "slots": 30,
             "res": {"list": 8, "info": 8, "avail": 6, "book": 8, "my": 8, "cancel": 3}, "faq": 28, "oos": 24},
}


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def build_split(split, seed, blocked):
    rng = random.Random(f"{seed}-{split}")
    c = COUNTS[split]
    rs = gt.gen_room_search(rng, split, c["room_list"], c["room_info"])
    cats = {
        "01_room_search": rs,
        "02_room_availability": gt.gen_availability(rng, split, c["availability"]),
        "03_booking_create": gt.gen_booking(rng, split, c["booking"]),
        "04_my_bookings": gt.gen_my_bookings(rng, split, c["my"]),
        "05_booking_cancel": gt.gen_cancel(rng, split, c["cancel"]),
        "06_slot_filling": gs.gen_slot_filling(rng, split, c["slots"]),
        "07_tool_results": gr.gen_tool_results(rng, split, c["res"]),
        "08_faq": gx.gen_faq(rng, split, c["faq"]),
        "09_out_of_scope": gx.gen_oos(rng, split, c["oos"]),
    }
    kept = {}
    for name, rows in cats.items():
        if blocked:
            before = len(rows)
            rows = [r for r in rows if norm(last_user(r)) not in blocked]
            if len(rows) != before:
                print(f"  [{split}] {name}: {before - len(rows)} contoh dibuang karena identik dengan eval")
        kept[name] = rows
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    for sub in ("train", "eval"):
        d = OUT / sub
        if d.exists():
            shutil.rmtree(d)

    eval_sets = build_split("eval", args.seed, set())
    blocked = {norm(last_user(r)) for rows in eval_sets.values() for r in rows}
    blocked |= {norm(last_user(r)) for r in adhoc.build()}  # set adhoc juga tidak boleh bocor ke train
    train_sets = build_split("train", args.seed, blocked)

    for split, sets in (("train", train_sets), ("eval", eval_sets)):
        for name, rows in sets.items():
            write_jsonl(OUT / split / f"{name}.jsonl", rows, f"{name}-{split}")
    adhoc_rows = adhoc.build()
    write_jsonl(OUT / "eval" / "10_adhoc_natural.jsonl", adhoc_rows, "10_adhoc_natural-eval")

    print(f"\n{'kategori':<26}{'train':>7}{'eval':>7}")
    tt = te = 0
    for name in train_sets:
        print(f"{name:<26}{len(train_sets[name]):>7}{len(eval_sets[name]):>7}")
        tt += len(train_sets[name])
        te += len(eval_sets[name])
    print(f"{'10_adhoc_natural':<26}{0:>7}{len(adhoc_rows):>7}")
    print(f"{'TOTAL':<26}{tt:>7}{te + len(adhoc_rows):>7}")


if __name__ == "__main__":
    main()
