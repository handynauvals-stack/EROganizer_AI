"""Kategori 06: percakapan multi-giliran saat informasi belum lengkap (model bertanya satu hal per giliran)."""
import random
import re

from common import *

OPENERS = {"train": ["Saya mau pinjam", "Mau booking", "Tolong pesankan", "Pinjam", "Bisa booking", "Aku mau reservasi", "Saya ingin meminjam", "Saya perlu", "Pengen booking",
                     "Butuh", "Mau pakai", "Bisa pinjam", "Ada rencana memakai", "Kami butuh", "Saya mau memakai"],
           "eval": ["Mohon bantu pinjamkan", "Aku butuh", "Tolong reservasikan", "Kami mau memakai"]}
Q = {
    "room": {"train": ["Ruangan mana yang ingin kamu pinjam?", "Kamu mau meminjam ruangan yang mana?", "Boleh tahu ruangan mana yang ingin dipinjam?"],
             "eval": ["Ruangan apa yang kamu butuhkan?", "Mau pakai ruangan yang mana?"], "must": ["ruang|lab|aula"]},
    "date": {"train": ["Untuk tanggal berapa?", "Kamu mau pinjam di hari apa?", "Tanggal berapa kamu ingin meminjamnya?"],
             "eval": ["Hari atau tanggal berapa rencananya?", "Kapan kamu akan memakainya?"], "must": ["tanggal|hari|kapan"]},
    "time": {"train": ["Jam berapa mulai dan selesainya?", "Dari jam berapa sampai jam berapa?", "Kamu butuh ruangan dari jam berapa sampai jam berapa?"],
             "eval": ["Pukul berapa mulai dan selesai pemakaiannya?", "Rencana waktunya dari jam berapa sampai jam berapa?"], "must": ["jam|pukul"]},
    "end": {"train": ["Sampai jam berapa kamu memakainya?", "Selesainya jam berapa?"], "eval": ["Rencana selesai pukul berapa?"], "must": ["jam|pukul"]},
    "purpose": {"train": ["Apa keperluan atau tujuan peminjamannya?", "Untuk keperluan apa ruangan ini dipinjam?", "Boleh tahu tujuan peminjamannya?"],
                "eval": ["Kegiatan apa yang akan dilakukan di sana?", "Apa tujuan penggunaan ruangannya?"], "must": ["keperluan|tujuan|kegiatan"]},
    "cancel_room": {"train": ["Booking ruangan apa yang ingin kamu batalkan?", "Ruangan mana yang bookingnya mau dibatalkan?"],
                    "eval": ["Booking untuk ruangan yang mana yang mau dibatalkan?"], "must": ["ruang|lab|aula|booking"]},
    "info_room": {"train": ["Ruangan mana yang kamu maksud?", "Ruangan apa yang ingin kamu ketahui?"], "eval": ["Maksud kamu ruangan yang mana?"], "must": ["ruang|lab|aula"]},
}
AMBIG_Q = {"train": ["Maksudnya yang mana: {c}?", "Ada beberapa pilihan: {c}. Kamu mau yang mana?", "Maksud kamu yang mana, {c}?"],
           "eval": ["Di sistem ada {c}. Yang mana yang kamu mau?"]}
ORDER = ["room", "date", "time", "purpose"]


def _join(names):
    return ", ".join(names[:-1]) + ", atau " + names[-1]


def _spec(rng, split):
    room = rng.choice(ROOMS)
    slang = rng.random() < 0.2
    dtext, dnorm = date_slot_norm(rng, slang)
    s, e = pick_times(rng)
    ttext, targs = time_args(rng, slang, allow_duration=False, start_min=s, end_min=e)
    ptext, parg = purpose_slot(rng, split)
    return dict(room=room, dtext=dtext, dnorm=dnorm, ttext=ttext, targs=targs, ptext=ptext, parg=parg, s=s, e=e)


def _ask(slot, rng, split, expects):
    expects.append(expect_text(must=Q[slot]["must"]))
    return rng.choice(Q[slot][split])


