"""Kategori 01-05: pesan pengguna (satu giliran) -> tool call JSON."""
import random

from common import *

LOCATIONS = [("Gedung A", ["Gedung A", "gedung A", "gedung a"]), ("Gedung B", ["Gedung B", "gedung B", "gedung b"]),
             ("Perpustakaan", ["Perpustakaan", "perpustakaan"])]
CAPS = [5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]
KEYWORDS = [("facility", "yang ada proyektornya", "proyektor"), ("facility", "yang pakai AC", "AC"),
            ("facility", "yang ada whiteboard", "whiteboard"), ("facility", "yang ada sound system", "sound system"),
            ("facility", "yang ada PC-nya", "PC"), ("kind", "lab", "lab"), ("kind", "lab komputer", "lab komputer"),
            ("kind", "ruang seminar", "seminar"), ("kind", "ruang diskusi", "diskusi"), ("kind", "ruang kelas", "kelas"),
            ("kind", "ruang rapat", "rapat"), ("kind", "studio", "studio")]

# ------------------------------------------------------------------ 01 cari ruangan
LIST_NONE = {"train": ["Ruangan apa saja yang tersedia?", "Ada ruangan kosong?", "Tolong tampilkan daftar ruangan",
                       "Mau lihat ruangan yang bisa dipinjam", "Ruangan apa aja yang bisa dipakai?", "Daftar ruangan dong",
                       "Ada ruangan apa saja di fakultas?", "Saya mau tahu ruangan apa yang bisa dipinjam", "Ruangan apa yang available?", "Berapa ruangan yang kosong?", "Ada berapa ruangan yang tersedia?", "Ruangan yang bisa dipinjam ada berapa?",
                       "ada berapa ruangan yang bisa di booking?", "Berapa ruangan yang bisa dipesan?", "Ruangan yang bisa dibooking ada berapa?", "Ada berapa ruangan yang bisa dipakai?",
                       "Jumlah ruangan yang tersedia berapa?", "Ada berapa ruangan kosong sekarang?", "Berapa banyak ruangan yang bisa saya pakai?"],
             "eval": ["Boleh lihat semua ruangan yang tersedia?", "Apa saja ruangan yang bisa saya booking?", "Tunjukkan ruangan yang masih bisa dipesan", "Sekarang tersedia berapa ruangan kosong?"]}
LIST_CAP = {"train": ["Cari ruangan yang muat {n} orang", "Ada ruangan dengan kapasitas minimal {n} orang?", "Saya butuh ruangan untuk {n} orang",
                      "Ruangan yang bisa menampung {n} orang apa ya?", "Ruangan buat {n} orang ada?", "Tampilkan ruangan berkapasitas {n} orang ke atas"],
            "eval": ["Adakah ruangan yang cukup untuk {n} orang?", "Rekomendasikan ruangan yang muat minimal {n} peserta"]}
LIST_LOC = {"train": ["Ruangan apa saja di {loc}?", "Ada ruangan yang tersedia di {loc}?", "Tampilkan ruangan di {loc}", "Mau cari ruangan di {loc}"],
            "eval": ["Di {loc} ada ruangan apa saja yang bisa dipinjam?", "Ruangan yang berlokasi di {loc} apa saja?"]}
LIST_KW_FAC = {"train": ["Ruangan {kwp} apa saja?", "Ada ruangan {kwp}?", "Tampilkan ruangan {kwp}", "Cari ruangan {kwp}", "ruangan {kwp} yang tersedia apa aja ya?", "Ada berapa ruangan {kwp}?", "Ruangan {kwp} ada di mana saja?"],
               "eval": ["Mau cari ruangan {kwp}, ada?", "Daftar ruangan {kwp} dong"]}
LIST_KW_KIND = {"train": ["Ada {kwp} yang tersedia?", "Tampilkan daftar {kwp}", "Mau lihat {kwp} yang bisa dipinjam", "{kwp} apa saja yang ada?", "Cari {kwp}", "Carikan {kwp} dong", "Bisa tunjukkan {kwp}?", "{kwp} ada berapa?", "{kwp} yang ada di mana saja?", "Di mana saya bisa menemukan {kwp}?", "Ada {kwp} yang ukurannya kecil?", "Cari {kwp} yang luas", "{kwp} yang besar ada?", "Adakah {kwp} yang bisa digunakan?", "Ada {kwp} yang bisa dipakai hari ini?",
                         "Ada berapa {kwp}?", "{kwp} ada berapa sih?", "Jumlah {kwp} berapa?"],
                "eval": ["Apakah ada {kwp} yang bisa dipakai?", "Tolong carikan {kwp}"]}
