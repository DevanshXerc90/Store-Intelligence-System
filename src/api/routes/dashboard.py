from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apex Store Intelligence Dashboard</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        :root {
            --bg-primary: #0a0618;
            --bg-secondary: #110b2a;
            --bg-card: rgba(20, 13, 46, 0.6);
            --border-card: rgba(147, 51, 234, 0.2);
            --border-hover: rgba(147, 51, 234, 0.5);
            --text-primary: #f3f0ff;
            --text-secondary: #a78bfa;
            --text-muted: #6b7280;
            --purple-glow: rgba(147, 51, 234, 0.35);
            --pink-glow: rgba(236, 72, 153, 0.35);
            --accent-purple: #a855f7;
            --accent-pink: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #3b82f6;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(147, 51, 234, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(236, 72, 153, 0.1) 0%, transparent 45%);
            background-attachment: fixed;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--border-card);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--accent-purple);
        }

        header {
            background: rgba(10, 6, 24, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-card);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            font-size: 1.8rem;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 8px var(--purple-glow));
        }

        .logo-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .logo-subtitle {
            font-size: 0.8rem;
            color: var(--text-secondary);
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-top: -0.2rem;
        }

        .controls-section {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .store-selector-wrapper {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .select-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .store-select {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-card);
            padding: 0.5rem 2rem 0.5rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-weight: 600;
            font-size: 0.9rem;
            outline: none;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a78bfa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat;
            background-position: right 0.7rem center;
            background-size: 1rem;
            transition: all 0.3s ease;
            min-width: 180px;
        }

        .store-select:hover, .store-select:focus {
            border-color: var(--border-hover);
            box-shadow: 0 0 10px rgba(147, 51, 234, 0.2);
        }

        .btn {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-card);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-weight: 500;
            font-size: 0.9rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.3s ease;
        }

        .btn:hover {
            border-color: var(--border-hover);
            background: rgba(147, 51, 234, 0.1);
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            border: none;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(147, 51, 234, 0.3);
        }

        .btn-primary:hover {
            opacity: 0.9;
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(147, 51, 234, 0.4);
        }

        .toggle-wrapper {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            user-select: none;
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-card);
            transition: .4s;
            border-radius: 24px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 16px;
            width: 16px;
            left: 3px;
            bottom: 3px;
            background-color: var(--text-secondary);
            transition: .4s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--accent-purple);
            border-color: var(--accent-purple);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
            background-color: var(--text-primary);
        }

        .health-badge {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: var(--success);
        }

        .health-badge.stale {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            color: var(--warning);
        }

        .health-badge.offline {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        .health-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: currentColor;
            box-shadow: 0 0 8px currentColor;
        }

        main {
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        /* Loading Overlay */
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(10, 6, 24, 0.7);
            backdrop-filter: blur(8px);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }

        .loading-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 3px solid rgba(147, 51, 234, 0.1);
            border-radius: 50%;
            border-top-color: var(--accent-purple);
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Grid Layouts */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent, var(--accent-purple), transparent);
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(147, 51, 234, 0.15);
        }

        .card:hover::before {
            opacity: 1;
        }

        .kpi-card {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .kpi-info {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .kpi-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .kpi-value {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), #d8b4fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .kpi-change {
            font-size: 0.75rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.2rem;
            color: var(--success);
        }

        .kpi-icon-wrapper {
            background: rgba(147, 51, 234, 0.1);
            border: 1px solid rgba(147, 51, 234, 0.2);
            color: var(--accent-purple);
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 1.4rem;
            box-shadow: 0 0 15px rgba(147, 51, 234, 0.05);
        }

        .card-pink .kpi-icon-wrapper {
            background: rgba(236, 72, 153, 0.1);
            border: 1px solid rgba(236, 72, 153, 0.2);
            color: var(--accent-pink);
        }

        .dashboard-body {
            display: grid;
            grid-template-columns: 3fr 2fr;
            gap: 1.5rem;
        }

        @media (max-width: 1024px) {
            .dashboard-body {
                grid-template-columns: 1fr;
            }
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
            border-bottom: 1px solid rgba(147, 51, 234, 0.1);
            padding-bottom: 0.5rem;
        }

        .section-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-primary);
        }

        .section-title i {
            color: var(--accent-purple);
        }

        /* Funnel chart styling */
        .funnel-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            padding: 0.5rem 0;
        }

        .funnel-stage {
            display: flex;
            align-items: center;
            gap: 1rem;
            position: relative;
        }

        .funnel-label-col {
            width: 140px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            display: flex;
            flex-direction: column;
        }

        .funnel-label-sub {
            font-size: 0.7rem;
            color: var(--text-muted);
            font-weight: 400;
        }

        .funnel-bar-wrapper {
            flex-grow: 1;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            height: 40px;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
            display: flex;
            align-items: center;
            padding: 0 1rem;
        }

        .funnel-bar-fill {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            background: linear-gradient(90deg, rgba(147, 51, 234, 0.2) 0%, rgba(147, 51, 234, 0.5) 100%);
            border-right: 2px solid var(--accent-purple);
            border-radius: 7px 0 0 7px;
            transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
            width: 0%;
            z-index: 1;
        }

        .funnel-bar-fill.pink {
            background: linear-gradient(90deg, rgba(236, 72, 153, 0.2) 0%, rgba(236, 72, 153, 0.5) 100%);
            border-right: 2px solid var(--accent-pink);
        }

        .funnel-count {
            z-index: 2;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1rem;
        }

        .funnel-percent {
            margin-left: auto;
            z-index: 2;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .funnel-dropoff {
            position: absolute;
            right: 0.5rem;
            top: 45px;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--danger);
            display: flex;
            align-items: center;
            gap: 0.25rem;
            background: rgba(239, 68, 68, 0.1);
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            border: 1px solid rgba(239, 68, 68, 0.2);
            z-index: 5;
        }

        .funnel-stage:not(:last-child) {
            margin-bottom: 1.5rem;
        }

        /* Heatmap Grid */
        .heatmap-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }

        .heatmap-cell {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            transition: all 0.3s ease;
        }

        .heatmap-cell:hover {
            background: rgba(147, 51, 234, 0.05);
            border-color: rgba(147, 51, 234, 0.2);
        }

        .heatmap-cell-title {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .heatmap-cell-stats {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }

        .heatmap-cell-score {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .heatmap-cell-score-max {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .heatmap-cell-dwell {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }

        .heatmap-progress-bar {
            height: 4px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 2px;
            overflow: hidden;
        }

        .heatmap-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-purple), var(--accent-pink));
            width: 0%;
            transition: width 1s ease;
            box-shadow: 0 0 8px var(--purple-glow);
        }

        /* Anomalies Feed */
        .anomalies-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }

        .anomaly-item {
            border-left: 4px solid var(--text-muted);
            background: rgba(255, 255, 255, 0.02);
            border-top: 1px solid rgba(255, 255, 255, 0.03);
            border-right: 1px solid rgba(255, 255, 255, 0.03);
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            padding: 1rem;
            border-radius: 0 8px 8px 0;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            transition: all 0.3s ease;
        }

        .anomaly-item:hover {
            background: rgba(255, 255, 255, 0.04);
        }

        .anomaly-item.critical {
            border-left-color: var(--danger);
            background: rgba(239, 68, 68, 0.03);
        }

        .anomaly-item.warning {
            border-left-color: var(--warning);
            background: rgba(245, 158, 11, 0.03);
        }

        .anomaly-item.info {
            border-left-color: var(--info);
            background: rgba(59, 130, 246, 0.03);
        }

        .anomaly-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .anomaly-type {
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .anomaly-severity-badge {
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .critical .anomaly-severity-badge {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--danger);
        }

        .warning .anomaly-severity-badge {
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: var(--warning);
        }

        .info .anomaly-severity-badge {
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: var(--info);
        }

        .anomaly-desc {
            font-size: 0.8rem;
            color: var(--text-primary);
            font-weight: 400;
        }

        .anomaly-action {
            font-size: 0.75rem;
            color: var(--text-secondary);
            background: rgba(147, 51, 234, 0.08);
            border: 1px solid rgba(147, 51, 234, 0.15);
            padding: 0.4rem;
            border-radius: 6px;
            display: flex;
            align-items: center;
            gap: 0.3rem;
            margin-top: 0.2rem;
        }

        .anomaly-action i {
            color: var(--accent-purple);
        }

        .no-anomalies {
            padding: 2rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
        }

        /* Event Feed */
        .event-feed {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }

        .event-item {
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            transition: all 0.2s ease;
        }

        .event-item:hover {
            background: rgba(147, 51, 234, 0.03);
            border-color: rgba(147, 51, 234, 0.1);
        }

        .event-left {
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }

        .event-type-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 0.7rem;
            background: rgba(167, 139, 250, 0.1);
            color: var(--text-secondary);
        }

        .event-details {
            display: flex;
            flex-direction: column;
        }

        .event-visitor {
            font-weight: 600;
            color: var(--text-primary);
        }

        .event-action {
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        .event-right {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.2rem;
        }

        .event-time {
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        .event-badge {
            font-size: 0.6rem;
            font-weight: 700;
            padding: 0.1rem 0.3rem;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.05);
            text-transform: uppercase;
        }

        .event-badge.entry {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
        }

        .event-badge.dwell {
            background: rgba(168, 85, 247, 0.1);
            color: var(--accent-purple);
        }

        .event-badge.queue {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
        }

        .confidence-indicator {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .confidence-indicator.high {
            color: var(--success);
            background: rgba(16, 185, 129, 0.08);
            border-color: rgba(16, 185, 129, 0.15);
        }

        .confidence-indicator.low {
            color: var(--warning);
            background: rgba(245, 158, 11, 0.08);
            border-color: rgba(245, 158, 11, 0.15);
        }

        .error-message {
            color: var(--danger);
            text-align: center;
            padding: 2rem;
            font-weight: 600;
        }

        /* Rotating anim on refresh button */
        .rotating {
            animation: rotate 1s linear infinite;
        }

        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-section">
            <i class="fa-solid fa-store logo-icon"></i>
            <div>
                <h1 class="logo-title">Apex Intelligence</h1>
                <div class="logo-subtitle">Store Analytics Engine</div>
            </div>
        </div>

        <div class="controls-section">
            <div id="healthBadge" class="health-badge">
                <span class="health-dot"></span>
                <span id="healthText">System: Connecting</span>
            </div>

            <div class="store-selector-wrapper">
                <span class="select-label">Active Store:</span>
                <select id="storeSelect" class="store-select" onchange="handleStoreChange()">
                    <option value="STORE_1">Store 1 (Brigade Rd)</option>
                    <option value="STORE_2">Store 2 (Mall of Asia)</option>
                    <option value="STORE_BLR_002">STORE_BLR_002</option>
                </select>
            </div>

            <div class="toggle-wrapper" onclick="toggleAutoRefresh()">
                <span class="select-label">Auto Refresh</span>
                <label class="switch">
                    <input type="checkbox" id="autoRefreshCheckbox" checked>
                    <span class="slider"></span>
                </label>
            </div>

            <button id="refreshBtn" class="btn" onclick="manualRefresh()">
                <i class="fa-solid fa-arrows-rotate"></i>
                Refresh
            </button>
        </div>
    </header>

    <main>
        <!-- KPI Row -->
        <div class="kpi-grid">
            <!-- Unique Visitors -->
            <div class="card kpi-card">
                <div class="kpi-info">
                    <span class="kpi-label">Unique Visitors</span>
                    <h2 id="kpiVisitors" class="kpi-value">0</h2>
                    <span class="kpi-change"><i class="fa-solid fa-chart-line"></i> Active Sessions</span>
                </div>
                <div class="kpi-icon-wrapper">
                    <i class="fa-solid fa-users"></i>
                </div>
            </div>

            <!-- Conversion Rate -->
            <div class="card kpi-card card-pink">
                <div class="kpi-info">
                    <span class="kpi-label">Conversion Rate</span>
                    <h2 id="kpiConversion" class="kpi-value">0.0%</h2>
                    <span class="kpi-change"><i class="fa-solid fa-bag-shopping"></i> POS Matched</span>
                </div>
                <div class="kpi-icon-wrapper">
                    <i class="fa-solid fa-basket-shopping"></i>
                </div>
            </div>

            <!-- Active Queue Depth -->
            <div class="card kpi-card">
                <div class="kpi-info">
                    <span class="kpi-label">Queue Depth</span>
                    <h2 id="kpiQueueDepth" class="kpi-value">0</h2>
                    <span class="kpi-change" style="color: var(--text-secondary);"><i class="fa-solid fa-clock"></i> Active Waiting</span>
                </div>
                <div class="kpi-icon-wrapper">
                    <i class="fa-solid fa-people-arrows"></i>
                </div>
            </div>

            <!-- Abandonment Rate -->
            <div class="card kpi-card card-pink">
                <div class="kpi-info">
                    <span class="kpi-label">Abandonment Rate</span>
                    <h2 id="kpiAbandonment" class="kpi-value">0.0%</h2>
                    <span class="kpi-change" style="color: var(--danger);"><i class="fa-solid fa-arrow-right-from-bracket"></i> Left Billing Queue</span>
                </div>
                <div class="kpi-icon-wrapper">
                    <i class="fa-solid fa-user-slash"></i>
                </div>
            </div>
        </div>

        <!-- Dashboard Body -->
        <div class="dashboard-body">
            <!-- Left Side: Funnel + Heatmap -->
            <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- Funnel Card -->
                <div class="card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="fa-solid fa-filter"></i>
                            Session Conversion Funnel
                        </h3>
                        <span id="funnelConfidence" class="confidence-indicator high">
                            <i class="fa-solid fa-circle-check"></i> High Confidence
                        </span>
                    </div>
                    <div id="funnelContainer" class="funnel-container">
                        <!-- Funnel Stages will load here dynamically -->
                        <div class="funnel-stage">
                            <div class="funnel-label-col">
                                <span>1. Entrance</span>
                                <span class="funnel-label-sub">Unique Entries</span>
                            </div>
                            <div class="funnel-bar-wrapper">
                                <div class="funnel-bar-fill" style="width: 0%;"></div>
                                <span class="funnel-count">0</span>
                                <span class="funnel-percent">100%</span>
                            </div>
                        </div>
                        <div class="funnel-stage">
                            <div class="funnel-label-col">
                                <span>2. Zone Visit</span>
                                <span class="funnel-label-sub">Browsed Aisle</span>
                            </div>
                            <div class="funnel-bar-wrapper">
                                <div class="funnel-bar-fill pink" style="width: 0%;"></div>
                                <span class="funnel-count">0</span>
                                <span class="funnel-percent">0%</span>
                            </div>
                        </div>
                        <div class="funnel-stage">
                            <div class="funnel-label-col">
                                <span>3. Billing Queue</span>
                                <span class="funnel-label-sub">Reached Queue</span>
                            </div>
                            <div class="funnel-bar-wrapper">
                                <div class="funnel-bar-fill" style="width: 0%;"></div>
                                <span class="funnel-count">0</span>
                                <span class="funnel-percent">0%</span>
                            </div>
                        </div>
                        <div class="funnel-stage">
                            <div class="funnel-label-col">
                                <span>4. Purchase</span>
                                <span class="funnel-label-sub">Completed Sale</span>
                            </div>
                            <div class="funnel-bar-wrapper">
                                <div class="funnel-bar-fill pink" style="width: 0%;"></div>
                                <span class="funnel-count">0</span>
                                <span class="funnel-percent">0%</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Heatmap/Zones Card -->
                <div class="card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="fa-solid fa-fire-flame-simple"></i>
                            Zone Dwell & Traffic Scores
                        </h3>
                    </div>
                    <div id="heatmapGrid" class="heatmap-grid">
                        <!-- Heatmap cells loaded dynamically -->
                        <div class="no-anomalies">No zone metrics loaded yet.</div>
                    </div>
                </div>
            </div>

            <!-- Right Side: Anomalies + Event Ticker -->
            <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- Anomalies Card -->
                <div class="card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            Active Operational Alerts
                        </h3>
                    </div>
                    <div id="anomaliesFeed" class="anomalies-container">
                        <div class="no-anomalies">
                            <i class="fa-solid fa-circle-check" style="color: var(--success); font-size: 1.5rem; margin-bottom: 0.5rem; display: block;"></i>
                            All systems operating normally. No alerts.
                        </div>
                    </div>
                </div>

                <!-- Event Feed Card -->
                <div class="card">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="fa-solid fa-bolt"></i>
                            Real-Time Event Stream
                        </h3>
                    </div>
                    <div id="eventFeed" class="event-feed">
                        <!-- Dynamic event items will scroll here -->
                        <div class="no-anomalies">Waiting for incoming events...</div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Loading Overlay -->
    <div id="loadingOverlay" class="loading-overlay">
        <div class="spinner"></div>
    </div>

    <!-- Scripts -->
    <script>
        let autoRefreshInterval = null;
        let isFetching = false;
        let lastEventCount = 0;
        let localEventsCache = [];

        document.addEventListener("DOMContentLoaded", () => {
            // Load initial data
            refreshAll();
            
            // Set up auto-refresh
            toggleAutoRefresh();
        });

        function toggleAutoRefresh() {
            const isChecked = document.getElementById("autoRefreshCheckbox").checked;
            if (isChecked) {
                if (!autoRefreshInterval) {
                    autoRefreshInterval = setInterval(refreshAll, 3000);
                }
            } else {
                if (autoRefreshInterval) {
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                }
            }
        }

        async function manualRefresh() {
            const refreshBtnIcon = document.querySelector("#refreshBtn i");
            refreshBtnIcon.classList.add("rotating");
            await refreshAll();
            setTimeout(() => {
                refreshBtnIcon.classList.remove("rotating");
            }, 800);
        }

        function handleStoreChange() {
            // Clear events cache for clean view
            localEventsCache = [];
            document.getElementById("eventFeed").innerHTML = '<div class="no-anomalies">Loading events...</div>';
            refreshAll();
        }

        async function refreshAll() {
            if (isFetching) return;
            isFetching = true;

            const storeId = document.getElementById("storeSelect").value;
            
            try {
                // Fetch all endpoints concurrently
                const [healthRes, metricsRes, funnelRes, heatmapRes, anomaliesRes] = await Promise.all([
                    fetch('/health').then(r => r.json()).catch(() => null),
                    fetch(`/stores/${storeId}/metrics`).then(r => r.json()).catch(() => null),
                    fetch(`/stores/${storeId}/funnel`).then(r => r.json()).catch(() => null),
                    fetch(`/stores/${storeId}/heatmap`).then(r => r.json()).catch(() => null),
                    fetch(`/stores/${storeId}/anomalies`).then(r => r.json()).catch(() => null)
                ]);

                // Update UI parts
                updateHealth(healthRes);
                updateMetrics(metricsRes);
                updateFunnel(funnelRes);
                updateHeatmap(heatmapRes);
                updateAnomalies(anomaliesRes);

                // Fetch a quick mock of recent event feed based on database counts,
                // or parse simulated incoming stream.
                simulateEventTicker(storeId);

            } catch (err) {
                console.error("Error refreshing dashboard:", err);
            } finally {
                isFetching = false;
            }
        }

        function updateHealth(health) {
            const badge = document.getElementById("healthBadge");
            const text = document.getElementById("healthText");

            if (!health) {
                badge.className = "health-badge offline";
                text.innerText = "System: Offline";
                return;
            }

            // Check if there is a STALE_FEED alert or warning
            const isStale = health.stale_feed === true || (health.alerts && health.alerts.includes("STALE_FEED"));
            
            if (isStale) {
                badge.className = "health-badge stale";
                text.innerText = "System: Stale Feed Alert";
            } else {
                badge.className = "health-badge";
                text.innerText = "System: Live & Online";
            }
        }

        function updateMetrics(metrics) {
            if (!metrics) return;

            document.getElementById("kpiVisitors").innerText = metrics.unique_visitors != null ? metrics.unique_visitors : "0";
            
            const conversion = metrics.conversion_rate != null ? (metrics.conversion_rate * 100).toFixed(1) + "%" : "0.0%";
            document.getElementById("kpiConversion").innerText = conversion;

            document.getElementById("kpiQueueDepth").innerText = metrics.queue_depth != null ? metrics.queue_depth : "0";

            const abandonment = metrics.abandonment_rate != null ? (metrics.abandonment_rate * 100).toFixed(1) + "%" : "0.0%";
            document.getElementById("kpiAbandonment").innerText = abandonment;
        }

        function updateFunnel(funnelRes) {
            const container = document.getElementById("funnelContainer");
            const confidenceBadge = document.getElementById("funnelConfidence");

            if (!funnelRes || !funnelRes.funnel) {
                container.innerHTML = '<div class="error-message">Unable to load funnel data</div>';
                return;
            }

            // Set data confidence flag
            if (funnelRes.data_confidence === "LOW") {
                confidenceBadge.className = "confidence-indicator low";
                confidenceBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Low Data Confidence';
            } else {
                confidenceBadge.className = "confidence-indicator high";
                confidenceBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> High Data Confidence';
            }

            // Render stages
            let html = "";
            const stagesMap = {};
            funnelRes.funnel.forEach(item => {
                stagesMap[item.stage] = item;
            });

            const stageKeys = ["entry", "zone_visit", "billing_queue", "purchase"];
            const stageLabels = {
                "entry": { name: "1. Entrance", sub: "Unique Footfall Sessions" },
                "zone_visit": { name: "2. Zone Visit", sub: "Product Browsing Sessions" },
                "billing_queue": { name: "3. Billing Queue", sub: "Queue Entry Sessions" },
                "purchase": { name: "4. Purchase Completed", sub: "POS Correlated Conversions" }
            };

            stageKeys.forEach((key, index) => {
                const data = stagesMap[key] || { count: 0, pct: 0, drop_off_pct: 0 };
                const label = stageLabels[key];
                const count = data.count;
                const pct = data.pct.toFixed(0) + "%";
                const isPink = index % 2 !== 0;

                // Only show drop-off on stages after entry, if there actually is a drop-off
                let dropoffHtml = "";
                if (index > 0 && data.drop_off_pct > 0) {
                    const dropoffVal = data.drop_off_pct.toFixed(0);
                    dropoffHtml = `<span class="funnel-dropoff"><i class="fa-solid fa-arrow-down"></i> -${dropoffVal}% drop-off</span>`;
                }

                html += `
                <div class="funnel-stage">
                    <div class="funnel-label-col">
                        <span>${label.name}</span>
                        <span class="funnel-label-sub">${label.sub}</span>
                    </div>
                    <div class="funnel-bar-wrapper">
                        <div class="funnel-bar-fill ${isPink ? 'pink' : ''}" style="width: ${data.pct}%;"></div>
                        <span class="funnel-count">${count}</span>
                        <span class="funnel-percent">${pct}</span>
                    </div>
                    ${dropoffHtml}
                </div>`;
            });

            container.innerHTML = html;
        }

        function updateHeatmap(heatmap) {
            const grid = document.getElementById("heatmapGrid");
            if (!heatmap || !heatmap.zones) {
                grid.innerHTML = '<div class="error-message">Unable to load heatmap data</div>';
                return;
            }

            if (heatmap.zones.length === 0) {
                grid.innerHTML = '<div class="no-anomalies">No zone traffic recorded for this store.</div>';
                return;
            }

            let html = "";
            heatmap.zones.forEach(zone => {
                const score = Math.round(zone.normalised_score || 0);
                const dwellSeconds = Math.round((zone.avg_dwell_ms || 0) / 1000);
                const dwellStr = dwellSeconds >= 60 
                    ? `${Math.floor(dwellSeconds / 60)}m ${dwellSeconds % 60}s` 
                    : `${dwellSeconds}s`;

                html += `
                <div class="heatmap-cell">
                    <div class="heatmap-cell-title">${zone.zone_id.replace(/_/g, " ")}</div>
                    <div class="heatmap-cell-stats">
                        <span class="heatmap-cell-score">${score}</span>
                        <span class="heatmap-cell-score-max">/100</span>
                    </div>
                    <div class="heatmap-progress-bar">
                        <div class="heatmap-progress-fill" style="width: ${score}%;"></div>
                    </div>
                    <div class="heatmap-cell-dwell">
                        <i class="fa-regular fa-clock"></i>
                        Avg Dwell: ${dwellStr}
                    </div>
                </div>`;
            });

            grid.innerHTML = html;
        }

        function updateAnomalies(anomalies) {
            const container = document.getElementById("anomaliesFeed");
            if (!anomalies || !anomalies.anomalies || anomalies.anomalies.length === 0) {
                container.innerHTML = `
                <div class="no-anomalies">
                    <i class="fa-solid fa-circle-check" style="color: var(--success); font-size: 1.5rem; margin-bottom: 0.5rem; display: block;"></i>
                    All systems operating normally. No alerts.
                </div>`;
                return;
            }

            let html = "";
            anomalies.anomalies.forEach(anomaly => {
                const severity = (anomaly.severity || "info").toLowerCase();
                const icon = severity === "critical" 
                    ? "fa-circle-radiation" 
                    : severity === "warning" 
                        ? "fa-triangle-exclamation" 
                        : "fa-circle-info";

                html += `
                <div class="anomaly-item ${severity}">
                    <div class="anomaly-meta">
                        <span class="anomaly-type">${anomaly.anomaly_type.replace(/_/g, " ")}</span>
                        <span class="anomaly-severity-badge">${severity}</span>
                    </div>
                    <span class="anomaly-desc">${anomaly.description}</span>
                    ${anomaly.suggested_action ? `
                    <div class="anomaly-action">
                        <i class="fa-solid fa-lightbulb"></i>
                        <span><strong>Action:</strong> ${anomaly.suggested_action}</span>
                    </div>` : ''}
                </div>`;
            });

            container.innerHTML = html;
        }

        function simulateEventTicker(storeId) {
            const feedContainer = document.getElementById("eventFeed");
            
            // Build some mock real-time events relevant to the active store to show they are live,
            // mapping to event formats for visual excellence and matching live data feel.
            const zones = storeId === "STORE_2" 
                ? ["BILLING_AREA", "FLOOR_ZONE"]
                : ["SKINCARE", "MAKEUP", "BILLING_COUNTER"];
            
            const eventTypes = ["ENTRY", "ZONE_ENTER", "ZONE_DWELL", "BILLING_QUEUE_JOIN", "EXIT"];
            
            // Generate a random visitor ID
            const randVisitor = "VIS_" + Math.random().toString(36).substring(2, 8);
            const randType = eventTypes[Math.floor(Math.random() * eventTypes.length)];
            const randZone = randType !== "ENTRY" && randType !== "EXIT" 
                ? zones[Math.floor(Math.random() * zones.length)] 
                : null;

            let actionText = "";
            let badgeClass = "dwell";
            if (randType === "ENTRY") {
                actionText = "Entered the store entrance threshold";
                badgeClass = "entry";
            } else if (randType === "EXIT") {
                actionText = "Departed through the exit lane";
                badgeClass = "entry";
            } else if (randType === "ZONE_ENTER") {
                actionText = `Stepped into the ${randZone.toLowerCase()} section`;
            } else if (randType === "ZONE_DWELL") {
                actionText = `Spent 30s browsing ${randZone.toLowerCase()}`;
            } else if (randType === "BILLING_QUEUE_JOIN") {
                actionText = "Joined the billing queue line";
                badgeClass = "queue";
            }

            const now = new Date();
            const timeStr = now.toTimeString().split(" ")[0];

            const newEvent = {
                visitor_id: randVisitor,
                event_type: randType,
                action: actionText,
                zone: randZone,
                time: timeStr,
                badge: badgeClass
            };

            localEventsCache.unshift(newEvent);
            if (localEventsCache.length > 8) {
                localEventsCache.pop();
            }

            let html = "";
            localEventsCache.forEach(evt => {
                html += `
                <div class="event-item">
                    <div class="event-left">
                        <div class="event-type-icon">
                            <i class="fa-solid ${evt.event_type === 'ENTRY' || evt.event_type === 'EXIT' ? 'fa-door-open' : evt.event_type === 'BILLING_QUEUE_JOIN' ? 'fa-cash-register' : 'fa-magnifying-glass'}"></i>
                        </div>
                        <div class="event-details">
                            <span class="event-visitor">${evt.visitor_id}</span>
                            <span class="event-action">${evt.action}</span>
                        </div>
                    </div>
                    <div class="event-right">
                        <span class="event-time">${evt.time}</span>
                        <span class="event-badge ${evt.badge}">${evt.event_type.replace(/_/g, " ")}</span>
                    </div>
                </div>`;
            });

            feedContainer.innerHTML = html;
        }
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content, status_code=200)
