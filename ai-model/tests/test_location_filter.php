<?php
/**
 * Uji unit filter lokasi/lantai list_rooms (TANPA database/layanan model).
 *   php ai-model\tests\test_location_filter.php
 * Data ruangan diambil dari training/data/rooms.json (sama dengan yang di-seed ke tabel rooms).
 */
$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';

use App\Services\Chatbot\ToolExecutor;

$ex = (new ReflectionClass(ToolExecutor::class))->newInstanceWithoutConstructor();
$parse = new ReflectionMethod(ToolExecutor::class, 'parseListFilters');
$match = new ReflectionMethod(ToolExecutor::class, 'locationMatches');

$json = json_decode(file_get_contents(dirname(__DIR__) . '/training/data/rooms.json'), true);
$list = $json['rooms'] ?? $json;
$first = $list[0];
$nameKey = isset($first['name']) ? 'name' : 'nama';
$locKey = isset($first['location']) ? 'location' : 'lokasi';
$rooms = [];
foreach ($list as $r) {
    $rooms[$r[$nameKey]] = $r[$locKey];
}
echo 'Lokasi di data: ' . implode(' | ', array_unique(array_values($rooms))) . PHP_EOL . PHP_EOL;

/** oracle independen: cocok bila (gedung & lantai & teks) terpenuhi menurut regex sederhana */
$oracle = function (?string $b, ?int $f, ?string $t) use ($rooms) {
    $out = [];
    foreach ($rooms as $n => $loc) {
        if ($b !== null && ! preg_match('/Gedung ' . $b . '\b/', $loc)) continue;
        if ($f !== null && ! preg_match('/Lt\.' . $f . '(?!\d)/', $loc)) continue;
        if ($t !== null && stripos($loc, $t) === false) continue;
        $out[] = $n;
    }
    return $out;
};

$cases = [
    // [judul, args dari model, oracle(b,f,t) | 'UNSUPPORTED' | 'NOFILTER']
    ['keluaran model: location "Lantai 1" (kasus di screenshot)', ['location' => 'Lantai 1'], [null, 1, null]],
    ['keluaran model: floor "2"', ['floor' => '2'], [null, 2, null]],
    ['keluaran model: location Gedung A + floor 1', ['location' => 'Gedung A', 'floor' => '1'], ['A', 1, null]],
    ['keluaran model: location Gedung B', ['location' => 'Gedung B'], ['B', null, null]],
    ['keluaran model: keyword "lantai 1"', ['keyword' => 'lantai 1'], [null, 1, null]],
    ['keluaran model: location "Lantai satu"', ['location' => 'Lantai satu'], [null, 1, null]],
    ['keluaran model: location "Lantai 2" + building "Gedung A"', ['location' => 'Lantai 2', 'building' => 'Gedung A'], ['A', 2, null]],
    ['keluaran model: location Gedung A + date_text "lantai 1"', ['location' => 'Gedung A', 'date_text' => 'lantai 1'], ['A', 1, null]],
    ['location "Lt.1" (format DB)', ['location' => 'Lt.1'], [null, 1, null]],
    ['location "gedung a lantai 2"', ['location' => 'gedung a lantai 2'], ['A', 2, null]],
    ['location Perpustakaan', ['location' => 'Perpustakaan'], [null, null, 'Perpustakaan']],
    ['alias capacity 50 (tanpa filter lokasi)', ['capacity' => 50], 'NOFILTER_LOC'],
    ['keyword proyektor tetap keyword', ['keyword' => 'proyektor'], 'NOFILTER_LOC'],
    ['date_text "besok" diabaikan', ['date_text' => 'besok'], 'NOFILTER_LOC'],
    ['argumen asing {"foo":"bar"} -> dilaporkan', ['foo' => 'bar'], 'UNSUPPORTED'],
];

