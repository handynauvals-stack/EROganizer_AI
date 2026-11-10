<?php

namespace App\Http\Controllers;

use App\Models\Member;
use App\Models\User;
use App\Services\Chatbot\ChatbotException;
use App\Services\Chatbot\ChatbotService;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Http;

class ChatbotController extends Controller
{
    /**
     * Terima pesan dari widget chat. Model mengusulkan tool call, ChatbotService menjalankannya ke database
     * atas nama pengguna yang sedang login, lalu model menjelaskan hasilnya.
     */
    public function message(Request $request, ChatbotService $chatbot): JsonResponse
    {
        $data = $request->validate([
            'message' => ['required', 'string', 'max:' . config('chatbot.max_message_length')],
            'history' => ['sometimes', 'array', 'max:20'],
            'history.*.role' => ['required', 'in:user,assistant'], // client tidak boleh menyisipkan role "system"/"tool"
            'history.*.content' => ['required', 'string', 'max:2000'],
        ]);

        $history = array_slice($data['history'] ?? [], -config('chatbot.max_history'));

        try {
            $reply = $chatbot->reply($history, $data['message'], $this->currentUserId());
        } catch (ChatbotException $e) {
            return response()->json(['message' => $e->getMessage()], $e->status);
        }

        return response()->json(['reply' => $reply]);
    }

    /**
     * Cek apakah layanan AI aktif (dipakai widget untuk label Online/Offline).
     */
    public function status(): JsonResponse
    {
        try {
            $response = Http::baseUrl(config('chatbot.url'))
                ->connectTimeout(1)
                ->timeout(2)
                ->get('/health');

            $online = $response->ok() && $response->json('status') === 'ok';
        } catch (ConnectionException $e) {
            $online = false;
        }

        return response()->json(['online' => $online]);
    }

    /** Sama dengan RoomBookingController::memberUserId(): admin = Auth::id(), member = user dengan email yang sama. */
    private function currentUserId(): ?int
    {
        if (Auth::id()) {
            return Auth::id();
        }

        $member = session('member_id') ? Member::find(session('member_id')) : null;

        return $member ? User::where('email', $member->email)->value('id') : null;
    }
}
