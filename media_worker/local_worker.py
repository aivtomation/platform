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
import requests
import tempfile
import shutil
import subprocess
import io
import threading
import socket

# Ensure modules in current directory can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.chdir(CURRENT_DIR)


LOG_FILE = os.path.join(CURRENT_DIR, "worker.log")

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
    bot_token = "8915027231:AAGGLkrcPHgpNChy5ShmLOaKwu8QgYJYkIE"
    chat_id = "425927724"
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

# Multi-environment support: service Stage 1, Stage 2 and Production
DEFAULT_URLS = [
    "https://aivtomation.com/crossposting/app/media_worker_api.php",
    "https://aivtomation.com/crossposting-stage/app/media_worker_api.php",
    "https://aivtomation.com/crossposting-stage2/app/media_worker_api.php"
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
WORK_TEMP_DIR = os.path.join(CURRENT_DIR, "temp_jobs")
os.makedirs(WORK_TEMP_DIR, exist_ok=True)

def print_banner():
    print("=" * 70)
    print("🚀 [AIVTOMATION MEDIA PROCESSING ENGINE ONLINE]")
    print(f"💻 Система: {HARDWARE_NAME} (Тип: {WORKER_TYPE})")
    print(f"🌐 Сервери завдань: {SERVER_URLS}")
    print("⚡ Режим: Повноцінний автономний рендеринг відео (Burn-in Subtitles / JumpCut / Cover)")
    print("=" * 70)

def send_heartbeat():
    for url in SERVER_URLS:
        try:
            requests.post(
                url,
                params={"action": "ping", "secret": SECRET_KEY},
                data={"hardware": HARDWARE_NAME, "worker_type": WORKER_TYPE},
                timeout=5
            )
        except Exception:
            pass

def heartbeat_daemon_loop():
    """
    Continuous background heartbeat thread.
    Guarantees the worker status is ALWAYS ONLINE even during heavy 100% CPU multi-minute renders!
    """
    while True:
        send_heartbeat()
        time.sleep(8)

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

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
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
            temp_input = os.path.join(job_dir, "input_video.mp4")
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
            subprocess.run(cmd_local, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if os.path.exists(temp_input):
                try:
                    os.remove(temp_input)
                except Exception:
                    pass

        mp3_size_kb = round(os.path.getsize(out_mp3) / 1024, 1)
        t_conv = round(time.time() - t_conv0, 2)
        print(f"  ⚡ MP3 вилучено успішно за {t_conv}с (розмір: {mp3_size_kb} КБ)")

        report_job_progress(job_id, progress=50, stage_msg="ШІ-розпізнавання мови через OpenAI Whisper...", server_url=server_url)

        # Step 2: Transcribe via OpenAI Whisper
        t_stt0 = time.time()
        from modules.stt import openai_client
        with open(out_mp3, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                language=language if language != "auto" else None,
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"]
            )
        t_stt = round(time.time() - t_stt0, 2)
        print(f"  🤖 Whisper розпізнавання завершено за {t_stt}с!")

        full_text = getattr(transcript, "text", "").strip()
        segments = getattr(transcript, "segments", []) or []
        words = getattr(transcript, "words", []) or []

        # Step 3: Format cues and SRT
        cues = []
        srt_lines = []
        idx = 1
        for seg in segments:
            start = float(seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0))
            end = float(seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0))
            text = (seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")).strip()

            seg_words = []
            if words:
                for w in words:
                    w_start = float(w.get("start", 0.0) if isinstance(w, dict) else getattr(w, "start", 0.0))
                    w_end = float(w.get("end", 0.0) if isinstance(w, dict) else getattr(w, "end", 0.0))
                    w_text = (w.get("word", "") if isinstance(w, dict) else getattr(w, "word", "")).strip()
                    if w_start >= start - 0.08 and w_end <= end + 0.12:
                        seg_words.append({
                            "word": w_text,
                            "start": round(w_start, 2),
                            "end": round(w_end, 2)
                        })

            cues.append({
                "id": idx,
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
                "words": seg_words
            })

            s_ms = int((start - int(start)) * 1000)
            s_sec = int(start) % 60
            s_min = (int(start) // 60) % 60
            s_hr = int(start) // 3600

            e_ms = int((end - int(end)) * 1000)
            e_sec = int(end) % 60
            e_min = (int(end) // 60) % 60
            e_hr = int(end) // 3600

            time_str = f"{s_hr:02d}:{s_min:02d}:{s_sec:02d},{s_ms:03d} --> {e_hr:02d}:{e_min:02d}:{e_sec:02d},{e_ms:03d}"
            srt_lines.append(f"{idx}\n{time_str}\n{text}\n")
            idx += 1

        srt_content = "\n".join(srt_lines).strip()

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

def process_single_job(job: dict):
    job_id = job.get("id")
    server_url = job.get("_server_url", SERVER_URLS[0])
    options = job.get("options", {})
    srt_content = job.get("srt", "")
    caption = job.get("caption", "")
    custom_cover_text = job.get("custom_cover_text", "")
    source_url = job.get("source_url")

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

def acquire_single_instance_lock(port: int = 49281):
    """
    Guarantees only ONE worker process runs on the PC at any time.
    Binds a local TCP port that Windows automatically releases if the process closes.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        return s
    except Exception:
        print(f"\n⚠️ [УВАГА] Воркер уже активно працює у системі (порт {port} зайнято).")
        print("Всі завдання обробляються автоматично. Повторний запуск пропущено.\n")
        time.sleep(3)
        sys.exit(0)

def main():
    # 0. Single instance lock
    _lock = acquire_single_instance_lock()

    print_banner()

    # Launch daemon heartbeat thread
    hb_thread = threading.Thread(target=heartbeat_daemon_loop, daemon=True)
    hb_thread.start()
    print("💓 Постійний пульс (Heartbeat) воркера активовано кожні 8 секунд.")

    while True:
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
                        if job.get("job_type") == "stt" or job.get("type") == "stt":
                            process_stt_job(job)
                        else:
                            process_single_job(job)
            except requests.exceptions.ConnectionError:
                pass
            except Exception as e:
                pass
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Локальний воркер зупинено.")
