"""
Probe model lewat layanan HTTP (server.py) dengan HASIL TOOL REKAYASA, untuk menguji apakah jawaban
benar-benar mengikuti data di pesan role "tool" (bukan hafalan data training).

  venv\\Scripts\\python.exe training\\scripts\\probe.py [url]      (default http://127.0.0.1:8002)
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SYSTEM_PROMPT  # noqa: E402

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002").rstrip("/") + "/chat"


def chat(messages):
    body = json.dumps({"messages": messages, "max_new_tokens": 400, "temperature": 0.0}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["reply"]


def tool(o):
    return json.dumps(o, ensure_ascii=False).replace('", "', '", "')  # gaya Python seperti di data training


def rooms(n, cap=40):
    names = ["Aula Utama", "Ruang Seminar 1", "Ruang Seminar 2", "Lab Komputer 1", "Lab Komputer 2", "Lab Komputer 3", "Ruang Multimedia", "Ruang Rapat Dekanat"]
    return [{"name": names[i], "location": "Gedung A Lt.1", "capacity": cap + i} for i in range(n)]


def b(room, d, s, e, p, st):
    return {"room": room, "date_label": d, "start": s, "end": e, "purpose": p, "status": st}


SYS = {"role": "system", "content": SYSTEM_PROMPT}
CASES = []


def case(title, user, call, result):
    CASES.append((title, [SYS, {"role": "user", "content": user}, {"role": "assistant", "content": call}, {"role": "tool", "content": tool(result)}]))


# --- angka harus mengikuti hasil tool
case("list_rooms count=11 (hafalan training: 14)", "Ada berapa ruangan kosong yang bisa di booking?", '{"tool": "list_rooms", "args": {}}',
     {"ok": True, "count": 11, "shown": 8, "filters": {}, "rooms": rooms(8)})
case("list_rooms count=3", "Ada berapa ruangan kosong yang bisa di booking?", '{"tool": "list_rooms", "args": {}}',
     {"ok": True, "count": 3, "shown": 3, "filters": {}, "rooms": rooms(3)})
case("list_rooms count=0", "Ada berapa ruangan kosong yang bisa di booking?", '{"tool": "list_rooms", "args": {}}',
     {"ok": True, "count": 0, "shown": 0, "filters": {}, "rooms": []})
# --- "booking saya": pertanyaan berbentuk hitungan
EMPTY = {"ok": True, "count": 0, "shown": 0, "filters": {}, "bookings": []}
THREE = {"ok": True, "count": 3, "shown": 3, "filters": {}, "bookings": [
    b("Aula Utama", "Kamis, 5 November 2026", "10:00", "12:00", "Rapat himpunan", "approved"),
    b("Lab Komputer 1", "Jumat, 6 November 2026", "13:00", "15:00", "Praktikum basis data", "approved"),
    b("Ruang Diskusi 1", "Senin, 9 November 2026", "09:00", "10:30", "Belajar kelompok", "pending")]}
for q in ["ada berapa ruangan yang saya booking?", "berapa booking saya?", "saya sudah booking berapa ruangan?", "Booking saya apa saja?"]:
    case(f"my_bookings kosong | {q}", q, '{"tool": "my_bookings", "args": {}}', EMPTY)
case("my_bookings 3 booking | ada berapa ruangan yang saya booking?", "ada berapa ruangan yang saya booking?", '{"tool": "my_bookings", "args": {}}', THREE)
# --- alasan ruangan tidak bisa dipesan
for st in ["unavailable", "booked", "available"]:
    case(f"room_info why status={st}", "Kenapa Lab Jaringan nggak bisa dipesan?", '{"tool": "room_info", "args": {"room": "Lab Jaringan"}}',
         {"ok": True, "room": {"name": "Lab Jaringan", "location": "Gedung B Lt.2", "capacity": 25, "description": "Lab praktikum jaringan dengan router, switch, dan rak server.", "status": st}})

print(f"Probe -> {URL}\n")
for title, msgs in CASES:
    print(f"## {title}\n{chat(msgs)}\n")

print("=" * 70 + "\nKeputusan tool (tanpa hasil tool): tool & argumen apa yang dipilih model?\n")
for q in ["ada berapa ruangan yang saya booking?", "saya pernah pinjam apa saja?", "Hari ini saya ada pemakaian ruangan nggak?", "Tolong tampilkan jadwal peminjaman yang akan datang",
          "Booking yang aku batalin kemarin mana?", "Besok Aula Utama kosong nggak jam 1 sampai 3 sore?", "Pinjam ruang Teater besok jam 9 sampai 11 buat rapat",
          "Pinjam Aula Utama besok jam 9 sampai 11 buat rapat", "Pinjam Aula Utama besok jam 9 sampai 11 buat diskusi"]:
    print(f"- {q}\n    -> {chat([SYS, {'role': 'user', 'content': q}])}")
