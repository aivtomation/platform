"""
Aivtomation Worker Job Registry (Python Mirror of crossposting/app/worker_job_registry.php).
Defines resource classes, slot budgets, and concurrency limits for Worker Nodes.
"""

JOB_REGISTRY = {
    "video_montage": {
        "project": "crossposting",
        "class": "gpu_heavy",
        "priority": 20,
        "timeout": 600,
    },
    "unsynth_video": {
        "project": "production",
        "class": "gpu_heavy",
        "priority": 30,
        "timeout": 900,
    },
    "unsynth_audio": {
        "project": "production",
        "class": "io_light",
        "priority": 25,
        "timeout": 180,
    },
    "compress_telegram": {
        "project": "crossposting",
        "class": "cpu_heavy",
        "priority": 15,
        "timeout": 240,
    },
    "stt": {
        "project": "crossposting",
        "class": "gpu_light",
        "priority": 10,
        "timeout": 180,
    },
    "social_download": {
        "project": "idea_hub",
        "class": "io_light",
        "priority": 10,
        "timeout": 180,
    },
    "trim_threads": {
        "project": "crossposting",
        "class": "io_light",
        "priority": 15,
        "timeout": 180,
    },
}

CLASS_SLOTS_NORMAL = {
    "gpu_heavy": 1,
    "cpu_heavy": 1,
    "gpu_light": 1,
    "io_light": 3,
}

CLASS_SLOTS_CREATOR = {
    "gpu_heavy": 1,   # Allowed locally in throttled mode (user chose option 2)
    "cpu_heavy": 1,   # Allowed locally in throttled mode (-threads 4, IDLE priority)
    "gpu_light": 1,   # Only if >= 3 GB VRAM free
    "io_light": 2,
}


def get_job_spec(job_type: str) -> dict:
    return JOB_REGISTRY.get(job_type or "video_montage", {
        "project": "crossposting",
        "class": "gpu_heavy",
        "priority": 50,
        "timeout": 300,
    })
