"""Kategori 07: hasil tool (role "tool") -> jawaban bahasa Indonesia yang jujur sesuai data."""
import datetime as dt
import difflib
import json
import random
import re

from common import *
import gen_tools as gt

TODAY = dt.date(2026, 10, 30)  # Jumat
STATUS_ID = {"approved": "disetujui", "cancelled": "dibatalkan", "completed": "selesai", "pending": "menunggu persetujuan"}
PERIOD_ID = {"upcoming": "yang akan datang", "today": "hari ini", "past": "yang sudah lewat"}
ROOM_STATUS_TEXT = {
    "unavailable": "sedang tidak tersedia (dinonaktifkan oleh admin)",
    "booked": "sedang memiliki booking aktif",
}
MONTH_NUM = {m.lower(): i + 1 for i, m in enumerate(MONTHS_ID)}


def rng_date(rng, dnorm):
    """Tanggal yang konsisten dengan date_text (hari ini = Jumat 30 Okt 2026)."""
    t = dnorm.lower()
    days = [d.lower() for d in DAYS_ID]
    if t == "hari ini":
        return TODAY
    if t == "besok":
        return TODAY + dt.timedelta(days=1)
    if t == "lusa":
        return TODAY + dt.timedelta(days=2)
    first = t.split()[0]
    if first in days:
        while True:
            d = TODAY + dt.timedelta(days=rng.randint(1, 20))
            if d.weekday() == days.index(first):
                return d
    m = re.match(r"(\d+) (\w+)(?: (\d{4}))?$", t)
    if m and m.group(2) in MONTH_NUM:
        mon = MONTH_NUM[m.group(2)]
        year = int(m.group(3)) if m.group(3) else (2026 if mon >= 10 else 2027)
        return dt.date(year, mon, int(m.group(1)))
    m = re.match(r"tanggal (\d+)$", t)
    if m:
        return dt.date(2026, 11, int(m.group(1)))
    return random_date(rng)


def overlap_window(rng, s, e):
    """Jadwal bentrok yang tumpang tindih dengan [s, e] tetapi jam mulai DAN selesainya berbeda dari permintaan."""
    sm, em = int(s[:2]) * 60 + int(s[3:]), int(e[:2]) * 60 + int(e[3:])
    for _ in range(80):
        cs = sm + rng.choice([-90, -60, -30, 30, 60, 90])
        ce = cs + rng.choice([60, 90, 120, 150])
        if cs >= 7 * 60 and ce <= 21 * 60 and cs < em and ce > sm and cs != sm and ce != em:
            return hm(cs), hm(ce)
    return hm(max(7 * 60, sm - 30)), hm(sm + 60)


def fr(s, e):
    return f"{dot(s)}-{dot(e)}"


def slot_windows(rng, n):
    """n jendela waktu yang tidak saling tumpang tindih (menit)."""
    starts = sorted(rng.sample(range(7 * 2, 18 * 2), n))
    out, last_end = [], 0
    for s in starts:
        s *= 30
        if s < last_end:
            continue
        e = s + rng.choice([60, 90, 120])
        out.append((s, e))
        last_end = e
    return [(hm(s), hm(e)) for s, e in out]


def tool_msg(result: dict) -> dict:
    return {"role": "tool", "content": json.dumps(result, ensure_ascii=False)}


def ex7(user_text, call_name, call_args, result, answer, must, must_not=None, extra=None):
    msgs = [{"role": "user", "content": user_text}, {"role": "assistant", "content": tool_json(call_name, call_args)}, tool_msg(result),
            {"role": "assistant", "content": answer}]
    return example("07_tool_results", msgs, expect_text(must=must, must_not=must_not or []), extra)


def suggestions(name):
    return difflib.get_close_matches(name, NAMES, n=3, cutoff=0.0)


