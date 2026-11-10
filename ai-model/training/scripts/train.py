"""
Fine-tuning LoRA model bahasa (default Qwen2.5-0.5B-Instruct) untuk chatbot EROganizer.

Pakai (dari folder ai-model, atau cukup jalankan train.bat):
  venv\\Scripts\\python.exe training\\scripts\\train.py --run-name run01 --epochs 3

Hasil: training/output/<run-name>/adapter  (+ train_log.json, train.log)
Loss HANYA dihitung pada token jawaban asisten (termasuk tool call JSON dan <|im_end|>).
Logits hanya dihitung pada posisi berlabel (hemat VRAM; kosakata Qwen 152 ribu token).
"""
import argparse
import json
import math
import random
import time
import os
from pathlib import Path

import torch
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL = Path(os.environ.get("CHATBOT_MODEL_DIR") or ROOT.parent / "models" / "Qwen2.5-0.5B-Instruct")
from modelutil import detect_markers  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--run-name", required=True)
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--rank", type=int, default=32)
ap.add_argument("--alpha", type=int, default=64)
ap.add_argument("--max-len", type=int, default=1280)
ap.add_argument("--tokens-per-batch", type=int, default=3200, help="anggaran token per micro-batch (padding ikut dihitung)")
ap.add_argument("--accum", type=int, default=2)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--overwrite", action="store_true", help="izinkan menimpa adapter dengan --run-name yang sudah ada (default: ditolak)")
ap.add_argument("--max-steps", type=int, default=0, help="batasi jumlah langkah untuk uji cepat (smoke test); 0 = training penuh")
ap.add_argument("--assistant-start", default=None, help="paksa penanda awal giliran asisten (default: dideteksi dari chat template); escape seperti \\n boleh")
ap.add_argument("--assistant-end", default=None, help="paksa penanda akhir giliran asisten (default: dideteksi dari chat template)")
ap.add_argument("--model-dir", default=None, help="folder model dasar (default: env CHATBOT_MODEL_DIR atau ../models/Qwen2.5-0.5B-Instruct)")
ap.add_argument("--target-modules", default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj", help="modul LoRA dipisah koma, atau all-linear untuk arsitektur lain")
args = ap.parse_args()
if args.model_dir:
    BASE_MODEL = Path(args.model_dir)

random.seed(args.seed)
torch.manual_seed(args.seed)
out_dir = ROOT / "output" / args.run_name
if (out_dir / "adapter" / "adapter_config.json").exists() and not args.overwrite:
    raise SystemExit(f"Adapter '{args.run_name}' SUDAH ADA di {out_dir / 'adapter'} dan tidak ditimpa.\nPakai --run-name lain (set RUN_NAME=... di CMD atau config.local.bat), atau tambahkan --overwrite bila memang ingin menimpa.")
out_dir.mkdir(parents=True, exist_ok=True)
log_file = (out_dir / "train.log").open("w", encoding="utf-8")


def log(msg):
    print(msg, flush=True)
    log_file.write(msg + "\n")
    log_file.flush()


if not (BASE_MODEL / "config.json").exists():
    raise SystemExit(f"Model dasar tidak ditemukan di {BASE_MODEL}\nJalankan download_model.bat (atau set CHATBOT_MODEL_DIR / --model-dir).")
tok = AutoTokenizer.from_pretrained(BASE_MODEL)
PAD = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
START, END = detect_markers(tok)
if args.assistant_start is not None:
    START = args.assistant_start.encode().decode("unicode_escape")
if args.assistant_end is not None:
    END = args.assistant_end.encode().decode("unicode_escape")
if not START or not END:
    raise SystemExit(f"Penanda giliran asisten tidak terdeteksi (START={START!r} END={END!r}). Beri --assistant-start/--assistant-end.")
log(f"penanda giliran asisten: START={START!r} END={END!r}")


def encode(messages):
    text = tok.apply_chat_template(messages, tokenize=False)
    enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
    ids, offs = enc["input_ids"], enc["offset_mapping"]
    spans, pos = [], 0
    while True:
        i = text.find(START, pos)
        if i == -1:
            break
        s = i + len(START)
        e = text.find(END, s) + len(END)
        spans.append((s, e))
        pos = e
    labels = [ids[k] if any(a >= s and b <= e for s, e in spans) else -100 for k, (a, b) in enumerate(offs)]
    return ids, labels


def load(split, skip=("10_adhoc_natural",)):
    items = []
    for path in sorted((ROOT / "datasets" / split).glob("*.jsonl")):
        if path.stem in skip:
            continue
        for line in path.open(encoding="utf-8"):
            ids, labels = encode(json.loads(line)["messages"])
            if len(ids) <= args.max_len:
                items.append((ids, labels))
    return items


train, evals = load("train"), load("eval")
log(f"data: train={len(train)} eval={len(evals)} token_train={sum(len(i) for i, _ in train):,}")


def make_batches(items, shuffle):
    idx = list(range(len(items)))
    if shuffle:
        random.shuffle(idx)
    batches, chunk = [], 256
    for c in range(0, len(idx), chunk):
        part = sorted(idx[c:c + chunk], key=lambda i: len(items[i][0]))
        cur, cur_max = [], 0
        for i in part:
            m = max(cur_max, len(items[i][0]))
            if cur and (m * (len(cur) + 1) > args.tokens_per_batch or len(cur) >= 16):
                batches.append(cur)
                cur, m = [], len(items[i][0])
            cur.append(i)
            cur_max = m
        if cur:
            batches.append(cur)
    if shuffle:
        random.shuffle(batches)
    return batches


def collate(items, batch, device):
    n = max(len(items[i][0]) for i in batch)
    ids = torch.full((len(batch), n), PAD, dtype=torch.long)
    lab = torch.full((len(batch), n), -100, dtype=torch.long)
    att = torch.zeros((len(batch), n), dtype=torch.long)
    for r, i in enumerate(batch):
        a, b = items[i]
        ids[r, :len(a)] = torch.tensor(a)
        lab[r, :len(b)] = torch.tensor(b)
        att[r, :len(a)] = 1
    return ids.to(device), att.to(device), lab.to(device)


device = "cuda" if torch.cuda.is_available() else "cpu"
model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16 if device == "cuda" else torch.float32)
model.to(device)
lcfg = LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                  target_modules="all-linear" if args.target_modules == "all-linear" else [m.strip() for m in args.target_modules.split(",")])
model = get_peft_model(model, lcfg)
inner = model.base_model.model  # Qwen2ForCausalLM; modul LoRA sudah terpasang di dalamnya
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
log(f"device={device} lora r={args.rank} alpha={args.alpha} trainable_params={trainable:,}")


