"""Pustaka bersama untuk pembangkit dataset EROganizer (ruangan, frasa tanggal/jam, variasi bahasa, penulis JSONL)."""
import datetime as dt
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOMS = json.loads((ROOT / "data" / "rooms.json").read_text(encoding="utf-8"))["rooms"]
BY_NAME = {r["name"]: r for r in ROOMS}
NAMES = [r["name"] for r in ROOMS]
AVAILABLE_ROOMS = [r for r in ROOMS if r["status"] == "available"]
SYSTEM_PROMPT = (ROOT / "system_prompt.txt").read_text(encoding="utf-8").replace("{{ROOMS}}", "; ".join(NAMES)).strip()

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
MONTH_ABBR = {"nov": "november", "des": "desember", "jan": "januari", "feb": "februari"}

# kelompok nama yang ambigu (tanpa nomor) -> kandidat ruangan
GROUPS = {
    "lab komputer": ["Lab Komputer 1", "Lab Komputer 2", "Lab Komputer 3"],
    "lab kom": ["Lab Komputer 1", "Lab Komputer 2", "Lab Komputer 3"],
    "ruang seminar": ["Ruang Seminar 1", "Ruang Seminar 2"],
    "seminar": ["Ruang Seminar 1", "Ruang Seminar 2"],
    "ruang diskusi": ["Ruang Diskusi 1", "Ruang Diskusi 2"],
    "diskusi": ["Ruang Diskusi 1", "Ruang Diskusi 2"],
    "ruang kelas": ["Ruang Kelas A101", "Ruang Kelas A102", "Ruang Kelas B201", "Ruang Kelas B202"],
    "kelas": ["Ruang Kelas A101", "Ruang Kelas A102", "Ruang Kelas B201", "Ruang Kelas B202"],
    "lab": ["Lab Komputer 1", "Lab Komputer 2", "Lab Komputer 3", "Lab Jaringan"],
}

# ruangan yang TIDAK ada di sistem (untuk skenario "tidak ditemukan")
FAKE_ROOMS = ["Ruang Teater", "Lab Fisika", "Ruang Server", "Studio Musik", "Lab Bahasa", "Ruang Sidang Senat",
              "Aula Barat", "Ruang Kelas C301", "Lab Robotik", "Ruang Dosen"]

TRAIN_PURPOSES = [
    "rapat himpunan", "seminar proposal", "kuliah tambahan", "latihan presentasi", "praktikum basis data",
    "diskusi kelompok", "workshop desain UI", "rapat panitia dies natalis", "sidang proyek akhir", "belajar kelompok",
    "pelatihan web", "bimbingan skripsi", "lomba coding", "rapat BEM", "sosialisasi beasiswa", "kuliah tamu",
    "kerja kelompok tugas akhir", "pelatihan Excel", "rapat dosen", "ujian praktikum", "latihan debat",
    "pembekalan KKN", "rapat UKM fotografi", "tutorial Laravel", "presentasi tugas besar", "review desain aplikasi",
    "persiapan hackathon", "rapat organisasi", "kelas pengganti", "seminar hasil",
    # tujuan singkat/generik (model sempat mengarang "Rapat Dekanat" untuk "buat rapat") dan kata "evaluasi" (sempat menjadi "Evaluate")
    "rapat", "diskusi", "belajar bareng", "kuliah", "ujian", "praktikum", "pelatihan", "presentasi", "evaluasi kegiatan", "evaluasi program kerja",
]
EVAL_PURPOSES = [
    "pelatihan Python", "rapat koordinasi asisten lab", "bimbingan akademik", "diskusi proposal penelitian",
    "presentasi kerja praktik", "simulasi wawancara kerja", "ujian remedial", "workshop UI/UX", "rapat angkatan",
    "latihan public speaking", "pelatihan data science", "sosialisasi magang", "evaluasi proyek kelompok", "rapat redaksi majalah kampus",
]
TRAIN_NOTES = ["bawa laptop sendiri", "butuh 2 mikrofon", "mohon disiapkan proyektor", "peserta sekitar 30 orang",
               "acara internal himpunan", "tolong AC dinyalakan", "butuh stop kontak tambahan", "akan ada tamu dari luar kampus"]