def not_found_answer(rng, q, sugg):
    s = ", ".join(sugg[:-1]) + ", atau " + sugg[-1]
    return rng.choice([f'Saya tidak menemukan ruangan "{q}" di sistem. Mungkin maksud kamu: {s}?',
                       f'Ruangan "{q}" tidak ada di sistem EROganizer. Apakah maksud kamu {s}?',
                       f'Maaf, tidak ada ruangan bernama "{q}". Pilihan yang mirip: {s}.'])


# ------------------------------------------------------------------ list_rooms
def filter_rooms(args, blocked=()):
    out = []
    for r in ROOMS:
        if r["status"] != "available" or r["name"] in blocked:
            continue
        if "min_capacity" in args and r["capacity"] < args["min_capacity"]:
            continue
        if "location" in args and args["location"].lower() not in r["location"].lower():
            continue
        if "keyword" in args:
            kw = args["keyword"]
            hay = r["name"] + " " + r["description"]
            if kw == "AC" and "tanpa AC" in hay:
                continue
            if not re.search(r"\b" + re.escape(kw) + r"\b", hay, re.I):
                continue
        out.append(r)
    return out


def pick_blocked(rng):
    """Simulasi ruangan yang sedang 'booked'. Di aplikasi, SATU booking aktif membuat seluruh ruangan tidak tersedia, jadi jumlah
    ruangan tersedia di database nyata sangat bervariasi (14 .. 0). Tanpa ini, count selalu 14 dan kasus sedikit/kosong tak pernah dilatih."""
    avail = [r["name"] for r in ROOMS if r["status"] == "available"]
    if rng.random() < 0.30:
        return set()
    target = rng.randint(0, len(avail) - 1)  # jumlah ruangan yang masih tersedia, merata 0..13 (agar "Dan N ruangan lainnya" tak dihafal)
    return set(rng.sample(avail, len(avail) - target))


def filters_text(args):
    parts = []
    if "min_capacity" in args:
        parts.append(f"kapasitas minimal {args['min_capacity']} orang")
    if "location" in args:
        parts.append(f"di {args['location']}")
    if "keyword" in args:
        parts.append(f'kata kunci "{args["keyword"]}"')
    return ", ".join(parts)


def gen_list(rng, split):
    frames, slots, args = gt.list_rooms_example(rng, split)
    if rng.random() < 0.25:  # lebih banyak pertanyaan tanpa filter: di situlah jumlah ruangan tersedia paling sering ditanyakan
        frames, slots, args = gt.LIST_NONE[split], {}, {}
    frame = rng.choice(frames)
    count_q = "berapa" in frame.lower() or "jumlah" in frame.lower()
    text = fill(stylize(frame, rng), **slots)
    blocked = pick_blocked(rng)
    found = filter_rooms(args, blocked)
    shown = found[:8]
    result = {"ok": True, "count": len(found), "shown": len(shown), "filters": args,
              "rooms": [{"name": r["name"], "location": r["location"], "capacity": r["capacity"]} for r in shown]}
    ft = filters_text(args)
    if not found:
        ans = rng.choice([f"Belum ada ruangan tersedia yang cocok dengan kriteria itu ({ft}). Coba ubah kapasitas, lokasi, atau kata kuncinya." if ft else
                          "Saat ini belum ada ruangan yang tersedia untuk dipinjam.",
                          f"Maaf, tidak ada ruangan tersedia dengan kriteria {ft}. Mau coba kriteria lain?" if ft else
                          "Maaf, belum ada ruangan yang bisa dipinjam saat ini.",
                          "Saat ini semua ruangan sedang memiliki booking aktif atau dinonaktifkan admin, jadi belum ada yang bisa dipinjam." if not ft else
                          f"Belum ada ruangan tersedia ({ft}). Coba kriteria lain."])
        return ex7(text, "list_rooms", args, result, ans, ["belum ada|tidak ada"], ["- ", "mungkin maksud"])
    intro = rng.choice([f"Berikut ruangan tersedia ({ft}):", f"Ruangan yang cocok ({ft}):"] if ft else ["Berikut ruangan yang tersedia untuk dipinjam:", "Ini ruangan yang bisa kamu pinjam saat ini:"])
    if count_q:
        intro = rng.choice([f"Ada {len(found)} ruangan yang tersedia" + (f" ({ft})" if ft else "") + ":", f"Saat ini ada {len(found)} ruangan yang bisa dipinjam" + (f" ({ft})" if ft else "") + ":"])
    lines = "\n".join(f"- {r['name']} ({r['location']}, kapasitas {r['capacity']} orang)" for r in shown)
    tail = ""
    if len(found) > len(shown):
        tail = f"\nDan {len(found) - len(shown)} ruangan lainnya. Sebutkan kapasitas atau lokasi untuk mempersempit pencarian."
    elif rng.random() < 0.5:
        tail = "\n" + rng.choice(["Mau saya bantu booking salah satunya?", "Sebutkan ruangan, tanggal, dan jam kalau mau dibooking.", "Mau cek ketersediaan salah satunya?"])
    return ex7(text, "list_rooms", args, result, f"{intro}\n{lines}{tail}", [r["name"] for r in shown] + ([str(len(found))] if count_q else []) + ([f"{len(found) - len(shown)} ruangan lainnya"] if len(found) > len(shown) else []))


