#!/usr/bin/env python3
"""
Silent Watchdog Daemon for Aivtomation Local Media Worker.
Checks every 15 seconds whether local_worker.py is holding its single-instance lock port (49281).
If local_worker.py exited, crashed, or was killed, automatically restarts it silently via pythonw.exe.
"""

import os
import sys
import time
import socket
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_SCRIPT = os.path.join(CURRENT_DIR, "local_worker.py")
WATCHDOG_LOG = os.path.join(CURRENT_DIR, "watchdog.log")
WORKER_BOOT_ERROR_LOG = os.path.join(CURRENT_DIR, "worker_boot_error.log")
WORKER_LOCK_PORT = 49281
WATCHDOG_LOCK_PORT = 49282
CHECK_INTERVAL_SEC = 15
OPENWHISPR_PORT = 8178
OPENWHISPR_BIN = r"C:\Users\alexe\AppData\Roaming\open-whispr\bin\whisper-cuda\whisper-server-win32-x64-cuda.exe"
OPENWHISPR_MODEL = r"C:\Users\alexe\.cache\openwhispr\whisper-models\ggml-medium.bin"
COBALT_PORT = 9000
COBALT_COMPOSE_DIR = os.path.join(CURRENT_DIR, "cobalt")


def log_msg(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def get_pythonw_path() -> str:
    candidates = [
        r"C:\Program Files\Python310\pythonw.exe",
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        sys.executable,
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return sys.executable


def acquire_watchdog_lock():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", WATCHDOG_LOCK_PORT))
        s.listen(1)
        return s
    except Exception:
        sys.exit(0)


def is_worker_running() -> bool:
    """Returns True if port 49281 is already bound by local_worker.py."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", WORKER_LOCK_PORT))
        # Bind succeeded -> nobody is holding 49281 -> worker is NOT running
        s.close()
        return False
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return True


def start_worker():
    pythonw = get_pythonw_path()
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    boot_err_fp = None
    try:
        boot_err_fp = open(WORKER_BOOT_ERROR_LOG, "a", encoding="utf-8")
        boot_err_fp.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting local_worker.py via {pythonw}\n")
        boot_err_fp.flush()
    except Exception:
        boot_err_fp = None
    try:
        subprocess.Popen(
            [pythonw, WORKER_SCRIPT],
            cwd=CURRENT_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=boot_err_fp if boot_err_fp is not None else subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    finally:
        if boot_err_fp is not None:
            try:
                boot_err_fp.close()
            except Exception:
                pass
    log_msg(f"Started local_worker.py via {pythonw} (stderr -> {WORKER_BOOT_ERROR_LOG})")


def is_openwhispr_running() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.8)
    try:
        return s.connect_ex(("127.0.0.1", OPENWHISPR_PORT)) == 0
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def start_openwhispr():
    if not (os.path.exists(OPENWHISPR_BIN) and os.path.exists(OPENWHISPR_MODEL)):
        return
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    subprocess.Popen(
        [OPENWHISPR_BIN, "--model", OPENWHISPR_MODEL, "--port", str(OPENWHISPR_PORT), "--host", "127.0.0.1"],
        cwd=os.path.dirname(OPENWHISPR_BIN),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )
    log_msg("Started OpenWhispr CUDA server on port 8178")


def is_cobalt_running() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.8)
    try:
        return s.connect_ex(("127.0.0.1", COBALT_PORT)) == 0
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def start_cobalt():
    compose_file = os.path.join(COBALT_COMPOSE_DIR, "docker-compose.yml")
    if not os.path.exists(compose_file):
        return
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        res = subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d"],
            cwd=COBALT_COMPOSE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            timeout=25,
        )
        if res.returncode == 0:
            log_msg("Started aiv-cobalt container on 127.0.0.1:9000")
    except Exception as e:
        log_msg(f"Cobalt start skipped/error: {e}")


def main():
    _lock = acquire_watchdog_lock()
    log_msg("Aivtomation Worker Watchdog started.")

    while True:
        try:
            if not is_worker_running():
                log_msg("Worker port 49281 is down. Restarting local_worker.py...")
                start_worker()
                time.sleep(6)
            if not is_openwhispr_running():
                start_openwhispr()
            if not is_cobalt_running():
                start_cobalt()
        except Exception as e:
            log_msg(f"Watchdog loop error: {e}")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