def _answer(slot, sp, rng):
    if slot == "room":
        return room_mention(sp["room"], rng)
    if slot == "date":
        return rng.choice([sp["dtext"], sp["dtext"], f"untuk {sp['dtext']}"])
    if slot == "time":
        return sp["ttext"]
    if slot == "purpose":
        return rng.choice([sp["ptext"], f"untuk {sp['ptext']}", f"buat {sp['ptext']}", f"keperluannya {sp['ptext']}"])
    raise ValueError(slot)


def booking_conv(rng, split):
    sp = _spec(rng, split)
    k = rng.choices([0, 1, 2, 3], weights=[8, 30, 40, 22])[0]
    provided = set(rng.sample(ORDER, k))
    amb = "room" in provided and rng.random() < 0.18
    start_only = "time" in provided and rng.random() < 0.12
    have = {s: (s in provided) for s in ORDER}
    group_key = None
    if amb:
        group_key = rng.choice(list(GROUPS))
        sp["room"] = BY_NAME[rng.choice(GROUPS[group_key])]
        have["room"] = False
    opener = rng.choice(OPENERS[split])
    room_text = (group_key.title() if rng.random() < 0.4 else group_key) if amb else (room_mention(sp["room"], rng) if "room" in provided else "ruangan")
    frame = f"{opener} {{room}}"
    if "date" in provided:
        frame += " {date}"
    if "time" in provided:
        frame += " {time}"
    if "purpose" in provided:
        frame += " " + rng.choice(["untuk", "buat"]) + " {purpose}"
    ttxt = sp["ttext"]
    if start_only:
        p, c = rng.choice(time_variants(sp["s"]))
        ttxt = f"mulai {p}{c}"
    first = fill(stylize(frame, rng), room=room_text, date=sp["dtext"], time=ttxt, purpose=sp["ptext"])
    msgs, expects = [{"role": "user", "content": first}], [None]

    while True:
        if amb:
            cands = GROUPS[group_key]
            msgs.append({"role": "assistant", "content": rng.choice(AMBIG_Q[split]).format(c=_join(cands))})
            expects.append(expect_text(must=list(cands)))
            num = re.search(r"(\d)$", sp["room"]["name"])
            ans = rng.choice([room_mention(sp["room"], rng)] * 3 + ([f"yang {num.group(1)}", f"nomor {num.group(1)}"] if num and group_key not in ("kelas", "ruang kelas", "lab") else []))
            msgs.append({"role": "user", "content": ans})
            expects.append(None)
            amb, have["room"] = False, True
            continue
        slot = next((s for s in ORDER if not have[s] or (s == "time" and start_only)), None)
        if slot is None:
            args = {"room": sp["room"]["name"], "date_text": sp["dnorm"], **sp["targs"], "purpose": sp["parg"]}
            msgs.append({"role": "assistant", "content": tool_json("book_room", args)})
            expects.append(expect_tool("book_room", args))
            return msgs, expects
        if slot == "time" and start_only:
            msgs.append({"role": "assistant", "content": _ask("end", rng, split, expects)})
            p, c = rng.choice(time_variants(sp["e"]))
            msgs.append({"role": "user", "content": rng.choice([f"sampai {p}{c}", f"{p}{c}", f"selesai {p}{c}"])})
            expects.append(None)
            start_only = False
            continue
        msgs.append({"role": "assistant", "content": _ask(slot, rng, split, expects)})
        answered = [slot]
        nxt = [s for s in ORDER if not have[s] and s != slot]
        if nxt and not start_only and rng.random() < 0.35 and nxt[0] != "room":
            answered.append(nxt[0])
        parts = [_answer(s, sp, rng) for s in answered]
        msgs.append({"role": "user", "content": rng.choice([", ", " "]).join(parts)})
        expects.append(None)
        for s in answered:
            have[s] = True


