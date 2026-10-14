#!/usr/bin/env python3
"""
Aivtomation GitHub Actions Cloud Media Worker (Failover Engine)
Runs on GitHub Actions Ubuntu runners (2 vCPU, 7 GB RAM, fast NVMe & pre-installed FFmpeg).

Processes video montage tasks and Whisper STT when the user's primary local PC is offline,
guaranteeing 100% preservation of custom user typography, .ass karaoke subtitles,
hook cover badge, and JumpCut silence trimming.
"""

import os
import sys
import time
import requests
from datetime import datetime

# Ensure modules in current directory can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.chdir(CURRENT_DIR)

# Force Cloud/GitHub Actions identity
os.environ["AIV_WORKER_TYPE"] = "github_actions"
os.environ["AIV_HARDWARE_NAME"] = "GitHub Actions Cloud Runner (Ubuntu 2 vCPU / 7 GB RAM)"

from local_worker import (
    process_single_job,
    process_stt_job,
    SERVER_URLS,
    SECRET_KEY,
    WORKER_TYPE,
    HARDWARE_NAME
)

target_job_id = os.getenv("TARGET_JOB_ID", "").strip()
server_url_override = os.getenv("AIV_SERVER_URL", "").strip()
if server_url_override:
    SERVER_URLS = [server_url_override]

def send_heartbeat():
    for s_url in SERVER_URLS:
        try:
            requests.post(
                s_url,
                params={"action": "ping", "secret": SECRET_KEY},
                data={"hardware": HARDWARE_NAME, "worker_type": WORKER_TYPE},
                timeout=5
            )
        except Exception:
            pass

def main():
    print("=" * 70)
    print("🚀 [AIVTOMATION: GITHUB ACTIONS CLOUD MEDIA WORKER ONLINE]")
    print(f"💻 Runner: {HARDWARE_NAME}")
    print(f"🌐 Server targets: {SERVER_URLS}")
    print(f"🎯 Target Job ID: {target_job_id if target_job_id else 'Auto-detect from queue'}")
    print("⚡ Режим: Повноцінний автономний рендеринг відео (Burn-in Subtitles / JumpCut / Cover)")
    print("=" * 70)

    # 1. Notify server that GitHub Actions runner is active
    send_heartbeat()
    print("💓 Heartbeat надіслано на сервер: GitHub Actions ONLINE")

    processed_count = 0
    max_idle_polls = 3
    idle_count = 0

    while idle_count < max_idle_polls:
        job_handled = False

        for s_url in SERVER_URLS:
            try:
                res = requests.get(
                    s_url,
                    params={
                        "action": "poll",
                        "secret": SECRET_KEY,
                        "worker_type": WORKER_TYPE,
                        "job_id": target_job_id if target_job_id else ""
                    },
                    timeout=10
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("has_job") and data.get("job"):
                        job = data["job"]
                        job["_server_url"] = s_url
                        job_id = job.get("id", "unknown")
                        is_stt = (job.get("job_type") == "stt" or job.get("type") == "stt")

                        print("\n" + "#" * 60)
                        print(f"🎬 [JOB START] Processing Job ID: {job_id} ({'STT' if is_stt else 'Video Montage'})")
                        print("#" * 60)

                        if is_stt:
                            process_stt_job(job)
                        else:
                            process_single_job(job)

                        processed_count += 1
                        job_handled = True
                        send_heartbeat()
                        print(f"✅ [JOB DONE] Job ID {job_id} successfully finished and uploaded!")

            except Exception as e:
                print(f"⚠️ [POLL ERROR]: {e}")

        if job_handled:
            idle_count = 0
            # If target_job_id was specified and finished, we're done
            if target_job_id:
                break
        else:
            idle_count += 1
            if idle_count < max_idle_polls:
                print(f"⏳ Черга порожня (спроба {idle_count}/{max_idle_polls}). Очікування нових завдань...")
                time.sleep(4)

    print("\n" + "=" * 70)
    print(f"🏁 [GITHUB ACTIONS RUNNER COMPLETE] Всього оброблено завдань: {processed_count}")
    print("=" * 70)

if __name__ == "__main__":
    main()