LIST_CAP_KW = {"train": ["Cari {kwp} untuk {n} orang", "Ada {kwp} yang muat {n} orang?", "{kwp} yang kapasitasnya minimal {n} orang ada?"],
               "eval": ["Butuh {kwp} buat {n} orang, ada?"]}
LIST_CAP_LOC = {"train": ["Ruangan di {loc} yang muat {n} orang", "Ada ruangan di {loc} untuk {n} orang?"],
                "eval": ["Cari ruangan {n} orang di {loc}"]}

INFO_FRAMES = {
    "capacity": {"train": ["Kapasitas {room} berapa?", "{room} bisa menampung berapa orang?", "Berapa orang yang muat di {room}?", "{room} muat berapa orang ya?", "Kapasitas {room}?", "{room} muatnya berapa orang?", "{room} brp orang?", "Kapasitas maksimum {room} brp?"],
                 "eval": ["Daya tampung {room} berapa?", "Berapa kapasitas maksimal {room}?"]},
    "location": {"train": ["{room} letaknya di mana?", "Di gedung mana {room}?", "Lokasi {room} di mana ya?", "{room} ada di lantai berapa?"],
                 "eval": ["Di mana posisi {room}?", "Tolong kasih tahu lokasi {room}"]},
    "facilities": {"train": ["Fasilitas {room} apa saja?", "{room} ada proyektornya?", "Apakah {room} pakai AC?", "{room} dilengkapi apa saja?", "{room} ada whiteboard nggak?"],
                   "eval": ["Apa saja perlengkapan di {room}?", "Ada sound system di {room}?"]},
    "status": {"train": ["Apakah {room} sedang tersedia?", "Status {room} saat ini apa?", "{room} lagi bisa dipinjam nggak?", "{room} sedang tidak dipakai?", "{room} bisa dipinjam sekarang?", "Apakah {room} bisa dipakai saat ini?", "Sekarang {room} bisa dibooking?"],
               "eval": ["Bisakah {room} dipinjam saat ini?", "Gimana kondisi {room}, tersedia?"]},
    "general": {"train": ["Ceritakan tentang {room}", "Info {room} dong", "Tolong jelaskan {room}", "Detail {room} apa saja?", "Mau tahu soal {room}"],
                "eval": ["Saya penasaran dengan {room}, bisa dijelaskan?", "Informasi lengkap {room} ya"]},
}
INFO_WEIGHTS = {"capacity": 25, "location": 15, "facilities": 25, "status": 15, "general": 20}
INFO_FRAMES["why"] = {"train": ["Kok {room} nggak bisa dibooking?", "Kenapa {room} tidak bisa dipesan?", "{room} tidak bisa dipinjam, kenapa ya?", "Mengapa saya tidak dapat memesan {room}?", "Kok {room} gak bisa dipilih?", "Kok saya tidak bisa booking {room}?", "{room} nggak bisa dipesan, ada masalah apa?", "Apa alasan {room} tidak bisa dibooking?", "Kenapa {room} gak bisa dipinjam sekarang?"],
                      "eval": ["Kenapa {room} nggak bisa saya booking?"]}
INFO_WEIGHTS["why"] = 22


def _style(frame, rng, **slots):
    return fill(stylize(frame, rng), **slots)


def list_rooms_example(rng, split):
    kind = rng.choices(["none", "cap", "loc", "kw", "cap_kw", "cap_loc"], weights=[18, 24, 16, 24, 9, 9])[0]
    if kind == "none":
        return LIST_NONE[split], {}, {}
    if kind == "cap":
        n = rng.choice(CAPS)
        return LIST_CAP[split], {"n": n}, {"min_capacity": n}
    if kind == "loc":
        canon, variants = rng.choice(LOCATIONS)
        loc = rng.choice(variants)
        return LIST_LOC[split], {"loc": loc}, {"location": canon}
    if kind == "kw":
        k, kwp, canon = rng.choice(KEYWORDS)
        return (LIST_KW_FAC if k == "facility" else LIST_KW_KIND)[split], {"kwp": kwp}, {"keyword": canon}
    if kind == "cap_kw":
        k, kwp, canon = rng.choice([x for x in KEYWORDS if x[0] == "kind"])
        n = rng.choice(CAPS)
        return LIST_CAP_KW[split], {"kwp": kwp, "n": n}, {"min_capacity": n, "keyword": canon}
    canon, variants = rng.choice(LOCATIONS)
    n = rng.choice(CAPS)
    return LIST_CAP_LOC[split], {"loc": rng.choice(variants), "n": n}, {"min_capacity": n, "location": canon}


