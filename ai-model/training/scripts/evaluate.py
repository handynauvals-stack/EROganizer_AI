"""
Evaluasi model (base atau base+adapter LoRA) pada training/datasets/eval/*.jsonl

Pakai:
  venv\\Scripts\\python.exe training\\scripts\\evaluate.py --tag base                       (model dasar, tanpa adapter)
  venv\\Scripts\\python.exe training\\scripts\\evaluate.py --tag run01 --adapter training\\output\\run01\\adapter

Hasil: training/reports/<tag>/{summary.json, results.jsonl, report.md}
Penilaian:
  - jawaban berupa tool call : JSON valid, nama tool benar, argumen benar (exact; subset untuk set alami)
  - jawaban berupa teks       : bukan JSON, memuat semua kata/fakta wajib (a|b = salah satu), tidak memuat kata terlarang
  - tanda halusinasi          : jam yang tidak ada di data, nama ruangan yang tidak ada di sistem, istilah UI yang tidak ada di aplikasi
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
import os
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL = Path(os.environ.get("CHATBOT_MODEL_DIR") or ROOT.parent / "models" / "Qwen2.5-0.5B-Instruct")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
ROOMS = json.loads((ROOT / "data" / "rooms.json").read_text(encoding="utf-8"))["rooms"]
ROOM_NAMES = [r["name"] for r in ROOMS]
BAD_TERMS = ["book now", "reschedule", "submit booking", "forgot password", "klik edit", "hubungi admin untuk membatalkan"]

ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True)
ap.add_argument("--adapter", default=None)
ap.add_argument("--files", default="", help="awalan nama file dipisah koma, mis. 03,06 (default: semua)")
ap.add_argument("--batch", type=int, default=16)
ap.add_argument("--max-new", type=int, default=300)
ap.add_argument("--model-dir", default=None, help="folder model dasar (default: env CHATBOT_MODEL_DIR atau ../models/Qwen2.5-0.5B-Instruct)")
args = ap.parse_args()
if args.model_dir:
    BASE_MODEL = Path(args.model_dir)

if not (BASE_MODEL / "config.json").exists():
    raise SystemExit(f"Model dasar tidak ditemukan di {BASE_MODEL}\nJalankan download_model.bat (atau set CHATBOT_MODEL_DIR / --model-dir).")
tok = AutoTokenizer.from_pretrained(BASE_MODEL)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "left"
model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=DTYPE).to(DEVICE)
if args.adapter:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
model.eval()
from modelutil import eos_ids  # noqa: E402
EOS = eos_ids(tok, model)

prefixes = [p for p in args.files.split(",") if p]
rows = []
for path in sorted((ROOT / "datasets" / "eval").glob("*.jsonl")):
    if prefixes and not any(path.stem.startswith(p) for p in prefixes):
        continue
    rows += [json.loads(line) for line in path.open(encoding="utf-8")]
print(f"{len(rows)} contoh uji | tag={args.tag} adapter={args.adapter}")


def prompt_of(r):
    msgs = r["messages"]
    return msgs[:-1] if msgs[-1]["role"] == "assistant" else msgs


@torch.inference_mode()
def generate(batch_rows):
    texts = [tok.apply_chat_template(prompt_of(r), tokenize=False, add_generation_prompt=True) for r in batch_rows]
    enc = tok(texts, return_tensors="pt", padding=True).to(DEVICE)
    out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False, eos_token_id=EOS, pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else EOS[0], repetition_penalty=1.0)
    return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip() for o in out]


order = sorted(range(len(rows)), key=lambda i: len(json.dumps(rows[i]["messages"])))
outputs = [None] * len(rows)
t0 = time.time()
for s in range(0, len(order), args.batch):
    idxs = order[s:s + args.batch]
    for i, o in zip(idxs, generate([rows[i] for i in idxs])):
        outputs[i] = o
    print(f"  {min(s + args.batch, len(order))}/{len(order)} selesai ({time.time() - t0:.0f} dtk)", flush=True)


def parse_tool(s):
    s = s.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    return obj if isinstance(obj, dict) and "tool" in obj and isinstance(obj.get("args", {}), dict) else None


def nv(v):
    return v.strip().lower() if isinstance(v, str) else v


def args_ok(pred, gold, mode):
    if mode == "subset":
        return all(nv(pred.get(k)) == nv(v) for k, v in gold.items())
    return {k: nv(v) for k, v in pred.items()} == {k: nv(v) for k, v in gold.items()}


def flat(s):
    return re.sub(r"(\d{1,2}):(\d{2})", r"\1.\2", s).lower()


def must_ok(text, must):
    t = flat(text)
    return [m for m in must if not any(flat(alt) in t for alt in m.split("|"))]


TIME_RE = re.compile(r"\b(\d{1,2})[.:](\d{2})\b")


def halluc_flags(r, out):
    flags = []
    ctx = json.dumps(r["messages"], ensure_ascii=False)
    ctx_times = {f"{int(h):02d}:{m}" for h, m in TIME_RE.findall(ctx)}
    for h, m in TIME_RE.findall(out):
        if f"{int(h):02d}:{m}" not in ctx_times:
            flags.append(f"jam_tidak_ada_di_data:{h}.{m}")
            break
    for name in re.findall(r"\b(?:Ruang(?: Kelas| Seminar| Diskusi| Rapat| Multimedia)?|Lab(?: Komputer| Jaringan)?|Aula(?: Utama)?)\s?(?:Dekanat|[A-Z]?\d+)?", out):
        name = name.strip()
        if name and not any(n.startswith(name) or name.startswith(n) for n in ROOM_NAMES) and name not in ("Ruang", "Lab", "Aula"):
            flags.append(f"ruangan_tidak_dikenal:{name}")
            break
    low = out.lower()
    for b in BAD_TERMS:
        if b in low:
            flags.append(f"istilah_tidak_ada:{b}")
    return flags


results = []
for r, out in zip(rows, outputs):
    e = r["meta"]["expect"]
    res = {"id": r["id"], "category": r["category"], "group": r["meta"].get("group"), "user": next((m["content"] for m in reversed(prompt_of(r)) if m["role"] == "user"), ""),
           "expect": e, "output": out}
    pt = parse_tool(out)
    if e["type"] == "tool":
        res["valid_json"] = pt is not None
        res["tool_ok"] = bool(pt) and pt.get("tool") == e["tool"]
        res["args_ok"] = bool(pt) and res["tool_ok"] and args_ok(pt.get("args", {}), e["args"], e.get("args_mode", "exact"))
        res["pass"] = res["args_ok"]
    else:
        miss = must_ok(out, e["must"])
        bad = [b for b in e["must_not"] if flat(b) in flat(out)]
        res["not_tool"] = pt is None and not out.lstrip().startswith("{")
        res["missing"], res["forbidden"] = miss, bad
        res["pass"] = res["not_tool"] and not miss and not bad
    res["halluc"] = halluc_flags(r, out) if e["type"] == "text" else []
    results.append(res)

by_cat = defaultdict(list)
for x in results:
    by_cat[x["category"]].append(x)
summary = {"tag": args.tag, "adapter": args.adapter, "n": len(results), "pass": sum(x["pass"] for x in results), "categories": {}, "groups": {}}
for c, xs in sorted(by_cat.items()):
    d = {"n": len(xs), "pass": sum(x["pass"] for x in xs), "halluc": sum(bool(x["halluc"]) for x in xs)}
    tools = [x for x in xs if x["expect"]["type"] == "tool"]
    if tools:
        d.update({"tool_n": len(tools), "valid_json": sum(x["valid_json"] for x in tools), "tool_ok": sum(x["tool_ok"] for x in tools), "args_ok": sum(x["args_ok"] for x in tools)})
    summary["categories"][c] = d
by_group = defaultdict(list)
for x in results:
    if x["group"]:
        by_group[x["group"]].append(x)
for g, xs in sorted(by_group.items()):
    summary["groups"][g] = {"n": len(xs), "pass": sum(x["pass"] for x in xs), "halluc": sum(bool(x["halluc"]) for x in xs)}

rep = ROOT / "reports" / args.tag
rep.mkdir(parents=True, exist_ok=True)
(rep / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
with (rep / "results.jsonl").open("w", encoding="utf-8") as f:
    for x in results:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")

lines = [f"# Laporan evaluasi: {args.tag}", f"adapter: `{args.adapter}`  |  total lulus: **{summary['pass']}/{summary['n']}** ({100 * summary['pass'] / summary['n']:.1f}%)", "",
         "| kategori | lulus | % | JSON valid | tool benar | argumen benar | kemungkinan halusinasi |", "|---|---|---|---|---|---|---|"]
for c, d in summary["categories"].items():
    t = f"{d['valid_json']}/{d['tool_n']}" if "tool_n" in d else "-"
    tn = f"{d['tool_ok']}/{d['tool_n']}" if "tool_n" in d else "-"
    an = f"{d['args_ok']}/{d['tool_n']}" if "tool_n" in d else "-"
    lines.append(f"| {c} | {d['pass']}/{d['n']} | {100 * d['pass'] / d['n']:.0f}% | {t} | {tn} | {an} | {d['halluc']} |")
if summary["groups"]:
    lines += ["", "## Set pertanyaan alami (10_adhoc_natural) per tipe pertanyaan", "| tipe | lulus | % | halusinasi |", "|---|---|---|---|"]
    for g, d in summary["groups"].items():
        lines.append(f"| {g} | {d['pass']}/{d['n']} | {100 * d['pass'] / d['n']:.0f}% | {d['halluc']} |")
fails = [x for x in results if not x["pass"] or x["halluc"]]
lines += ["", f"## Kegagalan / tanda halusinasi ({len(fails)})"]
for x in fails:
    why = []
    if x["expect"]["type"] == "tool":
        why.append(f"tool_ok={x['tool_ok']} args_ok={x['args_ok']} | harapan: `{json.dumps({'tool': x['expect']['tool'], 'args': x['expect']['args']}, ensure_ascii=False)}`")
    else:
        why.append(f"hilang={x.get('missing')} terlarang={x.get('forbidden')} bukan_tool={x.get('not_tool')}")
    if x["halluc"]:
        why.append(f"halusinasi={x['halluc']}")
    lines += ["", f"- **[{x['category']}{'/' + x['group'] if x['group'] else ''}]** {x['user']}", f"  - keluaran: `{x['output'][:400]}`", f"  - {' ; '.join(why)}"]
(rep / "report.md").write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines[:22]))
print(f"\nLaporan lengkap: {rep / 'report.md'}")
