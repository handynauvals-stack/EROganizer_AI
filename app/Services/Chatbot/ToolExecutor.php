<?php

namespace App\Services\Chatbot;

use App\Models\Room;
use App\Models\RoomBooking;
use Carbon\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Menjalankan tool call yang DIUSULKAN model terhadap database EROganizer.
 *
 * Model tidak pernah menyentuh database. Alurnya: model -> {"tool": ..., "args": ...} -> kelas ini -> hasil (JSON)
 * -> dikirim balik ke model sebagai pesan role "tool" -> model menjelaskan hasilnya.
 *
 * PENTING: bentuk hasil (nama kunci, kode error, urutan kunci) mengikuti data training
 * (ai-model/training/scripts/gen_results.py). Jangan diubah tanpa melatih ulang model.
 * Aturan bisnis (status ruangan, bentrok jadwal, pembatalan) mengikuti RoomBookingController.
 * Identitas pengguna HANYA dari sesi login ($userId), tidak pernah dari argumen buatan model.
 */
class ToolExecutor
{
    public const TOOLS = ['list_rooms', 'room_info', 'check_availability', 'book_room', 'my_bookings', 'cancel_booking'];

    private const DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'];
    private const MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
    private const MONTH_ABBR = ['jan' => 1, 'feb' => 2, 'mar' => 3, 'apr' => 4, 'mei' => 5, 'jun' => 6, 'jul' => 7, 'agu' => 8, 'agt' => 8, 'ags' => 8, 'sep' => 9, 'okt' => 10, 'nov' => 11, 'des' => 12];
    private const MAX_ROOMS = 8;
    private const MAX_BOOKINGS = 6;

    /** "Sekarang" dalam jam dinding lokal, dinyatakan di timezone aplikasi supaya sebanding dengan kolom start_at/end_at. */
    private Carbon $now;

    /** Pesan pengguna terakhir: dipakai hanya untuk membaca lantai/gedung yang TERTULIS di sana (lihat withUserMessageLocation). */
    private string $userMessage = '';

    public function __construct(private readonly ?int $userId, ?Carbon $now = null, string $userMessage = '')
    {
        $this->userMessage = $userMessage;
        if ($now) {
            $this->now = $now->copy();
            return;
        }
        // config('app.timezone') = UTC, tetapi pengguna memesan dengan jam WIB. Nilai di DB adalah jam dinding.
        $local = Carbon::now(config('chatbot.timezone', 'Asia/Jakarta'));
        $this->now = Carbon::parse($local->format('Y-m-d H:i:s'), config('app.timezone'));
    }