# ------------------------------------------------------------------ room_info
def has_fac(desc, fac):
    if fac == "AC":
        return "AC" in desc and "tanpa AC" not in desc
    return fac.lower() in desc.lower()


def gen_info(rng, split):
    frame, room_text, room_arg, focus = gt.info_example(rng, split)
    text = fill(stylize(frame, rng), room=room_text)
    args = {"room": room_arg}
    if room_arg not in BY_NAME:
        sg = suggestions(room_arg)
        res = {"ok": False, "error": "room_not_found", "query": room_arg, "suggestions": sg}
        return ex7(text, "room_info", args, res, not_found_answer(rng, room_arg, sg), sg[:2], [])
    r = BY_NAME[room_arg]
    status = r["status"] if r["status"] != "available" or rng.random() > 0.15 else "booked"
    if focus in ("why", "status"):  # status ruangan di database nyata bervariasi; jangan hanya Lab Jaringan yang 'unavailable'
        status = rng.choices(["available", "booked", "unavailable"], weights=[25, 35, 40])[0]
    res = {"ok": True, "room": {"name": r["name"], "location": r["location"], "capacity": r["capacity"], "description": r["description"], "status": status}}
    n, loc, cap, desc = r["name"], r["location"], r["capacity"], r["description"]
    st_text = {"available": "saat ini tersedia dan bisa dipesan", "booked": "saat ini sedang memiliki booking aktif sehingga belum bisa dipesan",
               "unavailable": "sedang tidak tersedia (dinonaktifkan oleh admin) sehingga belum bisa dipinjam"}[status]
    if focus == "capacity":
        ans = rng.choice([f"Kapasitas {n} adalah {cap} orang.", f"{n} bisa menampung hingga {cap} orang."])
        must = [str(cap)]
    elif focus == "location":
        ans = rng.choice([f"{n} berlokasi di {loc}.", f"{n} ada di {loc}."])
        must = [loc]
    elif focus == "facilities":
        fac = next((f for f in ["proyektor", "AC", "whiteboard", "sound system"] if f.lower() in frame.lower() or (f == "AC" and " AC" in frame)), None)
        if fac:
            if has_fac(desc, fac):
                ans = f"Ya, {n} dilengkapi {fac}. {desc}"
            else:
                ans = f"Menurut data sistem, {fac} tidak tercantum di {n}. {desc}"
            must = [("ya" if has_fac(desc, fac) else "tidak")]
        else:
            ans = f"{n}: {desc}"
            must = [desc.split(",")[0].split(".")[0][:25]]
    elif focus == "why":
        if status == "unavailable":
            ans = rng.choice([f"{n} tidak bisa dipesan karena sedang tidak tersedia (dinonaktifkan oleh admin).", f"{n} belum bisa dipesan karena statusnya unavailable, yaitu dinonaktifkan oleh admin.",
                              f"Penyebabnya: {n} sedang dinonaktifkan oleh admin (unavailable), jadi belum bisa dipesan."])
            must = ["dinonaktifkan"]
        elif status == "booked":
            ans = rng.choice([f"{n} tidak bisa dipesan karena sedang memiliki booking aktif.", f"{n} belum bisa dipesan karena statusnya booked: sedang ada booking aktif."])
            must = ["booking aktif"]
        else:
            ans = f"Menurut data, {n} tersedia dan bisa dipesan. Kalau booking gagal, biasanya karena jadwal bentrok atau waktu mulai sudah lewat."
            must = ["tersedia"]
    elif focus == "status":
        ans = f"{n} {st_text}."
        must = [{"available": "tersedia", "booked": "booking aktif", "unavailable": "tidak tersedia"}[status]]
    else:
        ans = f"{n} berlokasi di {loc} dengan kapasitas {cap} orang. {desc} Status saat ini: {st_text}."
        must = [loc, str(cap)]
    must_not = ["booking bisa dilakukan", "tersedia dan bisa dipesan"] if (focus in ("why", "status") and status != "available") else []
    return ex7(text, "room_info", args, res, ans, must, must_not, {"focus": focus})


