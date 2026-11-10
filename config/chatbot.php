<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Layanan inferensi (model bahasa + adapter LoRA hasil training)
    |--------------------------------------------------------------------------
    | Service Python di folder ai-model (ai-model\run_server.bat). Hanya dipanggil dari
    | server Laravel, tidak pernah langsung dari browser.
    */
    'url' => rtrim(env('CHATBOT_URL', 'http://127.0.0.1:8001'), '/'),
    'timeout' => (int) env('CHATBOT_TIMEOUT', 60),

    // Jawaban berupa tool call (JSON) harus deterministik: temperature 0 = greedy, sama seperti saat evaluasi.
    // Jangan dinaikkan tanpa menguji ulang; sampling bisa merusak argumen tool call.
    'max_new_tokens' => (int) env('CHATBOT_MAX_NEW_TOKENS', 400),
    'temperature' => (float) env('CHATBOT_TEMPERATURE', 0.0),

    // Berapa kali model boleh memanggil tool dalam satu pertanyaan (tool -> hasil -> tool -> ... -> jawaban).
    'max_tool_rounds' => (int) env('CHATBOT_MAX_TOOL_ROUNDS', 3),

    // Zona waktu pengguna untuk "hari ini/besok" dan pengecekan "waktu sudah lewat".
    // (config app.timezone = UTC, sedangkan jam booking di database adalah jam dinding lokal.)
    'timezone' => env('CHATBOT_TIMEZONE', 'Asia/Jakarta'),

    /*
    |--------------------------------------------------------------------------
    | Batas input dari pengguna
    |--------------------------------------------------------------------------
    */
    'max_message_length' => 500,
    'max_history' => 8, // jumlah pesan sebelumnya yang dikirim sebagai konteks

    /*
    |--------------------------------------------------------------------------
    | System prompt
    |--------------------------------------------------------------------------
    | SATU sumber untuk training, evaluasi, dan aplikasi: training/system_prompt.txt
    | ({{ROOMS}} diisi nama ruangan dari database). Jika file itu diubah, model harus dilatih ulang.
    */
    'system_prompt_path' => env('CHATBOT_SYSTEM_PROMPT_PATH', base_path('ai-model/training/system_prompt.txt')),

];
