<?php

namespace App\Services\Chatbot;

use App\Models\Room;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Orkestrasi chatbot: pesan pengguna -> model -> (tool call? jalankan ke database -> kirim hasil ke model) -> jawaban akhir.
 */
class ChatbotService
{
    private const FALLBACK = 'Maaf, saya belum bisa memproses permintaan itu. Coba tanyakan dengan kalimat lain.';

    /**
     * @param  array<int, array{role: string, content: string}>  $history  hanya role user/assistant
     */
    public function reply(array $history, string $message, ?int $userId): string
    {
        $messages = [['role' => 'system', 'content' => $this->systemPrompt()]];
        foreach ($history as $item) {
            $messages[] = ['role' => $item['role'], 'content' => $item['content']];
        }
        $messages[] = ['role' => 'user', 'content' => $message];

        $executor = new ToolExecutor($userId, null, $message);
        $maxCalls = (int) config('chatbot.max_tool_rounds', 3);

        for ($i = 0; $i <= $maxCalls; $i++) {
            $reply = $this->ask($messages);
            $call = self::parseToolCall($reply);

            if ($call === null) {
                $reply = trim($reply);
                // JSON mentah yang bukan tool call valid tidak boleh sampai ke pengguna.
                return ($reply === '' || $reply[0] === '{') ? self::FALLBACK : $reply;
            }
            if ($i === $maxCalls) {
                break;
            }

            $messages[] = ['role' => 'assistant', 'content' => $reply];
            $messages[] = ['role' => 'tool', 'content' => ToolExecutor::encode($executor->run($call['tool'], $call['args']))];
        }

        return self::FALLBACK;
    }

    /**
     * System prompt = isi training/system_prompt.txt (sumber tunggal yang juga dipakai saat training & evaluasi)
     * dengan {{ROOMS}} diganti nama ruangan dari database. Harus identik dengan yang dilihat model saat training.
     */
    public function systemPrompt(): string
    {
        $path = config('chatbot.system_prompt_path');
        if (! is_string($path) || ! is_file($path)) {
            Log::error('Chatbot: file system prompt tidak ditemukan', ['path' => $path]);
            throw new ChatbotException('Asisten AI belum dikonfigurasi dengan benar.', 500);
        }

        $template = str_replace("\r\n", "\n", (string) file_get_contents($path)); // Python membaca teks dengan newline "\n"
        $rooms = Room::orderBy('id')->pluck('name')->implode('; ');

        return trim(str_replace('{{ROOMS}}', $rooms, $template));
    }

    /** @return array{tool: string, args: array}|null */
    public static function parseToolCall(string $text): ?array
    {
        $s = trim($text);
        if (preg_match('/^```(?:json)?\s*(.*?)\s*```$/s', $s, $m)) {
            $s = $m[1];
        }
        if ($s === '' || $s[0] !== '{') {
            return null;
        }
        $obj = json_decode($s, true);
        if (! is_array($obj) || ! isset($obj['tool']) || ! in_array($obj['tool'], ToolExecutor::TOOLS, true)) {
            return null;
        }
        $args = $obj['args'] ?? [];

        return is_array($args) ? ['tool' => $obj['tool'], 'args' => $args] : null;
    }

    private function ask(array $messages): string
    {
        try {
            $response = Http::baseUrl(config('chatbot.url'))
                ->connectTimeout(3)
                ->timeout(config('chatbot.timeout'))
                ->acceptJson()
                ->post('/chat', [
                    'messages' => $messages,
                    'max_new_tokens' => config('chatbot.max_new_tokens'),
                    'temperature' => config('chatbot.temperature'),
                ]);
        } catch (ConnectionException $e) {
            Log::warning('Chatbot: layanan AI tidak dapat dihubungi', ['error' => $e->getMessage()]);
            throw new ChatbotException('Asisten AI sedang tidak aktif. Silakan coba beberapa saat lagi.', 503);
        }

        if ($response->failed()) {
            Log::warning('Chatbot: layanan AI mengembalikan error', ['status' => $response->status(), 'body' => $response->body()]);
            throw new ChatbotException('Asisten AI sedang mengalami gangguan. Silakan coba lagi.', 502);
        }

        return (string) $response->json('reply', '');
    }
}
