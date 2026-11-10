<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EROganizer</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">

    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

    <style>
        :root {
            --primary-blue: #3b82f6;
            --primary-blue-dark: #1e40af;
            --bg-dark: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --border-color: #475569;
            --card-bg: #1e293b;
            --hover-color: #0f172a;
            --accent-success: #10b981;
            --accent-danger: #ef4444;
            --accent-warning: #f59e0b;
        }

        * {
            box-sizing: border-box;
        }

        html, body {
            height: 100%;
            background: var(--bg-dark);
            color: var(--text-primary);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
        }

        /* SIDEBAR */
        .sidebar {
            width: 260px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            min-height: 100vh;
            padding: 20px 0;
            transition: transform 0.3s ease;
            overflow-y: auto;
        }

        .sidebar-brand {
            padding: 0 20px;
            margin-bottom: 30px;
            font-size: 20px;
            font-weight: 700;
            color: var(--primary-blue);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sidebar-nav {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .sidebar-nav a {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 20px;
            color: var(--text-secondary);
            text-decoration: none;
            transition: all 0.2s ease;
            border-left: 3px solid transparent;
        }

        .sidebar-nav a:hover,
        .sidebar-nav a.active {
            color: var(--primary-blue);
            background: var(--bg-tertiary);
            border-left-color: var(--primary-blue);
        }

        .sidebar-nav i {
            font-size: 18px;
            min-width: 20px;
        }

        /* NAVBAR */
        .navbar-dark {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 12px 20px;
        }

        .navbar-brand {
            font-size: 18px;
            font-weight: 700;
            color: var(--primary-blue) !important;
            margin: 0;
        }

        .search-bar {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            padding: 8px 12px;
            width: 300px;
            transition: all 0.2s ease;
        }

        .search-bar:focus {
            background: var(--bg-dark);
            border-color: var(--primary-blue);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
            outline: none;
        }

        .search-bar::placeholder {
            color: var(--text-muted);
        }

        /* MAIN CONTAINER */
        .main-wrapper {
            display: flex;
            height: 100vh;
        }

        .content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .navbar-section {
            flex-shrink: 0;
            border-bottom: 1px solid var(--border-color);
        }

        .page-content {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
        }

        /* CARDS & COMPONENTS */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .card:hover {
            border-color: var(--primary-blue);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
        }

        .card-header {
            background: transparent;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }

        .card-body {
            color: var(--text-primary);
        }

        /* BUTTONS */
        .btn-primary {
            background: var(--primary-blue);
            border: none;
            color: white;
            transition: all 0.2s ease;
        }

        .btn-primary:hover {
            background: var(--primary-blue-dark);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .btn-outline-secondary {
            color: var(--text-secondary);
            border-color: var(--border-color);
        }

        .btn-outline-secondary:hover {
            background: var(--bg-tertiary);
            border-color: var(--primary-blue);
            color: var(--primary-blue);
        }

        .btn-danger {
            background: var(--accent-danger);
            border: none;
        }

        .btn-danger:hover {
            background: #dc2626;
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
        }

        /* BADGES */
        .badge {
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }

        .badge.bg-primary {
            background: var(--primary-blue) !important;
        }

        .badge.bg-success {
            background: var(--accent-success) !important;
        }

        .badge.bg-warning {
            background: var(--accent-warning) !important;
        }

        /* ALERTS */
        .alert {
            border: none;
            border-radius: 6px;
        }

        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-success);
        }

        .alert-danger {
            background: rgba(239, 68, 68, 0.1);
            color: var(--accent-danger);
        }

        /* TYPOGRAPHY */
        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary);
            font-weight: 600;
            margin-bottom: 10px;
        }

        h2 {
            font-size: 28px;
        }

        h5 {
            font-size: 16px;
        }

        .text-muted {
            color: var(--text-muted) !important;
        }

        /* FORMS */
        .form-control, .form-select {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-radius: 6px;
            transition: all 0.2s ease;
        }

        .form-control:focus, .form-select:focus {
            background: var(--bg-tertiary);
            border-color: var(--primary-blue);
            color: var(--text-primary);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
        }

        .form-label {
            color: var(--text-secondary);
            font-weight: 500;
            margin-bottom: 8px;
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
            .sidebar {
                position: fixed;
                left: 0;
                top: 0;
                z-index: 1040;
                height: 100vh;
                transform: translateX(-100%);
            }

            .sidebar.show {
                transform: translateX(0);
            }

            .search-bar {
                width: 200px;
            }

            .page-content {
                padding: 20px;
            }
        }

        /* EMPTY STATE */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }

        .empty-state h5 {
            color: var(--text-secondary);
            margin-bottom: 10px;
        }

        .empty-state i {
            font-size: 48px;
            color: var(--text-muted);
            margin-bottom: 20px;
            opacity: 0.5;
        }

        /* SCROLLBAR */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
    </style>

</head>

<body>

<div class="main-wrapper">

    <!-- Sidebar -->
    @include('layouts.sidebar')

    <!-- Content -->
    <div class="content">

        <!-- Navbar -->
        <nav class="navbar navbar-dark navbar-section">
            <div class="container-fluid">
                <div class="d-flex align-items-center gap-3 flex-grow-1">
                    <button id="toggleSidebar" class="btn btn-outline-secondary btn-sm d-md-none">
                        <i class="bi bi-list"></i>
                    </button>
                    <a class="navbar-brand" href="{{ Auth::check() ? route('admin.dashboard') : (session()->has('member_id') ? route('member.dashboard') : '#') }}">Efficient Room Organizer</a>
                </div>

                <div class="d-flex align-items-center gap-2">
                    <span class="text-muted small">
                        @if(Auth::check())
                            {{ Auth::user()->name }}
                        @elseif(session()->has('member_id'))
                            {{ session('member')->nama }} (Member)
                        @endif
                    </span>
                    <form action="{{ route('logout') }}" method="POST" class="d-inline">
                        @csrf
                        <button class="btn btn-danger btn-sm">Logout</button>
                    </form>
                </div>
            </div>
        </nav>

        <!-- Page Content -->
        <div class="page-content">
            @include('partials.alerts')
            @yield('content')
        </div>

    </div>

</div>

@include('partials.chatbot')

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

<script>
    document.addEventListener('DOMContentLoaded', function(){
        const toggle = document.getElementById('toggleSidebar');
        const sidebar = document.querySelector('.sidebar');

        if (toggle) {
            toggle.addEventListener('click', function(){
                sidebar.classList.toggle('show');
            });
        }

        // Close sidebar when clicking on a link on mobile
        sidebar.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function(){
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('show');
                }
            });
        });
    });
</script>

</body>
</html>