EVAL_NOTES = ["peserta sekitar 15 orang", "butuh papan tulis tambahan", "acara dimulai tepat waktu", "mohon kursi ditata melingkar"]


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def date_label(d: dt.date) -> str:
    return f"{DAYS_ID[d.weekday()]}, {d.day} {MONTHS_ID[d.month - 1]} {d.year}"


def dot(t: str) -> str:
    return t.replace(":", ".")


def hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def random_date(rng: random.Random) -> dt.date:
    start = dt.date(2026, 11, 2)
    while True:
        d = start + dt.timedelta(days=rng.randint(0, 120))
        if d.weekday() < 5 or rng.random() < 0.15:
            return d


def pick_times(rng: random.Random):
    """(start_menit, end_menit) yang masuk akal."""
    while True:
        start = rng.choice([7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]) * 60 + rng.choice([0, 0, 0, 30])
        dur = rng.choice([60, 60, 90, 120, 120, 120, 150, 180, 240])
        if start + dur <= 21 * 60:
            return start, start + dur


# ---------------------------------------------------------------- tool-call helpers
def tool_json(name: str, args: dict) -> str:
    return json.dumps({"tool": name, "args": args}, ensure_ascii=False)


def example(category: str, msgs: list, expect: dict, extra: dict | None = None) -> dict:
    meta = {"expect": expect}
    if extra:
        meta.update(extra)
    return {"category": category, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + msgs, "meta": meta}


def expect_tool(name: str, args: dict) -> dict:
    return {"type": "tool", "tool": name, "args": args}


def expect_text(must=None, must_not=None) -> dict:
    return {"type": "text", "must": must or [], "must_not": must_not or []}


# ---------------------------------------------------------------- slot generators
def purpose_slot(rng, split):
    p = rng.choice(TRAIN_PURPOSES if split == "train" else EVAL_PURPOSES)
    return p, cap(p)


def notes_slot(rng, split):
    n = rng.choice(TRAIN_NOTES if split == "train" else EVAL_NOTES)
    return n, cap(n)


def room_mention(room: dict, rng: random.Random) -> str:
    r = rng.random()
    if r < 0.40:
        return room["name"]
    alias = rng.choice(room["aliases"])
    return alias if r < 0.75 else alias.title().replace("A1", "A1").replace("B2", "B2")


def date_slot(rng: random.Random, slang: bool = False):
    """(teks_pengguna, date_text_ternormalisasi)"""
    kind = rng.choices(["today", "tomorrow", "lusa", "weekday", "weekday_next", "absolute", "absolute_short", "day_only"],
                       weights=[8, 22, 6, 14, 14, 22, 8, 6])[0]
    day_name = rng.choice(DAYS_ID).lower()
    d = rng.randint(1, 28)
    month = rng.choice(["november", "desember", "januari", "februari"])
    if kind == "today":
        return rng.choice(["hari ini", "hari ini", "hari ini juga"]), "hari ini"
    if kind == "tomorrow":
        return ("bsk" if slang and rng.random() < 0.5 else rng.choice(["besok", "besok", "hari besok"])), "besok"
    if kind == "lusa":
        return "lusa", "lusa"
    if kind == "weekday":
        return rng.choice([f"hari {day_name}", day_name, f"pas hari {day_name}"]), day_name
    if kind == "weekday_next":
        return rng.choice([f"{day_name} depan", f"hari {day_name} depan", f"{day_name} minggu depan"]), f"{day_name} depan"
    if kind == "absolute":
        abbr = next((k for k, v in MONTH_ABBR.items() if v == month), None)
        month_txt = rng.choice([month, month.capitalize()] + ([abbr] if abbr else []))
        return rng.choice([f"tanggal {d} {month_txt}", f"tgl {d} {month_txt}", f"{d} {month_txt}"]), f"{d} {month}"
    if kind == "absolute_short":
        return f"tanggal {d} {month.capitalize()} {2027 if month in ('januari', 'februari') else 2026}", None
    return f"tanggal {d}", f"tanggal {d}"


