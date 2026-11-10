"""
Demo end-to-end: model (base / base+adapter) + backend TIRUAN yang mengeksekusi tool call terhadap data/rooms.json.
Tidak menyentuh aplikasi maupun database; booking disimpan di memori selama skrip berjalan.

Pakai (dari folder ai-model):
  venv\\Scripts\\python.exe training\\scripts\\demo.py --adapter training\\output\\<RUN_NAME>\\adapter
  venv\\Scripts\\python.exe training\\scripts\\demo.py --adapter training\\output\\<RUN_NAME>\\adapter --ask "ada berapa ruangan yang bisa di booking?"
  venv\\Scripts\\python.exe training\\scripts\\demo.py                       (tanpa adapter = model dasar, hanya untuk pembanding)
Alur: pesan -> model -> (tool call JSON?) -> eksekusi -> hasil dikirim kembali sebagai pesan role "tool" -> model menjawab.
"""
import argparse
import datetime as dt
import difflib
import json
import re
import sys
import os
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BY_NAME, NAMES, ROOMS, SYSTEM_PROMPT, DAYS_ID, MONTHS_ID  # noqa: E402
from gen_results import filter_rooms  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL = Path(os.environ.get("CHATBOT_MODEL_DIR") or ROOT.parent / "models" / "Qwen2.5-0.5B-Instruct")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", default=None)
ap.add_argument("--ask", default=None, help="satu pertanyaan saja (tanpa --ask: jalankan skenario bawaan)")
ap.add_argument("--out", default=None, help="simpan transkrip ke file .md")
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


@torch.inference_mode()
def generate(messages):
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt").to(DEVICE)
    out = model.generate(**enc, max_new_tokens=300, do_sample=False, eos_token_id=EOS, pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else EOS[0])
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()


# ----------------------------------------------------------------------------- backend tiruan
NOW = dt.datetime.now()
BOOKINGS = []  # {"room","date","start","end","purpose","status"}
STATUS = {"unavailable", "booked"}


def label(d):
    return f"{DAYS_ID[d.weekday()]}, {d.day} {MONTHS_ID[d.month - 1]} {d.year}"


def resolve_date(text):
    t = (text or "").strip().lower()
    today = NOW.date()
    if t == "hari ini":
        return today
    if t == "besok":
        return today + dt.timedelta(days=1)
    if t == "lusa":
        return today + dt.timedelta(days=2)
    days = [d.lower() for d in DAYS_ID]
    m = re.match(r"^(\w+?)( depan)?$", t)
    if m and m.group(1) in days:
        idx = days.index(m.group(1))
        if m.group(2):
            return today + dt.timedelta(days=(7 - today.weekday()) + idx)
        return today + dt.timedelta(days=(idx - today.weekday()) % 7)
    months = {x.lower(): i + 1 for i, x in enumerate(MONTHS_ID)}
    m = re.match(r"^(\d{1,2}) (\w+)(?: (\d{4}))?$", t)
    try:
        if m and m.group(2) in months:
            y = int(m.group(3)) if m.group(3) else today.year
            d = dt.date(y, months[m.group(2)], int(m.group(1)))
            return d if d >= today or m.group(3) else d.replace(year=y + 1)
        m = re.match(r"^tanggal (\d{1,2})$", t)
        if m:
            return dt.date(today.year, today.month, int(m.group(1)))
    except ValueError:
        return None
    return None


