import os
import re
import subprocess
from .color_utils import probe_video_color, get_tonemap_filter, get_color_args


def remove_silence_from_video(input_video: str, output_video: str, min_silence_len: float = 0.45, silence_thresh_db: int = -30) -> str:
    """
    Detects silent gaps longer than min_silence_len (e.g. 0.45s) using FFmpeg silencedetect,
    and stitches together the active speech segments without silent pauses (JumpCut effect).
    """
    # 1. Detect silence intervals
    cmd_detect = [
        "ffmpeg", "-i", input_video,
        "-af", f"silencedetect=noise={silence_thresh_db}dB:d={min_silence_len}",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd_detect, stderr=subprocess.PIPE, text=True, check=True)
    stderr = res.stderr

    silence_starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9\.]+)", stderr)]
    silence_ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9\.]+)", stderr)]

    # If no silence detected or mismatch, return original
    if not silence_starts or len(silence_starts) != len(silence_ends):
        return input_video

    # Get total video duration
    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video]
    dur_res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
    try:
        total_duration = float(dur_res.stdout.strip())
    except:
        return input_video

    # 2. Build speech segments (inverting silence)
    speech_segments = []
    current_time = 0.0

    for s_start, s_end in zip(silence_starts, silence_ends):
        # Keep a tiny 0.05s buffer around words so cuts feel natural and don't cut off consonants
        seg_start = current_time
        seg_end = max(current_time, s_start + 0.05)
        if seg_end - seg_start > 0.15:
            speech_segments.append((seg_start, seg_end))
        current_time = max(current_time, s_end - 0.05)

    if total_duration - current_time > 0.2:
        speech_segments.append((current_time, total_duration))

    if not speech_segments:
        return input_video

    # 3. Create complex filter for smooth concatenation
    filter_parts = []
    concat_inputs = []
    for i, (start, end) in enumerate(speech_segments):
        filter_parts.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}];")
        filter_parts.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}];")
        concat_inputs.append(f"[v{i}][a{i}]")

    hdr_trc = probe_video_color(input_video)
    if hdr_trc:
        tonemap_vf = get_tonemap_filter(hdr_trc)
        v_filter = f"[raw_v]{tonemap_vf}[outv]"
    else:
        v_filter = "[raw_v]format=yuv420p[outv]"

    num_segments = len(speech_segments)
    filter_str = "".join(filter_parts) + "".join(concat_inputs) + f"concat=n={num_segments}:v=1:a=1[raw_v][outa];{v_filter}"

    cmd_cut = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        *get_color_args(),
        "-c:a", "aac",
        "-b:a", "192k",
        output_video
    ]

    try:
        subprocess.run(cmd_cut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_video
    except Exception as e:
        print(f"Silence removal fallback: {e}")
        return input_video