def batch_loss(ids, att, lab):
    """-> (jumlah loss pada token berlabel, banyak token berlabel)"""
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
        h = inner.model(input_ids=ids, attention_mask=att).last_hidden_state[:, :-1]
        tgt = lab[:, 1:]
        keep = tgt != -100
        logits = inner.lm_head(h[keep])
    return F.cross_entropy(logits.float(), tgt[keep], reduction="sum"), int(keep.sum())


params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
steps_per_epoch = math.ceil(len(make_batches(train, False)) / args.accum)
total_steps = steps_per_epoch * args.epochs
if args.max_steps:
    total_steps = min(total_steps, args.max_steps)  # uji cepat (smoke test)
warm = max(1, int(total_steps * 0.05))


def lr_at(step):
    if step < warm:
        return args.lr * (step + 1) / warm
    p = (step - warm) / max(1, total_steps - warm)
    return args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * p)))


@torch.no_grad()
def eval_loss():
    model.eval()
    tot, cnt = 0.0, 0
    for b in make_batches(evals, False):
        loss, n = batch_loss(*collate(evals, b, device))
        tot += loss.item()
        cnt += n
    model.train()
    return tot / max(1, cnt)


history = {"args": vars(args), "steps": [], "epochs": []}
log(f"steps_per_epoch={steps_per_epoch} total_steps={total_steps}")
base_eval = eval_loss()
history["eval_loss_before"] = base_eval
log(f"eval_loss sebelum training: {base_eval:.4f}")
model.train()
t0, step, seen_tokens = time.time(), 0, 0
for epoch in range(1, args.epochs + 1):
    batches = make_batches(train, True)
    run_loss, run_cnt = 0.0, 0
    for bi in range(0, len(batches), args.accum):
        group = batches[bi:bi + args.accum]
        n_label = sum(int((collate(train, b, "cpu")[2][:, 1:] != -100).sum()) for b in group)
        for b in group:
            ids, att, lab = collate(train, b, device)
            loss, n = batch_loss(ids, att, lab)
            (loss / n_label).backward()
            run_loss += loss.item()
            run_cnt += n
            seen_tokens += int(att.sum())
            del loss
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        if step % 20 == 0 or step == total_steps:
            tr = run_loss / max(1, run_cnt)
            history["steps"].append({"step": step, "loss": tr, "lr": lr_at(step)})
            log(f"epoch {epoch} step {step}/{total_steps} loss={tr:.4f} lr={lr_at(step):.2e} tok/s={seen_tokens / (time.time() - t0):.0f} vram_maks={torch.cuda.max_memory_allocated() / 2**30:.1f}GB")
            run_loss, run_cnt = 0.0, 0
        if step >= total_steps:
            break
    ev = eval_loss()
    history["epochs"].append({"epoch": epoch, "eval_loss": ev})
    log(f"=== epoch {epoch} selesai | eval_loss={ev:.4f} | {(time.time() - t0) / 60:.1f} menit")
    if step >= total_steps:
        break

model.save_pretrained(out_dir / "adapter")
history["minutes"] = (time.time() - t0) / 60
(out_dir / "train_log.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
log(f"adapter disimpan di {out_dir / 'adapter'}")
