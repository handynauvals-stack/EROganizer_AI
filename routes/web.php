<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\MemberController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\RoomBookingController;
use App\Http\Controllers\RoomController;
use App\Http\Controllers\ChatbotController;

Route::get('/', function () {
    if (Illuminate\Support\Facades\Auth::check()) {
        return redirect()->route('admin.dashboard');
    } elseif (session()->has('member_id')) {
        return redirect()->route('member.dashboard');
    }
    return redirect()->route('login');
});

// Authentication
Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login']);
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
Route::get('/register', [AuthController::class, 'showRegister'])->name('register');
Route::post('/register', [AuthController::class, 'register']);

// Admin Routes - Full Management Access
Route::middleware(['auth', 'is_admin'])->prefix('admin')->name('admin.')->group(function () {
    // Dashboard
    Route::get('/dashboard', [DashboardController::class, 'admin'])->name('dashboard');

    // Member Management
    Route::resource('members', MemberController::class);

    // Faculty room management and reservations
    Route::resource('rooms', RoomController::class)->except(['show']);
    Route::get('/room-bookings', [RoomBookingController::class, 'adminIndex'])->name('room-bookings.index');
    Route::patch('/room-bookings/{roomBooking}/status', [RoomBookingController::class, 'updateStatus'])->name('room-bookings.status');

});

// Chatbot (Qwen) - tersedia untuk admin maupun member yang sudah login
Route::middleware(['auth.check'])->prefix('chatbot')->name('chatbot.')->group(function () {
    Route::post('/message', [ChatbotController::class, 'message'])->middleware('throttle:20,1')->name('message');
    Route::get('/status', [ChatbotController::class, 'status'])->name('status');
});

// Member Routes - Limited Access
Route::middleware(['is_member'])->group(function () {
    // Dashboard
    Route::get('/dashboard', [DashboardController::class, 'member'])->name('member.dashboard');

    Route::get('/rooms', [RoomController::class, 'memberIndex'])->name('rooms.index');
    Route::post('/rooms/{room}/book', [RoomBookingController::class, 'store'])->name('rooms.book');
    Route::get('/room-bookings', [RoomBookingController::class, 'index'])->name('room-bookings.index');
    Route::patch('/room-bookings/{roomBooking}/cancel', [RoomBookingController::class, 'cancel'])->name('room-bookings.cancel');
    Route::get('/profile', [\App\Http\Controllers\ProfileController::class, 'edit'])->name('member.profile');
    Route::post('/profile', [\App\Http\Controllers\ProfileController::class, 'update'])->name('member.profile.update');
});
