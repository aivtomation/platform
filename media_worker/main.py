#!/usr/bin/env python3
"""
Aivtomation Cloud Media Worker (Hugging Face Spaces Edition)
24/7 Failover Rendering Engine for Video Montage & Whisper STT

Runs autonomously inside Docker on Hugging Face Spaces (2 vCPU, 16 GB RAM),
listening for video processing tasks when the local PC worker is offline.
"""

import os
import sys
import time
import json
import threading
import collections
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Ensure modules in current directory can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.chdir(CURRENT_DIR)

# Configure Environment for Cloud Mode
os.environ["AIV_WORKER_TYPE"] = os.getenv("AIV_WORKER_TYPE", "cloud")
os.environ["AIV_HARDWARE_NAME"] = os.getenv("AIV_HARDWARE_NAME", "Hugging Face Spaces Cloud Worker (24/7)")

from local_worker import (
    process_single_job,
    process_stt_job,
    SERVER_URLS,
    SECRET_KEY,
    WORKER_TYPE,
    HARDWARE_NAME
)
import requests

START_TIME = time.time()
STATS = {
    "jobs_completed": 0,
    "last_job_id": None,
    "last_job_type": None,
    "last_job_time": None,
    "last_heartbeat": None,
    "status": "Starting..."
}

LOG_BUFFER = collections.deque(maxlen=100)

def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    LOG_BUFFER.append(formatted)
    print(formatted, flush=True)

app = FastAPI(title="Aivtomation Cloud Worker", version="2.0.0")

