@if(Auth::check() || session()->has('member_id'))
{{-- Widget chatbot EROganizer: tombol melayang + panel chat. Dipasang di layouts/app.blade.php --}}
<div id="eroChat"
     data-send-url="{{ route('chatbot.message') }}"
     data-status-url="{{ route('chatbot.status') }}"
     data-csrf="{{ csrf_token() }}"
     data-uid="{{ Auth::check() ? 'u' . Auth::id() : 'm' . session('member_id') }}">

    <button type="button" id="eroChatFab" class="eroc-fab" aria-label="Buka chat asisten" aria-expanded="false" aria-controls="eroChatPanel" title="Tanya Asisten EROganizer">
        <i class="bi bi-chat-dots-fill" aria-hidden="true"></i>
    </button>

    <section id="eroChatPanel" class="eroc-panel" role="dialog" aria-label="Asisten EROganizer" hidden>
        <header class="eroc-header">
            <div class="eroc-avatar"><i class="bi bi-robot" aria-hidden="true"></i></div>
            <div class="eroc-title">
                <strong>Asisten EROganizer</strong>
                <small><span id="eroChatDot" class="eroc-dot"></span><span id="eroChatStatus">Memeriksa...</span></small>
            </div>
            <button type="button" id="eroChatClear" class="eroc-iconbtn" aria-label="Hapus percakapan" title="Hapus percakapan"><i class="bi bi-trash3" aria-hidden="true"></i></button>
            <button type="button" id="eroChatClose" class="eroc-iconbtn" aria-label="Tutup chat" title="Tutup"><i class="bi bi-x-lg" aria-hidden="true"></i></button>
        </header>

        <div id="eroChatLog" class="eroc-log" aria-live="polite"></div>

        <form id="eroChatForm" class="eroc-form" autocomplete="off">
            <textarea id="eroChatInput" rows="1" maxlength="500" placeholder="Tulis pertanyaan..." aria-label="Pesan"></textarea>
            <button type="submit" id="eroChatSend" class="eroc-send" aria-label="Kirim"><i class="bi bi-send-fill" aria-hidden="true"></i></button>
        </form>
    </section>
</div>

