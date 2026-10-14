import os
import subprocess
import json
import httpx
from openai import OpenAI
from config import OPENAI_API_KEY, GEMINI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client())

def extract_audio_from_video(video_path: str, output_wav_path: str) -> str:
    """
    Extract 16kHz mono WAV audio from any video container using hardware/CLI FFmpeg in seconds.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_wav_path

def transcribe_audio_to_srt(wav_path: str, language: str = "uk") -> dict:
    """
    Transcribe audio via OpenAI Whisper API with verbose JSON response (including word timestamps).
    Returns dict: {'srt': str, 'words': list, 'text': str, 'segments': list}
    """
    with open(wav_path, "rb") as f:
        transcript = openai_client.audio.transcriptions.create(
            file=f,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"]
        )

    # Convert segments to SubRip (.srt) format
    srt_lines = []
    idx = 1
    for seg in getattr(transcript, "segments", []):
        start_sec = seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0)
        end_sec = seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0)
        text = (seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")).strip()

        start_time = _format_timestamp(start_sec)
        end_time = _format_timestamp(end_sec)

        srt_lines.append(f"{idx}\n{start_time} --> {end_time}\n{text}\n")
        idx += 1

    srt_content = "\n".join(srt_lines).strip()
    words = getattr(transcript, "words", []) or []
    full_text = getattr(transcript, "text", "").strip()

    return {
        "srt": srt_content,
        "text": full_text,
        "words": words,
        "segments": getattr(transcript, "segments", []) or []
    }

def _format_timestamp(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    secs = int(seconds)
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    s = secs % 60
    return f"{hours:02d}:{minutes:02d}:{s:02d},{millis:03d}"