def info_example(rng, split):
    focus = rng.choices(list(INFO_WEIGHTS), weights=list(INFO_WEIGHTS.values()))[0]
    if rng.random() < 0.08:
        room_text = rng.choice(FAKE_ROOMS)
        room_arg = room_text
    else:
        room = rng.choice(ROOMS)
        room_text, room_arg = room_mention(room, rng), room["name"]
    frame = rng.choice(INFO_FRAMES[focus][split])
    return frame, room_text, room_arg, focus


def gen_room_search(rng, split, n_list, n_info):
    rows = []
    for _ in range(n_list * 3):
        frames, slots, args = list_rooms_example(rng, split)
        text = _style(rng.choice(frames), rng, **slots)
        rows.append(example("01_room_search", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("list_rooms", args)}],
                            expect_tool("list_rooms", args), {"sub": "list_rooms"}))
    rows = dedupe(rows)[:n_list]
    info = []
    for _ in range(n_info * 4):
        frame, room_text, room_arg, focus = info_example(rng, split)
        text = _style(frame, rng, room=room_text)
        args = {"room": room_arg}
        info.append(example("01_room_search", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("room_info", args)}],
                            expect_tool("room_info", args), {"sub": "room_info", "focus": focus}))
    return rows + dedupe(info)[:n_info]


# ------------------------------------------------------------------ 02 ketersediaan
AV_TIME = {"train": ["Apakah {room} kosong {date} {time}?", "Cek ketersediaan {room} {date} {time}", "{room} bisa dipakai {date} {time}?",
                     "Kira-kira {room} masih kosong {date} {time}?", "Boleh cek {room} {date}, {time}?", "Available nggak {room} {date} {time}?",
                     "{room} {date} {time} ada yang pakai?", "Tolong cek apakah {room} bisa dipinjam {date} {time}", "Apakah {room} free {date} {time}?", "{room} free nggak {date} {time}?", "{room} nganggur nggak {date} {time}?",
                     "Dicek dulu {room} {date} {time}, kosong?", "Coba cek {room} buat {date} {time}", "Mau ngecek {room} {date} {time}, ada yang pakai?", "Cek dong {room} {date} {time}, bisa nggak?", "{room} kosong nggak {date} {time}?", "{date} {time}, {room} kosong nggak?", "Cek {room} kosong atau tidak {date} {time}"],
           "eval": ["Mau tahu, {room} free tidak {date} {time}?", "Bisa dicek {room} untuk {date} {time}?", "Apakah slot {room} {date} {time} masih terbuka?"]}
AV_DAY = {"train": ["{room} kosong {date}?", "Jam berapa saja {room} kosong {date}?", "Cek jadwal {room} {date}", "Apakah {room} dipakai {date}?",
                    "{room} {date} ada yang pinjam?", "Bagaimana jadwal {room} {date}?", "Tampilkan jadwal pemakaian {room} {date}", "Lihat jadwal {room} untuk {date}", "Jadwal pakai {room} {date} apa saja?"],
          "eval": ["Tolong lihatkan jadwal pemakaian {room} {date}", "{room} {date} masih ada slot kosong?"]}


def gen_availability(rng, split, n):
    rows = []
    for _ in range(n * 3):
        if rng.random() < 0.08:
            room_text = room_arg = rng.choice(FAKE_ROOMS)
        else:
            room = rng.choice(ROOMS)
            room_text, room_arg = room_mention(room, rng), room["name"]
        slang = rng.random() < 0.25
        dtext, dnorm = date_slot_norm(rng, slang)
        args = {"room": room_arg, "date_text": dnorm}
        if rng.random() < 0.7:
            ttext, targs = time_args(rng, slang, allow_duration=False)
            args.update(targs)
            frame = rng.choice(AV_TIME[split])
        else:
            ttext = ""
            frame = rng.choice(AV_DAY[split])
        text = _style(frame, rng, room=room_text, date=dtext, time=ttext).replace("  ", " ").replace(" ?", "?").replace(" ,", ",")
        rows.append(example("02_room_availability", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("check_availability", args)}],
                            expect_tool("check_availability", args)))
    return dedupe(rows)[:n]


