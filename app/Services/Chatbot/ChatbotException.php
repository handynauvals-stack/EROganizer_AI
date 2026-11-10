<?php

namespace App\Services\Chatbot;

use RuntimeException;

/**
 * Kegagalan yang boleh ditampilkan ke pengguna (layanan AI mati / error).
 * $status = kode HTTP yang dikirim ke widget chat.
 */
class ChatbotException extends RuntimeException
{
    public function __construct(string $message, public readonly int $status = 502)
    {
        parent::__construct($message);
    }
}
