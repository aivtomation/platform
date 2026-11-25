import os
import subprocess
import json
import time
import requests
import httpx
from openai import OpenAI
from config import OPENAI_API_KEY, GEMINI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY, http_client=httpx.Client())

OPENWHISPR_SERVER_URL = os.getenv("OPENWHISPR_SERVER_URL", "http://127.0.0.1:8178")
OPENWHISPR_MODEL_PATH = r"C:\Users\alexe\.cache\openwhispr\whisper-models\ggml-medium.bin"
OPENWHISPR_BIN_PATH = r"C:\Users\alexe\AppData\Roaming\open-whispr\bin\whisper-cuda\whisper-server-win32-x64-cuda.exe"

def ensure_openwhispr_server() -> bool:
    """
    Checks if OpenWhispr CUDA Server is responsive on port 8178.
    If not running, attempts to start it in the background using RTX 3080 GPU CUDA.
    """
    try:
        r = requests.get(f"{OPENWHISPR_SERVER_URL}/", timeout=1.0)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    if os.path.exists(OPENWHISPR_BIN_PATH) and os.path.exists(OPENWHISPR_MODEL_PATH):
        try:
            print("🚀 [STT] Автозапуск сервера OpenWhispr CUDA на порту 8178...")
            cmd = [
                OPENWHISPR_BIN_PATH,
                "--model", OPENWHISPR_MODEL_PATH,
                "--host", "127.0.0.1",
                "--port", "8178",
                "--threads", "12",
                "--language", "auto",
                "--max-len", "4096"
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            return True
        except Exception as e:
            print(f"⚠️ [STT] Не вдалося запустити OpenWhispr CUDA сервер: {e}")
    return False

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

def chunk_words_to_segments(words: list, raw_segments: list = None, min_words: int = 2, max_words: int = 6) -> list:
    # HARD CLAMP: Absolute maximum 6 words per segment across entire system
    max_words = min(6, max_words)
    min_words = min(2, min_words)
    """
    Groups words into balanced subtitle segments:
    - 4 to 8 words per segment
    - Maximum 2 lines of text per segment
    - Natural breaks at punctuation (. , ! ? ; : —) and pauses
    """
    cleaned_words = []
    if words:
        for w in words:
            w_text = (w.get("word", "") if isinstance(w, dict) else getattr(w, "word", "")).strip()
            if not w_text:
                continue
            w_start = float(w.get("start", 0.0) if isinstance(w, dict) else getattr(w, "start", 0.0))
            w_end = float(w.get("end", 0.0) if isinstance(w, dict) else getattr(w, "end", 0.0))
            cleaned_words.append({
                "word": w_text,
                "start": round(w_start, 2),
                "end": round(max(w_end, w_start + 0.1), 2)
            })

    if not cleaned_words and raw_segments:
        for s in raw_segments:
            s_start = float(s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0))
            s_end = float(s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0))
            s_text = (s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "")).strip()
            s_tokens = s_text.split()
            if not s_tokens:
                continue
            step = (s_end - s_start) / max(1, len(s_tokens))
            for i, sw in enumerate(s_tokens):
                cleaned_words.append({
                    "word": sw,
                    "start": round(s_start + i * step, 2),
                    "end": round(min(s_end, s_start + (i + 1) * step), 2)
                })

    if not cleaned_words:
        return []

    total = len(cleaned_words)
    if total <= max_words:
        n = total
        seg_words = [w["word"] for w in cleaned_words]
        if n <= 3:
            text = " ".join(seg_words)
        else:
            mid = (n + 1) // 2
            text = " ".join(seg_words[:mid]) + "\n" + " ".join(seg_words[mid:])
        return [{
            "id": 1,
            "start": cleaned_words[0]["start"],
            "end": cleaned_words[-1]["end"],
            "text": text,
            "words": cleaned_words
        }]

    segments = []
    curr = []
    for i, w in enumerate(cleaned_words):
        curr.append(w)
        rem = total - (i + 1)
        word_text = w["word"]
        has_punct = any(word_text.endswith(p) for p in [".", "!", "?", ";", ",", ":", "—"])
        is_pause = False
        if i + 1 < total:
            gap = cleaned_words[i + 1]["start"] - w["end"]
            if gap >= 0.45:
                is_pause = True

        # Prevent leaving an orphaned tiny chunk at the end
        if rem > 0 and rem < min_words and len(curr) + rem <= max_words:
            continue

        if len(curr) >= max_words or (len(curr) >= min_words and (has_punct or is_pause)):
            segments.append(curr)
            curr = []

    if curr:
        if len(curr) < min_words and segments and len(segments[-1]) + len(curr) <= max_words:
            segments[-1].extend(curr)
        elif len(curr) < min_words and segments:
            combined = segments[-1] + curr
            half = len(combined) // 2
            segments[-1] = combined[:half]
            segments.append(combined[half:])
        else:
            segments.append(curr)

    # HARD CLAMP: Guarantee that NO segment ever has more than max_words (6)
    clamped_segments = []
    for seg in segments:
        if len(seg) > max_words:
            num_sub = (len(seg) + max_words - 1) // max_words
            c_size = (len(seg) + num_sub - 1) // num_sub
            for sub_i in range(0, len(seg), c_size):
                sub = seg[sub_i:sub_i + c_size]
                if sub:
                    clamped_segments.append(sub)
        else:
            clamped_segments.append(seg)
    segments = clamped_segments

    result_cues = []
    for idx, seg in enumerate(segments, start=1):
        seg_words = [w["word"] for w in seg]
        n = len(seg_words)
        if n <= 3:
            text = " ".join(seg_words)
        else:
            mid = (n + 1) // 2
            text = " ".join(seg_words[:mid]) + "\n" + " ".join(seg_words[mid:])

        start = seg[0]["start"]
        end = seg[-1]["end"]
        if end <= start:
            end = round(start + 0.6, 2)

        result_cues.append({
            "id": idx,
            "start": start,
            "end": end,
            "text": text,
            "words": seg
        })

    return result_cues