# ------------------------------------------------------------------ check_availability
def gen_availability_result(rng, split):
    if rng.random() < 0.05:  # tanggal tidak valid
        text_date, dnorm = rng.choice([("tanggal 30 februari", "30 februari"), ("tanggal 31 november", "31 november"), ("31 desember 2027 palsu", None)][:2])
        room = rng.choice(AVAILABLE_ROOMS)
        text = fill(stylize(rng.choice(gt.AV_DAY[split]), rng), room=room_mention(room, rng), date=text_date)
        args = {"room": room["name"], "date_text": dnorm}
        res = {"ok": False, "error": "invalid_date", "date_text": dnorm}
        ans = f'Saya belum bisa memahami tanggal "{dnorm}". Coba sebutkan tanggal yang valid, misalnya "5 November" atau "Senin depan".'
        return ex7(text, "check_availability", args, res, ans, ["tanggal"], [])
    if rng.random() < 0.08:
        q = rng.choice(FAKE_ROOMS)
        dtext, dnorm = date_slot_norm(rng)
        text = fill(stylize(rng.choice(gt.AV_DAY[split]), rng), room=q, date=dtext)
        args = {"room": q, "date_text": dnorm}
        sg = suggestions(q)
        res = {"ok": False, "error": "room_not_found", "query": q, "suggestions": sg}
        return ex7(text, "check_availability", args, res, not_found_answer(rng, q, sg), sg[:2], [])
    room = rng.choice(ROOMS)
    slang = rng.random() < 0.25
    dtext, dnorm = date_slot_norm(rng, slang)
    d = rng_date(rng, dnorm)
    lab = date_label(d)
    with_time = rng.random() < 0.7
    args = {"room": room["name"], "date_text": dnorm}
    ttext = ""
    if with_time:
        ttext, targs = time_args(rng, slang, allow_duration=False)
        args.update(targs)
        frame = rng.choice(gt.AV_TIME[split])
    else:
        frame = rng.choice(gt.AV_DAY[split])
    text = fill(stylize(frame, rng), room=room_mention(room, rng), date=dtext, time=ttext).replace("  ", " ").replace(" ?", "?").replace(" ,", ",")
    n = room["name"]
    status = room["status"] if room["status"] != "available" or rng.random() > 0.07 else "booked"
    if status != "available":
        res = {"ok": True, "room": n, "date_label": lab, "available": False, "reason": "room_unavailable", "room_status": status}
        ans = f"{n} {ROOM_STATUS_TEXT[status]}, jadi saat ini belum bisa dipinjam." if status == "unavailable" else f"{n} {ROOM_STATUS_TEXT[status]}, sehingga saat ini belum bisa dipesan."
        return ex7(text, "check_availability", args, res, ans, ["belum bisa"], ["tersedia pada"])
    if with_time:
        s, e = args["start_time"], args["end_time"]
        if rng.random() < 0.6:
            res = {"ok": True, "room": n, "date_label": lab, "start": s, "end": e, "available": True}
            ans = rng.choice([f"{n} tersedia pada {lab}, pukul {fr(s, e)}. Mau saya bookingkan?", f"Bisa! {n} masih kosong pada {lab} pukul {fr(s, e)}.",
                              f"{n} kosong pada {lab}, pukul {fr(s, e)}. Kalau mau dipesan, sebutkan tujuan peminjamannya ya."])
            return ex7(text, "check_availability", args, res, ans, [dot(s), dot(e)], ["tidak tersedia", "bentrok"])
        sm = int(s[:2]) * 60 + int(s[3:])
        pass
        conf = [overlap_window(rng, s, e)]
        res = {"ok": True, "room": n, "date_label": lab, "start": s, "end": e, "available": False, "reason": "time_conflict",
               "conflicts": [{"start": a, "end": b} for a, b in conf]}
        ans = rng.choice([f"Maaf, {n} sudah dipakai pada {lab}. Jadwal yang bentrok: pukul {fr(*conf[0])}. Coba pilih jam lain atau ruangan lain.",
                          f"{n} tidak tersedia pada jam itu. Pada {lab} sudah ada booking pukul {fr(*conf[0])}."])
        return ex7(text, "check_availability", args, res, ans, [dot(conf[0][0]), dot(conf[0][1])], ["Bisa!"])
    k = rng.choice([0, 0, 1, 2, 3])
    busy = slot_windows(rng, k) if k else []
    res = {"ok": True, "room": n, "date_label": lab, "available": True, "busy": [{"start": a, "end": b} for a, b in busy]}
    if not busy:
        ans = rng.choice([f"Pada {lab}, belum ada booking di {n}, jadi masih kosong seharian.", f"{n} masih kosong seharian pada {lab}."])
        return ex7(text, "check_availability", args, res, ans, ["kosong"], [])
    bt = ", ".join(fr(a, b) for a, b in busy)
    ans = rng.choice([f"Pada {lab}, {n} sudah terpakai pukul {bt}. Di luar jam itu masih kosong.", f"{n} pada {lab} sudah dibooking di jam: {bt}. Selain itu masih tersedia."])
    return ex7(text, "check_availability", args, res, ans, [dot(busy[0][0])], [])