# ------------------------------------------------------------------ 03 booking
BOOK = {"train": [
    "Saya mau pinjam {room} {date} {time} untuk {purpose}.", "Mau booking {room} {date} {time}, untuk {purpose}", "Tolong pesankan {room} {date} {time} buat {purpose}",
    "Bisa pinjam {room} {date} {time}? Keperluannya {purpose}", "Pinjam {room} {date} {time} untuk {purpose} ya", "Aku mau reservasi {room} untuk {purpose}, {date} {time}",
    "Boleh saya booking {room} {date} {time} untuk {purpose}?", "{date} {time} saya butuh {room} buat {purpose}", "Booking {room} dong, {date} {time}, buat {purpose}",
    "Saya ingin meminjam {room} pada {date}, {time}. Tujuannya {purpose}.", "Tolong bookingkan {room} untuk {purpose} {date} {time}", "Reservasi {room} {date} {time} - {purpose}",
    "Pesan {room} {date} {time} untuk keperluan {purpose}", "mau pinjam {room} buat {purpose}, {date}, {time}", "Bisa tolong booking {room} {date} {time}? Untuk {purpose}",
    "Halo, saya mau meminjam {room} untuk {purpose} pada {date} {time}", "Booking {room} untuk {purpose} {date} {time}", "Saya perlu {room} {date} {time} untuk {purpose}, bisa dipesan?",
    "Ruang yang saya mau: {room}. Waktu: {date}, {time}. Keperluan: {purpose}", "Pinjam {room} ya, {date} {time}, {purpose}",
    "Apakah saya bisa memesan {room} {date} {time} untuk {purpose}?", "Book {room} {date} {time} buat {purpose}",
    "Mau pinjam {room} {date} {time}, agendanya {purpose}", "Kami berencana memakai {room} {date} {time} untuk {purpose}", "Tolong catat peminjaman {room} {date} {time}, acaranya {purpose}",
    "Pesan {room} untuk {date} {time}, rencananya {purpose}", "{room} {date} {time} buat {purpose} ya", "Saya ada rencana {purpose} di {room} {date} {time}, tolong dibookingkan",
    "Bisa booking {room}? {date} {time}, untuk {purpose}", "Booking dong {room} buat {purpose}. {date}, {time}", "Pinjam {room} {date} {time}, intinya buat {purpose}",
    "Aku mau pakai {room} {date} {time}. Kegiatannya {purpose}", "Tolong siapkan {room} {date} {time} untuk {purpose}", "Request pinjam {room} {date} {time} untuk kegiatan {purpose}",
    "Halo, bisa pinjam {room}? Waktunya {date} {time}, tujuannya {purpose}", "Saya mau {room} {date} {time} ya, keperluan {purpose}"],
    "eval": [
    "Mohon bantu pinjamkan {room} pada {date} {time} guna {purpose}.", "Aku butuh {room} {date} {time}, rencananya buat {purpose}", "Bantu booking {room} ya, {purpose}, {date} {time}",
    "Tolong reservasikan {room} untuk {purpose} {date} {time}", "{room} {date} {time} untuk {purpose}, bisa saya pinjam?", "Kami mau memakai {room} {date} {time} untuk {purpose}",
    "Saya ada kegiatan {purpose}, mau pinjam {room} {date} {time}", "Request booking: {room}, {date}, {time}, {purpose}"]}
NOTE_SUFFIX = [" Catatan: {notes}.", " (catatan: {notes})", " Notes: {notes}", " Oh ya, {notes}.", " Note: {notes}", " Tambahan: {notes}", " NB: {notes}", " Keterangan: {notes}.", " Catatan tambahan: {notes}"]


def booking_args(room_arg, dnorm, targs, purpose_arg, notes_arg=None):
    args = {"room": room_arg, "date_text": dnorm, **targs, "purpose": purpose_arg}
    if notes_arg:
        args["notes"] = notes_arg
    return args


def gen_booking(rng, split, n):
    rows = []
    for _ in range(n * 3):
        if rng.random() < 0.05:
            room_text = room_arg = rng.choice(FAKE_ROOMS)
        else:
            room = rng.choice(ROOMS)
            room_text, room_arg = room_mention(room, rng), room["name"]
        slang = rng.random() < 0.25
        dtext, dnorm = date_slot_norm(rng, slang)
        ttext, targs = time_args(rng, slang)
        ptext, parg = purpose_slot(rng, split)
        frame = rng.choice(BOOK[split])
        notes_arg = None
        if rng.random() < 0.30:
            ntext, notes_arg = notes_slot(rng, split)
            frame = frame.rstrip("?.") + rng.choice(NOTE_SUFFIX)
        text = _style(frame, rng, room=room_text, date=dtext, time=ttext, purpose=ptext, notes=ntext if notes_arg else "")
        args = booking_args(room_arg, dnorm, targs, parg, notes_arg)
        rows.append(example("03_booking_create", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("book_room", args)}],
                            expect_tool("book_room", args)))
    return dedupe(rows)[:n]


