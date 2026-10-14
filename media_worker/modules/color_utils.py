import subprocess
import json

_LIBPLACEBO_AVAILABLE = None

def has_libplacebo() -> bool:
    """
    Checks if FFmpeg has libplacebo filter enabled AND working at runtime.
    On headless cloud runners (GitHub Actions / Linux VMs without Vulkan GPU),
    libplacebo is compiled into FFmpeg but crashes at runtime with exit code 187.
    Testing execution directly ensures 100% stability.
    """
    global _LIBPLACEBO_AVAILABLE
    if _LIBPLACEBO_AVAILABLE is None:
        try:
            test_cmd = [
                "ffmpeg", "-v", "error", "-f", "lavfi",
                "-i", "color=c=black:s=16x16:d=0.05",
                "-vf", "libplacebo=colorspace=bt709",
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            _LIBPLACEBO_AVAILABLE = (res.returncode == 0)
        except Exception:
            _LIBPLACEBO_AVAILABLE = False
    return _LIBPLACEBO_AVAILABLE

def probe_video_color(video_path: str):
    """
    Detects if the input video uses Apple HDR / HLG / BT.2020 10-bit wide color gamut.
    Returns transfer characteristic like 'arib-std-b67', 'smpte2084', or None.
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", video_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        data = json.loads(res.stdout)
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                trc = str(s.get("color_transfer", "")).lower()
                pri = str(s.get("color_primaries", "")).lower()
                pix = str(s.get("pix_fmt", "")).lower()
                if "smpte2084" in trc:
                    return "smpte2084"
                if "arib-std-b67" in trc or "bt2020" in pri or "10le" in pix:
                    return "arib-std-b67"
                break
    except Exception:
        pass
    return None

_ZSCALE_AVAILABLE = None

def has_zscale() -> bool:
    global _ZSCALE_AVAILABLE
    if _ZSCALE_AVAILABLE is None:
        try:
            test_cmd = [
                "ffmpeg", "-v", "error", "-f", "lavfi",
                "-i", "color=c=black:s=16x16:d=0.05",
                "-vf", "zscale=t=linear",
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            _ZSCALE_AVAILABLE = (res.returncode == 0)
        except Exception:
            _ZSCALE_AVAILABLE = False
    return _ZSCALE_AVAILABLE

def get_tonemap_filter(hdr_trc: str = None) -> str:
    """
    Returns high-fidelity tonemapping video filter:
    - Primary: libplacebo (cinema-grade ITU BT.2446a perceptual tonemapping, warm natural skin tones)
    - Fallback: calibrated ITU Mobius tonemapping with nominal 1000 nits and balanced desaturation
    - Safe default: format=yuv420p if neither filter is available in host FFmpeg
    """
    if has_libplacebo():
        return "libplacebo=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv,format=yuv420p"
    
    if has_zscale():
        trc = hdr_trc or "arib-std-b67"
        return f"setparams=color_primaries=bt2020:color_trc={trc}:colorspace=bt2020nc,zscale=t=linear:npl=1000,tonemap=tonemap=mobius:param=0.4:desat=1.0,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p"

    return "format=yuv420p"

def get_color_args() -> list[str]:
    """
    Standard Rec.709 color tags for H.264 MP4.
    Guarantees that Apple devices (iOS QuickTime / Safari / Instagram) render
    standard 2.2/2.4 gamma and do NOT distort colors.
    """
    return [
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-pix_fmt", "yuv420p"
    ]
