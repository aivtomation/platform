"""
Local Cobalt API v10 adapter for fast direct CDN/stream extraction.
Used as Level 2 fallback/offloader when yt-dlp fails or lacks a separate audio stream.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import requests

COBALT_API_URL = "http://127.0.0.1:9000/"


def _is_public_cdn_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https"):
            return False
        if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1") or host.startswith("192.168.") or host.startswith("10."):
            return False
        return True
    except Exception:
        return False


def is_cobalt_available(timeout: float = 0.8) -> bool:
    try:
        res = requests.get(COBALT_API_URL, timeout=timeout)
        return res.status_code < 500
    except Exception:
        return False


def _call_cobalt(target_url: str, download_mode: str = "auto", video_quality: str = "1080", timeout: int = 12) -> Dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "url": target_url,
        "downloadMode": download_mode,
        "videoQuality": str(video_quality),
        "audioFormat": "mp3",
        "filenameStyle": "basic",
    }
    try:
        res = requests.post(COBALT_API_URL, json=payload, headers=headers, timeout=timeout)
        data = res.json() if res.content else {}
        if res.status_code >= 400 or data.get("status") == "error":
            err = data.get("error", {})
            code = err.get("code") if isinstance(err, dict) else str(err or res.status_code)
            return {"ok": False, "error": f"Cobalt error: {code}"}
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def resolve_with_cobalt(target_url: str, want_video: bool = True, want_audio: bool = True, video_quality: str = "1080") -> Dict[str, Any]:
    """
    Resolves direct video, audio, and carousel media URLs via local Cobalt API.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "video_url": "",
        "audio_url": "",
        "videos": [],
        "photos": [],
        "error": "",
    }

    if want_video:
        v_res = _call_cobalt(target_url, download_mode="auto", video_quality=video_quality)
        if v_res.get("ok"):
            data = v_res["data"]
            status = data.get("status")
            if status in ("tunnel", "redirect") and data.get("url"):
                u = str(data["url"])
                if _is_public_cdn_url(u):
                    result["video_url"] = u
                    result["videos"].append({"index": 1, "url": u, "thumbnail": None})
            elif status == "picker" and isinstance(data.get("picker"), list):
                for item in data["picker"]:
                    if not isinstance(item, dict) or not item.get("url"):
                        continue
                    itype = item.get("type", "")
                    u = str(item["url"])
                    if not _is_public_cdn_url(u):
                        continue
                    if itype == "photo":
                        result["photos"].append(u)
                    else:
                        result["videos"].append({
                            "index": len(result["videos"]) + 1,
                            "url": u,
                            "thumbnail": item.get("thumb"),
                        })
                        if not result["video_url"]:
                            result["video_url"] = u
        else:
            result["error"] = v_res.get("error", "")

    if want_audio:
        a_res = _call_cobalt(target_url, download_mode="audio", video_quality=video_quality)
        if a_res.get("ok"):
            data = a_res["data"]
            if data.get("status") in ("tunnel", "redirect") and data.get("url"):
                u = str(data["url"])
                if _is_public_cdn_url(u):
                    result["audio_url"] = u
        elif not result["error"]:
            result["error"] = a_res.get("error", "")

    result["ok"] = bool(result["video_url"] or result["audio_url"] or result["photos"])
    return result