def availability_conv(rng, split):
    sp = _spec(rng, split)
    if rng.random() < 0.5:  # ruangan belum disebut
        frame = rng.choice(["Cek ketersediaan ruangan {date} {time}", "Tolong cek apakah ada yang kosong {date} {time}", "Mau cek jadwal ruangan {date}"])
        with_time = "{time}" in frame
        first = fill(stylize(frame, rng), date=sp["dtext"], time=sp["ttext"]).replace("  ", " ").strip()
        msgs = [{"role": "user", "content": first}]
        expects = [None]
        msgs.append({"role": "assistant", "content": _ask("room", rng, split, expects)})
        msgs.append({"role": "user", "content": room_mention(sp["room"], rng)})
        expects.append(None)
        args = {"room": sp["room"]["name"], "date_text": sp["dnorm"]}
        if with_time:
            args.update(sp["targs"])
    else:  # tanggal belum disebut
        first = fill(stylize(rng.choice(["Cek ketersediaan {room}", "Mau cek jadwal {room}", "Tolong cek {room} kosong atau tidak"]), rng), room=room_mention(sp["room"], rng))
        msgs = [{"role": "user", "content": first}]
        expects = [None]
        msgs.append({"role": "assistant", "content": _ask("date", rng, split, expects)})
        with_time = rng.random() < 0.4
        msgs.append({"role": "user", "content": sp["dtext"] + (" " + sp["ttext"] if with_time else "")})
        expects.append(None)
        args = {"room": sp["room"]["name"], "date_text": sp["dnorm"]}
        if with_time:
            args.update(sp["targs"])
    msgs.append({"role": "assistant", "content": tool_json("check_availability", args)})
    expects.append(expect_tool("check_availability", args))
    return msgs, expects


def cancel_conv(rng, split):
    sp = _spec(rng, split)
    if rng.random() < 0.6:
        first = stylize(rng.choice(["Saya mau batalkan booking", "Tolong cancel peminjaman saya", "Batalkan booking saya dong", "Mau membatalkan pinjaman ruangan"]), rng)
        msgs, expects = [{"role": "user", "content": first}], [None]
        msgs.append({"role": "assistant", "content": _ask("cancel_room", rng, split, expects)})
        if rng.random() < 0.5:
            msgs.append({"role": "user", "content": f"{room_mention(sp['room'], rng)} {sp['dtext']}"})
            args = {"room": sp["room"]["name"], "date_text": sp["dnorm"]}
        else:
            msgs.append({"role": "user", "content": room_mention(sp["room"], rng)})
            args = {"room": sp["room"]["name"]}
    else:
        first = fill(stylize(rng.choice(["Batalkan booking saya {date}", "Cancel pinjaman {date} ya", "Tolong batalkan peminjaman {date}"]), rng), date=sp["dtext"])
        msgs, expects = [{"role": "user", "content": first}], [None]
        msgs.append({"role": "assistant", "content": _ask("cancel_room", rng, split, expects)})
        msgs.append({"role": "user", "content": room_mention(sp["room"], rng)})
        args = {"room": sp["room"]["name"], "date_text": sp["dnorm"]}
    expects.append(None)
    msgs.append({"role": "assistant", "content": tool_json("cancel_booking", args)})
    expects.append(expect_tool("cancel_booking", args))
    return msgs, expects


def info_conv(rng, split):
    sp = _spec(rng, split)
    first = stylize(rng.choice(["Kapasitasnya berapa?", "Fasilitasnya apa saja?", "Letaknya di mana?", "Ada proyektornya nggak?", "Ruangannya bisa muat berapa orang?"]), rng)
    msgs, expects = [{"role": "user", "content": first}], [None]
    msgs.append({"role": "assistant", "content": _ask("info_room", rng, split, expects)})
    msgs.append({"role": "user", "content": room_mention(sp["room"], rng)})
    expects.append(None)
    args = {"room": sp["room"]["name"]}
    msgs.append({"role": "assistant", "content": tool_json("room_info", args)})
    expects.append(expect_tool("room_info", args))
    return msgs, expects


def gen_slot_filling(rng, split, n):
    rows = []
    for _ in range(n * 3):
        kind = rng.choices(["booking", "availability", "cancel", "info"], weights=[72, 12, 10, 6])[0]
        msgs, expects = {"booking": booking_conv, "availability": availability_conv, "cancel": cancel_conv, "info": info_conv}[kind](rng, split)
        if split == "train":
            rows.append(example("06_slot_filling", msgs, expects[-1], {"scenario": kind}))
        else:
            idxs = [i for i, m in enumerate(msgs) if m["role"] == "assistant"]
            i = rng.choice(idxs)
            rows.append(example("06_slot_filling", msgs[: i + 1], expects[i], {"scenario": kind}))
    return dedupe(rows)[:n]