    /** Format JSON ala Python (", " dan ": ") karena begitulah hasil tool tampil di data training. */
    public static function encode(mixed $data): string
    {
        $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_INVALID_UTF8_SUBSTITUTE);
        $out = '';
        $inString = false;
        $escaped = false;
        $len = strlen($json);
        for ($i = 0; $i < $len; $i++) {
            $ch = $json[$i];
            $out .= $ch;
            if ($inString) {
                if ($escaped) {
                    $escaped = false;
                } elseif ($ch === '\\') {
                    $escaped = true;
                } elseif ($ch === '"') {
                    $inString = false;
                }
                continue;
            }
            if ($ch === '"') {
                $inString = true;
            } elseif ($ch === ':' || $ch === ',') {
                $out .= ' ';
            }
        }
        return $out;
    }

    public function run(string $tool, array $args): array
    {
        if (! in_array($tool, self::TOOLS, true)) {
            return ['ok' => false, 'error' => 'unknown_tool'];
        }

        try {
            if (in_array($tool, ['list_rooms', 'room_info', 'check_availability', 'book_room'], true)) {
                // Sama seperti halaman admin: booking yang sudah berakhir melepas status "booked".
                Room::all()->each->syncBookingStatus();
            }

            $result = match ($tool) {
                'list_rooms' => $this->listRooms($args),
                'room_info' => $this->roomInfo($args),
                'check_availability' => $this->checkAvailability($args),
                'book_room' => $this->bookRoom($args),
                'my_bookings' => $this->myBookings($args),
                'cancel_booking' => $this->cancelBooking($args),
            };
        } catch (\Throwable $e) {
            Log::error('Chatbot: tool gagal dijalankan', ['tool' => $tool, 'error' => $e->getMessage()]);
            return ['ok' => false, 'error' => 'internal_error'];
        }

        Log::info('Chatbot tool', ['tool' => $tool, 'args' => $args, 'user_id' => $this->userId, 'ok' => $result['ok'] ?? null, 'error' => $result['error'] ?? null]);

        return $result;
    }

    // ------------------------------------------------------------------ tools

    private function listRooms(array $a): array
    {
        $parsed = $this->withUserMessageLocation($this->parseListFilters($a));
        if ($parsed['unsupported']) {
            // Jangan diam-diam membuang filter yang tidak dipahami: hasil "semua ruangan" akan terdengar meyakinkan tetapi salah.
            Log::warning('Chatbot: filter list_rooms tidak didukung', ['args' => $a, 'unsupported' => $parsed['unsupported']]);
            return ['ok' => false, 'error' => 'unsupported_filter', 'unsupported' => $parsed['unsupported']];
        }
        $filters = $parsed['filters'];

        $found = Room::orderBy('id')->get()->filter(function (Room $r) use ($filters, $parsed) {
            if ($r->status !== 'available') {
                return false;
            }
            if (isset($filters['min_capacity']) && $r->capacity < $filters['min_capacity']) {
                return false;
            }
            if (! $this->locationMatches((string) $r->location, $parsed)) {
                return false;
            }
            if (isset($filters['keyword'])) {
                $kw = $filters['keyword'];
                $hay = $r->name . ' ' . $r->description;
                if ($kw === 'AC' && str_contains($hay, 'tanpa AC')) {
                    return false;
                }
                if (! preg_match('/\b' . preg_quote($kw, '/') . '\b/iu', $hay)) {
                    return false;
                }
            }
            return true;
        })->values();

        $shown = $found->take(self::MAX_ROOMS);

        return [
            'ok' => true,
            'count' => $found->count(),
            'shown' => $shown->count(),
            'filters' => $filters ?: new \stdClass(),
            'rooms' => $shown->map(fn (Room $r) => ['name' => $r->name, 'location' => $r->location, 'capacity' => (int) $r->capacity])->all(),
        ];
    }

    // ------------------------------------------------------------ filter list_rooms (lokasi / lantai)

    private const FLOOR_WORDS = ['satu' => 1, 'dua' => 2, 'tiga' => 3, 'empat' => 4, 'lima' => 5, 'enam' => 6];
    private const FLOOR_RE = '/\b(?:lantai|lt\.?|level)\s*(\d+|satu|dua|tiga|empat|lima|enam)\b/iu';
    private const BUILDING_RE = '/\bgedung\s+([a-z])\b/iu';
    /** Argumen terkait waktu yang kadang ikut dikirim model ke list_rooms; tidak berarti apa-apa di sini, aman diabaikan. */
    private const IGNORABLE_ARGS = ['date_text', 'date', 'tanggal', 'start_time', 'end_time', 'duration_minutes', 'jam'];

    /**
     * Model (0,5B) tidak pernah dilatih soal lantai: ia mengarang argumen ("floor", "building", "Lantai 1", date_text: "lantai 1", ...).
     * Di database lokasi tersimpan sebagai "Gedung A Lt.1". Di sini semua bentuk itu dipahami dan diterjemahkan ke
     * (gedung, lantai, teks bebas); argumen yang benar-benar tidak dikenal dilaporkan, tidak dibuang diam-diam.
     *
     * @return array{filters: array, building: ?string, floor: ?int, texts: string[], keyword: ?string, unsupported: string[]}
     */
    private function parseListFilters(array $a): array
    {
        $floor = null;
        $building = null;
        $minCap = null;
        $keyword = null;
        $texts = [];
        $unsupported = [];

        foreach ($a as $key => $val) {
            $k = mb_strtolower((string) $key);
            if (in_array($k, ['min_capacity', 'capacity', 'kapasitas'], true)) {
                if (is_numeric($val)) {
                    $minCap = (int) $val;
                } else {
                    $unsupported[] = (string) $key;
                }
            } elseif (in_array($k, ['floor', 'lantai', 'level'], true)) {
                $f = $this->floorValue($val);
                if ($f !== null) {
                    $floor = $f;
                } else {
                    $unsupported[] = (string) $key;
                }
            } elseif (in_array($k, ['building', 'gedung'], true)) {
                $b = $this->buildingValue($val);
                if ($b !== null) {
                    $building = $b;
                } elseif (is_string($val) && trim($val) !== '') {
                    $texts[] = trim($val);
                }
            } elseif (in_array($k, ['location', 'lokasi'], true)) {
                if (! is_string($val)) {
                    $unsupported[] = (string) $key;
                    continue;
                }
                $floor ??= $this->floorFrom($val);
                $building ??= $this->buildingFrom($val);
                $rest = $this->withoutFloorAndBuilding($val);
                if ($rest !== '') {
                    $texts[] = $rest;
                }
            } elseif (in_array($k, ['keyword', 'facility', 'fasilitas'], true)) {
                if (! is_string($val) || trim($val) === '') {
                    continue;
                }
                $kw = trim($val);
                // "lantai 1" / "Gedung A" yang salah masuk ke keyword sebenarnya lokasi
                if (($this->floorFrom($kw) !== null || $this->buildingFrom($kw) !== null) && $this->withoutFloorAndBuilding($kw) === '') {
                    $floor ??= $this->floorFrom($kw);
                    $building ??= $this->buildingFrom($kw);
                } else {
                    $keyword = $kw;
                }
            } elseif (is_string($val) && $this->floorFrom($val) !== null) {
                $floor ??= $this->floorFrom($val); // mis. date_text: "lantai 1"
            } elseif (is_string($val) && $this->buildingFrom($val) !== null) {
                $building ??= $this->buildingFrom($val);
            } elseif (! in_array($k, self::IGNORABLE_ARGS, true)) {
                $unsupported[] = (string) $key;
            }
        }

        // Gema filter yang dilihat model: kunci baku skema (min_capacity, location, keyword), lantai ditulis "Lantai N".
        $filters = [];
        if ($minCap !== null && $minCap > 1) { // kapasitas <= 1 tidak bermakna (model sering salah menafsir "lt 1" sebagai kapasitas)
            $filters['min_capacity'] = $minCap;
        }
        $loc = array_filter([$building !== null ? "Gedung $building" : null, $floor !== null ? "Lantai $floor" : null, ...$texts]);
        if ($loc) {
            $filters['location'] = implode(' ', $loc);
        }
        if ($keyword !== null) {
            $filters['keyword'] = $keyword;
        }

        return ['filters' => $filters, 'building' => $building, 'floor' => $floor, 'texts' => $texts, 'keyword' => $keyword, 'unsupported' => array_values(array_unique($unsupported))];
    }

    /** @param array{building: ?string, floor: ?int, texts: string[]} $q */
    private function locationMatches(string $roomLocation, array $q): bool
    {
        $loc = mb_strtolower($roomLocation);
        if ($q['building'] !== null && ! preg_match('/\bgedung\s+' . preg_quote(mb_strtolower($q['building']), '/') . '\b/u', $loc)) {
            return false;
        }
        if ($q['floor'] !== null && ! preg_match('/\b(?:lantai|lt\.?)\s*' . $q['floor'] . '(?!\d)/u', $loc)) {
            return false;
        }
        foreach ($q['texts'] as $t) {
            if (mb_stripos($loc, mb_strtolower($t)) === false) {
                return false;
            }
        }

        return true;
    }

    /**
     * Model sering menjatuhkan atau salah menafsir lantai/gedung ("lt 1" -> min_capacity 1; "lantai 2 gedung A" -> keyword saja).
     * Bila pesan pengguna TERTULIS menyebut lantai/gedung yang belum ada di filter, tambahkan. Hanya mempersempit hasil dengan
     * kata-kata pengguna sendiri; tidak pernah membuat filter baru dari tebakan.
     */
    private function withUserMessageLocation(array $p): array
    {
        if ($this->userMessage === '') {
            return $p;
        }
        $floor = $p['floor'] ?? $this->floorFrom($this->userMessage);
        $building = $p['building'] ?? $this->buildingFrom($this->userMessage);
        if ($floor === $p['floor'] && $building === $p['building']) {
            return $p;
        }

        $p['floor'] = $floor;
        $p['building'] = $building;
        $loc = array_filter([$building !== null ? "Gedung $building" : null, $floor !== null ? "Lantai $floor" : null, ...$p['texts']]);
        $filters = [];
        if (isset($p['filters']['min_capacity'])) {
            $filters['min_capacity'] = $p['filters']['min_capacity'];
        }
        if ($loc) {
            $filters['location'] = implode(' ', $loc);
        }
        if (isset($p['filters']['keyword'])) {
            $filters['keyword'] = $p['filters']['keyword'];
        }
        $p['filters'] = $filters;

        return $p;
    }

    private function floorFrom(string $text): ?int
    {
        if (! preg_match(self::FLOOR_RE, $text, $m)) {
            return null;
        }

        return ctype_digit($m[1]) ? (int) $m[1] : self::FLOOR_WORDS[mb_strtolower($m[1])];
    }

    private function floorValue(mixed $v): ?int
    {
        if (is_int($v) || (is_string($v) && ctype_digit(trim($v)))) {
            return (int) $v;
        }
        if (! is_string($v)) {
            return null;
        }
        $t = mb_strtolower(trim($v));

        return self::FLOOR_WORDS[$t] ?? $this->floorFrom($t);
    }

    private function buildingFrom(string $text): ?string
    {
        return preg_match(self::BUILDING_RE, $text, $m) ? mb_strtoupper($m[1]) : null;
    }

    private function buildingValue(mixed $v): ?string
    {
        if (! is_string($v)) {
            return null;
        }
        $t = trim($v);

        return preg_match('/^(?:gedung\s+)?([a-z])$/iu', $t, $m) ? mb_strtoupper($m[1]) : $this->buildingFrom($t);
    }

    private function withoutFloorAndBuilding(string $text): string
    {
        $rest = preg_replace([self::FLOOR_RE, self::BUILDING_RE], '', $text);

        return trim(preg_replace('/[\s,]+/u', ' ', (string) $rest));
    }

    private function roomInfo(array $a): array
    {
        $room = $this->findRoom($a['room'] ?? null);
        if (! $room) {
            return $this->notFound((string) ($a['room'] ?? ''));
        }

        return ['ok' => true, 'room' => [
            'name' => $room->name,
            'location' => $room->location,
            'capacity' => (int) $room->capacity,
            'description' => (string) $room->description,
            'status' => $room->status,
        ]];
    }

    private function checkAvailability(array $a): array
    {
        $room = $this->findRoom($a['room'] ?? null);
        if (! $room) {
            return $this->notFound((string) ($a['room'] ?? ''));
        }
        $date = $this->resolveDate($a['date_text'] ?? null);
        if (! $date) {
            return ['ok' => false, 'error' => 'invalid_date', 'date_text' => $a['date_text'] ?? null];
        }
        $label = $this->dateLabel($date);

        if ($room->status !== 'available') {
            return ['ok' => true, 'room' => $room->name, 'date_label' => $label, 'available' => false, 'reason' => 'room_unavailable', 'room_status' => $room->status];
        }

        [$s, $e] = $this->window($a);
        if ($s === null || $e === null || $e <= $s) {
            $dayStart = $date->copy()->startOfDay();
            $dayEnd = $dayStart->copy()->addDay();
            $busy = RoomBooking::where('room_id', $room->id)
                ->whereIn('status', ['pending', 'approved'])
                ->where('start_at', '<', $dayEnd)->where('end_at', '>', $dayStart)
                ->orderBy('start_at')->get()
                ->map(fn (RoomBooking $b) => [
                    'start' => $b->start_at->lt($dayStart) ? '00:00' : $b->start_at->format('H:i'),
                    'end' => $b->end_at->gte($dayEnd) ? '23:59' : $b->end_at->format('H:i'),
                ])->all();

            return ['ok' => true, 'room' => $room->name, 'date_label' => $label, 'available' => true, 'busy' => $busy];
        }

        $conflicts = $this->conflicts($room, $date->copy()->startOfDay()->addMinutes($s), $date->copy()->startOfDay()->addMinutes($e));
        $base = ['ok' => true, 'room' => $room->name, 'date_label' => $label, 'start' => $this->hm($s), 'end' => $this->hm($e)];

        return $conflicts
            ? $base + ['available' => false, 'reason' => 'time_conflict', 'conflicts' => $conflicts]
            : $base + ['available' => true];
    }

    private function bookRoom(array $a): array
    {
        if (! $this->userId) {
            return ['ok' => false, 'error' => 'not_logged_in'];
        }
        $room = $this->findRoom($a['room'] ?? null);
        if (! $room) {
            return $this->notFound((string) ($a['room'] ?? ''));
        }
        $date = $this->resolveDate($a['date_text'] ?? null);
        if (! $date) {
            return ['ok' => false, 'error' => 'invalid_date', 'date_text' => $a['date_text'] ?? null];
        }
        [$s, $e] = $this->window($a);
        if ($s === null || $e === null) {
            return ['ok' => false, 'error' => 'end_before_start', 'room' => $room->name];
        }
        $purpose = mb_substr(trim((string) ($a['purpose'] ?? '')), 0, 255);
        if ($purpose === '') {
            return ['ok' => false, 'error' => 'missing_purpose', 'room' => $room->name];
        }
        if ($room->status !== 'available') {
            return ['ok' => false, 'error' => 'room_unavailable', 'room' => $room->name, 'room_status' => $room->status];
        }

        $start = $date->copy()->startOfDay()->addMinutes($s);
        $end = $date->copy()->startOfDay()->addMinutes($e);
        if ($start->lt($this->now)) {
            return ['ok' => false, 'error' => 'start_in_past', 'room' => $room->name];
        }
        if ($e <= $s) {
            return ['ok' => false, 'error' => 'end_before_start', 'room' => $room->name];
        }

        $notes = isset($a['notes']) && is_string($a['notes']) && trim($a['notes']) !== '' ? mb_substr(trim($a['notes']), 0, 1000) : null;

        return DB::transaction(function () use ($room, $start, $end, $s, $e, $date, $purpose, $notes) {
            $locked = Room::lockForUpdate()->find($room->id);
            if (! $locked || $locked->status !== 'available') {
                return ['ok' => false, 'error' => 'room_unavailable', 'room' => $room->name, 'room_status' => $locked->status ?? 'unavailable'];
            }
            $conflicts = $this->conflicts($locked, $start, $end);
            if ($conflicts) {
                return ['ok' => false, 'error' => 'time_conflict', 'room' => $locked->name, 'date_label' => $this->dateLabel($date), 'conflicts' => $conflicts];
            }

            RoomBooking::create([
                'room_id' => $locked->id,
                'user_id' => $this->userId,
                'start_at' => $start,
                'end_at' => $end,
                'purpose' => $purpose,
                'notes' => $notes,
                'status' => 'approved',
            ]);
            $locked->markBooked();

            return ['ok' => true, 'booking' => [
                'room' => $locked->name,
                'date_label' => $this->dateLabel($date),
                'start' => $this->hm($s),
                'end' => $this->hm($e),
                'purpose' => $purpose,
                'status' => 'approved',
            ]];
        });
    }

    private function myBookings(array $a): array
    {
        if (! $this->userId) {
            return ['ok' => false, 'error' => 'not_logged_in'];
        }

        $filters = [];
        if (isset($a['status']) && in_array($a['status'], ['pending', 'approved', 'cancelled', 'completed'], true)) {
            $filters['status'] = $a['status'];
        }
        if (isset($a['period']) && in_array($a['period'], ['upcoming', 'today', 'past'], true)) {
            $filters['period'] = $a['period'];
        }

        $today = $this->now->copy()->startOfDay();
        $query = RoomBooking::with('room')->where('user_id', $this->userId);
        if (($filters['status'] ?? null) === 'completed') {
            // Aplikasi tidak pernah mengubah booking yang sudah berakhir menjadi "completed" (tetap "approved"). Bagi pengguna,
            // "sudah selesai" = completed ATAU approved yang waktunya sudah lewat. Hanya filter; status yang ditampilkan tetap sesuai database.
            $query->where(fn ($q) => $q->where('status', 'completed')
                ->orWhere(fn ($q2) => $q2->where('status', 'approved')->where('end_at', '<=', $this->now)));
        } elseif (isset($filters['status'])) {
            $query->where('status', $filters['status']);
        }
        $period = $filters['period'] ?? null;
        if ($period === 'today') {
            $query->where('start_at', '>=', $today)->where('start_at', '<', $today->copy()->addDay());
        } elseif ($period === 'upcoming') {
            $query->where('start_at', '>=', $today);
        } elseif ($period === 'past') {
            $query->where('start_at', '<', $today);
        }
        $query->orderBy('start_at', in_array($period, ['upcoming', 'today'], true) ? 'asc' : 'desc');

        $all = $query->get();
        $shown = $all->take(self::MAX_BOOKINGS);

        return [
            'ok' => true,
            'count' => $all->count(),
            'shown' => $shown->count(),
            'filters' => $filters ?: new \stdClass(),
            'bookings' => $shown->map(fn (RoomBooking $b) => $this->view($b) + ['status' => $b->status])->values()->all(),
        ];
    }

    private function cancelBooking(array $a): array
    {
        if (! $this->userId) {
            return ['ok' => false, 'error' => 'not_logged_in'];
        }
        $room = $this->findRoom($a['room'] ?? null);
        if (! $room) {
            return $this->notFound((string) ($a['room'] ?? ''));
        }

        $date = null;
        if (! empty($a['date_text'])) {
            $date = $this->resolveDate($a['date_text']);
            if (! $date) {
                return ['ok' => false, 'error' => 'invalid_date', 'date_text' => $a['date_text']];
            }
        }

        $rows = RoomBooking::with('room')->where('user_id', $this->userId)->where('room_id', $room->id)
            ->when($date, fn ($q) => $q->where('start_at', '>=', $date->copy()->startOfDay())->where('start_at', '<', $date->copy()->startOfDay()->addDay()))
            ->orderBy('start_at')->get();

        if ($rows->isEmpty()) {
            $echo = ['room' => $room->name];
            if (! empty($a['date_text'])) {
                $echo['date_text'] = $a['date_text'];
            }
            return ['ok' => false, 'error' => 'not_found'] + $echo;
        }

        // Aturan sama dengan RoomBookingController::cancel(): hanya "approved" yang belum dimulai.
        $cancellable = $rows->filter(fn (RoomBooking $b) => $b->status === 'approved' && $b->start_at->gt($this->now))->values();

        if ($cancellable->isEmpty()) {
            $row = $rows->first(fn (RoomBooking $b) => $b->status !== 'cancelled') ?? $rows->first();
            $reason = match (true) {
                $row->status === 'cancelled' => 'already_cancelled',
                $row->status === 'completed' => 'already_completed',
                $row->status === 'pending' => 'not_approved',
                default => 'already_started',
            };
            return ['ok' => false, 'error' => 'not_cancellable', 'reason' => $reason, 'booking' => $this->view($row)];
        }

        if ($cancellable->count() > 1) {
            return ['ok' => false, 'error' => 'multiple_matches', 'room' => $room->name, 'matches' => $cancellable->map(fn (RoomBooking $b) => [
                'date_label' => $this->dateLabel($b->start_at),
                'start' => $b->start_at->format('H:i'),
                'end' => $b->end_at->format('H:i'),
            ])->all()];
        }

        $booking = $cancellable->first();
        $booking->update(['status' => 'cancelled']);
        $booking->room->markAvailable(); // sama seperti RoomBookingController::cancel()

        return ['ok' => true, 'booking' => $this->view($booking) + ['status' => 'cancelled']];
    }

    // ------------------------------------------------------------------ pembantu

    private function view(RoomBooking $b): array
    {
        return [
            'room' => $b->room?->name,
            'date_label' => $this->dateLabel($b->start_at),
            'start' => $b->start_at->format('H:i'),
            'end' => $b->end_at->format('H:i'),
            'purpose' => $b->purpose,
        ];
    }

    private function findRoom(mixed $name): ?Room
    {
        $needle = mb_strtolower(trim((string) $name));
        if ($needle === '') {
            return null;
        }
        return Room::orderBy('id')->get()->first(fn (Room $r) => mb_strtolower($r->name) === $needle);
    }

    private function notFound(string $query): array
    {
        $names = Room::orderBy('id')->pluck('name')->all();
        $scored = [];
        foreach ($names as $i => $name) {
            similar_text(mb_strtolower($query), mb_strtolower($name), $pct);
            $scored[] = [$pct, $i, $name];
        }
        usort($scored, fn ($x, $y) => ($y[0] <=> $x[0]) ?: ($x[1] <=> $y[1]));

        return ['ok' => false, 'error' => 'room_not_found', 'query' => $query, 'suggestions' => array_column(array_slice($scored, 0, 3), 2)];
    }

    private function conflicts(Room $room, Carbon $start, Carbon $end): array
    {
        return RoomBooking::where('room_id', $room->id)
            ->whereIn('status', ['pending', 'approved'])
            ->where('start_at', '<', $end)->where('end_at', '>', $start)
            ->orderBy('start_at')->get()
            ->map(fn (RoomBooking $b) => ['start' => $b->start_at->format('H:i'), 'end' => $b->end_at->format('H:i')])
            ->all();
    }

    private function minutes(mixed $hhmm): ?int
    {
        if (! is_string($hhmm) || ! preg_match('/^(\d{1,2})[:.](\d{2})$/', trim($hhmm), $m)) {
            return null;
        }
        [$h, $mi] = [(int) $m[1], (int) $m[2]];
        return ($h > 23 || $mi > 59) ? null : $h * 60 + $mi;
    }

    /** @return array{0: ?int, 1: ?int} menit sejak 00:00 (mulai, selesai) */
    private function window(array $a): array
    {
        if (! isset($a['start_time'])) {
            return [null, null];
        }
        $s = $this->minutes($a['start_time']);
        if ($s === null) {
            return [null, null];
        }
        $e = isset($a['end_time']) ? $this->minutes($a['end_time']) : $s + (int) ($a['duration_minutes'] ?? 60);

        return [$s, $e];
    }

    private function hm(int $minutes): string
    {
        return sprintf('%02d:%02d', intdiv($minutes, 60) % 24, $minutes % 60);
    }

    private function dateLabel(Carbon $d): string
    {
        return self::DAYS[$d->dayOfWeekIso - 1] . ', ' . $d->day . ' ' . self::MONTHS[$d->month - 1] . ' ' . $d->year;
    }

    /** Ucapan tanggal yang sudah dinormalisasi model ("besok", "senin depan", "5 november") -> tanggal. Dihitung di sini, bukan oleh model. */
    private function resolveDate(mixed $text): ?Carbon
    {
        $t = preg_replace('/\s+/', ' ', mb_strtolower(trim((string) $text)));
        $t = preg_replace('/^(tanggal|tgl) (?=\d{1,2} \p{L})/u', '', $t);
        if ($t === '') {
            return null;
        }

        $today = $this->now->copy()->startOfDay();
        switch ($t) {
            case 'hari ini': return $today;
            case 'besok': return $today->copy()->addDay();
            case 'lusa': return $today->copy()->addDays(2);
            case 'kemarin': return $today->copy()->subDay();
        }

        $days = array_map('mb_strtolower', self::DAYS);
        if (preg_match('/^(\p{L}+?)( depan)?$/u', $t, $m) && ($idx = array_search($m[1], $days, true)) !== false) {
            $weekday = $today->dayOfWeekIso - 1; // Senin = 0
            if (! empty($m[2])) {
                return $today->copy()->addDays((7 - $weekday) + $idx);
            }
            return $today->copy()->addDays((($idx - $weekday) % 7 + 7) % 7);
        }

        $months = array_flip(array_map('mb_strtolower', self::MONTHS));
        if (preg_match('/^(\d{1,2}) (\p{L}+)(?: (\d{4}))?$/u', $t, $m)) {
            $month = isset($months[$m[2]]) ? $months[$m[2]] + 1 : (self::MONTH_ABBR[$m[2]] ?? null);
            if ($month === null) {
                return null;
            }
            $day = (int) $m[1];
            $year = isset($m[3]) ? (int) $m[3] : (int) $today->year;
            if (! checkdate($month, $day, $year)) {
                return null;
            }
            $d = Carbon::create($year, $month, $day, 0, 0, 0, config('app.timezone'));
            if (! isset($m[3]) && $d->lt($today)) { // tanpa tahun dan sudah lewat -> tahun depan
                return checkdate($month, $day, $year + 1) ? Carbon::create($year + 1, $month, $day, 0, 0, 0, config('app.timezone')) : null;
            }
            return $d;
        }

        if (preg_match('/^tanggal (\d{1,2})$/', $t, $m)) {
            return checkdate((int) $today->month, (int) $m[1], (int) $today->year)
                ? Carbon::create((int) $today->year, (int) $today->month, (int) $m[1], 0, 0, 0, config('app.timezone'))
                : null;
        }

        return null;
    }
}