def transcribe_with_openwhispr_cuda(audio_path: str, language: str = "uk") -> dict:
    """
    Priority 1: Superfast local GPU CUDA transcription via OpenWhispr server (ggml-medium.bin).
    Transcribes a 1-min video in ~2.8 seconds with word timestamps and zero API cost.
    """
    if not ensure_openwhispr_server():
        raise RuntimeError("OpenWhispr CUDA server is offline")

    t_start = time.time()
    with open(audio_path, "rb") as f:
        data = {
            "response_format": "verbose_json",
            "temperature": "0.0",
        }
        if language and language != "auto":
            data["language"] = language

        resp = requests.post(f"{OPENWHISPR_SERVER_URL}/inference", files={"file": f}, data=data, timeout=60)
        resp.raise_for_status()
        raw = resp.json()

    dur = round(time.time() - t_start, 2)
    print(f"✅ [STT Пріоритет 1 - OpenWhispr CUDA] Розпізнано за {dur}с на GPU RTX 3080!")

    full_text = raw.get("text", "").strip()
    raw_segments = raw.get("segments", [])

    all_words = []
    for seg in raw_segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))

        # Merge sub-word tokens from whisper.cpp into whole words
        curr = None
        for token in seg.get("words", []):
            t_text = token.get("word", "")
            w_s = float(token.get("start", start))
            w_e = float(token.get("end", end))
            if t_text.startswith(" ") or curr is None:
                if curr and curr["word"].strip():
                    all_words.append(curr)
                curr = {"word": t_text.strip(), "start": round(w_s, 2), "end": round(w_e, 2)}
            else:
                curr["word"] += t_text
                curr["end"] = round(w_e, 2)
        if curr and curr["word"].strip():
            all_words.append(curr)

    # Balanced Segmentation: 4-8 words per segment, maximum 2 lines per segment
    cues = chunk_words_to_segments(all_words, raw_segments=raw_segments, min_words=2, max_words=6)
    srt_lines = []
    for c in cues:
        s_time = _format_timestamp(c["start"])
        e_time = _format_timestamp(c["end"])
        srt_lines.append(f"{c['id']}\n{s_time} --> {e_time}\n{c['text']}\n")

    return {
        "success": True,
        "engine": "openwhispr_cuda_rtx3080",
        "text": full_text,
        "srt": "\n".join(srt_lines).strip(),
        "cues": cues,
        "words": all_words,
        "segments": raw_segments,
        "cost_uah": 0.00
    }

