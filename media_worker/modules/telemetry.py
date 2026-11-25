"""
Hardware Telemetry Collector for Aivtomation Worker Nodes.
Collects CPU (total + per-core), RAM, Disk, NVIDIA GPU (util, NVENC, VRAM, temp, power),
and Ryzen CPU temperature via LibreHardwareMonitor (HTTP :8085 or WMI root\\LibreHardwareMonitor).
"""

import os
import json
import time
import subprocess
import urllib.request
import psutil


_LAST_GPU_CACHE = {"ts": 0.0, "data": {}}
_LAST_CPU_TEMP_CACHE = {"ts": 0.0, "val": None}


def _query_nvidia_smi() -> dict:
    now = time.time()
    if now - _LAST_GPU_CACHE["ts"] < 4.0 and _LAST_GPU_CACHE["data"]:
        return _LAST_GPU_CACHE["data"]

    info = {
        "gpu_name": None,
        "gpu_util": None,
        "nvenc_util": None,
        "vram_used_mb": None,
        "vram_total_mb": None,
        "gpu_temp": None,
        "gpu_power_w": None,
    }
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,utilization.encoder,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            creationflags=flags,
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
            if len(parts) >= 7:
                info["gpu_name"] = parts[0]
                info["gpu_util"] = float(parts[1]) if parts[1] not in ("", "[N/A]") else None
                info["nvenc_util"] = float(parts[2]) if parts[2] not in ("", "[N/A]") else None
                info["vram_used_mb"] = float(parts[3]) if parts[3] not in ("", "[N/A]") else None
                info["vram_total_mb"] = float(parts[4]) if parts[4] not in ("", "[N/A]") else None
                info["gpu_temp"] = float(parts[5]) if parts[5] not in ("", "[N/A]") else None
                info["gpu_power_w"] = float(parts[6]) if parts[6] not in ("", "[N/A]") else None
    except Exception:
        pass

    _LAST_GPU_CACHE["ts"] = now
    _LAST_GPU_CACHE["data"] = info
    return info


def _extract_lhm_cpu_temp_from_json(node: dict):
    """Recursively searches LibreHardwareMonitor JSON tree for CPU Package / Tctl / Core Max temp."""
    if not isinstance(node, dict):
        return None
    text = str(node.get("Text", ""))
    val_str = str(node.get("Value", ""))
    if "°C" in val_str and any(k in text for k in ("Core (Tctl/Tdie)", "CPU Package", "Tctl/Tdie", "CCD1", "Core Max")):
        try:
            num = float(val_str.replace("°C", "").replace(",", ".").strip().split()[0])
            if 10.0 <= num <= 125.0:
                return round(num, 1)
        except Exception:
            pass
    for child in node.get("Children", []) or []:
        found = _extract_lhm_cpu_temp_from_json(child)
        if found is not None:
            return found
    return None


def _query_cpu_temperature() -> float | None:
    now = time.time()
    if now - _LAST_CPU_TEMP_CACHE["ts"] < 8.0:
        return _LAST_CPU_TEMP_CACHE["val"]

    temp = None
    # 1. Try LibreHardwareMonitor HTTP web server (http://127.0.0.1:8085/data.json)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/data.json", timeout=0.8) as resp:
            tree = json.loads(resp.read().decode("utf-8", errors="ignore"))
            temp = _extract_lhm_cpu_temp_from_json(tree)
    except Exception:
        pass

    # 2. Fallback: Try LibreHardwareMonitor WMI namespace via PowerShell
    if temp is None and os.name == "nt":
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            ps = (
                "Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction Stop "
                "| Where-Object {$_.SensorType -eq 'Temperature' -and $_.Name -match 'Tctl|Package|CPU'} "
                "| Select-Object -First 1 -ExpandProperty Value"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2,
                creationflags=flags,
            )
            if res.returncode == 0 and res.stdout.strip():
                val = float(res.stdout.strip().replace(",", "."))
                if 10.0 <= val <= 125.0:
                    temp = round(val, 1)
        except Exception:
            pass

    _LAST_CPU_TEMP_CACHE["ts"] = now
    _LAST_CPU_TEMP_CACHE["val"] = temp
    return temp


def collect_hardware_telemetry(disk_path: str = None) -> dict:
    if disk_path is None:
        disk_path = os.path.abspath(os.sep)

    per_core = psutil.cpu_percent(interval=None, percpu=True)
    cpu_total = round(sum(per_core) / max(1, len(per_core)), 1) if per_core else round(psutil.cpu_percent(interval=None), 1)
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(disk_path)
    gpu = _query_nvidia_smi()
    cpu_temp = _query_cpu_temperature()

    return {
        "cpu_total": cpu_total,
        "cpu_per_core": [round(x, 1) for x in per_core],
        "cpu_cores_count": len(per_core),
        "ram_used_gb": round((vm.total - vm.available) / (1024 ** 3), 2),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_pct": round(vm.percent, 1),
        "disk_free_gb": round(du.free / (1024 ** 3), 1),
        "disk_total_gb": round(du.total / (1024 ** 3), 1),
        "cpu_temp": cpu_temp,
        "gpu_name": gpu.get("gpu_name"),
        "gpu_util": gpu.get("gpu_util"),
        "nvenc_util": gpu.get("nvenc_util"),
        "vram_used_mb": gpu.get("vram_used_mb"),
        "vram_total_mb": gpu.get("vram_total_mb"),
        "gpu_temp": gpu.get("gpu_temp"),
        "gpu_power_w": gpu.get("gpu_power_w"),
    }
