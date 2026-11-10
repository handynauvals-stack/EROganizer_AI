<?php
/**
 * Uji regresi ToolExecutor TANPA model & TANPA MySQL (SQLite sementara). Aturan bisnis mengikuti RoomBookingController.
 *   php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_executor_sqlite.php
 */
$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Room;
use App\Models\RoomBooking;
use App\Services\Chatbot\ToolExecutor;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

$dbFile = dirname(__DIR__) . '/.workdir/executor_test.sqlite';
@unlink($dbFile);
touch($dbFile);
config(['database.default' => 'sqlite', 'database.connections.sqlite.database' => $dbFile, 'database.connections.sqlite.foreign_key_constraints' => false]);
DB::purge('sqlite');
Schema::create('rooms', function (Blueprint $t) {
    $t->id(); $t->string('name'); $t->string('location')->nullable(); $t->unsignedInteger('capacity')->default(1);
    $t->text('description')->nullable(); $t->enum('status', ['available', 'booked', 'unavailable'])->default('available'); $t->timestamps();
});
Schema::create('room_bookings', function (Blueprint $t) {
    $t->id(); $t->unsignedBigInteger('room_id'); $t->unsignedBigInteger('user_id'); $t->dateTime('start_at'); $t->dateTime('end_at');
    $t->string('purpose'); $t->enum('status', ['pending', 'approved', 'cancelled', 'completed'])->default('approved'); $t->text('notes')->nullable(); $t->timestamps();
});
$json = json_decode(file_get_contents(dirname(__DIR__) . '/training/data/rooms.json'), true);
foreach ($json['rooms'] ?? $json as $r) {
    Room::create(['name' => $r['name'] ?? $r['nama'], 'location' => $r['location'] ?? $r['lokasi'], 'capacity' => $r['capacity'] ?? $r['kapasitas'],
        'description' => $r['description'] ?? $r['deskripsi'] ?? '', 'status' => $r['status'] ?? 'available']);
}
$U = 3;
$aula = Room::where('name', 'Aula Utama')->first();
RoomBooking::create(['room_id' => $aula->id, 'user_id' => $U, 'start_at' => '2026-11-02 07:00:00', 'end_at' => '2026-11-02 12:00:00', 'purpose' => 'Meeting', 'status' => 'approved']);

$fail = 0;
function check(string $title, bool $ok, string $detail = ''): void
{
    global $fail;
    if (! $ok) { $fail++; }
    printf("%s  %-62s %s\n", $ok ? 'PASS' : 'FAIL', $title, $detail);
}
$run = fn (string $tool, array $args = [], ?int $user = 3, string $msg = '') => (new ToolExecutor($user, null, $msg))->run($tool, $args);

// --- daftar ruangan & lantai
$r = $run('list_rooms');
check('list_rooms tanpa filter: 14 tersedia (Lab Jaringan unavailable)', $r['count'] === 14 && $r['shown'] === 8, 'count=' . $r['count']);
check('filters kosong dikodekan sebagai {} (bukan [])', str_contains(ToolExecutor::encode($r), '"filters": {}'));
check('encode bergaya Python (", " dan ": ")', str_starts_with(ToolExecutor::encode($r), '{"ok": true, "count": 14, "shown": 8, "filters": {}, "rooms": [{"name": "Aula Utama"'));
$r = $run('list_rooms', ['location' => 'Lantai 1']);
check('list_rooms location "Lantai 1" -> 5 ruangan (kasus screenshot)', $r['count'] === 5, 'count=' . $r['count']);
$r = $run('list_rooms', ['floor' => '2']);
check('list_rooms floor "2" -> 7 tersedia (Lab Jaringan tak tersedia)', $r['count'] === 7, 'count=' . $r['count']);
$r = $run('list_rooms', ['keyword' => 'diskusi'], 3, 'Ada ruang diskusi di lantai 2 gedung A?');
check('keyword diskusi + pesan "lantai 2 gedung A" -> 0 (benar)', $r['count'] === 0 && $r['filters']['location'] === 'Gedung A Lantai 2', json_encode($r['filters']));
$r = $run('list_rooms', ['foo' => 'bar']);
check('argumen asing -> unsupported_filter (tidak diam-diam semua)', ($r['error'] ?? '') === 'unsupported_filter');

