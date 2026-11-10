<?php

namespace Database\Seeders;

use App\Models\Room;
use Illuminate\Database\Seeder;

class RoomSeeder extends Seeder
{
    /**
     * Mengisi daftar ruangan dari ai-model/training/data/rooms.json.
     *
     * File yang SAMA dipakai saat training chatbot, sehingga nama dan urutan ruangan di database identik
     * dengan yang dikenal model (nama ruangan masuk ke system prompt). Idempotent: ruangan yang namanya
     * sudah ada tidak diubah atau digandakan, jadi aman dijalankan ulang.
     */
    public function run(): void
    {
        $path = base_path('ai-model/training/data/rooms.json');

        if (! is_file($path)) {
            $this->command?->warn("rooms.json tidak ditemukan di {$path}; RoomSeeder dilewati.");

            return;
        }

        $data = json_decode((string) file_get_contents($path), true);

        foreach ($data['rooms'] ?? $data as $room) {
            Room::firstOrCreate(
                ['name' => $room['name']],
                [
                    'location' => $room['location'] ?? null,
                    'capacity' => $room['capacity'] ?? 1,
                    'description' => $room['description'] ?? null,
                    'status' => $room['status'] ?? 'available',
                ],
            );
        }
    }
}