# ------------------------------------------------------------------ book_room
def gen_booking_result(rng, split):
    outcome = rng.choices(["ok", "conflict", "unavail", "past", "end_before", "not_found", "invalid_date"], weights=[55, 16, 10, 6, 3, 6, 4])[0]
    room = rng.choice(ROOMS)
    room_text, room_arg = room_mention(room, rng), room["name"]
    if room["status"] != "available":
        outcome = "unavail"
    if outcome == "not_found":
        room_text = room_arg = rng.choice(FAKE_ROOMS)
    slang = rng.random() < 0.25
    dtext, dnorm = date_slot_norm(rng, slang)
    if outcome == "past":
        dtext, dnorm = rng.choice(["kemarin", "kemarin"]), "kemarin"
    if outcome == "invalid_date":
        dtext, dnorm = rng.choice([("tanggal 30 februari", "30 februari"), ("tanggal 31 november", "31 november")])
    s_min, e_min = pick_times(rng)
    if outcome == "end_before":
        s_min, e_min = e_min, s_min
    ttext, targs = time_args(rng, slang, allow_duration=(outcome == "ok"), start_min=s_min if outcome != "end_before" else None, end_min=e_min if outcome != "end_before" else None) \
        if outcome != "end_before" else (lambda t: (t[0], {"start_time": t[1], "end_time": t[2]}))(time_range_slot(rng, s_min, e_min, slang))
    ptext, parg = purpose_slot(rng, split)
    frame = rng.choice(gt.BOOK[split])
    text = fill(stylize(frame, rng), room=room_text, date=dtext, time=ttext, purpose=ptext)
    args = gt.booking_args(room_arg, dnorm, targs, parg)
    d = rng_date(rng, dnorm) if outcome not in ("past", "invalid_date") else TODAY - dt.timedelta(days=1)
    lab = date_label(d)
    n = room_arg
    if "duration_minutes" in targs:
        s = targs["start_time"]
        e = hm(int(s[:2]) * 60 + int(s[3:]) + targs["duration_minutes"])
    else:
        s, e = targs["start_time"], targs["end_time"]
    if outcome == "ok":
        res = {"ok": True, "booking": {"room": n, "date_label": lab, "start": s, "end": e, "purpose": parg, "status": "approved"}}
        ans = rng.choice([
            f"Booking berhasil! {n} sudah kamu pesan pada {lab}, pukul {fr(s, e)} untuk {parg}. Statusnya approved (langsung disetujui). Kamu bisa membatalkannya di menu My Room Bookings selama belum dimulai.",
            f"Beres! {n} berhasil dibooking pada {lab}, pukul {fr(s, e)} (keperluan: {parg}). Status: approved. Pembatalan bisa dilakukan di menu My Room Bookings sebelum waktu mulai."])
        return ex7(text, "book_room", args, res, ans, [n, dot(s), dot(e)], ["maaf", "gagal"])
    if outcome == "conflict":
        pass
        c = overlap_window(rng, s, e)
        res = {"ok": False, "error": "time_conflict", "room": n, "date_label": lab, "conflicts": [{"start": c[0], "end": c[1]}]}
        ans = rng.choice([f"Maaf, booking gagal karena {n} sudah dipesan pada waktu tersebut ({lab}, pukul {fr(*c)}). Silakan pilih jam lain atau ruangan lain.",
                          f"Booking tidak bisa dibuat: jadwal bentrok dengan booking lain di {n} pada {lab} pukul {fr(*c)}. Mau coba jam atau ruangan lain?"])
        return ex7(text, "book_room", args, res, ans, [dot(c[0]), dot(c[1])], ["berhasil"])
    if outcome == "unavail":
        status = room["status"] if room["status"] != "available" else "booked"
        res = {"ok": False, "error": "room_unavailable", "room": n, "room_status": status}
        ans = f"Maaf, booking gagal karena {n} {ROOM_STATUS_TEXT[status]}, jadi belum bisa dipesan saat ini. Mau coba ruangan lain?"
        return ex7(text, "book_room", args, res, ans, [n], ["berhasil"])
    if outcome == "past":
        res = {"ok": False, "error": "start_in_past", "room": n}
        ans = "Maaf, booking gagal karena waktu mulainya sudah lewat. Pilih tanggal dan jam yang belum berlalu ya."
        return ex7(text, "book_room", args, res, ans, ["lewat"], ["berhasil"])
    if outcome == "end_before":
        res = {"ok": False, "error": "end_before_start", "room": n}
        ans = "Maaf, booking gagal karena jam selesai harus setelah jam mulai. Coba sebutkan ulang jamnya."
        return ex7(text, "book_room", args, res, ans, ["jam selesai"], ["berhasil"])
    if outcome == "not_found":
        sg = suggestions(n)
        res = {"ok": False, "error": "room_not_found", "query": n, "suggestions": sg}
        return ex7(text, "book_room", args, res, not_found_answer(rng, n, sg), sg[:2], ["berhasil"])
    res = {"ok": False, "error": "invalid_date", "date_text": dnorm}
    ans = f'Saya belum bisa memahami tanggal "{dnorm}". Coba sebutkan tanggal yang valid, misalnya "5 November" atau "Senin depan".'
    return ex7(text, "book_room", args, res, ans, ["tanggal"], ["berhasil"])