def transcribe_audio_hybrid(audio_path: str, language: str = "uk") -> dict:
    """
    Two-Tier Hybrid Speech-to-Text Architecture:
    1. Priority 1 (Local Model via OpenWhispr CUDA):
       Uses user's ready model C:\\Users\\alexe\\.cache\\openwhispr\\whisper-models\\ggml-medium.bin (1.5 GB).
       Hardware accelerated on NVIDIA GeForce RTX 3080 (~2.8s render, 0.00 грн, 0 токенів).
    2. Priority 2 (Cloud Fallback):
       If local server is unreachable, gracefully falls back to OpenAI Whisper Cloud API.
    """
    # -------------------------------------------------------------
    # PRIORITY 1: LOCAL OPENWHISPR CUDA MODEL
    # -------------------------------------------------------------
    try:
        print("🎙️ [STT Пріоритет 1] Запуск OpenWhispr CUDA (ggml-medium.bin)...")
        return transcribe_with_openwhispr_cuda(audio_path, language=language)
    except Exception as local_err:
        print(f"⚠️ [STT Пріоритет 1] Помилка OpenWhispr CUDA ({local_err})")
        print("🔄 [STT Пріоритет 2] Перемикання на хмарний OpenAI Whisper Cloud API...")

    # -------------------------------------------------------------
    # PRIORITY 2: OPENAI WHISPER CLOUD API FALLBACK
    # -------------------------------------------------------------
    try:
        print("☁️ [STT Пріоритет 2] Відправка аудіо до OpenAI Whisper Cloud API...")
        t_cloud0 = time.time()
        with open(audio_path, "rb") as f:
            kwargs = {
                "file": f,
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment", "word"]
            }
            if language and language != "auto":
                kwargs["language"] = language
            transcript = openai_client.audio.transcriptions.create(**kwargs)
        duration = round(time.time() - t_cloud0, 2)
        print(f"✅ [STT Пріоритет 2] Хмарне розпізнавання Whisper завершено за {duration}с!")

        full_text = getattr(transcript, "text", "").strip()
        segments = getattr(transcript, "segments", []) or []
        words = getattr(transcript, "words", []) or []

        # Balanced Segmentation: 4-8 words per segment, maximum 2 lines per segment
        cues = chunk_words_to_segments(words, raw_segments=segments, min_words=2, max_words=6)
        srt_lines = []
        for c in cues:
            s_time = _format_timestamp(c["start"])
            e_time = _format_timestamp(c["end"])
            srt_lines.append(f"{c['id']}\n{s_time} --> {e_time}\n{c['text']}\n")

        return {
            "success": True,
            "engine": "openai_whisper_cloud",
            "text": full_text,
            "srt": "\n".join(srt_lines).strip(),
            "cues": cues,
            "words": words,
            "segments": segments,
            "cost_uah": 0.25
        }
    except Exception as cloud_err:
        print(f"❌ [STT Пріоритет 2] Помилка хмарного Whisper API: {cloud_err}")
        raise cloud_err

def transcribe_audio_to_srt(wav_path: str, language: str = "uk") -> dict:
    return transcribe_audio_hybrid(wav_path, language=language)

def _format_timestamp(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    secs = int(seconds)
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    s = secs % 60
    return f"{hours:02d}:{minutes:02d}:{s:02d},{millis:03d}"
