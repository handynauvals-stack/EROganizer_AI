<?php
/**
 * Uji RoomSeeder + perakitan system prompt (SQLite sementara, tanpa MySQL/model).
 *   php -d extension=pdo_sqlite -d extension=sqlite3 ai-model\tests\test_room_seeder.php
 */
$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Room;
use App\Services\Chatbot\ChatbotService;
use Database\Seeders\RoomSeeder;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

$dbFile = dirname(__DIR__) . '/.workdir/seeder_test.sqlite';
@unlink($dbFile);
touch($dbFile);
config(['database.default' => 'sqlite', 'database.connections.sqlite.database' => $dbFile, 'database.connections.sqlite.foreign_key_constraints' => false]);
DB::purge('sqlite');
Schema::create('rooms', function (Blueprint $t) {
    $t->id(); $t->string('name'); $t->string('location')->nullable(); $t->unsignedInteger('capacity')->default(1);
    $t->text('description')->nullable(); $t->enum('status', ['available', 'booked', 'unavailable'])->default('available'); $t->timestamps();
});

$json = json_decode(file_get_contents(dirname(__DIR__) . '/training/data/rooms.json'), true);
$list = $json['rooms'] ?? $json;
$names = array_column($list, 'name');

$fail = 0;
function check(string $title, bool $ok, string $detail = ''): void
{
    global $fail;
    $fail += $ok ? 0 : 1;
    printf("%s  %-66s %s\n", $ok ? 'PASS' : 'FAIL', $title, $detail);
}

(new RoomSeeder)->run();
check('seeder mengisi semua ruangan dari rooms.json', Room::count() === count($names), Room::count() . '/' . count($names));
(new RoomSeeder)->run();
check('dijalankan dua kali: tidak menggandakan (idempotent)', Room::count() === count($names));
check('nama & urutan di DB (urut id) = urutan di rooms.json', Room::orderBy('id')->pluck('name')->all() === $names);
check('status Lab Jaringan = unavailable', Room::where('name', 'Lab Jaringan')->value('status') === 'unavailable');
check('lokasi memakai format "Gedung A Lt.1"', Room::where('name', 'Aula Utama')->value('location') === 'Gedung A Lt.1');

Room::where('name', 'Aula Utama')->update(['capacity' => 999]);
(new RoomSeeder)->run();
check('seed ulang TIDAK menimpa perubahan admin (kapasitas 999 tetap)', (int) Room::where('name', 'Aula Utama')->value('capacity') === 999);

$prompt = (new ChatbotService)->systemPrompt();
check('system prompt dirakit dari ai-model/training/system_prompt.txt', strlen($prompt) > 500 && ! str_contains($prompt, '{{ROOMS}}'), strlen($prompt) . ' byte');
check('daftar ruangan di prompt = nama dari DB (urutan sama, dipisah "; ")', str_contains($prompt, implode('; ', $names)));

echo PHP_EOL . ($fail === 0 ? 'SEMUA LULUS' : "$fail GAGAL") . PHP_EOL;
@unlink($dbFile);
exit($fail === 0 ? 0 : 1);