def date_slot_norm(rng, slang=False):
    """Seperti date_slot, tetapi date_text selalu terisi (absolute_short -> dengan tahun)."""
    while True:
        text, norm = date_slot(rng, slang)
        if norm is None:
            m = re.match(r"tanggal (\d+) (\w+) (\d{4})", text)
            norm = f"{m.group(1)} {m.group(2).lower()} {m.group(3)}"
        return text, norm


def _part(h: int) -> str:
    return "pagi" if h < 11 else "siang" if h < 15 else "sore" if h < 19 else "malam"


def time_variants(minutes: int):
    h, m = divmod(minutes, 60)
    h12 = h % 12 or 12
    part = _part(h)
    v = []
    if m == 0:
        v += [("jam ", f"{h12} {part}"), ("jam ", f"{h:02d}.00"), ("pukul ", f"{h:02d}.00"), ("", f"{h:02d}:00"), ("jam ", f"{h}.00")]
        if 7 <= h <= 12:
            v += [("jam ", f"{h}")] * 3
        if h >= 13:
            v += [("jam ", f"{h}")]
    elif m == 30:
        nxt = (h + 1) % 12 or 12
        v += [("jam ", f"{h:02d}.30"), ("pukul ", f"{h:02d}.30"), ("", f"{h:02d}:30"), ("jam ", f"{h12}.30 {part}"), ("jam ", f"setengah {nxt} {part}")]
        if 7 <= h <= 10:
            v += [("jam ", f"setengah {nxt}")] * 2
    else:
        v += [("jam ", f"{h:02d}.{m:02d}"), ("pukul ", f"{h:02d}.{m:02d}")]
    return v


def time_range_slot(rng, start_min: int, end_min: int, slang: bool = False):
    p1, c1 = rng.choice(time_variants(start_min))
    p2, c2 = rng.choice(time_variants(end_min))
    plain = c1.replace(".", "").replace(":", "").isdigit() and c2.replace(".", "").replace(":", "").isdigit()
    sampai = "sampe" if slang and rng.random() < 0.5 else "sampai"
    options = [f"{p1}{c1} {sampai} {p2}{c2}", f"dari {p1}{c1} {sampai} {p2}{c2}", f"{p1}{c1} {sampai} {c2}", f"mulai {p1}{c1} {sampai} {p2}{c2}",
               f"{p1}{c1} hingga {p2}{c2}", f"{p1}{c1} s/d {p2}{c2}"]
    if plain and p1 == p2 == "jam ":
        options += [f"{p1}{c1}-{c2}", f"{p1}{c1} - {c2}"]
    if start_min >= 13 * 60 and end_min <= 18 * 60 + 59 and start_min % 60 == 0 and end_min % 60 == 0:
        s12, e12, part = start_min // 60 - 12, end_min // 60 - 12, _part(end_min // 60)
        options += [f"jam {s12} {sampai} jam {e12} {part}", f"jam {s12} {sampai} {e12} {part}", f"jam {s12}-{e12} {part}", f"jam {s12} {sampai} {e12} {part}"] * 2  # gaya 12-jam sore ("jam 1 sampai 3 sore") diperbanyak
    return rng.choice(options), hm(start_min), hm(end_min)


DURATION_TEXT = {30: ["30 menit"], 45: ["45 menit"], 60: ["1 jam"], 90: ["90 menit", "1,5 jam", "1.5 jam"], 120: ["2 jam"], 150: ["2,5 jam"],
                 180: ["3 jam"], 240: ["4 jam"]}


def duration_slot(rng, start_min: int, dur: int):
    p, c = rng.choice(time_variants(start_min))
    d = rng.choice(DURATION_TEXT[dur])
    text = rng.choice([f"{p}{c} selama {d}", f"mulai {p}{c}, durasi {d}", f"{p}{c} untuk {d}", f"{p}{c}, {d}"])
    return text, hm(start_min), dur


def time_args(rng, slang=False, allow_duration=True, start_min=None, end_min=None):
    """-> (teks_pengguna, args_waktu). Kadang durasi, kadang rentang."""
    if start_min is None:
        start_min, end_min = pick_times(rng)
    dur = end_min - start_min
    if allow_duration and dur in DURATION_TEXT and rng.random() < 0.18:
        text, s, d = duration_slot(rng, start_min, dur)
        return text, {"start_time": s, "duration_minutes": d}
    text, s, e = time_range_slot(rng, start_min, end_min, slang)
    return text, {"start_time": s, "end_time": e}