# ------------------------------------------------------------------ 04 booking saya
MY = [  # (args, frames_train, frames_eval)
    ({}, ["Apa saja ruangan yang saya pinjam?", "Lihat booking saya", "Booking saya apa saja?", "Tampilkan riwayat peminjaman saya", "Ruangan apa saja yang sudah saya booking?",
          "my bookings", "Daftar pinjaman saya dong", "Saya sudah pinjam ruangan apa saja ya?", "Cek peminjaman ruangan saya"],
     ["Tolong tampilkan semua booking milik saya", "Booking apa saja yang saya miliki?", "ada berapa ruangan yang saya booking?"]),
    ({"period": "upcoming"}, ["Booking saya yang akan datang apa saja?", "Jadwal peminjaman saya ke depan?", "Ruangan apa yang akan saya pakai nanti?", "Booking saya yang belum dimulai?"],
     ["Saya punya jadwal pinjam apa saja ke depannya?", "Peminjaman mendatang saya apa?"]),
    ({"status": "approved", "period": "upcoming"}, ["Booking aktif saya apa saja?", "Booking saya yang masih berlaku?", "Peminjaman saya yang aktif apa saja?"],
     ["Apa booking aktif yang saya punya?"]),
    ({"period": "today"}, ["Hari ini saya pinjam ruangan apa?", "Ada booking saya hari ini?", "Jadwal ruangan saya hari ini apa?"],
     ["Hari ini saya ada pemakaian ruangan nggak?"]),
    ({"period": "past"}, ["Riwayat booking saya yang sudah lewat", "Ruangan apa saja yang pernah saya pinjam?", "Booking saya sebelumnya apa saja?"],
     ["Peminjaman saya yang lalu apa saja?", "Saya pernah pinjam apa saja?"]),
    ({"status": "cancelled"}, ["Booking saya yang dibatalkan apa saja?", "Lihat booking yang sudah saya cancel", "Peminjaman saya yang batal?"],
     ["Tampilkan booking saya yang berstatus cancelled"]),
    ({"status": "completed"}, ["Booking saya yang sudah selesai?", "Ruangan yang sudah selesai saya pakai apa saja?", "Peminjaman saya yang completed apa saja?"],
     ["Tunjukkan booking saya yang telah selesai"]),
    ({"status": "approved"}, ["Booking saya yang disetujui apa saja?", "Booking yang approved punya saya", "Peminjaman saya yang berstatus approved?"],
     ["Tampilkan booking saya yang sudah disetujui"]),
    ({"status": "pending"}, ["Booking saya yang masih pending?", "Ada peminjaman saya yang menunggu persetujuan?", "Booking saya yang berstatus pending apa saja?"],
     ["Apakah ada booking saya yang pending?"]),
]
MY_WEIGHTS = [22, 14, 12, 12, 12, 8, 7, 7, 6]
_EXTRA_MY = {  # tambahan kerangka (train) supaya "booking SAYA" tidak tertukar dengan permintaan admin/orang lain
    0: ["Dulu aku pinjam ruangan apa saja ya?", "Tampilkan jadwal peminjaman saya", "Lihat semua pinjaman aku", "Saya punya booking apa saja?", "Booking atas nama saya apa aja?",
        "Daftar booking milik saya", "Cek reservasi saya", "Apa saja ruangan yang aku pesan?", "Tunjukkan peminjaman saya", "Boleh lihat booking punyaku?", "Tolong cek peminjaman atas nama saya",
        # pertanyaan berbentuk hitungan tentang booking SAYA (bukan daftar ruangan tersedia)
        "Total booking saya berapa?", "Berapa jumlah peminjaman saya?", "Aku punya berapa booking sekarang?", "Ada berapa booking atas nama saya?", "Berapa banyak ruangan yang sedang aku pinjam?", "Sampai sekarang aku sudah booking berapa kali?"],
    1: ["Tampilkan booking saya yang mendatang", "Peminjaman saya minggu-minggu ke depan apa?", "Booking saya yang belum terjadi?", "Jadwal pinjam saya berikutnya apa?", "Aku nanti pinjam apa aja?",
        "Tolong tampilkan jadwal pemakaian ruangan saya selanjutnya", "Apa saja booking saya yang belum dimulai?",
        # tanpa kata "saya" (jangan tertukar dengan permintaan admin "semua booking")
        "Lihat peminjaman yang akan datang", "Jadwal peminjaman mendatang ada apa saja?", "Tunjukkan jadwal pinjam ke depan", "Peminjaman ke depan apa saja?", "Yang akan datang apa saja peminjamannya?"],
    2: ["Booking saya yang masih aktif?", "Peminjaman aktif saya apa?", "Booking saya yang masih berlaku apa saja?"],
    3: ["Aku hari ini ada pinjam ruangan apa?", "Booking saya untuk hari ini", "Ada jadwal pakai ruangan hari ini?", "Hari ini saya ada booking nggak?", "Aku ada pakai ruangan hari ini nggak?", "Hari ini ada pemakaian ruangan atas nama saya?", "Ada booking aku hari ini?", "Hari ini aku bookingnya apa?"],
    4: ["Booking saya yang sudah lewat apa saja?", "Riwayat pinjam saya sebelumnya", "Ruangan apa yang dulu saya pinjam?", "Yang sudah pernah aku pinjam apa aja?", "Pernah pinjam ruangan apa aja aku?", "Ruangan apa yang pernah aku booking?", "Aku pernah booking apa saja?"],
    5: ["Daftar booking yang pernah aku batalkan", "Pinjaman saya yang di-cancel apa aja?", "Booking yang batal punya saya", "Lihat riwayat booking saya yang dibatalkan", "Daftar yang pernah aku batalin", "Mana peminjaman yang sudah kubatalkan?", "Apa aja yang udah aku cancel?"],
    6: ["Daftar booking saya yang sudah selesai", "Peminjaman yang sudah kelar punya saya", "Booking saya yang statusnya completed"],
    7: ["Booking approved saya", "Peminjaman saya yang disetujui", "Tampilkan booking saya yang approved"],
    8: ["Booking pending saya ada?", "Peminjaman saya yang menunggu", "Ada booking saya yang masih pending?"],
}
for _i, _extra in _EXTRA_MY.items():
    MY[_i][1].extend(_extra)