# ------------------------------------------------------------------ my_bookings
def gen_my_result(rng, split):
    args, tr, ev = rng.choices(gt.MY, weights=gt.MY_WEIGHTS)[0]
    text = fill(stylize(rng.choice(tr if split == "train" else ev), rng))
    count = rng.choices([0, 1, 2, 3, 4, 5, 7], weights=[30, 22, 18, 14, 8, 5, 3])[0]  # kasus kosong sering muncul pada pengguna baru
    items = []
    for _ in range(count):
        room = rng.choice(ROOMS)
        s, e = pick_times(rng)
        status = args.get("status")
        period = args.get("period")
        if status is None:
            status = rng.choice({"upcoming": ["approved", "approved", "pending", "cancelled"], "today": ["approved", "completed", "cancelled"],
                                 "past": ["completed", "completed", "cancelled"], None: ["approved", "completed", "cancelled", "pending"]}[period])
        if period is None:
            period = {"approved": "upcoming", "pending": "upcoming", "completed": "past"}.get(status) or rng.choice(["upcoming", "past"])
        d = {"today": TODAY, "upcoming": TODAY + dt.timedelta(days=rng.randint(1, 40)), "past": TODAY - dt.timedelta(days=rng.randint(1, 40))}[period]
        status = status
        _, parg = purpose_slot(rng, split)
        items.append({"room": room["name"], "date_label": date_label(d), "start": hm(s), "end": hm(e), "purpose": parg, "status": status})
    shown = items[:6]
    res = {"ok": True, "count": len(items), "shown": len(shown), "filters": args, "bookings": shown}
    if not items:
        if "status" in args and "period" not in args:
            ans = f"Tidak ada booking dengan status {STATUS_ID[args['status']]}."
        elif "period" in args and "status" not in args:
            ans = f"Tidak ada booking {PERIOD_ID[args['period']]}."
        elif args:
            ans = f"Tidak ada booking {STATUS_ID[args['status']]} {PERIOD_ID[args['period']]}."
        else:
            ans = rng.choice(["Kamu belum punya booking ruangan.", "Belum ada riwayat peminjaman atas nama kamu."])
        return ex7(text, "my_bookings", args, res, ans, ["booking|peminjaman"], ["- ", "bisa dipinjam", "tersedia"])
    lines = "\n".join(f"- {b['room']}, {b['date_label']}, {fr(b['start'], b['end'])} ({b['purpose']}) - {STATUS_ID[b['status']]}" for b in shown)
    count_q = any(w in text.lower() for w in ("berapa", "jumlah", "total", "banyak"))
    head = rng.choice([f"Kamu punya {len(items)} booking:", f"Saat ini kamu punya {len(items)} booking:"] if count_q else [f"Kamu punya {len(items)} booking:", "Berikut booking kamu:"])
    tail = f"\nDan {len(items) - len(shown)} booking lainnya." if len(items) > len(shown) else ""
    must = [b["room"] for b in shown[:3]] + [dot(shown[0]["start"])] + ([str(len(items))] if count_q else []) + ([f"{len(items) - len(shown)} booking lainnya"] if len(items) > len(shown) else [])
    return ex7(text, "my_bookings", args, res, f"{head}\n{lines}{tail}", must)