# ---------------------------------------------------------------- variasi gaya bahasa (hanya pada kerangka kalimat, bukan nilai slot)
SLANG_MAP = {"pinjam": ["pinjem", "minjem"], "tidak": ["gak", "ga", "nggak"], "untuk": ["buat", "utk"], "dengan": ["sama", "dgn"],
             "tolong": ["tlg", "plis", "tolong"], "bisa": ["bs", "bisa"], "saya": ["aku", "saya"], "sudah": ["udah", "sdh"],
             "apakah": ["apa", "apakah"], "berapa": ["brp", "berapa"], "yang": ["yg", "yang"], "ruangan": ["ruang", "ruangan"]}
KEY_TYPOS = {"dicek": ["dciek", "dicke", "diceek"], "cek": ["ckek", "cke", "chek"], "kapan": ["kpaan", "kapn", "kpan"], "aktif": ["akitf", "aktf", "atif"],
             "perlengkapan": ["pelrengkapan", "perlngkapan", "perlengkapn"], "fasilitas": ["fasilitsa", "fasiltas"], "booking": ["bokking", "boking", "bookign"],
             "dibooking": ["dibokking", "diboking"], "tersedia": ["terdesia", "tersdia", "tersedai"], "kosong": ["kosnog", "kosog", "ksosong"],
             "ketersediaan": ["ketersedian", "ketersediann"], "jadwal": ["jadwla", "jdwal", "jaadwal"], "batalkan": ["batlakan", "bataklan"],
             "ruangan": ["ruanagn", "ruagan", "rungan"], "kapasitas": ["kapasiats", "kpasitas"], "lokasi": ["lkoasi", "lokasii"], "peminjaman": ["peminjamn", "pemijaman"]}
SUFFIXES = [" dong", " ya", " nih", " kak", " min", " please", " makasih"]


def _typo(word: str, rng) -> str:
    if len(word) < 5:
        return word
    i = rng.randint(1, len(word) - 3)
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def stylize(frame: str, rng: random.Random, level: float = 1.0) -> str:
    """Terapkan slang/typo/huruf kecil pada kerangka (token ber-{placeholder} tidak disentuh)."""
    tokens = frame.split(" ")
    lower = rng.random() < 0.40 * level
    out = []
    for t in tokens:
        if "{" in t:
            out.append(t)
            continue
        core = re.sub(r"[?.,!]+$", "", t)
        tail = t[len(core):]
        key = core.lower()
        if key in SLANG_MAP and rng.random() < 0.35 * level:
            core = rng.choice(SLANG_MAP[key])
        elif key in KEY_TYPOS and rng.random() < 0.25 * level:
            core = rng.choice(KEY_TYPOS[key])
        elif rng.random() < 0.08 * level:
            core = _typo(core, rng)
        if lower:
            core = core.lower()
        out.append(core + tail)
    s = " ".join(out)
    if rng.random() < 0.35 * level:
        s = s.rstrip("?.!")
    if rng.random() < 0.08 * level:
        s = rng.choice(["Halo, ", "Permisi, ", "Kak, ", "Hai, ", "Min, "]) + s[:1].lower() + s[1:]
    if rng.random() < 0.12 * level:
        s = s.rstrip("?.!") + rng.choice(SUFFIXES)
    return s


def fill(frame: str, **slots) -> str:
    return frame.format_map({k: v for k, v in slots.items()})


# ---------------------------------------------------------------- penulis
def write_jsonl(path: Path, rows: list, prefix: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({"id": f"{prefix}-{i:04d}", **r}, ensure_ascii=False) + "\n")


def last_user(ex: dict) -> str:
    users = [m["content"] for m in ex["messages"] if m["role"] == "user"]
    return users[-1] if users else ""


def dedupe(rows: list, seen: set | None = None) -> list:
    seen = set() if seen is None else seen
    out = []
    for r in rows:
        key = json.dumps([m["content"] for m in r["messages"][1:]], ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