def mins(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def find_room(name):
    for r in ROOMS:
        if r["name"].lower() == (name or "").strip().lower():
            return r
    return None


def not_found(q):
    return {"ok": False, "error": "room_not_found", "query": q, "suggestions": difflib.get_close_matches(q, NAMES, n=3, cutoff=0.0)}


def times_of(a):
    if "start_time" not in a:
        return None, None
    s = mins(a["start_time"])
    e = mins(a["end_time"]) if "end_time" in a else s + int(a.get("duration_minutes", 60))
    return s, e


def tool_list_rooms(a):
    found = filter_rooms(a)
    shown = found[:8]
    return {"ok": True, "count": len(found), "shown": len(shown), "filters": a,
            "rooms": [{"name": r["name"], "location": r["location"], "capacity": r["capacity"]} for r in shown]}


def tool_room_info(a):
    r = find_room(a.get("room"))
    if not r:
        return not_found(a.get("room", ""))
    booked = any(b["room"] == r["name"] and b["status"] == "approved" for b in BOOKINGS)
    st = r["status"] if r["status"] != "available" or not booked else "booked"
    return {"ok": True, "room": {"name": r["name"], "location": r["location"], "capacity": r["capacity"], "description": r["description"], "status": st}}


def conflicts(room, date, s, e):
    return [{"start": b["start"], "end": b["end"]} for b in BOOKINGS if b["room"] == room and b["date"] == date and b["status"] == "approved" and mins(b["start"]) < e and mins(b["end"]) > s]


def tool_check(a):
    r = find_room(a.get("room"))
    if not r:
        return not_found(a.get("room", ""))
    d = resolve_date(a.get("date_text"))
    if not d:
        return {"ok": False, "error": "invalid_date", "date_text": a.get("date_text")}
    if r["status"] != "available":
        return {"ok": True, "room": r["name"], "date_label": label(d), "available": False, "reason": "room_unavailable", "room_status": r["status"]}
    s, e = times_of(a)
    if s is None:
        busy = [{"start": b["start"], "end": b["end"]} for b in BOOKINGS if b["room"] == r["name"] and b["date"] == d and b["status"] == "approved"]
        return {"ok": True, "room": r["name"], "date_label": label(d), "available": True, "busy": busy}
    c = conflicts(r["name"], d, s, e)
    base = {"ok": True, "room": r["name"], "date_label": label(d), "start": hm(s), "end": hm(e)}
    return {**base, "available": False, "reason": "time_conflict", "conflicts": c} if c else {**base, "available": True}


def tool_book(a):
    r = find_room(a.get("room"))
    if not r:
        return not_found(a.get("room", ""))
    d = resolve_date(a.get("date_text"))
    if not d:
        return {"ok": False, "error": "invalid_date", "date_text": a.get("date_text")}
    s, e = times_of(a)
    if s is None or e is None:
        return {"ok": False, "error": "end_before_start", "room": r["name"]}
    if r["status"] != "available":
        return {"ok": False, "error": "room_unavailable", "room": r["name"], "room_status": r["status"]}
    if dt.datetime.combine(d, dt.time(s // 60, s % 60)) < NOW:
        return {"ok": False, "error": "start_in_past", "room": r["name"]}
    if e <= s:
        return {"ok": False, "error": "end_before_start", "room": r["name"]}
    c = conflicts(r["name"], d, s, e)
    if c:
        return {"ok": False, "error": "time_conflict", "room": r["name"], "date_label": label(d), "conflicts": c}
    b = {"room": r["name"], "date": d, "start": hm(s), "end": hm(e), "purpose": a.get("purpose", ""), "status": "approved"}
    BOOKINGS.append(b)
    return {"ok": True, "booking": {"room": r["name"], "date_label": label(d), "start": b["start"], "end": b["end"], "purpose": b["purpose"], "status": "approved"}}


def view(b):
    return {"room": b["room"], "date_label": label(b["date"]), "start": b["start"], "end": b["end"], "purpose": b["purpose"], "status": b["status"]}


def tool_my(a):
    rows = [b for b in BOOKINGS if ("status" not in a or b["status"] == a["status"])]
    if a.get("period") == "upcoming":
        rows = [b for b in rows if b["date"] >= NOW.date()]
    elif a.get("period") == "past":
        rows = [b for b in rows if b["date"] < NOW.date()]
    elif a.get("period") == "today":
        rows = [b for b in rows if b["date"] == NOW.date()]
    return {"ok": True, "count": len(rows), "shown": len(rows[:6]), "filters": a, "bookings": [view(b) for b in rows[:6]]}


def tool_cancel(a):
    r = find_room(a.get("room"))
    if not r:
        return not_found(a.get("room", ""))
    d = resolve_date(a["date_text"]) if a.get("date_text") else None
    rows = [b for b in BOOKINGS if b["room"] == r["name"] and (d is None or b["date"] == d)]
    if not rows:
        return {"ok": False, "error": "not_found", **a}
    active = [b for b in rows if b["status"] == "approved"]
    if not active:
        return {"ok": False, "error": "not_cancellable", "reason": "already_cancelled", "booking": view(rows[0])}
    if len(active) > 1 and d is None:
        return {"ok": False, "error": "multiple_matches", "room": r["name"], "matches": [{"date_label": label(b["date"]), "start": b["start"], "end": b["end"]} for b in active]}
    active[0]["status"] = "cancelled"
    return {"ok": True, "booking": view(active[0])}


TOOLS = {"list_rooms": tool_list_rooms, "room_info": tool_room_info, "check_availability": tool_check, "book_room": tool_book, "my_bookings": tool_my, "cancel_booking": tool_cancel}


def parse_tool(s):
    s = s.strip()
    if not s.startswith("{"):
        return None
    try:
        o = json.loads(s)
    except Exception:
        return None
    return o if isinstance(o, dict) and o.get("tool") in TOOLS and isinstance(o.get("args", {}), dict) else None


# ----------------------------------------------------------------------------- percakapan
transcript = []


def say(line=""):
    print(line, flush=True)
    transcript.append(line)


def run_conversation(user_turns):
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    say("-" * 78)
    for u in user_turns:
        say(f"PENGGUNA : {u}")
        history.append({"role": "user", "content": u})
        for _ in range(3):  # model boleh memanggil tool lalu menjawab
            out = generate(history)
            history.append({"role": "assistant", "content": out})
            call = parse_tool(out)
            if not call:
                say(f"ASISTEN  : {out}")
                break
            say(f"  [tool call] {out}")
            result = TOOLS[call["tool"]](call.get("args", {}))
            res = json.dumps(result, ensure_ascii=False, default=str)
            say(f"  [hasil    ] {res[:300]}{'...' if len(res) > 300 else ''}")
            history.append({"role": "tool", "content": res})


SCENARIOS = [
    ["ada berapa ruangan yang bisa di booking?"],
    ["Kapasitas Aula Utama berapa?"],
    ["Kenapa Lab Jaringan nggak bisa dipesan?"],
    ["Aula Utama kosong besok jam 9 sampai 11?"],
    ["Mau pinjam Aula Utama", "besok", "jam 9 sampai jam 11", "rapat himpunan"],
    ["Pinjam Aula Utama besok jam 10 sampai 12 buat seminar"],
    ["Aula Utama besok jadwalnya gimana?"],
    ["Booking saya apa saja?"],
    ["Batalkan booking Aula Utama besok"],
    ["Booking saya yang dibatalkan apa saja?"],
    ["Bagaimana cara membatalkan booking?"],
    ["Tolong tambahkan ruangan baru dong"],
    ["Besok cuaca gimana?"],
]

if args.ask:
    run_conversation([args.ask])
else:
    say(f"# Demo chatbot EROganizer | adapter: {args.adapter or '(tanpa adapter = model dasar)'} | backend: tiruan (data rooms.json)")
    for conv in SCENARIOS:
        run_conversation(conv)
if args.out:
    Path(args.out).write_text("\n".join(transcript), encoding="utf-8")
    print(f"\nTranskrip disimpan: {args.out}")
