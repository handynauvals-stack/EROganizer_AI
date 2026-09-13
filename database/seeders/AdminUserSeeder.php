<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;
use App\Models\User;

class AdminUserSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $canonicalEmail = 'admin@eroganizer.com';
        $canonicalPassword = 'password123';

        $adminCandidates = User::whereIn('email', [
            'admin@eroganizer.com',
            'admin@ub.ac.id',
            'admin@ub.com',
        ])->orderBy('id')->get();

        $primaryAdmin = $adminCandidates->first();

        if ($primaryAdmin) {
            $primaryAdmin->fill([
                'name' => 'Admin',
                'email' => $canonicalEmail,
                'password' => Hash::make($canonicalPassword),
                'role' => 'admin',
            ]);
            $primaryAdmin->save();

            foreach ($adminCandidates->skip(1) as $duplicateAdmin) {
                $duplicateAdmin->delete();
            }

            return;
        }

        User::create([
            'name' => 'Admin',
            'email' => $canonicalEmail,
            'password' => Hash::make($canonicalPassword),
            'role' => 'admin',
        ]);
    }
}