def gen_my_bookings(rng, split, n):
    rows = []
    for _ in range(n * 6):
        args, tr, ev = rng.choices(MY, weights=MY_WEIGHTS)[0]
        text = _style(rng.choice(tr if split == "train" else ev), rng)
        rows.append(example("04_my_bookings", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("my_bookings", args)}],
                            expect_tool("my_bookings", args)))
    return dedupe(rows)[:n]


# ------------------------------------------------------------------ 05 batalkan booking
CANCEL_DATE = {"train": ["Tolong batalkan booking {room} {date}", "Cancel pinjaman {room} {date}", "Saya mau membatalkan peminjaman {room} {date}",
                         "Batalin booking {room} {date} dong", "Booking {room} {date} tidak jadi, tolong dibatalkan", "Batalkan pesanan saya untuk {room} {date}"],
               "eval": ["Mohon dibatalkan peminjaman {room} untuk {date}", "Saya batal pinjam {room} {date}, tolong cancel"]}
CANCEL_ROOM = {"train": ["Batalkan booking {room} saya", "Cancel {room}", "Saya mau cancel booking {room}", "Tolong batalkan peminjaman {room}",
                         "Yang di {room} tolong dicancel", "Batalin yang buat {room} ya", "Yang {room} nggak jadi, cancel"],
               "eval": ["Booking {room} saya tolong dibatalkan ya", "Aku nggak jadi pakai {room}, cancel dong"]}


def gen_cancel(rng, split, n):
    rows = []
    for _ in range(n * 4):
        room = rng.choice(ROOMS)
        room_text, room_arg = room_mention(room, rng), room["name"]
        if rng.random() < 0.7:
            slang = rng.random() < 0.25
            dtext, dnorm = date_slot_norm(rng, slang)
            text = _style(rng.choice(CANCEL_DATE[split]), rng, room=room_text, date=dtext)
            args = {"room": room_arg, "date_text": dnorm}
        else:
            text = _style(rng.choice(CANCEL_ROOM[split]), rng, room=room_text)
            args = {"room": room_arg}
        rows.append(example("05_booking_cancel", [{"role": "user", "content": text}, {"role": "assistant", "content": tool_json("cancel_booking", args)}],
                            expect_tool("cancel_booking", args)))
    return dedupe(rows)[:n]