def cloud_worker_loop():
    """
    Continuous 24/7 background worker loop.
    Pings server with worker_type='cloud' every 8s.
    Polls for jobs with worker_type='cloud' every 3.5s.
    """
    log("🚀 [CLOUD WORKER DAEMON STARTING]")
    log(f"💻 Engine: {HARDWARE_NAME} (Type: {WORKER_TYPE})")
    log(f"🌐 Server endpoints: {SERVER_URLS}")

    last_ping_time = 0
    STATS["status"] = "Active & Listening (24/7)"

    while True:
        now = time.time()

        # 1. Heartbeat every 8 seconds
        if now - last_ping_time >= 8.0:
            for s_url in SERVER_URLS:
                try:
                    res = requests.post(
                        s_url,
                        params={"action": "ping", "secret": SECRET_KEY},
                        data={"hardware": HARDWARE_NAME, "worker_type": WORKER_TYPE},
                        timeout=5
                    )
                    if res.status_code == 200:
                        STATS["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
                except Exception:
                    pass
            last_ping_time = now

        # 2. Poll for queued jobs
        for s_url in SERVER_URLS:
            try:
                res = requests.get(
                    s_url,
                    params={"action": "poll", "secret": SECRET_KEY, "worker_type": WORKER_TYPE},
                    timeout=8
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("has_job") and data.get("job"):
                        job = data["job"]
                        job["_server_url"] = s_url
                        job_id = job.get("id", "unknown")
                        is_stt = (job.get("job_type") == "stt" or job.get("type") == "stt")
                        
                        log(f"⚡ [JOB RECEIVED] ID: {job_id} | Type: {'STT' if is_stt else 'Video Montage'}")
                        STATS["status"] = f"Rendering Job: {job_id}"

                        if is_stt:
                            process_stt_job(job)
                        else:
                            process_single_job(job)

                        STATS["jobs_completed"] += 1
                        STATS["last_job_id"] = job_id
                        STATS["last_job_type"] = "STT" if is_stt else "Montage"
                        STATS["last_job_time"] = datetime.now().strftime("%H:%M:%S")
                        STATS["status"] = "Active & Listening (24/7)"
                        log(f"✅ [JOB COMPLETED] Total processed: {STATS['jobs_completed']}")

            except requests.exceptions.ConnectionError:
                pass
            except Exception as e:
                log(f"⚠️ [POLL NOTICE]: {e}")

        time.sleep(3.5)

@app.on_event("startup")
def on_startup():
    worker_thread = threading.Thread(target=cloud_worker_loop, daemon=True)
    worker_thread.start()
    log("💓 Cloud Worker background thread initialized successfully.")

@app.get("/health")
def health():
    uptime = int(time.time() - START_TIME)
    return {
        "status": "ok",
        "service": "Aivtomation Cloud Media Worker",
        "worker_type": WORKER_TYPE,
        "hardware": HARDWARE_NAME,
        "uptime_sec": uptime,
        "jobs_completed": STATS["jobs_completed"],
        "last_heartbeat": STATS["last_heartbeat"]
    }

@app.get("/api/logs")
def get_logs():
    return {
        "logs": list(LOG_BUFFER),
        "stats": {
            **STATS,
            "uptime_sec": int(time.time() - START_TIME)
        }
    }

@app.get("/", response_class=HTMLResponse)
def dashboard():
    uptime_sec = int(time.time() - START_TIME)
    uptime_h = uptime_sec // 3600
    uptime_m = (uptime_sec % 3600) // 60
    uptime_s = uptime_sec % 60
    uptime_str = f"{uptime_h}h {uptime_m}m {uptime_s}s"

    logs_html = "".join([f"<div class='log-line'>{line}</div>" for line in LOG_BUFFER])

    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aivtomation 24/7 Cloud Media Worker</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #090d16;
            color: #f1f5f9;
            font-family: 'Inter', -apple-system, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 24px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            width: 100%;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 24px;
            border-bottom: 1px solid #1e293b;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .logo-wrap {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .logo-icon {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, #3b82f6, #6366f1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
        }}
        .title-h1 {{
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}
        .subtitle {{
            font-size: 13px;
            color: #94a3b8;
            margin-top: 2px;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 9999px;
            color: #34d399;
            font-size: 13px;
            font-weight: 600;
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.85); }}
        }}
        .grid-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 18px;
            transition: all 0.2s;
        }}
        .card:hover {{
            border-color: #334155;
            transform: translateY(-2px);
        }}
        .card-label {{
            font-size: 12px;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }}
        .card-value {{
            font-size: 22px;
            font-weight: 800;
            color: #f8fafc;
        }}
        .card-desc {{
            font-size: 12px;
            color: #94a3b8;
            margin-top: 4px;
        }}
        .features-box {{
            background: linear-gradient(180deg, #0f172a 0%, #090d16 100%);
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .features-title {{
            font-size: 14px;
            font-weight: 700;
            color: #cbd5e1;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .feature-chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .chip {{
            background: #1e293b;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            color: #e2e8f0;
            border: 1px solid #334155;
        }}
        .chip strong {{
            color: #60a5fa;
        }}
        .terminal-wrap {{
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .terminal-header {{
            background: #0f172a;
            padding: 10px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #1e293b;
        }}
        .terminal-title {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .terminal-dots {{
            display: flex;
            gap: 6px;
        }}
        .tdot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        .tdot-red {{ background: #ef4444; }}
        .tdot-yellow {{ background: #f59e0b; }}
        .tdot-green {{ background: #10b981; }}
        .terminal-body {{
            padding: 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            line-height: 1.6;
            max-height: 380px;
            overflow-y: auto;
            color: #cbd5e1;
        }}
        .log-line {{
            margin-bottom: 4px;
            word-break: break-all;
        }}
        .footer {{
            margin-top: auto;
            padding-top: 24px;
            font-size: 12px;
            color: #475569;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-wrap">
                <div class="logo-icon">🎬</div>
                <div>
                    <h1 class="title-h1">Aivtomation Cloud Media Worker</h1>
                    <p class="subtitle">24/7 Failover Engine • Hugging Face Spaces (2 vCPU, 16 GB RAM)</p>
                </div>
            </div>
            <div class="status-badge">
                <span class="pulse-dot"></span>
                <span>{STATS['status']}</span>
            </div>
        </div>

        <div class="grid-stats">
            <div class="card">
                <div class="card-label">Оброблено завдань</div>
                <div class="card-value" id="val-jobs">{STATS['jobs_completed']}</div>
                <div class="card-desc">Субтитри, JumpCut, Обкладинки, STT</div>
            </div>
            <div class="card">
                <div class="card-label">Час роботи (Uptime)</div>
                <div class="card-value" id="val-uptime">{uptime_str}</div>
                <div class="card-desc">24/7 безперервний хмарний стрім</div>
            </div>
            <div class="card">
                <div class="card-label">Останній пульс (Heartbeat)</div>
                <div class="card-value" id="val-hb" style="color: #38bdf8;">{STATS['last_heartbeat'] or 'Щойно'}</div>
                <div class="card-desc">Синхронізація з aivtomation.com</div>
            </div>
            <div class="card">
                <div class="card-label">Пріоритет роботи</div>
                <div class="card-value" style="font-size: 16px; color: #a78bfa; margin-top: 4px;">Failover Backup</div>
                <div class="card-desc">ПК пріоритет ➔ Хмара при вимкненому ПК</div>
            </div>
        </div>

        <div class="features-box">
            <div class="features-title">⚡ АКТИВНІ МОДУЛІ ОБРОБКИ МЕДІА</div>
            <div class="feature-chips">
                <span class="chip"><strong>.ass Караоке:</strong> Montserrat-Black, жовтий актив, плашка</span>
                <span class="chip"><strong>Hook Cover:</strong> Кастомні шрифти на 0.5с - 2с</span>
                <span class="chip"><strong>JumpCut:</strong> Автообрізка пауз і тиші (FFmpeg)</span>
                <span class="chip"><strong>Whisper STT:</strong> 16kHz аудіо-екстракт + word cues</span>
                <span class="chip"><strong>Rec.709:</strong> Tone-mapping для Apple HDR відео</span>
            </div>
        </div>

        <div class="terminal-wrap">
            <div class="terminal-header">
                <div class="terminal-title">
                    <span>Термінал активності воркера (Live Stream)</span>
                </div>
                <div class="terminal-dots">
                    <span class="tdot tdot-red"></span>
                    <span class="tdot tdot-yellow"></span>
                    <span class="tdot tdot-green"></span>
                </div>
            </div>
            <div class="terminal-body" id="log-box">
                {logs_html if logs_html else '<div class="log-line">Очікування завдань з черги aivtomation.com...</div>'}
            </div>
        </div>

        <div class="footer">
            Aivtomation Crossposting Studio &copy; 2026 • Powered by FFmpeg & OpenAI Whisper
        </div>
    </div>

    <script>
        async function refreshLogs() {{
            try {{
                const res = await fetch('/api/logs');
                if (res.ok) {{
                    const data = await res.json();
                    const box = document.getElementById('log-box');
                    if (data.logs && data.logs.length) {{
                        box.innerHTML = data.logs.map(l => `<div class='log-line'>${{l}}</div>`).join('');
                        box.scrollTop = box.scrollHeight;
                    }}
                    if (data.stats) {{
                        document.getElementById('val-jobs').innerText = data.stats.jobs_completed;
                        if (data.stats.last_heartbeat) {{
                            document.getElementById('val-hb').innerText = data.stats.last_heartbeat;
                        }}
                    }}
                }}
            }} catch (e) {{}}
        }}
        setInterval(refreshLogs, 3000);
    </script>
</body>
</html>"""
    return html

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