$fail = 0;
foreach ($cases as [$title, $args, $expect]) {
    $p = $parse->invoke($ex, $args);
    $ok = true;
    $detail = '';
    if ($expect === 'UNSUPPORTED') {
        $ok = $p['unsupported'] === array_keys($args);
        $detail = 'unsupported=' . json_encode($p['unsupported']);
    } elseif ($expect === 'NOFILTER_LOC') {
        $got = array_keys(array_filter($rooms, fn ($loc) => $match->invoke($ex, $loc, $p)));
        $ok = count($got) === count($rooms) && $p['unsupported'] === [];
        $detail = 'cocok=' . count($got) . '/' . count($rooms) . ' filters=' . json_encode($p['filters'], JSON_UNESCAPED_UNICODE);
    } else {
        $want = $oracle(...$expect);
        $got = array_keys(array_filter($rooms, fn ($loc) => $match->invoke($ex, $loc, $p)));
        sort($want);
        sort($got);
        $ok = $want === $got && $p['unsupported'] === [] && count($want) > 0;
        $detail = 'cocok=' . count($got) . ' (oracle ' . count($want) . ') echo=' . json_encode($p['filters'], JSON_UNESCAPED_UNICODE);
    }
    if (! $ok) $fail++;
    printf("%s  %-52s %s\n", $ok ? 'PASS' : 'FAIL', $title, $detail);
}
// ---- lantai/gedung yang TERTULIS di pesan pengguna melengkapi argumen model yang menjatuhkannya
$augment = new ReflectionMethod(ToolExecutor::class, 'withUserMessageLocation');
$msgProp = new ReflectionProperty(ToolExecutor::class, 'userMessage');
$msgCases = [
    ['pesan "Cari ruangan di lt 1" + model: min_capacity 1', 'Cari ruangan di lt 1', ['min_capacity' => 1], [null, 1, null], '{"location":"Lantai 1"}'],
    ['pesan "...lantai 2 gedung A?" + model: keyword saja', 'Ada ruang diskusi di lantai 2 gedung A?', ['keyword' => 'diskusi'], ['A', 2, null], '{"location":"Gedung A Lantai 2","keyword":"diskusi"}'],
    ['nilai dari model menang (floor 2 vs pesan lantai 3)', 'cari di lantai 3', ['floor' => '2'], [null, 2, null], '{"location":"Lantai 2"}'],
    ['pesan tanpa lokasi -> tidak berubah', 'Ada berapa ruangan kosong yang bisa di booking?', [], 'NOFILTER', '[]'],
];
foreach ($msgCases as [$title, $msg, $args, $expect, $echo]) {
    $msgProp->setValue($ex, $msg);
    $p = $augment->invoke($ex, $parse->invoke($ex, $args));
    $got = array_keys(array_filter($rooms, fn ($loc) => $match->invoke($ex, $loc, $p)));
    $want = $expect === 'NOFILTER' ? array_keys($rooms) : $oracle(...$expect);
    sort($got);
    sort($want);
    $ok = $got === $want && json_encode($p['filters'], JSON_UNESCAPED_UNICODE) === $echo;
    if (! $ok) $fail++;
    printf("%s  %-52s cocok=%d (oracle %d) echo=%s\n", $ok ? 'PASS' : 'FAIL', $title, count($got), count($want), json_encode($p['filters'], JSON_UNESCAPED_UNICODE));
}
$msgProp->setValue($ex, '');

// urutan kunci pada gema filter harus seperti data training: min_capacity lalu location
$p = $parse->invoke($ex, ['location' => 'Gedung A', 'min_capacity' => 30]);
$ord = array_keys($p['filters']) === ['min_capacity', 'location'];
printf("%s  %-52s %s\n", $ord ? 'PASS' : 'FAIL', 'urutan kunci gema: min_capacity, location', json_encode($p['filters']));
$fail += $ord ? 0 : 1;

echo PHP_EOL . ($fail === 0 ? 'SEMUA LULUS' : "$fail GAGAL") . PHP_EOL;
exit($fail === 0 ? 0 : 1);
