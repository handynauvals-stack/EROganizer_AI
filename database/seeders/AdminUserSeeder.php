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

        $legacyAdmins = User::whereIn('email', ['admin@ub.com', 'admin@ub.ac.id'])
            ->get();

        foreach ($legacyAdmins as $legacyAdmin) {
            if ($legacyAdmin->email !== $canonicalEmail) {
                $legacyAdmin->update(['email' => $canonicalEmail]);
            }
        }

        User::updateOrCreate(
            ['email' => $canonicalEmail],
            [
                'name' => 'Admin',
                'email' => $canonicalEmail,
                'password' => Hash::make($canonicalPassword),
                'role' => 'admin',
            ]
        );
    }
}