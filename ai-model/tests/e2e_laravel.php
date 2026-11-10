<?php
/**
 * Uji end-to-end chatbot: kode Laravel asli (ChatbotService + ToolExecutor) + MySQL + layanan model.
 * SEMUA perubahan database dibungkus transaksi dan di-ROLLBACK di akhir (data tidak berubah).
 *
 * Pakai (layanan model harus sudah jalan):
 *   php ai-model\tests\e2e_laravel.php [url-layanan-model] [user_id]
 *   contoh: php ai-model\tests\e2e_laravel.php http://127.0.0.1:8002
 */
$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\User;
use App\Services\Chatbot\ChatbotService;
use Illuminate\Log\Events\MessageLogged;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;

config(['chatbot.url' => $argv[1] ?? 'http://127.0.0.1:8002']);
$userId = isset($argv[2]) ? (int) $argv[2] : User::orderBy('id')->value('id');

Event::listen(MessageLogged::class, function (MessageLogged $e) {
    if ($e->message === 'Chatbot tool') {
        $c = $e->context;
        echo '   [tool] ' . $c['tool'] . ' ' . json_encode($c['args'], JSON_UNESCAPED_UNICODE) . ' -> ok=' . json_encode($c['ok']) . ($c['error'] ? ' error=' . $c['error'] : '') . PHP_EOL;
    }
});

$bot = new ChatbotService();

/** Satu percakapan: tiap pesan dikirim dengan riwayat sebelumnya (seperti widget chat). */
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
    // pertanyaan persis dari screenshot
    ['Ada berapa ruangan kosong yang bisa di booking?'],
    ['ada berapa ruangan yang saya booking?'],
    // info & pencarian
    ['Kapasitas Aula Utama berapa?'],
    ['Kenapa Lab Jaringan nggak bisa dipesan?'],
    ['Cari ruangan yang muat minimal 40 orang'],
    ['Ruangan apa saja yang ada di Gedung B?'],
    ['Aula Utama kosong besok jam 9 sampai 11?'],
    // alur booking -> lihat -> batal -> lihat (di dalam transaksi, di-rollback)
    ['Pinjam Ruang Seminar 2 besok jam 10 sampai 12 buat rapat himpunan'],
    ['Booking saya apa saja?', 'ada berapa ruangan yang saya booking?'],
    ['Pinjam Ruang Seminar 2 besok jam 11 sampai 13 buat belajar kelompok'],   // harus ditolak (ruangan sudah dibooking)
    ['Batalkan booking Ruang Seminar 2 besok'],
    ['Booking saya yang dibatalkan apa saja?'],
    // melengkapi informasi bertahap
    ['Mau pinjam Lab Komputer 1', 'lusa', 'jam 1 siang sampai jam 3 sore', 'praktikum basis data'],
    // panduan & di luar cakupan
    ['Bagaimana cara membatalkan booking?'],
    ['Tolong tambahkan ruangan baru dong'],
    ['Besok cuaca gimana?'],
    ['Pinjam ruang Teater besok jam 9 sampai 11 buat rapat'],
];

echo 'Uji end-to-end | layanan model: ' . config('chatbot.url') . ' | user_id=' . $userId . ' | sekarang (WIB): ' . now(config('chatbot.timezone'))->format('Y-m-d H:i') . PHP_EOL;
$before = DB::table('room_bookings')->count();

DB::beginTransaction();
try {
    foreach ($scenarios as $turns) {
        convo($bot, $userId, $turns);
    }
} finally {
    DB::rollBack();
}

$after = DB::table('room_bookings')->count();
echo str_repeat('=', 78) . PHP_EOL . "Rollback selesai: jumlah booking sebelum=$before sesudah=$after " . ($before === $after ? '(data tidak berubah)' : '(!! BERUBAH)') . PHP_EOL;
