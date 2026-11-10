<?php
/**
 * Uji end-to-end chatbot TANPA MySQL: database SQLite sementara (file di .workdir) + kode Laravel asli
 * (ChatbotService + ToolExecutor) + layanan model sungguhan. Tidak menyentuh database aplikasi.
 *
 *   php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\e2e_sqlite.php http://127.0.0.1:8002 [user_id]
 */
$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Room;
use App\Models\RoomBooking;
use App\Services\Chatbot\ChatbotService;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Log\Events\MessageLogged;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Schema;

// ---- database sementara
$dbFile = dirname(__DIR__) . '/.workdir/e2e_test.sqlite';
@unlink($dbFile);
touch($dbFile);
config(['database.default' => 'sqlite', 'database.connections.sqlite.database' => $dbFile, 'database.connections.sqlite.foreign_key_constraints' => false]);
DB::purge('sqlite');

Schema::create('rooms', function (Blueprint $t) {
    $t->id();
    $t->string('name');
    $t->string('location')->nullable();
    $t->unsignedInteger('capacity')->default(1);
    $t->text('description')->nullable();
    $t->enum('status', ['available', 'booked', 'unavailable'])->default('available');
    $t->timestamps();
});
Schema::create('room_bookings', function (Blueprint $t) {
    $t->id();
    $t->unsignedBigInteger('room_id');
    $t->unsignedBigInteger('user_id');
    $t->dateTime('start_at');
    $t->dateTime('end_at');
    $t->string('purpose');
    $t->enum('status', ['pending', 'approved', 'cancelled', 'completed'])->default('approved');
    $t->text('notes')->nullable();
    $t->timestamps();
});

$json = json_decode(file_get_contents(dirname(__DIR__) . '/training/data/rooms.json'), true);
foreach ($json['rooms'] ?? $json as $r) {
    Room::create([
        'name' => $r['name'] ?? $r['nama'],
        'location' => $r['location'] ?? $r['lokasi'],
        'capacity' => $r['capacity'] ?? $r['kapasitas'],
        'description' => $r['description'] ?? $r['deskripsi'] ?? '',
        'status' => $r['status'] ?? 'available',
    ]);
}

config(['chatbot.url' => $argv[1] ?? 'http://127.0.0.1:8002']);
$userId = isset($argv[2]) ? (int) $argv[2] : 3;

// booking lama seperti di sesi uji pengguna (sudah lewat, disetujui)
$aula = Room::where('name', 'Aula Utama')->first();
RoomBooking::create(['room_id' => $aula->id, 'user_id' => $userId, 'start_at' => '2026-11-02 07:00:00', 'end_at' => '2026-11-02 12:00:00', 'purpose' => 'Meeting', 'status' => 'approved']);

Event::listen(MessageLogged::class, function (MessageLogged $e) {
    if ($e->message === 'Chatbot tool') {
        $c = $e->context;
        echo '   [tool] ' . $c['tool'] . ' ' . json_encode($c['args'], JSON_UNESCAPED_UNICODE) . ' -> ok=' . json_encode($c['ok']) . ($c['error'] ? ' error=' . $c['error'] : '') . PHP_EOL;
    } elseif (str_starts_with($e->message, 'Chatbot:')) {
        echo '   [!] ' . $e->message . ' ' . json_encode($e->context, JSON_UNESCAPED_UNICODE) . PHP_EOL;
    }
});

$bot = new ChatbotService();

function convo(ChatbotService $bot, int $userId, array $turns): void
{
    $history = [];
    echo str_repeat('-', 78) . PHP_EOL;
    foreach ($turns as $text) {
        echo "PENGGUNA : $text" . PHP_EOL;
        $t0 = microtime(true);
        try {
            $reply = $bot->reply(array_slice($history, -8), $text, $userId);
        } catch (Throwable $e) {
            echo '   !! ' . get_class($e) . ': ' . $e->getMessage() . PHP_EOL;
            return;
        }
        printf("ASISTEN  : %s   (%.1f dtk)\n", str_replace("\n", "\n           ", $reply), microtime(true) - $t0);
        $history[] = ['role' => 'user', 'content' => $text];
        $history[] = ['role' => 'assistant', 'content' => $reply];
    }
}

$scenarios = [
    // pertanyaan yang gagal di uji pengguna + variasi lantai/gedung
    ['Ada berapa ruangan lantai 1 yang bisa saya booking?'],
    ['Ruangan apa saja yang ada di lantai 2?'],
    ['Ada ruangan kosong di Gedung A lantai 1?'],
    ['Ruang di Gedung B yang tersedia apa saja?'],
    ['ruangan lantai satu yang bisa dipakai?'],
    ['Ada ruang diskusi di lantai 2 gedung A?'],
    ['Cari ruangan di lt 1'],
    ['Ada ruangan di lantai 5?'],
    // pertanyaan lain dari sesi uji pengguna
    ['Ada berapa ruangan kosong yang bisa di booking?'],
    ['Ada berapa ruangan yang saya booking?'],
    ['Booking saya yang sudah lewat apa saja?'],
    ['Tolong tampilkan jadwal peminjaman yang akan datang'],
    ['Kenapa Lab Jaringan nggak bisa dipesan?'],
];

echo 'E2E SQLite | layanan model: ' . config('chatbot.url') . ' | user_id=' . $userId . ' | sekarang (WIB): ' . now(config('chatbot.timezone'))->format('Y-m-d H:i') . ' | ruangan=' . Room::count() . PHP_EOL;
foreach ($scenarios as $turns) {
    convo($bot, $userId, $turns);
}
echo str_repeat('=', 78) . PHP_EOL . 'Selesai (database SQLite sementara, MySQL tidak disentuh).' . PHP_EOL;
