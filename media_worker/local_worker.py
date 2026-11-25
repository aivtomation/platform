#!/usr/bin/env python3
"""
Aivtomation High-Performance Media Processing Worker
Multi-threaded media rendering engine

Autonomously polls https://aivtomation.com for video montage tasks,
renders silence cuts, stylish yellow subtitles (20% below center), and 0.5s cover intros,
then uploads the completed hardcoded MP4 back to the server.
"""

import os
import sys
import time
import json

# Ensure user site-packages are visible when launched under Windows SYSTEM / Task Scheduler
_USER_SITE = r"C:\Users\alexe\AppData\Roaming\Python\Python310\site-packages"
if os.path.isdir(_USER_SITE) and _USER_SITE not in sys.path:
    sys.path.append(_USER_SITE)

import requests
import tempfile
import shutil
import subprocess
import io
import threading
import socket
from concurrent.futures import ThreadPoolExecutor

# Ensure modules in current directory can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.chdir(CURRENT_DIR)


LOG_FILE = os.path.join(CURRENT_DIR, "worker.log")

# Rotate worker.log if > 10 MB (keep up to 5 archives)
try:
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 10 * 1024 * 1024:
        for idx in range(4, 0, -1):
            src = f"{LOG_FILE}.{idx}"
            dst = f"{LOG_FILE}.{idx + 1}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.replace(src, dst)
        if os.path.exists(f"{LOG_FILE}.1"):
            os.remove(f"{LOG_FILE}.1")
        os.replace(LOG_FILE, f"{LOG_FILE}.1")
except Exception:
    pass

class FlushingStream:
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]
    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass

try:
    log_file_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    if sys.stdout is not None:
        try:
            sys.stdout = FlushingStream(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"), log_file_handle)
        except Exception:
            sys.stdout = FlushingStream(sys.stdout, log_file_handle)
    else:
        sys.stdout = log_file_handle

    if sys.stderr is not None:
        try:
            sys.stderr = FlushingStream(io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"), log_file_handle)
        except Exception:
            sys.stderr = FlushingStream(sys.stderr, log_file_handle)
    else:
        sys.stderr = log_file_handle
except Exception:
    pass

def send_telegram_alert(text: str):
    bot_token = os.getenv("LOG_PROBLEMS_BOT_TOKEN", "8915027231:AAGRPrSEYXCCfJwVpwQg_o78CrFoVNJChGA")
    chat_id = os.getenv("LOG_PROBLEMS_CHAT_ID", "425927724")
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

from modules.subtitle_burner import burn_subtitles_into_video
from modules.cover_generator import generate_and_apply_cover
from modules.silence_remover import remove_silence_from_video
from job_registry import get_job_spec, CLASS_SLOTS_NORMAL, CLASS_SLOTS_CREATOR
try:
    from modules.telemetry import collect_hardware_telemetry
    from modules.creator_mode import evaluate_node_mode, apply_process_priority, update_sleep_prevention
except Exception:
    collect_hardware_telemetry = None
    evaluate_node_mode = None
    apply_process_priority = None
    update_sleep_prevention = None

# Server endpoints
DEFAULT_URLS = [
    "https://aivtomation.com/crossposting/app/media_worker_api.php",
    "https://aivtomation.com/production/worker_api.php"
]
custom_url = os.getenv("AIV_SERVER_URL")
if custom_url:
    SERVER_URLS = [custom_url]
else:
    SERVER_URLS = DEFAULT_URLS
SECRET_KEY = os.getenv("AIV_SECRET_KEY", "run_cron_123")
POLL_INTERVAL = 2.0 # seconds
HARDWARE_NAME = os.getenv("AIV_HARDWARE_NAME", "High-Performance Media Engine (Ryzen 9 / PC)")
WORKER_TYPE = os.getenv("AIV_WORKER_TYPE", "local")
WORKER_INSTANCE_ID = f"{socket.gethostname()}_{os.getpid()}"
WORK_TEMP_DIR = os.path.join(CURRENT_DIR, "temp_jobs")
os.makedirs(WORK_TEMP_DIR, exist_ok=True)

MAX_CONCURRENT_JOBS = 5
CLASS_SEMAPHORES = {
    "gpu_heavy": threading.Semaphore(CLASS_SLOTS_NORMAL["gpu_heavy"]),
    "cpu_heavy": threading.Semaphore(CLASS_SLOTS_NORMAL["cpu_heavy"]),
    "gpu_light": threading.Semaphore(CLASS_SLOTS_NORMAL["gpu_light"]),
    "io_light": threading.Semaphore(CLASS_SLOTS_NORMAL["io_light"]),
}
ACTIVE_JOBS_LOCK = threading.Lock()
ACTIVE_JOBS_META = {}  # job_id -> {id, type, class, started_at}
ACTIVE_JOB_IDS = set()

NODE_STATE_LOCK = threading.Lock()
NODE_STATE = {
    "mode": "normal",
    "manual_override": "auto",
    "ffmpeg_threads": 12,
    "thermal_throttle": False,
    "creator_apps": [],
    "telemetry": {},
}

def _get_ffmpeg_threads() -> int:
    with NODE_STATE_LOCK:
        return int(NODE_STATE.get("ffmpeg_threads", 12))

def _get_slots_free() -> dict:
    with ACTIVE_JOBS_LOCK:
        used = {"gpu_heavy": 0, "cpu_heavy": 0, "gpu_light": 0, "io_light": 0}
        for meta in ACTIVE_JOBS_META.values():
            cls = meta.get("class", "gpu_heavy")
            if cls in used:
                used[cls] += 1
    with NODE_STATE_LOCK:
        mode = NODE_STATE.get("mode", "normal")
    budget = CLASS_SLOTS_CREATOR if mode == "creator" else CLASS_SLOTS_NORMAL
    return {k: max(0, budget[k] - used[k]) for k in budget}

def print_banner():
    print("=" * 70)
    print("🚀 [AIVTOMATION MEDIA PROCESSING ENGINE ONLINE]")
    print(f"💻 Система: {HARDWARE_NAME} (Тип: {WORKER_TYPE} | ID: {WORKER_INSTANCE_ID})")
    print(f"🌐 Сервери завдань: {SERVER_URLS}")
    print(f"⚡ Режим: Ресурсні слоти + Creator Mode + Телеметрія (до {MAX_CONCURRENT_JOBS} паралельних задач)")
    print("=" * 70)

def send_heartbeat():
    if WORKER_TYPE != "local" or collect_hardware_telemetry is None:
        for url in SERVER_URLS:
            try:
                requests.post(
                    url,
                    params={"action": "ping", "secret": SECRET_KEY},
                    data={
                        "hardware": HARDWARE_NAME,
                        "worker_type": WORKER_TYPE,
                        "worker_instance_id": WORKER_INSTANCE_ID,
                    },
                    timeout=5
                )
            except Exception:
                pass
        return

    tel = collect_hardware_telemetry(CURRENT_DIR)
    with ACTIVE_JOBS_LOCK:
        active_list = [
            {
                "id": jid,
                "type": m["type"],
                "class": m["class"],
                "elapsed": round(time.time() - m["started_at"], 1),
            }
            for jid, m in ACTIVE_JOBS_META.items()
        ]
        heavy_count = sum(1 for m in ACTIVE_JOBS_META.values() if m["class"] in ("gpu_heavy", "cpu_heavy"))

    with NODE_STATE_LOCK:
        cur_override = NODE_STATE.get("manual_override", "auto")

    eval_res = evaluate_node_mode(tel, heavy_count, cur_override)
    apply_process_priority(eval_res["mode"] == "creator")
    update_sleep_prevention(len(active_list) > 0)

    with NODE_STATE_LOCK:
        NODE_STATE["mode"] = eval_res["mode"]
        NODE_STATE["ffmpeg_threads"] = eval_res["ffmpeg_threads"]
        NODE_STATE["thermal_throttle"] = eval_res["thermal_throttle"]
        NODE_STATE["creator_apps"] = eval_res["creator_apps"]
        NODE_STATE["telemetry"] = tel

    slots_free = _get_slots_free()
    report_payload = {
        "node_id": socket.gethostname(),
        "display_name": f"{socket.gethostname()} (Ryzen 9 5900X + RTX 3080)",
        "worker_type": WORKER_TYPE,
        "worker_instance_id": WORKER_INSTANCE_ID,
        "hardware": HARDWARE_NAME,
        "mode": eval_res["mode"],
        "thermal_throttle": eval_res["thermal_throttle"],
        "creator_apps": eval_res["creator_apps"],
        "ffmpeg_threads": eval_res["ffmpeg_threads"],
        "capabilities": ["ffmpeg", "nvenc", "cuda_whisper", "yt_dlp"],
        "telemetry": tel,
        "active_jobs": active_list,
        "slots_free": slots_free,
    }

    for idx, url in enumerate(SERVER_URLS):
        try:
            if idx == 0:
                res = requests.post(
                    url,
                    params={"action": "node_report", "secret": SECRET_KEY},
                    json=report_payload,
                    timeout=6,
                )
                if res.status_code == 200:
                    rjson = res.json()
                    srv_override = rjson.get("manual_override")
                    if srv_override in ("auto", "light_only", "paused"):
                        with NODE_STATE_LOCK:
                            NODE_STATE["manual_override"] = srv_override
            else:
                requests.post(
                    url,
                    params={"action": "ping", "secret": SECRET_KEY},
                    data={
                        "hardware": HARDWARE_NAME,
                        "worker_type": WORKER_TYPE,
                        "worker_instance_id": WORKER_INSTANCE_ID,
                    },
                    timeout=5,
                )
        except Exception:
            pass

def heartbeat_daemon_loop():
    """
    Continuous background heartbeat + hardware telemetry thread (every 10s).
    Guarantees the worker status is ALWAYS ONLINE even during heavy renders!
    """
    while True:
        send_heartbeat()
        time.sleep(10)

def download_video(url: str, dest_path: str):
    print(f"  📥 Завантаження вихідного відео: {url}...")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        # Cross-environment fallback between stage2 and prod
        alt_url = None
        if "crossposting-stage2" in url:
            alt_url = url.replace("crossposting-stage2", "crossposting")
        elif "/crossposting/" in url:
            alt_url = url.replace("/crossposting/", "/crossposting-stage2/")

        if alt_url:
            print(f"  🔄 Спроба завантаження з альтернативного URL: {alt_url}...")
            with requests.get(alt_url, stream=True, timeout=120) as r2:
                r2.raise_for_status()
                with open(dest_path, "wb") as f2:
                    for chunk in r2.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f2.write(chunk)
        else:
            raise e

    size_bytes = os.path.getsize(dest_path)
    if size_bytes < 1024:
        raise RuntimeError(f"Завантажений файл пошкоджений або порожній ({size_bytes} Б)")
    with open(dest_path, "rb") as chk_f:
        head = chk_f.read(64).lstrip().lower()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            raise RuntimeError("Завантажено HTML-сторінку замість медіафайлу (404/помилка сервера)")
    size_mb = size_bytes / (1024 * 1024)
    print(f"  ✅ Відео завантажено ({size_mb:.2f} МБ)")

def upload_processed_video(job_id: str, video_path: str, server_url: str = None):
    target = server_url or SERVER_URLS[0]
    print(f"  📤 Відправка готового змонтованого MP4 на {target}...")
    with open(video_path, "rb") as vf:
        files = {"video": (os.path.basename(video_path), vf, "video/mp4")}
        data = {"job_id": job_id}
        res = requests.post(
            target,
            params={"action": "complete_job", "secret": SECRET_KEY},
            data=data,
            files=files,
            timeout=180
        )
        res.raise_for_status()
        res_json = res.json()
        if res_json.get("success"):
            print(f"  🎉 Відео успішно розміщено на сервері: {res_json.get('video_url')}")
            return res_json.get("video_url")
        else:
            raise Exception(res_json.get("message", "Upload error"))

def report_failure(job_id: str, err: str, server_url: str = None):
    target = server_url or SERVER_URLS[0]
    try:
        requests.post(
            target,
            params={"action": "fail_job", "secret": SECRET_KEY},
            data={"job_id": job_id, "error": err},
            timeout=10
        )
    except Exception:
        pass

def report_job_progress(job_id: str, progress: int, stage_msg: str = "", est_remain: int = None, server_url: str = None):
    target = server_url or SERVER_URLS[0]
    try:
        data = {
            "job_id": job_id,
            "progress": max(0, min(100, progress)),
            "stage_msg": stage_msg,
            "est_remain": est_remain if est_remain is not None else ""
        }
        requests.post(
            target,
            params={"action": "update_progress", "secret": SECRET_KEY},
            data=data,
            timeout=5
        )
    except Exception:
        pass

def get_video_duration(video_path: str) -> float:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, timeout=5)
        return float(res.stdout.strip())
    except Exception:
        return 60.0

class JobProgressTicker:
    """
    Background worker thread that pushes smooth progress % and remaining countdown
    to the web server every 1.5 seconds during heavy multi-minute encodes.
    """
    def __init__(self, job_id: str, total_video_duration: float, active_steps: list, server_url: str = None):
        self.job_id = job_id
        self.server_url = server_url
        self.total_dur = max(5.0, total_video_duration)
        self.active_steps = active_steps
        self.current_step = None
        self.stage_msg = ""
        self.start_pct = 10
        self.end_pct = 90
        self.step_start_time = time.time()
        self.job_start_time = time.time()
        self.stop_event = threading.Event()
        
        # Multi-threaded high-performance CPU encodes 1080x1920 at ~3.5x realtime speed
        num_heavy = (1 if 'subs' in active_steps else 0) + (1 if 'jumpcut' in active_steps else 0)
        self.est_total_sec = max(8.0, (self.total_dur / 3.5) * max(1, num_heavy) + (3.0 if 'cover' in active_steps else 0.0) + 6.0)
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def set_step(self, step_name: str, stage_msg: str, start_pct: int, end_pct: int):
        self.current_step = step_name
        self.stage_msg = stage_msg
        self.start_pct = start_pct
        self.end_pct = end_pct
        self.step_start_time = time.time()
        remain = self._est_remain()
        report_job_progress(self.job_id, start_pct, stage_msg, remain, server_url=self.server_url)

    def _est_remain(self) -> int:
        elapsed = time.time() - self.job_start_time
        return max(1, int(self.est_total_sec - elapsed))

    def _run(self):
        while not self.stop_event.is_set():
            time.sleep(1.5)
            if self.stop_event.is_set() or not self.current_step:
                break
            step_elapsed = time.time() - self.step_start_time
            est_step_dur = max(4.0, (self.total_dur / 3.2))
            frac = min(0.92, step_elapsed / est_step_dur)
            pct = int(self.start_pct + frac * (self.end_pct - self.start_pct))
            remain = self._est_remain()
            report_job_progress(self.job_id, pct, self.stage_msg, remain, server_url=self.server_url)

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

def process_stt_job(job: dict):
    job_id = job.get("id")
    server_url = job.get("_server_url", SERVER_URLS[0])
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return
    language = job.get("language", "uk")

    print("\n" + "=" * 60)
    print(f"🎙️ [НОВЕ ЗАВДАННЯ STT] Job ID: {job_id}")
    print(f"🔗 Джерело: {source_url}")
    start_time = time.time()

    job_dir = os.path.join(WORK_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    out_mp3 = os.path.join(job_dir, "extracted_audio.mp3")

    try:
        report_job_progress(job_id, progress=20, stage_msg="Конвертація відео у 16kHz MP3 через FFmpeg...", server_url=server_url)

        # Step 1: Extract 16kHz mono MP3 directly via FFmpeg
        t_conv0 = time.time()
        cmd = [
            "ffmpeg", "-y",
            "-i", source_url,
            "-vn",
            "-acodec", "libmp3lame",
            "-ar", "16000",
            "-ac", "1",
            "-b:a", "64k",
            out_mp3
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0 or not os.path.exists(out_mp3) or os.path.getsize(out_mp3) < 100:
            url_clean = source_url.split("?")[0]
            ext = os.path.splitext(url_clean)[1].lower() or ".mp4"
            temp_input = os.path.join(job_dir, f"input_media{ext}")
            download_video(source_url, temp_input)
            cmd_local = [
                "ffmpeg", "-y",
                "-i", temp_input,
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "16000",
                "-ac", "1",
                "-b:a", "64k",
                out_mp3
            ]
            sub_res = subprocess.run(cmd_local, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if sub_res.returncode != 0:
                err_text = sub_res.stderr.decode("utf-8", errors="ignore").strip()
                raise RuntimeError(f"FFmpeg conversion failed (code {sub_res.returncode}): {err_text[-300:]}")
            if os.path.exists(temp_input):
                try:
                    os.remove(temp_input)
                except Exception:
                    pass

        mp3_size_kb = round(os.path.getsize(out_mp3) / 1024, 1)
        t_conv = round(time.time() - t_conv0, 2)
        print(f"  ⚡ MP3 вилучено успішно за {t_conv}с (розмір: {mp3_size_kb} КБ)")

        report_job_progress(job_id, progress=45, stage_msg="ШІ-розпізнавання мови (пріоритет: локальна модель Whisper)...", server_url=server_url)

        # Step 2: Transcribe via Hybrid STT (Priority 1: Local Whisper model, Priority 2: OpenAI Cloud API)
        t_stt0 = time.time()
        from modules.stt import transcribe_audio_hybrid
        stt_result = transcribe_audio_hybrid(out_mp3, language=language)
        t_stt = round(time.time() - t_stt0, 2)
        engine_name = stt_result.get("engine", "whisper")
        print(f"  🤖 Whisper розпізнавання [{engine_name}] завершено за {t_stt}с!")

        full_text = stt_result.get("text", "")
        cues = stt_result.get("cues", [])
        srt_content = stt_result.get("srt", "")

        report_job_progress(job_id, progress=100, stage_msg="Субтитри успішно згенеровано!", server_url=server_url)
        requests.post(
            server_url,
            params={"action": "complete_stt_job", "secret": SECRET_KEY},
            json={
                "job_id": job_id,
                "cues": cues,
                "text": full_text,
                "srt": srt_content
            },
            timeout=10
        )
        total_time = round(time.time() - start_time, 2)
        print(f"✅ [STT УСПІШНО ЗА {total_time} СЕК] Отримано {len(cues)} сегментів субтитрів!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ [ПОМИЛКА STT]: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_stt_job", "secret": SECRET_KEY},
                json={"job_id": job_id, "error": str(e)},
                timeout=5
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

def compress_video_for_telegram(input_path: str, output_path: str, target_max_mb: float = 43.5) -> str:
    """
    Compresses video to <= target_max_mb (default 43.5 MB for Telegram Bot API <= 50MB ceiling).
    Calculates target bitrate dynamically based on duration, selects optimal resolution,
    and uses fast multi-threaded H.264 encoding with Web-optimized moov atom.
    """
    duration = max(1.0, get_video_duration(input_path))
    target_bytes = target_max_mb * 1024 * 1024
    total_bitrate = (target_bytes * 8) / duration

    # Allocate audio bitrate: 96k for videos > 10 min, 128k for standard length
    audio_kbps = 96 if duration > 600 else 128
    audio_bps = audio_kbps * 1000

    # Calculate video bitrate (floor at 280k, ceiling at 6000k)
    video_bps = max(280 * 1000, int(total_bitrate - audio_bps))
    video_kbps = min(6000, int(video_bps / 1000))

    # Adaptive resolution scaling based on available bitrate:
    # >= 2200 kbps: 1080p
    # 1000 - 2199 kbps: 720p
    # < 1000 kbps: 540p
    if video_kbps >= 2200:
        scale_filter = "scale='min(1080,iw)':-2"
    elif video_kbps >= 1000:
        scale_filter = "scale='min(720,iw)':-2"
    else:
        scale_filter = "scale='min(540,iw)':-2"

    vf = f"{scale_filter},format=yuv420p"
    maxrate_kbps = int(video_kbps * 1.15)
    bufsize_kbps = int(video_kbps * 2.0)

    cmd = [
        "ffmpeg", "-y",
        "-threads", str(_get_ffmpeg_threads()),
        "-i", os.path.abspath(input_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-b:v", f"{video_kbps}k",
        "-maxrate", f"{maxrate_kbps}k",
        "-bufsize", f"{bufsize_kbps}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",
        os.path.abspath(output_path)
    ]

    print(f"  🎬 FFmpeg компресія Telegram: {video_kbps}k v-bitrate, {audio_kbps}k audio, {scale_filter}...")
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # Verify output file size <= 44.8 MB
    if os.path.exists(output_path):
        out_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  📊 Розмір після першого проходу: {out_size_mb:.2f} МБ")
        if out_size_mb > 44.8:
            print("  ⚠️ Розмір перевищує ліміт! Запуск другого проходу зі зниженим бітрейтом...")
            video_kbps_pass2 = int(video_kbps * 0.82)
            cmd_p2 = [
                "ffmpeg", "-y",
                "-i", os.path.abspath(input_path),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-b:v", f"{video_kbps_pass2}k",
                "-maxrate", f"{int(video_kbps_pass2 * 1.15)}k",
                "-bufsize", f"{int(video_kbps_pass2 * 2.0)}k",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", f"{audio_kbps}k",
                "-movflags", "+faststart",
                os.path.abspath(output_path)
            ]
            subprocess.run(cmd_p2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            out_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  📊 Фінальний розмір після коригування: {out_size_mb:.2f} МБ")

    return output_path

def process_compress_telegram_job(job: dict):
    job_id = job.get("id")
    parent_job_id = job.get("parent_job_id", "")
    server_url = job.get("_server_url", SERVER_URLS[0])
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return
    target_max_mb = float(job.get("target_max_mb") or 43.5)

    print("\n" + "=" * 60)
    print(f"📦 [НОВЕ ЗАВДАННЯ ОПТИМІЗАЦІЇ ДЛЯ TELEGRAM] Job ID: {job_id}")
    if parent_job_id:
        print(f"🔗 Батьківський пост: {parent_job_id}")
    print(f"🎯 Цільовий ліміт розміру: <= {target_max_mb} МБ")
    print(f"🌐 Джерело: {source_url}")
    start_time = time.time()

    job_dir = os.path.join(WORK_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    raw_video = os.path.join(job_dir, "input.mp4")
    out_video = os.path.join(job_dir, "telegram_compressed.mp4")

    try:
        report_job_progress(job_id, progress=15, stage_msg="Завантаження відео для оптимізації під Telegram...", server_url=server_url)

        # Step 1: Download raw video
        download_video(source_url, raw_video)
        raw_size_mb = os.path.getsize(raw_video) / (1024 * 1024)
        total_duration = get_video_duration(raw_video)
        print(f"  ⏱️ Тривалість: {total_duration:.1f} сек, розмір: {raw_size_mb:.2f} МБ")

        # If already <= 44.5 MB, no compression needed!
        if raw_size_mb <= 44.5:
            print("  ✅ Відео вже менше 44.5 МБ. Перекодування не потрібне!")
            report_job_progress(job_id, progress=90, stage_msg="Відео вже відповідає умовам Telegram...", server_url=server_url)
            shutil.copy2(raw_video, out_video)
        else:
            report_job_progress(job_id, progress=35, stage_msg="Швидке стиснення до 43.5 МБ на ПК воркері...", server_url=server_url)
            compress_video_for_telegram(raw_video, out_video, target_max_mb=target_max_mb)

        final_size_mb = os.path.getsize(out_video) / (1024 * 1024)
        report_job_progress(job_id, progress=85, stage_msg=f"Стиснуто до {final_size_mb:.2f} МБ. Відправка на сервер...", server_url=server_url)

        # Upload compressed MP4 to server
        target_endpoint = server_url or SERVER_URLS[0]
        with open(out_video, "rb") as vf:
            files = {"video": ("telegram_compressed.mp4", vf, "video/mp4")}
            data = {
                "job_id": job_id,
                "parent_job_id": parent_job_id,
                "job_type": "compress_telegram",
                "final_size_mb": round(final_size_mb, 2)
            }
            res = requests.post(
                target_endpoint,
                params={"action": "complete_compress_job", "secret": SECRET_KEY},
                data=data,
                files=files,
                timeout=180
            )
            res.raise_for_status()
            res_json = res.json()
            if not res_json.get("success"):
                raise Exception(res_json.get("message", "Upload error"))

        report_job_progress(job_id, progress=100, stage_msg=f"Готово! Відео оптимізовано для Telegram ({final_size_mb:.2f} МБ)", est_remain=0, server_url=server_url)
        duration = round(time.time() - start_time, 2)
        print(f"🎉 [TELEGRAM ОПТИМІЗАЦІЮ ЗАВЕРШЕНО ЗА {duration} СЕК] Розмір: {final_size_mb:.2f} МБ (Було: {raw_size_mb:.2f} МБ)")
        print("=" * 60)

    except Exception as e:
        print(f"❌ [ПОМИЛКА ОПТИМІЗАЦІЇ TELEGRAM]: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": str(e)},
                timeout=5
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

def process_trim_threads_job(job: dict):
    job_id = job.get("id")
    parent_job_id = job.get("parent_job_id", "")
    server_url = job.get("_server_url", SERVER_URLS[0])
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return
    max_duration_sec = float(job.get("max_duration_sec") or 300.0)

    print("\n" + "=" * 60)
    print(f"✂️ [НОВЕ ЗАВДАННЯ ОБРІЗКИ ДЛЯ THREADS] Job ID: {job_id}")
    if parent_job_id:
        print(f"🔗 Батьківський пост: {parent_job_id}")
    print(f"🎯 Цільова тривалість: <= {max_duration_sec} сек (5 хв)")
    print(f"🌐 Джерело: {source_url}")
    start_time = time.time()

    job_dir = os.path.join(WORK_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    raw_video = os.path.join(job_dir, "input.mp4")
    out_video = os.path.join(job_dir, "threads_trimmed.mp4")

    try:
        report_job_progress(job_id, progress=15, stage_msg="Завантаження відео для обрізки під Threads...", server_url=server_url)

        # Step 1: Download raw video
        download_video(source_url, raw_video)
        raw_size_mb = os.path.getsize(raw_video) / (1024 * 1024)
        total_duration = get_video_duration(raw_video)
        print(f"  ⏱️ Вихідна тривалість: {total_duration:.1f} сек, розмір: {raw_size_mb:.2f} МБ")

        if total_duration <= max_duration_sec:
            print(f"  ✅ Відео вже <= {max_duration_sec} сек ({total_duration:.1f}с). Обрізка не потрібна!")
            report_job_progress(job_id, progress=90, stage_msg="Відео вже відповідає ліміту Threads (≤5хв)...", server_url=server_url)
            shutil.copy2(raw_video, out_video)
        else:
            report_job_progress(job_id, progress=40, stage_msg=f"Авто-обрізка перших 5 хв ({max_duration_sec:.0f}с) для Threads...", server_url=server_url)
            safe_trim_sec = int(max_duration_sec) - 1 if max_duration_sec >= 300 else int(max_duration_sec)
            # Fast stream copy trim (instant <1s execution without re-encoding)
            trim_cmd = [
                "ffmpeg", "-y",
                "-ss", "00:00:00",
                "-i", raw_video,
                "-t", str(safe_trim_sec),
                "-c", "copy",
                "-movflags", "+faststart",
                out_video
            ]
            res = subprocess.run(trim_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 or not os.path.exists(out_video) or os.path.getsize(out_video) == 0:
                print("  ⚠️ Stream copy trim failed, performing fast ultrafast re-encode...")
                trim_cmd_reencode = [
                    "ffmpeg", "-y",
                    "-ss", "00:00:00",
                    "-i", raw_video,
                    "-t", str(safe_trim_sec),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    out_video
                ]
                subprocess.run(trim_cmd_reencode, check=True)

        final_size_mb = os.path.getsize(out_video) / (1024 * 1024)
        final_dur = get_video_duration(out_video)
        report_job_progress(job_id, progress=85, stage_msg=f"Обрізано до {final_dur:.1f}с ({final_size_mb:.2f} МБ). Відправка...", server_url=server_url)

        # Upload trimmed MP4 to server
        target_endpoint = server_url or SERVER_URLS[0]
        with open(out_video, "rb") as vf:
            files = {"video": ("threads_trimmed.mp4", vf, "video/mp4")}
            data = {
                "job_id": job_id,
                "parent_job_id": parent_job_id,
                "job_type": "trim_threads",
                "final_size_mb": round(final_size_mb, 2)
            }
            res = requests.post(
                target_endpoint,
                params={"action": "complete_compress_job", "secret": SECRET_KEY},
                data=data,
                files=files,
                timeout=180
            )
            res.raise_for_status()
            res_json = res.json()
            if not res_json.get("success"):
                raise Exception(res_json.get("message", "Upload error"))

        report_job_progress(job_id, progress=100, stage_msg=f"Готово! Відео обрізано до 5 хв для Threads ({final_size_mb:.2f} МБ)", est_remain=0, server_url=server_url)
        duration = round(time.time() - start_time, 2)
        print(f"🎉 [THREADS ОБРІЗКУ ЗАВЕРШЕНО ЗА {duration} СЕК] Тривалість: {final_dur:.1f}с, Розмір: {final_size_mb:.2f} МБ (Було: {raw_size_mb:.2f} МБ)")
        print("=" * 60)

    except Exception as e:
        print(f"❌ [ПОМИЛКА ОБРІЗКИ THREADS]: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": str(e)},
                timeout=5
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

def _format_ytdlp_error(err_text: str) -> str:
    low = (err_text or "").lower()
    if (
        "instagram api is not granting access" in low
        or "empty media response" in low
        or "this content isn't available to everyone" in low
        or "can't be seen by certain audiences" in low
        or "login required" in low
    ):
        return "Instagram обмежив доступ до цього поста без входу в акаунт Instagram (приватний, віковий або видалений пост — не пов'язано з вашим входом у Telegram/Aivtomation)."
    if "private video" in low or "sign in to confirm" in low:
        return "Відео позначено автором як приватне або з віковим обмеженням."
    if "video unavailable" in low:
        return "Відео недоступне або видалене автором."
    return "Не вдалося завантажити жодного медіапотоку (відео або аудіо)"


def _pick_cdn_streams(entry: dict, max_quality: int = 1080) -> tuple:
    fmts = entry.get("formats") or []
    prog_videos = []
    any_mp4_videos = []
    audio_streams = []
    for f in fmts:
        if not isinstance(f, dict):
            continue
        f_url = f.get("url") or ""
        if not f_url.startswith("http"):
            continue
        ext = (f.get("ext") or "").lower()
        vc = f.get("vcodec")
        ac = f.get("acodec")
        height = int(f.get("height") or 0)
        if ext == "mp4" and vc not in (None, "none"):
            if ac not in (None, "none"):
                if height <= max_quality or height == 0:
                    prog_videos.append(f)
            any_mp4_videos.append(f)
        elif vc == "none" and ac not in (None, "none"):
            audio_streams.append(f)

    video_url = ""
    if prog_videos:
        prog_videos.sort(key=lambda x: (int(x.get("height") or 0), float(x.get("tbr") or 0)))
        video_url = prog_videos[-1].get("url") or ""
    elif any_mp4_videos:
        # Instagram GraphQL / some extractors omit acodec or only list mp4 video streams
        capped = [v for v in any_mp4_videos if int(v.get("height") or 0) <= max_quality]
        pool = capped if capped else any_mp4_videos
        pool.sort(key=lambda x: (int(x.get("height") or 0), float(x.get("tbr") or 0)))
        video_url = pool[-1].get("url") or ""
    elif str(entry.get("url") or "").startswith("http"):
        ent_ext = (entry.get("ext") or "").lower()
        if ent_ext in ("mp4", ""):
            video_url = str(entry.get("url"))

    audio_url = ""
    if audio_streams:
        audio_streams.sort(
            key=lambda x: (
                1 if (x.get("ext") or "").lower() in ("m4a", "mp3", "aac") else 0,
                float(x.get("abr") or x.get("tbr") or 0),
            )
        )
        audio_url = audio_streams[-1].get("url") or ""

    thumb = entry.get("thumbnail") or ""
    if not thumb and isinstance(entry.get("thumbnails"), list) and entry["thumbnails"]:
        for t in reversed(entry["thumbnails"]):
            if isinstance(t, dict) and str(t.get("url") or "").startswith("http"):
                thumb = str(t["url"])
                break

    return video_url, audio_url, thumb


def process_social_download_job(job: dict):
    job_id = job.get("id")
    target_url = job.get("url")
    server_url = job.get("_server_url", SERVER_URLS[0])
    max_quality = int(job.get("max_quality", 1080))
    platform = job.get("platform", "social")
    mode = str(job.get("mode", "both")).lower()
    want_video = mode in ("video", "both")
    want_audio = mode in ("audio", "both")

    print("\n" + "=" * 60)
    print(f"📥 [НОВЕ ЗАВДАННЯ СКАЧУВАННЯ МЕДІА] Job ID: {job_id} | Mode: {mode}")
    print(f"🌐 Джерело ({platform}): {target_url}")
    print(f"🎯 Максимальна роздільна здатність: {max_quality}p")
    start_time = time.time()

    job_dir = os.path.join(WORK_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    video_out = os.path.join(job_dir, f"{job_id}_video.mp4")
    audio_out = os.path.join(job_dir, f"{job_id}_audio.mp3")

    try:
        report_job_progress(job_id, progress=15, stage_msg="Аналіз медіа-потоків та витягування (yt-dlp)...", server_url=server_url)

        # Check for optional cookies.txt in worker directory (useful for restricted Instagram / YouTube)
        cookie_file = None
        for candidate in ["cookies.txt", "instagram_cookies.txt", "youtube_cookies.txt"]:
            c_path = os.path.join(CURRENT_DIR, candidate)
            if os.path.exists(c_path) and os.path.getsize(c_path) > 10:
                cookie_file = c_path
                break

        # Fast zero-clutter CDN resolution mode (0 MB downloaded/uploaded to Aivtomation)
        if mode == "resolve_cdn":
            cmd_meta = [
                sys.executable, "-m", "yt_dlp",
                "--no-warnings",
                "--skip-download",
                "-J",
            ]
            if cookie_file:
                cmd_meta.extend(["--cookies", cookie_file])
            cmd_meta.append(target_url)

            report_job_progress(job_id, progress=45, stage_msg="Отримання прямих CDN посилань...", server_url=server_url)
            proc_m = subprocess.run(cmd_meta, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            videos = []
            photos = []
            direct_video_url = ""
            direct_audio_url = ""
            main_thumb = ""
            info = {}
            extractor_engine = "yt_dlp"
            ytdlp_err = ""

            if proc_m.returncode == 0 and (proc_m.stdout or "").strip():
                try:
                    info = json.loads(proc_m.stdout)
                    entries = info.get("entries") if isinstance(info.get("entries"), list) and info.get("entries") else [info]
                    main_thumb = info.get("thumbnail") or ""
                    for ent in entries:
                        if not isinstance(ent, dict):
                            continue
                        v_u, a_u, t_u = _pick_cdn_streams(ent, max_quality=max_quality)
                        if t_u and not main_thumb:
                            main_thumb = t_u
                        if v_u:
                            videos.append({"index": len(videos) + 1, "url": v_u, "thumbnail": t_u or main_thumb or None})
                            if not direct_video_url:
                                direct_video_url = v_u
                        elif t_u:
                            photos.append(t_u)
                        if a_u and not direct_audio_url:
                            direct_audio_url = a_u
                except Exception as parse_ex:
                    ytdlp_err = str(parse_ex)
            else:
                ytdlp_err = (proc_m.stderr or "") + " " + (proc_m.stdout or "")

            # Level 2 Cascade: Cobalt API (127.0.0.1:9000) when yt-dlp failed, was blocked, or missed audio
            try:
                from modules.cobalt_engine import is_cobalt_available, resolve_with_cobalt
                if not direct_video_url and not direct_audio_url and not photos:
                    if is_cobalt_available():
                        report_job_progress(job_id, progress=65, stage_msg="Резервна екстракція через Cobalt API...", server_url=server_url)
                        cob = resolve_with_cobalt(target_url, want_video=True, want_audio=True, video_quality=str(max_quality))
                        if cob.get("ok"):
                            extractor_engine = "cobalt"
                            direct_video_url = cob.get("video_url") or ""
                            direct_audio_url = cob.get("audio_url") or ""
                            videos = cob.get("videos") or []
                            photos = cob.get("photos") or []
                elif not direct_audio_url and is_cobalt_available():
                    cob_aud = resolve_with_cobalt(target_url, want_video=False, want_audio=True, video_quality=str(max_quality))
                    if cob_aud.get("audio_url"):
                        direct_audio_url = cob_aud["audio_url"]
            except Exception as cob_ex:
                print(f"[Cobalt fallback warning] {cob_ex}")

            if not direct_audio_url and direct_video_url:
                direct_audio_url = direct_video_url

            if not direct_video_url and not direct_audio_url and not photos:
                raise Exception(_format_ytdlp_error(ytdlp_err))

            prefetched = job.get("prefetched_meta") if isinstance(job.get("prefetched_meta"), dict) else {}
            caption = (info.get("description") or info.get("title") or prefetched.get("caption") or "").strip()
            raw_title = (info.get("title") or prefetched.get("title") or "").strip()
            if caption and (not raw_title or raw_title.startswith("Video by ")):
                first_line = caption.splitlines()[0].strip()
                if first_line:
                    raw_title = first_line[:95]

            metadata = {
                "title": raw_title or prefetched.get("title") or "Соціальна публікація",
                "caption": caption or prefetched.get("caption") or "",
                "author": info.get("uploader") or info.get("channel") or prefetched.get("author") or "Автор",
                "thumbnail": main_thumb or prefetched.get("thumbnail") or (photos[0] if photos else None),
                "videos": videos,
                "photos": photos,
            }

            target_endpoint = server_url or SERVER_URLS[0]
            res = requests.post(
                target_endpoint,
                params={"action": "complete_social_job", "secret": SECRET_KEY},
                data={
                    "job_id": job_id,
                    "job_type": "social_download",
                    "mode": "resolve_cdn",
                    "extractor_engine": extractor_engine,
                    "direct_video_url": direct_video_url,
                    "direct_audio_url": direct_audio_url,
                    "metadata_json": json.dumps(metadata, ensure_ascii=False),
                },
                timeout=30,
            )
            res.raise_for_status()
            res_json = res.json()
            if not res_json.get("success"):
                raise Exception(res_json.get("message", "CDN resolve upload error"))

            report_job_progress(job_id, progress=100, stage_msg="Готово! Прямі CDN посилання отримано.", est_remain=0, server_url=server_url)
            duration = round(time.time() - start_time, 2)
            print(f"⚡ [CDN РОЗВ'ЯЗАНО ЗА {duration} СЕК ({extractor_engine})] Відео: {bool(direct_video_url)}, Аудіо: {bool(direct_audio_url)}")
            print("=" * 60)
            return

        has_video = False
        video_size_str = ""
        proc_v = None

        # 1. Download Video (merged 1080p MP4) — only if requested
        if want_video:
            fmt_spec = f"bv*[height<={max_quality}][ext=mp4]+ba[ext=m4a]/bv*[height<={max_quality}]+ba/b[height<={max_quality}][ext=mp4]/best[height<={max_quality}]/best"
            cmd_video = [
                sys.executable, "-m", "yt_dlp",
                "--no-warnings",
                "--no-playlist",
                "-f", fmt_spec,
                "--merge-output-format", "mp4",
                "-o", video_out
            ]
            if cookie_file:
                cmd_video.extend(["--cookies", cookie_file])
            cmd_video.append(target_url)

            report_job_progress(job_id, progress=35, stage_msg=f"Завантаження та склеювання HD MP4 ({max_quality}p)...", server_url=server_url)
            proc_v = subprocess.run(cmd_video, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc_v.returncode != 0 and not os.path.exists(video_out):
                cmd_video_fallback = [
                    sys.executable, "-m", "yt_dlp",
                    "--no-warnings",
                    "--no-playlist",
                    "-f", "bestvideo+bestaudio/best",
                    "--merge-output-format", "mp4",
                    "-o", video_out
                ]
                if cookie_file:
                    cmd_video_fallback.extend(["--cookies", cookie_file])
                cmd_video_fallback.append(target_url)
                proc_v = subprocess.run(cmd_video_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            has_video = os.path.exists(video_out) and os.path.getsize(video_out) > 5000
            if has_video:
                v_size_mb = os.path.getsize(video_out) / (1024 * 1024)
                video_size_str = f"{v_size_mb:.2f} МБ"
                print(f"  ✅ Відео завантажено успішно ({video_size_str})")

        has_audio = False
        audio_size_str = ""
        proc_a = None

        # 2. Extract Audio MP3 — only if requested
        if want_audio:
            report_job_progress(job_id, progress=70 if want_video else 45, stage_msg="Конвертація чистого MP3 аудіо (192 kbps)...", server_url=server_url)
            cmd_audio = [
                sys.executable, "-m", "yt_dlp",
                "--no-warnings",
                "--no-playlist",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "192K",
                "-o", audio_out
            ]
            if cookie_file:
                cmd_audio.extend(["--cookies", cookie_file])
            cmd_audio.append(target_url)

            proc_a = subprocess.run(cmd_audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            has_audio = os.path.exists(audio_out) and os.path.getsize(audio_out) > 5000
            if has_audio:
                a_size_mb = os.path.getsize(audio_out) / (1024 * 1024)
                audio_size_str = f"{a_size_mb:.2f} МБ"
                print(f"  ✅ Аудіо MP3 витягнуто успішно ({audio_size_str})")

        if not has_video and not has_audio:
            err_text = ((proc_v.stderr or "") + " " + (proc_v.stdout or "")) if proc_v else ((proc_a.stderr or "") + " " + (proc_a.stdout or "") if proc_a else "")
            raise Exception(_format_ytdlp_error(err_text))

        # 3. Upload to server
        report_job_progress(job_id, progress=88, stage_msg="Збереження файлів у сховищі Aivtomation...", server_url=server_url)
        target_endpoint = server_url or SERVER_URLS[0]

        files = {}
        file_handles = []
        try:
            if has_video:
                vf = open(video_out, "rb")
                file_handles.append(vf)
                files["video"] = (f"{job_id}_video.mp4", vf, "video/mp4")
            if has_audio:
                af = open(audio_out, "rb")
                file_handles.append(af)
                files["audio"] = (f"{job_id}_audio.mp3", af, "audio/mpeg")

            data = {
                "job_id": job_id,
                "video_size": video_size_str,
                "audio_size": audio_size_str,
                "job_type": "social_download"
            }

            res = requests.post(
                target_endpoint,
                params={"action": "complete_social_job", "secret": SECRET_KEY},
                data=data,
                files=files,
                timeout=180
            )
            res.raise_for_status()
            res_json = res.json()
            if not res_json.get("success"):
                raise Exception(res_json.get("message", "Upload error"))
        finally:
            for fh in file_handles:
                try:
                    fh.close()
                except Exception:
                    pass

        report_job_progress(job_id, progress=100, stage_msg="Готово! Файли підготовлено до завантаження.", est_remain=0, server_url=server_url)
        duration = round(time.time() - start_time, 2)
        print(f"🎉 [СКАЧУВАННЯ МЕДІА ЗАВЕРШЕНО ЗА {duration} СЕК] Відео: {video_size_str}, Аудіо: {audio_size_str}")
        print("=" * 60)

    except Exception as e:
        print(f"❌ [ПОМИЛКА СКАЧУВАННЯ МЕДІА]: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": str(e)},
                timeout=5
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

def process_single_job(job: dict):
    job_id = job.get("id")
    server_url = job.get("_server_url", SERVER_URLS[0])
    options = job.get("options", {})
    srt_content = job.get("srt", "")
    caption = job.get("caption", "")
    custom_cover_text = job.get("custom_cover_text", "")
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return

    # If caption contains separator, split into subtitles and post caption
    post_caption = caption
    subtitles_text_from_caption = ""
    if "━━━━━━━━━━━━━━━━━━━━" in caption:
        parts = caption.split("━━━━━━━━━━━━━━━━━━━━")
        subtitles_text_from_caption = parts[0].strip()
        post_caption = parts[1].strip() if len(parts) > 1 else ""
        if not custom_cover_text and subtitles_text_from_caption:
            custom_cover_text = subtitles_text_from_caption.split("\n")[0].strip()[:60]
    elif "---" in caption and ("допис" in caption.lower() or "субтитр" in caption.lower()):
        parts = caption.split("---")
        subtitles_text_from_caption = parts[0].strip()
        post_caption = parts[1].strip() if len(parts) > 1 else ""

    print("\n" + "-" * 60)
    print(f"🎬 [НОВЕ ЗАВДАННЯ] Job ID: {job_id}")
    print(f"📋 Опції монтажу:")
    print(f"   • Вшивання субтитрів (Burn-in): {'ТАК' if options.get('burn_subtitles') else 'НІ'}")
    print(f"   • Обрізка пауз (JumpCut): {'ТАК' if options.get('jumpcut') else 'НІ'}")
    print(f"   • Прев'ю-обкладинка (0.5с): {'ТАК' if options.get('cover') else 'НІ'}")
    if custom_cover_text:
        print(f"   • Текст обкладинки: {custom_cover_text.replace(chr(10), ' | ')}")

    job_dir = os.path.join(WORK_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    raw_video = os.path.join(job_dir, "input.mp4")
    current_video = raw_video

    start_time = time.time()
    ticker = None
    try:
        report_job_progress(job_id, progress=5, stage_msg="Завантаження відео...", est_remain=None, server_url=server_url)

        # Step 1: Download raw video from server
        download_video(source_url, raw_video)
        total_duration = get_video_duration(raw_video)
        print(f"  ⏱️ Тривалість відео: {total_duration:.1f} сек")

        active_steps = []
        if options.get("burn_subtitles"):
            # Auto-transcribe video using OpenAI Whisper STT if SRT was not provided
            if not srt_content or "-->" not in srt_content:
                print("  🎙️ [Крок 0] Автоматичне розпізнавання аудіо (OpenAI Whisper STT)...")
                report_job_progress(job_id, progress=8, stage_msg="Розпізнавання аудіо (Whisper STT)...", server_url=server_url)
                temp_wav = os.path.join(job_dir, "extracted_audio.wav")
                try:
                    from modules.stt import extract_audio_from_video, transcribe_audio_to_srt
                    extract_audio_from_video(raw_video, temp_wav)
                    stt_res = transcribe_audio_to_srt(temp_wav, language="uk")
                    srt_content = stt_res.get("srt", "")
                    if not caption and stt_res.get("text"):
                        caption = stt_res.get("text")
                    print(f"  ✅ Аудіо успішно транскрибовано ({len(stt_res.get('words', []))} слів)!")
                except Exception as stt_err:
                    print(f"  ⚠️ Помилка STT Whisper: {stt_err}")
            if srt_content:
                active_steps.append("subs")
        if options.get("jumpcut"):
            active_steps.append("jumpcut")
        if options.get("cover"):
            active_steps.append("cover")

        ticker = JobProgressTicker(job_id, total_duration, active_steps, server_url=server_url)
        ticker.start()

        cover_duration_sec = float(job.get("cover_duration") or total_duration)
        cover_duration_sec = min(cover_duration_sec, total_duration)

        # Step 2: ВШИВАННЯ СУБТИТРІВ СПОЧАТКУ
        typography = job.get("typography", {})
        if "subs" in active_steps:
            print("  💬 [Крок 1/3] Вшивання стильних субтитрів у пікселі (multi-thread)...")
            end_pct = 50 if ("cover" in active_steps or "jumpcut" in active_steps) else 85
            ticker.set_step("subs", "Вшивання субтитрів у пікселі (процесор)...", 12, end_pct)
            subtitled_out = os.path.join(job_dir, "subtitled.mp4")
            current_video = burn_subtitles_into_video(
                current_video, 
                srt_content, 
                subtitled_out, 
                typography=typography,
                min_start_ms=0
            )
            print("  ✅ Субтитри надійно впечено у відео (100% синхрон)!")

        # Step 3: НАКЛАДАННЯ ПРЕВ'Ю-ХУКА ДРУГИМ КРОКОМ
        if "cover" in active_steps:
            print(f"  🖼️ [Крок 2/3] Створення та вклейка хук-плашки на {cover_duration_sec:.1f}с...")
            ticker.set_step("cover", f"Вклейка хук-плашки на {cover_duration_sec:.1f}с...", 50, 75)
            cover_out = os.path.join(job_dir, "with_cover.mp4")
            cover_typography = job.get("cover_typography", typography)
            current_video = generate_and_apply_cover(
                input_video=current_video,
                output_video=cover_out,
                caption_or_topic=caption,
                custom_cover_text=custom_cover_text,
                frame_source_video=raw_video,
                duration_sec=cover_duration_sec,
                typography=cover_typography
            )
            print(f"  ✅ Хук-плашку ({cover_duration_sec:.1f}с) успішно впечено у відео!")

        # Step 4: АВТООБРІЗКА ПАУЗ (JumpCut) НА ФІНАЛЬНОМУ ЕТАПІ КОЛИ ВСЕ ВЖЕ ЗАПЕЧЕНО!
        if "jumpcut" in active_steps:
            print("  ✂️ [Крок 3/3] Фінальна автообрізка пауз і тиші (JumpCut)...")
            ticker.set_step("jumpcut", "Фінальна автообрізка пауз і тиші (JumpCut)...", 75, 92)
            trimmed_out = os.path.join(job_dir, "trimmed.mp4")
            current_video = remove_silence_from_video(current_video, trimmed_out)
            print("  ✅ Паузи вирізано з повністю готового запеченого відео!")

        # Step 5: Upload final hardcoded video back to Hostinger
        if ticker:
            ticker.stop()
        report_job_progress(job_id, progress=94, stage_msg="Відправка змонтованого MP4 на сервер...", est_remain=3, server_url=server_url)
        final_url = upload_processed_video(job_id, current_video, server_url=server_url)
        report_job_progress(job_id, progress=100, stage_msg="Готово! Відео успішно змонтовано", est_remain=0, server_url=server_url)

        duration = round(time.time() - start_time, 2)
        print(f"⚡ [ГОТОВО ЗА {duration} СЕК] Рендеринг завершено ідеально!")
        print("-" * 60)

    except Exception as e:
        if ticker:
            ticker.stop()
        print(f"❌ [ПОМИЛКА МОНТАЖУ]: {e}")
        report_failure(job_id, str(e), server_url=server_url)
    finally:
        if ticker:
            ticker.stop()
        # Cleanup temp directory
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
        except Exception:
            pass

UNSYNTH_AUDIO_AF = (
    "asetrate=44100*1.0012,aresample=44100,atempo=0.9988,"
    "highpass=f=16,lowpass=f=19200,"
    "equalizer=f=180:width_type=q:width=1.2:g=0.35,"
    "equalizer=f=4200:width_type=q:width=1.5:g=-0.25,"
    "alimiter=limit=0.98:level=disabled"
)


def _probe_video_bitrate(video_path: str) -> int | None:
    try:
        _flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate",
            "-show_entries", "format=bit_rate,duration",
            "-of", "json",
            video_path,
        ]
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, creationflags=_flags)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        if streams and streams[0].get("bit_rate"):
            val = str(streams[0]["bit_rate"]).strip()
            if val.isdigit() and int(val) > 0:
                return int(val)
        fmt = data.get("format", {})
        if fmt.get("bit_rate"):
            val = str(fmt["bit_rate"]).strip()
            if val.isdigit() and int(val) > 0:
                return int(val)
        if fmt.get("duration"):
            dur = float(fmt["duration"])
            if dur > 0:
                return int((os.path.getsize(video_path) * 8) / dur)
    except Exception:
        pass
    return None


def _has_audio_stream(media_path: str) -> bool:
    try:
        _flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", media_path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, creationflags=_flags
        )
        return "audio" in (res.stdout or "").lower()
    except Exception:
        return False


def process_unsynth_video_job(job: dict):
    """
    Process Aivtomation Production UnSynth video job across 9:16, 16:9, 4:3, 3:4
    without cropping, with blurred backdrop, chromatic aberration, pixel + audio desynthesis,
    original bitrate preservation, and full metadata removal.
    """
    job_id = job.get("id") or job.get("order_uid")
    server_url = job.get("_server_url", "https://aivtomation.com/production/worker_api.php")
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return
    aspect = job.get("aspect_ratio", "9:16")
    blur_bg = bool(job.get("blur_bg", True))
    ratio_map = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }
    target_w, target_h = ratio_map.get(aspect, (1080, 1920))

    print("\n" + "-" * 60)
    print(f"🎬 [UNSYNTH VIDEO] Job ID: {job_id} | Ratio: {aspect} ({target_w}x{target_h})")
    job_dir = os.path.join(WORK_TEMP_DIR, f"unsynth_{job_id}")
    os.makedirs(job_dir, exist_ok=True)
    t0 = time.time()

    try:
        src_path = os.path.join(job_dir, "input.mp4")
        out_path = os.path.join(job_dir, "output.mp4")
        download_video(source_url, src_path)

        requests.post(
            server_url,
            params={"action": "progress", "secret": SECRET_KEY},
            data={"job_id": job_id, "progress": 30, "stage_msg": f"FFmpeg UnSynth ({aspect})..."},
            timeout=5
        )

        if blur_bg:
            vf = (
                f"[0:v]split=2[bg_raw][fg_raw];"
                f"[bg_raw]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=25:5,eq=brightness=-0.08[bg];"
                f"[fg_raw]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                f"scale=iw*0.98:ih*0.98,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,"
                f"gblur=sigma=0.35,unsharp=5:5:0.5:5:5:0.0,rgbashift=rh=1:bh=-1,noise=c1s=3:c0f=u,eq=contrast=1.03"
            )
        else:
            vf = (
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=#0F172A,"
                f"scale=iw*0.98:ih*0.98,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,"
                f"gblur=sigma=0.35,unsharp=5:5:0.5:5:5:0.0,rgbashift=rh=1:bh=-1,noise=c1s=3:c0f=u,eq=contrast=1.03"
            )

        orig_bitrate = _probe_video_bitrate(src_path)
        if orig_bitrate and orig_bitrate > 0:
            rate_args = [
                "-b:v", str(orig_bitrate),
                "-maxrate", str(int(orig_bitrate * 1.5)),
                "-bufsize", str(int(orig_bitrate * 2)),
            ]
        else:
            rate_args = ["-crf", "19"]

        audio_args = ["-af", UNSYNTH_AUDIO_AF, "-c:a", "aac", "-b:a", "192k"] if _has_audio_stream(src_path) else ["-an"]

        cmd = [
            "ffmpeg", "-y",
            "-threads", str(_get_ffmpeg_threads()),
            "-i", src_path,
            "-filter_complex", vf,
            "-c:v", "libx264", "-preset", "faster",
            *rate_args,
            *audio_args,
            "-map_metadata", "-1", "-movflags", "+faststart", out_path
        ]
        _flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=_flags)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip().splitlines()[-1] if res.stderr else "FFmpeg UnSynth failed")

        elapsed = round(time.time() - t0, 2)
        payload = {"job_id": job_id, "cpu_duration_sec": elapsed, "gpu_duration_sec": 0}
        if job.get("item_index") is not None:
            payload["item_index"] = str(job.get("item_index"))
        with open(out_path, "rb") as f:
            up = requests.post(
                server_url,
                params={"action": "complete", "secret": SECRET_KEY},
                data=payload,
                files={"video_file": ("unsynth.mp4", f, "video/mp4")},
                timeout=180
            )
            up.raise_for_status()
        print(f"✅ [UNSYNTH VIDEO DONE] {job_id} ({elapsed}s)")
    except Exception as e:
        print(f"❌ [UNSYNTH VIDEO ERROR] {job_id}: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": str(e)},
                timeout=10
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def process_unsynth_audio_job(job: dict):
    """
    Process Aivtomation Production UnSynth audio job:
    strips generator metadata, shifts spectral phase by 0.12% (preserving duration),
    filters ultrasonic AI watermarks (>19.2 kHz), and applies subtle analog preamp EQ.
    """
    job_id = job.get("id") or job.get("order_uid")
    server_url = job.get("_server_url", "https://aivtomation.com/production/worker_api.php")
    source_url = job.get("source_url")
    if not source_url or not isinstance(source_url, str):
        jtype_label = job.get("job_type") or job.get("type") or "media"
        err_msg = f"Missing or invalid source_url for {jtype_label} job {job_id}"
        print(f"❌ [MONTAGE ERROR] {err_msg}")
        try:
            requests.post(
                server_url,
                params={"action": "fail_job", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                timeout=10,
            )
        except Exception:
            pass
        return
    item_index = job.get("item_index")

    print("\n" + "-" * 60)
    print(f"🎵 [UNSYNTH AUDIO] Job ID: {job_id}")
    job_dir = os.path.join(WORK_TEMP_DIR, f"unsynth_audio_{job_id}")
    os.makedirs(job_dir, exist_ok=True)
    t0 = time.time()

    try:
        src_path = os.path.join(job_dir, "input_audio")
        out_path = os.path.join(job_dir, "unsynth_audio.mp3")
        download_video(source_url, src_path)

        requests.post(
            server_url,
            params={"action": "progress", "secret": SECRET_KEY},
            data={"job_id": job_id, "progress": 40, "stage_msg": "FFmpeg UnSynth Audio mastering..."},
            timeout=5,
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", src_path,
            "-vn",
            "-af", UNSYNTH_AUDIO_AF,
            "-c:a", "libmp3lame", "-b:a", "320k",
            "-map_metadata", "-1",
            out_path,
        ]
        _flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=_flags)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip().splitlines()[-1] if res.stderr else "FFmpeg UnSynth Audio failed")

        elapsed = round(time.time() - t0, 2)
        payload = {"job_id": job_id, "cpu_duration_sec": elapsed, "gpu_duration_sec": 0}
        if item_index is not None:
            payload["item_index"] = str(item_index)
        with open(out_path, "rb") as f:
            up = requests.post(
                server_url,
                params={"action": "complete", "secret": SECRET_KEY},
                data=payload,
                files={"audio_file": ("unsynth_audio.mp3", f, "audio/mpeg")},
                timeout=120,
            )
            up.raise_for_status()
        print(f"✅ [UNSYNTH AUDIO DONE] {job_id} ({elapsed}s)")
    except Exception as e:
        print(f"❌ [UNSYNTH AUDIO ERROR] {job_id}: {e}")
        try:
            requests.post(
                server_url,
                params={"action": "fail", "secret": SECRET_KEY},
                data={"job_id": job_id, "error": str(e)},
                timeout=10,
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def acquire_single_instance_lock(port: int = 49281):
    """
    Guarantees only ONE worker process runs on the PC at any time.
    Binds a local TCP port that Windows automatically releases if the process closes.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        return s
    except Exception:
        print(f"\n⚠️ [УВАГА] Воркер уже активно працює у системі (порт {port} зайнято).")
        print("Всі завдання обробляються автоматично. Повторний запуск пропущено.\n")
        time.sleep(3)
        sys.exit(0)

def _send_slot_wait_ping(job_id: str, job_type: str, server_url: str):
    """Keep updated_at fresh while a queued heavy render waits for the local FFmpeg slot."""
    try:
        if job_type in ("unsynth_video", "unsynth_audio"):
            requests.post(
                server_url,
                params={"action": "progress", "secret": SECRET_KEY},
                data={"job_id": job_id, "progress": 5, "stage_msg": "Очікування звільнення рендер-слота на ПК..."},
                timeout=5,
            )
        else:
            report_job_progress(
                job_id,
                progress=3,
                stage_msg="Очікування звільнення рендер-слота на ПК...",
                server_url=server_url,
            )
    except Exception:
        pass


SUPPORTED_JOB_TYPES = (
    "video_montage",
    "stt",
    "compress_telegram",
    "trim_threads",
    "social_download",
    "unsynth_video",
    "unsynth_audio",
)


def _execute_job_worker(job: dict):
    job_id = str(job.get("id") or job.get("order_uid") or "")
    server_url = job.get("_server_url", SERVER_URLS[0])
    job_type = job.get("job_type") or job.get("type") or "video_montage"
    spec = get_job_spec(job_type)
    job_class = spec.get("class", "gpu_heavy")
    sem = CLASS_SEMAPHORES.get(job_class, CLASS_SEMAPHORES["gpu_heavy"])

    acquired_slot = False
    try:
        while not sem.acquire(timeout=20):
            _send_slot_wait_ping(job_id, job_type, server_url)
        acquired_slot = True

        if job_type == "stt":
            process_stt_job(job)
        elif job_type == "compress_telegram":
            process_compress_telegram_job(job)
        elif job_type == "trim_threads":
            process_trim_threads_job(job)
        elif job_type == "social_download":
            process_social_download_job(job)
        elif job_type == "unsynth_video":
            process_unsynth_video_job(job)
        elif job_type == "unsynth_audio":
            process_unsynth_audio_job(job)
        elif job_type == "video_montage":
            process_single_job(job)
        else:
            err_msg = f"Unsupported job_type '{job_type}' on worker {WORKER_TYPE}"
            print(f"❌ [UNSUPPORTED JOB] {job_id}: {err_msg}")
            try:
                requests.post(
                    server_url,
                    params={"action": "fail_job", "secret": SECRET_KEY},
                    data={"job_id": job_id, "error": err_msg, "worker_type": WORKER_TYPE},
                    timeout=10,
                )
            except Exception:
                pass
    except Exception as exc:
        print(f"❌ [DISPATCH ERROR] {job_id}: {exc}")
    finally:
        if acquired_slot:
            sem.release()
        with ACTIVE_JOBS_LOCK:
            ACTIVE_JOB_IDS.discard(job_id)
            ACTIVE_JOBS_META.pop(job_id, None)


def _compute_allowed_classes() -> list[str]:
    with NODE_STATE_LOCK:
        mode = NODE_STATE.get("mode", "normal")
        thermal = bool(NODE_STATE.get("thermal_throttle", False))
        tel = NODE_STATE.get("telemetry", {})
    if mode == "paused":
        return []
    slots_free = _get_slots_free()
    allowed = []
    for cls, free_cnt in slots_free.items():
        if free_cnt <= 0:
            continue
        if thermal and cls in ("gpu_heavy", "cpu_heavy"):
            continue
        if mode == "light_only" and cls in ("gpu_heavy", "cpu_heavy"):
            continue
        if cls == "gpu_light":
            v_used = tel.get("vram_used_mb")
            v_tot = tel.get("vram_total_mb")
            if v_used is not None and v_tot is not None and (v_tot - v_used) < 2500:
                continue
        allowed.append(cls)
    return allowed


def main():
    # 0. Single instance lock
    _lock = acquire_single_instance_lock()

    print_banner()

    # Launch daemon heartbeat + telemetry thread
    hb_thread = threading.Thread(target=heartbeat_daemon_loop, daemon=True)
    hb_thread.start()
    print("💓 Постійний пульс (Heartbeat) + телеметрія вузла активовано кожні 10 секунд.")

    last_err_log = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as pool:
        while True:
            allowed_classes = _compute_allowed_classes()
            if not allowed_classes:
                time.sleep(2.0)
                continue

            for s_url in SERVER_URLS:
                allowed_classes = _compute_allowed_classes()
                if not allowed_classes:
                    break
                try:
                    res = requests.get(
                        s_url,
                        params={
                            "action": "poll",
                            "secret": SECRET_KEY,
                            "worker_type": WORKER_TYPE,
                            "worker_instance_id": WORKER_INSTANCE_ID,
                            "allowed_classes": ",".join(allowed_classes),
                            "supported_types": ",".join(SUPPORTED_JOB_TYPES),
                        },
                        timeout=8,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("has_job") and data.get("job"):
                            job = data["job"]
                            job["_server_url"] = s_url
                            job_id = str(job.get("id") or job.get("order_uid") or "")
                            j_type = job.get("job_type") or job.get("type") or "video_montage"
                            j_class = get_job_spec(j_type).get("class", "gpu_heavy")
                            with ACTIVE_JOBS_LOCK:
                                if job_id in ACTIVE_JOB_IDS:
                                    continue
                                ACTIVE_JOB_IDS.add(job_id)
                                ACTIVE_JOBS_META[job_id] = {
                                    "id": job_id,
                                    "type": j_type,
                                    "class": j_class,
                                    "started_at": time.time(),
                                }
                            pool.submit(_execute_job_worker, job)
                    elif res.status_code != 200:
                        now_ts = time.time()
                        if now_ts - last_err_log.get(s_url, 0) > 60:
                            last_err_log[s_url] = now_ts
                            print(f"⚠️ [POLL HTTP {res.status_code}] {s_url}")
                except requests.exceptions.ConnectionError:
                    pass
                except Exception as e:
                    now_ts = time.time()
                    if now_ts - last_err_log.get(s_url, 0) > 60:
                        last_err_log[s_url] = now_ts
                        print(f"⚠️ [POLL ERROR] {s_url}: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Локальний воркер зупинено.")