// --- booking saya
$r = $run('my_bookings');
check('my_bookings: 1 booking (Aula Utama, 2 Nov)', $r['count'] === 1 && $r['bookings'][0]['date_label'] === 'Senin, 2 November 2026' && $r['bookings'][0]['status'] === 'approved');
check('my_bookings period=past -> 1', $run('my_bookings', ['period' => 'past'])['count'] === 1);
check('my_bookings period=upcoming -> 0', $run('my_bookings', ['period' => 'upcoming'])['count'] === 0);
$r = $run('my_bookings', ['status' => 'completed']);
check('my_bookings status=completed -> 1 (approved yang sudah berakhir)', $r['count'] === 1 && $r['bookings'][0]['status'] === 'approved');
check('my_bookings status=cancelled -> 0', $run('my_bookings', ['status' => 'cancelled'])['count'] === 0);
check('my_bookings milik user lain -> 0 (isolasi pengguna)', $run('my_bookings', [], 99)['count'] === 0);
check('my_bookings tanpa login -> not_logged_in', ($run('my_bookings', [], null)['error'] ?? '') === 'not_logged_in');

// --- booking -> bentrok -> pembatalan
$b = $run('book_room', ['room' => 'Ruang Seminar 2', 'date_text' => 'besok', 'start_time' => '10:00', 'end_time' => '12:00', 'purpose' => 'Rapat himpunan']);
check('book_room besok 10-12 -> ok', ($b['ok'] ?? false) === true && $b['booking']['start'] === '10:00' && $b['booking']['status'] === 'approved', json_encode($b['booking'] ?? $b, JSON_UNESCAPED_UNICODE));
check('ruangan jadi "booked" di database (aturan aplikasi)', Room::where('name', 'Ruang Seminar 2')->value('status') === 'booked');
check('book_room kedua pada ruangan sama -> room_unavailable', ($run('book_room', ['room' => 'Ruang Seminar 2', 'date_text' => 'besok', 'start_time' => '13:00', 'end_time' => '14:00', 'purpose' => 'x'])['error'] ?? '') === 'room_unavailable');
check('check_availability ruangan booked -> room_unavailable', ($run('check_availability', ['room' => 'Ruang Seminar 2', 'date_text' => 'besok'])['reason'] ?? '') === 'room_unavailable');
check('my_bookings upcoming -> 1 setelah booking', $run('my_bookings', ['period' => 'upcoming'])['count'] === 1);
check('book_room tanpa tujuan -> missing_purpose', ($run('book_room', ['room' => 'Lab Komputer 1', 'date_text' => 'besok', 'start_time' => '10:00', 'end_time' => '12:00'])['error'] ?? '') === 'missing_purpose');
check('book_room kemarin -> start_in_past', ($run('book_room', ['room' => 'Lab Komputer 1', 'date_text' => 'kemarin', 'start_time' => '10:00', 'end_time' => '12:00', 'purpose' => 'x'])['error'] ?? '') === 'start_in_past');
check('book_room ruangan tak ada -> room_not_found + saran', ($x = $run('book_room', ['room' => 'Teater', 'date_text' => 'besok', 'start_time' => '09:00', 'end_time' => '11:00', 'purpose' => 'x']))['error'] === 'room_not_found' && count($x['suggestions']) === 3);
check('book_room tanggal 30 februari -> invalid_date', ($run('book_room', ['room' => 'Lab Komputer 1', 'date_text' => '30 februari', 'start_time' => '09:00', 'end_time' => '11:00', 'purpose' => 'x'])['error'] ?? '') === 'invalid_date');
check('list_rooms sekarang 13 (satu ruangan booked)', $run('list_rooms')['count'] === 13);
$c = $run('cancel_booking', ['room' => 'Ruang Seminar 2', 'date_text' => 'besok']);
check('cancel_booking besok -> ok, status cancelled', ($c['ok'] ?? false) === true && $c['booking']['status'] === 'cancelled');
check('ruangan kembali "available" setelah batal', Room::where('name', 'Ruang Seminar 2')->value('status') === 'available');
check('cancel ulang -> not_cancellable already_cancelled', ($x = $run('cancel_booking', ['room' => 'Ruang Seminar 2', 'date_text' => 'besok']))['error'] === 'not_cancellable' && $x['reason'] === 'already_cancelled');
check('cancel booking yang sudah lewat -> already_started', ($x = $run('cancel_booking', ['room' => 'Aula Utama']))['error'] === 'not_cancellable' && $x['reason'] === 'already_started');
check('cancel tanpa booking -> not_found', ($run('cancel_booking', ['room' => 'Lab Komputer 1'])['error'] ?? '') === 'not_found');
check('list_rooms kembali 14', $run('list_rooms')['count'] === 14);
check('room_info Lab Jaringan -> status unavailable', $run('room_info', ['room' => 'Lab Jaringan'])['room']['status'] === 'unavailable');

echo PHP_EOL . ($fail === 0 ? 'SEMUA LULUS' : "$fail GAGAL") . PHP_EOL;
@unlink($dbFile);
exit($fail === 0 ? 0 : 1);