# ------------------------------------------------------------------ cancel_booking
def gen_cancel_result(rng, split):
    room = rng.choice(ROOMS)
    room_text, room_arg = room_mention(room, rng), room["name"]
    with_date = rng.random() < 0.7
    if with_date:
        slang = rng.random() < 0.25
        dtext, dnorm = date_slot_norm(rng, slang)
        text = fill(stylize(rng.choice(gt.CANCEL_DATE[split]), rng), room=room_text, date=dtext)
        args = {"room": room_arg, "date_text": dnorm}
        d = rng_date(rng, dnorm)
    else:
        text = fill(stylize(rng.choice(gt.CANCEL_ROOM[split]), rng), room=room_text)
        args = {"room": room_arg}
        d = TODAY + dt.timedelta(days=rng.randint(1, 30))
    lab = date_label(d)
    s, e = pick_times(rng)
    _, parg = purpose_slot(rng, split)
    outcome = rng.choices(["ok", "not_found", "multiple", "cancelled", "completed", "started", "pending"], weights=[55, 10, 0 if with_date else 12, 7, 6, 6, 4])[0]
    n = room_arg
    bk = {"room": n, "date_label": lab, "start": hm(s), "end": hm(e), "purpose": parg}
    if outcome == "ok":
        res = {"ok": True, "booking": {**bk, "status": "cancelled"}}
        ans = rng.choice([f"Booking {n} pada {lab}, pukul {fr(hm(s), hm(e))} sudah dibatalkan. Kalau mau, kamu bisa membuat booking baru.",
                          f"Sudah dibatalkan: {n}, {lab}, pukul {fr(hm(s), hm(e))}."])
        return ex7(text, "cancel_booking", args, res, ans, [n, dot(hm(s))], ["gagal", "tidak bisa"])
    if outcome == "not_found":
        res = {"ok": False, "error": "not_found", **args}
        ans = f"Saya tidak menemukan booking aktif atas nama kamu untuk {n}" + (f" pada tanggal itu." if with_date else ".") + " Cek daftar booking di menu My Room Bookings."
        return ex7(text, "cancel_booking", args, res, ans, [n], ["sudah dibatalkan"])
    if outcome == "multiple":
        ms = [{"date_label": date_label(TODAY + dt.timedelta(days=rng.randint(1, 40))), "start": hm(a), "end": hm(b)} for a, b in [pick_times(rng) for _ in range(2)]]
        res = {"ok": False, "error": "multiple_matches", "room": n, "matches": ms}
        ans = f"Kamu punya beberapa booking {n}: " + "; ".join(f"{m['date_label']}, {fr(m['start'], m['end'])}" for m in ms) + ". Yang mana yang mau dibatalkan?"
        return ex7(text, "cancel_booking", args, res, ans, [ms[0]["date_label"]], ["sudah dibatalkan"])
    reasons = {"cancelled": ("already_cancelled", "Booking itu sudah dibatalkan sebelumnya."),
               "completed": ("already_completed", "Booking itu sudah selesai, jadi tidak bisa dibatalkan."),
               "started": ("already_started", "Booking itu sudah dimulai, jadi tidak bisa dibatalkan. Pembatalan hanya bisa untuk booking approved yang belum dimulai."),
               "pending": ("not_approved", "Booking itu berstatus pending sehingga tidak bisa dibatalkan lewat sistem. Hanya booking approved yang bisa dibatalkan.")}
    code, msg = reasons[outcome]
    res = {"ok": False, "error": "not_cancellable", "reason": code, "booking": bk}
    return ex7(text, "cancel_booking", args, res, msg, [{"cancelled": "sebelumnya", "completed": "selesai", "started": "dimulai", "pending": "pending"}[outcome]], ["berhasil dibatalkan"])


def gen_tool_results(rng, split, counts):
    fns = {"list": gen_list, "info": gen_info, "avail": gen_availability_result, "book": gen_booking_result, "my": gen_my_result, "cancel": gen_cancel_result}
    rows = []
    for key, n in counts.items():
        part = []
        for _ in range(n * 4):
            part.append(fns[key](rng, split))
        rows += dedupe(part)[:n]
    return rows