<style>
    #eroChat { --eroc-blue: var(--primary-blue, #3b82f6); --eroc-blue-dark: var(--primary-blue-dark, #1e40af);
        --eroc-bg: var(--bg-secondary, #1e293b); --eroc-bg-deep: var(--bg-dark, #0f172a); --eroc-bg-soft: var(--bg-tertiary, #334155);
        --eroc-border: var(--border-color, #475569); --eroc-text: var(--text-primary, #f1f5f9); --eroc-muted: var(--text-muted, #94a3b8); }
    #eroChat *, #eroChat *::before, #eroChat *::after { box-sizing: border-box; }
    #eroChat [hidden] { display: none !important; }

    .eroc-fab { position: fixed; right: 24px; bottom: 24px; z-index: 1045; width: 58px; height: 58px; border: 0; border-radius: 50%;
        background: linear-gradient(135deg, var(--eroc-blue), var(--eroc-blue-dark)); color: #fff; font-size: 26px; line-height: 1;
        display: flex; align-items: center; justify-content: center; cursor: pointer;
        box-shadow: 0 8px 24px rgba(0, 0, 0, .45), 0 0 0 0 rgba(59, 130, 246, .5); transition: transform .2s ease, box-shadow .2s ease; }
    .eroc-fab:hover { transform: scale(1.07); box-shadow: 0 10px 28px rgba(0, 0, 0, .5); }
    .eroc-fab:focus-visible, .eroc-iconbtn:focus-visible, .eroc-send:focus-visible, .eroc-chip:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
    .eroc-fab.is-open i::before { content: "\f62a"; } /* bi-x-lg */

    .eroc-panel { position: fixed; right: 24px; bottom: 96px; z-index: 1045; width: 370px; height: 540px; max-height: calc(100vh - 120px);
        display: flex; flex-direction: column; background: var(--eroc-bg); color: var(--eroc-text); border: 1px solid var(--eroc-border);
        border-radius: 16px; box-shadow: 0 16px 48px rgba(0, 0, 0, .55); overflow: hidden; animation: eroc-pop .18s ease-out; }
    @keyframes eroc-pop { from { opacity: 0; transform: translateY(12px) scale(.97); } to { opacity: 1; transform: none; } }

    .eroc-header { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: linear-gradient(135deg, var(--eroc-blue), var(--eroc-blue-dark)); color: #fff; }
    .eroc-avatar { width: 38px; height: 38px; border-radius: 50%; background: rgba(255, 255, 255, .2); display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
    .eroc-title { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
    .eroc-title strong { font-size: 14px; }
    .eroc-title small { font-size: 12px; opacity: .9; display: flex; align-items: center; gap: 6px; }
    .eroc-dot { width: 8px; height: 8px; border-radius: 50%; background: #9ca3af; display: inline-block; }
    .eroc-dot.is-online { background: #34d399; }
    .eroc-dot.is-offline { background: #f87171; }
    .eroc-iconbtn { border: 0; background: transparent; color: #fff; width: 32px; height: 32px; border-radius: 8px; cursor: pointer; font-size: 15px; opacity: .85; }
    .eroc-iconbtn:hover { background: rgba(255, 255, 255, .18); opacity: 1; }

    .eroc-log { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; background: var(--eroc-bg-deep); }
    .eroc-msg { max-width: 85%; padding: 9px 13px; font-size: 13.5px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; }
    .eroc-msg--bot { align-self: flex-start; background: var(--eroc-bg-soft); color: var(--eroc-text); border-radius: 14px 14px 14px 4px; }
    .eroc-msg--user { align-self: flex-end; background: var(--eroc-blue); color: #fff; border-radius: 14px 14px 4px 14px; }
    .eroc-msg--error { align-self: flex-start; background: rgba(239, 68, 68, .12); color: #fca5a5; border: 1px solid rgba(239, 68, 68, .35); border-radius: 14px 14px 14px 4px; }
    .eroc-chips { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
    .eroc-chip { border: 1px solid var(--eroc-blue); background: transparent; color: var(--eroc-text); border-radius: 999px; padding: 6px 12px; font-size: 12.5px; cursor: pointer; text-align: left; }
    .eroc-chip:hover { background: rgba(59, 130, 246, .18); }
    .eroc-typing { align-self: flex-start; background: var(--eroc-bg-soft); border-radius: 14px 14px 14px 4px; padding: 11px 14px; display: flex; gap: 4px; }
    .eroc-typing span { width: 7px; height: 7px; border-radius: 50%; background: var(--eroc-muted); animation: eroc-bounce 1.2s infinite ease-in-out; }
    .eroc-typing span:nth-child(2) { animation-delay: .15s; }
    .eroc-typing span:nth-child(3) { animation-delay: .3s; }
    @keyframes eroc-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-5px); opacity: 1; } }

    .eroc-form { display: flex; align-items: flex-end; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--eroc-border); background: var(--eroc-bg); }
    .eroc-form textarea { flex: 1; resize: none; max-height: 96px; background: var(--eroc-bg-soft); color: var(--eroc-text); border: 1px solid var(--eroc-border);
        border-radius: 12px; padding: 9px 12px; font: inherit; font-size: 13.5px; line-height: 1.4; }
    .eroc-form textarea:focus { outline: none; border-color: var(--eroc-blue); box-shadow: 0 0 0 2px rgba(59, 130, 246, .2); }
    .eroc-form textarea::placeholder { color: var(--eroc-muted); }
    .eroc-send { width: 40px; height: 40px; border: 0; border-radius: 50%; background: var(--eroc-blue); color: #fff; cursor: pointer; font-size: 15px; flex-shrink: 0; }
    .eroc-send:hover:not(:disabled) { background: var(--eroc-blue-dark); }
    .eroc-send:disabled { opacity: .5; cursor: not-allowed; }

    @media (max-width: 480px) {
        .eroc-fab { right: 16px; bottom: 16px; }
        .eroc-panel { right: 12px; left: 12px; width: auto; bottom: 86px; height: calc(100vh - 110px); }
    }
    @media (prefers-reduced-motion: reduce) {
        .eroc-panel, .eroc-typing span { animation: none; }
        .eroc-fab { transition: none; }
    }
</style>

<script>
(function () {
    var root = document.getElementById('eroChat');
    if (!root) { return; }

    var sendUrl = root.dataset.sendUrl, statusUrl = root.dataset.statusUrl, csrf = root.dataset.csrf, uid = root.dataset.uid;
    var fab = document.getElementById('eroChatFab'), panel = document.getElementById('eroChatPanel'),
        log = document.getElementById('eroChatLog'), form = document.getElementById('eroChatForm'),
        input = document.getElementById('eroChatInput'), sendBtn = document.getElementById('eroChatSend'),
        closeBtn = document.getElementById('eroChatClose'), clearBtn = document.getElementById('eroChatClear'),
        dot = document.getElementById('eroChatDot'), statusText = document.getElementById('eroChatStatus');

    var STORE_KEY = 'eroChat.v1';
    var GREETING = 'Halo! Saya asisten virtual EROganizer. Ada yang bisa saya bantu seputar peminjaman ruangan?';
    var SUGGESTIONS = ['Bagaimana cara booking ruangan?', 'Bagaimana cara membatalkan booking?', 'Apa arti status booking?'];
    var state = { open: false, messages: [] };
    var busy = false;

    function load() {
        try {
            var raw = sessionStorage.getItem(STORE_KEY);
            if (!raw) { return; }
            var s = JSON.parse(raw);
            if (s && s.uid === uid && Array.isArray(s.messages)) {
                state.open = !!s.open;
                state.messages = s.messages.slice(-40);
            } else {
                sessionStorage.removeItem(STORE_KEY); // akun berbeda di tab yang sama: jangan tampilkan riwayat lama
            }
        } catch (e) { /* storage tidak tersedia */ }
    }
    function save() {
        try { sessionStorage.setItem(STORE_KEY, JSON.stringify({ uid: uid, open: state.open, messages: state.messages.slice(-40) })); } catch (e) {}
    }

    function scrollDown() { log.scrollTop = log.scrollHeight; }

    function bubble(kind, text) {
        var el = document.createElement('div');
        el.className = 'eroc-msg eroc-msg--' + kind;
        el.textContent = text; // textContent: aman dari XSS
        log.appendChild(el);
        scrollDown();
        return el;
    }

    function renderChips() {
        var wrap = document.createElement('div');
        wrap.className = 'eroc-chips';
        wrap.id = 'eroChatChips';
        SUGGESTIONS.forEach(function (q) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'eroc-chip';
            b.textContent = q;
            b.addEventListener('click', function () { send(q); });
            wrap.appendChild(b);
        });
        log.appendChild(wrap);
    }

    function render() {
        log.textContent = '';
        bubble('bot', GREETING);
        state.messages.forEach(function (m) { bubble(m.role === 'user' ? 'user' : 'bot', m.content); });
        if (state.messages.length === 0) { renderChips(); }
        scrollDown();
    }

    function setOpen(open, focus) {
        state.open = open;
        panel.hidden = !open;
        fab.classList.toggle('is-open', open);
        fab.setAttribute('aria-expanded', open ? 'true' : 'false');
        fab.setAttribute('aria-label', open ? 'Tutup chat asisten' : 'Buka chat asisten');
        save();
        if (open) {
            scrollDown();
            checkStatus();
            if (focus !== false) { input.focus(); }
        }
    }

    function checkStatus() {
        fetch(statusUrl, { headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) { setOnline(!!d.online); })
            .catch(function () { setOnline(false); });
    }
    function setOnline(on) {
        dot.className = 'eroc-dot ' + (on ? 'is-online' : 'is-offline');
        statusText.textContent = on ? 'Online' : 'Offline';
    }

    function showTyping() {
        var t = document.createElement('div');
        t.className = 'eroc-typing';
        t.id = 'eroChatTyping';
        t.innerHTML = '<span></span><span></span><span></span>';
        log.appendChild(t);
        scrollDown();
    }
    function hideTyping() {
        var t = document.getElementById('eroChatTyping');
        if (t) { t.remove(); }
    }
    function setBusy(b) {
        busy = b;
        sendBtn.disabled = b;
        input.disabled = b;
        if (!b && state.open) { input.focus(); }
    }

    function errorText(status, data) {
        if (status === 419) { return 'Sesi kamu telah berakhir. Muat ulang halaman, lalu coba lagi.'; }
        if (status === 429) { return 'Terlalu banyak pesan dalam waktu singkat. Tunggu sebentar lalu coba lagi.'; }
        if (status === 422) {
            var first = data && data.errors ? Object.values(data.errors)[0] : null;
            return (first && first[0]) || 'Pesan tidak valid.';
        }
        return (data && data.message) || 'Terjadi kesalahan. Silakan coba lagi.';
    }

    function send(text) {
        text = (text || '').trim();
        if (!text || busy) { return; }

        var chips = document.getElementById('eroChatChips');
        if (chips) { chips.remove(); }

        var history = state.messages.map(function (m) { return { role: m.role, content: m.content.slice(0, 2000) }; });
        state.messages.push({ role: 'user', content: text });
        bubble('user', text);
        save();

        input.value = '';
        autosize();
        setBusy(true);
        showTyping();

        var controller = new AbortController();
        var timer = setTimeout(function () { controller.abort(); }, 90000);

        fetch(sendUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrf, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body: JSON.stringify({ message: text, history: history }),
            signal: controller.signal
        }).then(function (res) {
            return res.json().then(function (data) { return { res: res, data: data }; }, function () { return { res: res, data: null }; });
        }).then(function (out) {
            hideTyping();
            if (out.res.ok && out.data && out.data.reply) {
                state.messages.push({ role: 'assistant', content: out.data.reply });
                bubble('bot', out.data.reply);
                setOnline(true);
            } else {
                if (out.res.redirected || (!out.data && out.res.status === 200)) {
                    bubble('error', 'Sesi login kamu berakhir. Muat ulang halaman dan login kembali.');
                } else {
                    bubble('error', errorText(out.res.status, out.data));
                    if (out.res.status === 503) { setOnline(false); }
                }
            }
        }).catch(function (err) {
            hideTyping();
            bubble('error', err && err.name === 'AbortError' ? 'Asisten terlalu lama merespons. Coba lagi.' : 'Tidak dapat terhubung ke server. Periksa koneksi lalu coba lagi.');
        }).then(function () {
            clearTimeout(timer);
            save();
            setBusy(false);
        });
    }

    function autosize() {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 96) + 'px';
    }

    fab.addEventListener('click', function () { setOpen(!state.open); });
    closeBtn.addEventListener('click', function () { setOpen(false); fab.focus(); });
    clearBtn.addEventListener('click', function () {
        if (busy) { return; }
        state.messages = [];
        save();
        render();
    });
    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener('input', autosize);
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && state.open) { setOpen(false); fab.focus(); }
    });

    load();
    render();
    setOpen(state.open, false);
})();
</script>
@endif
