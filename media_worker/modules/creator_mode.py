"""
Creator Mode Detector & Resource Protection for Aivtomation Worker.
Detects Adobe After Effects, Premiere Pro, Media Encoder, Blender, DaVinci Resolve
(plus sustained external GPU/CPU load), applies IDLE/BELOW_NORMAL process priority,
FFmpeg thread throttling, thermal protection, and Windows sleep prevention while active.
"""

import os
import time
import ctypes
import psutil

CREATOR_PROCESS_NAMES = {
    "afterfx.exe",
    "aerender.exe",
    "adobe premiere pro.exe",
    "adobe media encoder.exe",
    "blender.exe",
    "resolve.exe",
}

COOLDOWN_SEC = 120.0
_LAST_CREATOR_SEEN_TS = 0.0
_EXT_LOAD_START_TS = 0.0
_CURRENT_PRIORITY_MODE = None


def detect_creator_apps() -> list[str]:
    found = []
    try:
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").strip()
            if name.lower() in CREATOR_PROCESS_NAMES and name not in found:
                found.append(name)
    except Exception:
        pass
    return found


def evaluate_node_mode(
    telemetry: dict,
    active_heavy_count: int,
    manual_override: str = "auto",
) -> dict:
    """
    manual_override: 'auto' | 'light_only' | 'paused'
    Returns effective mode ('normal' | 'creator' | 'light_only' | 'paused'),
    detected creator_apps, ffmpeg_threads, and thermal_throttle flag.
    """
    global _LAST_CREATOR_SEEN_TS, _EXT_LOAD_START_TS

    now = time.time()
    creator_apps = detect_creator_apps()

    if creator_apps:
        _LAST_CREATOR_SEEN_TS = now
    else:
        # Detect sustained external GPU (>40%) or CPU (>60%) when worker has no heavy job
        gpu_u = telemetry.get("gpu_util") or 0.0
        cpu_u = telemetry.get("cpu_total") or 0.0
        if active_heavy_count == 0 and (gpu_u > 40.0 or cpu_u > 60.0):
            if _EXT_LOAD_START_TS == 0.0:
                _EXT_LOAD_START_TS = now
            elif (now - _EXT_LOAD_START_TS) >= 30.0:
                _LAST_CREATOR_SEEN_TS = now
        else:
            _EXT_LOAD_START_TS = 0.0

    in_creator = bool(creator_apps) or (_LAST_CREATOR_SEEN_TS > 0 and (now - _LAST_CREATOR_SEEN_TS) < COOLDOWN_SEC)

    gpu_temp = telemetry.get("gpu_temp")
    cpu_temp = telemetry.get("cpu_temp")
    thermal_throttle = bool(
        (gpu_temp is not None and gpu_temp > 83.0)
        or (cpu_temp is not None and cpu_temp > 90.0)
    )

    if manual_override in ("paused", "light_only"):
        effective_mode = manual_override
    elif in_creator:
        effective_mode = "creator"
    else:
        effective_mode = "normal"

    # Creator Mode uses option 2: throttle locally (4 threads, IDLE priority) instead of skipping
    ffmpeg_threads = 4 if effective_mode == "creator" else 12

    return {
        "mode": effective_mode,
        "manual_override": manual_override,
        "creator_apps": creator_apps,
        "ffmpeg_threads": ffmpeg_threads,
        "thermal_throttle": thermal_throttle,
    }


def apply_process_priority(is_creator: bool):
    global _CURRENT_PRIORITY_MODE
    if os.name != "nt":
        return
    target = "idle" if is_creator else "below_normal"
    if _CURRENT_PRIORITY_MODE == target:
        return
    try:
        p = psutil.Process(os.getpid())
        p.nice(psutil.IDLE_PRIORITY_CLASS if is_creator else psutil.BELOW_NORMAL_PRIORITY_CLASS)
        _CURRENT_PRIORITY_MODE = target
    except Exception:
        pass


def update_sleep_prevention(has_active_jobs: bool):
    """Prevents Windows sleep while jobs are running; allows normal sleep when idle."""
    if os.name != "nt":
        return
    try:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        flags = (ES_CONTINUOUS | ES_SYSTEM_REQUIRED) if has_active_jobs else ES_CONTINUOUS
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass
