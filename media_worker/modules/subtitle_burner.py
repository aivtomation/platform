import os
import re
import subprocess
from PIL import ImageFont
from .color_utils import probe_video_color, get_tonemap_filter, get_color_args

def time_to_ms(t_str: str) -> int:
    t_str = t_str.strip().replace(",", ".")
    parts = t_str.split(":")
    sec_parts = parts[2].split(".")
    return int(parts[0]) * 3600000 + int(parts[1]) * 60000 + int(sec_parts[0]) * 1000 + int(sec_parts[1])

def ms_to_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    milli = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"

def ms_to_ass_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def hex_to_ass_bgr(hex_color: str, alpha: int = 0) -> str:
    """Converts #RRGGBB to &HAABBGGRR for ASS format."""
    hex_color = (hex_color or "#FFE600").lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H{alpha:02X}{b}{g}{r}"
    return "&H0000DEFF"

def chunk_srt_to_viral_segments(srt_content: str, max_words: int = 3, max_chars: int = 20) -> str:
    """
    Splits long subtitle blocks into punchy viral segments (max 3 words, max 20 chars),
    interpolating timestamps proportionally. Preserves author's exact wording and timing.
    """
    if not srt_content or "-->" not in srt_content:
        return srt_content

    clean_srt = srt_content.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"\n\s*\n", clean_srt)
    new_blocks = []
    new_idx = 1

    for b in blocks:
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if len(lines) < 2:
            continue

        time_idx = -1
        for i, l in enumerate(lines):
            if "-->" in l:
                time_idx = i
                break
        if time_idx == -1:
            continue

        time_line = lines[time_idx]
        m = re.match(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})", time_line)
        if not m:
            continue

        start_ms = time_to_ms(m.group(1))
        end_ms = time_to_ms(m.group(2))
        total_dur = max(200, end_ms - start_ms)

        words = " ".join(lines[time_idx + 1:]).split()
        if not words:
            continue

        chunks = []
        curr_chunk = []
        curr_len = 0
        for w in words:
            w_len = len(w)
            if curr_chunk and (len(curr_chunk) >= max_words or (len(curr_chunk) >= 2 and (curr_len + 1 + w_len) > max_chars)):
                chunks.append(curr_chunk)
                curr_chunk = [w]
                curr_len = w_len
            else:
                curr_chunk.append(w)
                curr_len += (1 if curr_len > 0 else 0) + w_len
        if curr_chunk:
            chunks.append(curr_chunk)

        dur_per_chunk = total_dur / len(chunks)
        for c_idx, c_words in enumerate(chunks):
            c_start = start_ms + int(c_idx * dur_per_chunk)
            c_end = end_ms if c_idx == len(chunks) - 1 else start_ms + int((c_idx + 1) * dur_per_chunk)
            new_blocks.append(f"{new_idx}\n{ms_to_time(c_start)} --> {ms_to_time(c_end)}\n{' '.join(c_words)}")
            new_idx += 1

    return "\n\n".join(new_blocks)

def burn_subtitles_into_video(input_video: str, srt_content: str, output_video: str, typography: dict = None, min_start_ms: int = 0) -> str:
    """
    Studio-Grade Subtitle Burner (Matching UI Preview exactly):
    - Smooth rounded semi-transparent container badge (Layer 0)
    - Dynamic karaoke word-level highlighting (Layer 1)
    - Active word highlighted in user's accent color (default #FACC15 / #FFE600)
    - Inactive words crisp white (#FFFFFF) with dark outline
    - Exact vertical position (pos_y % from top)
    - Scaled typography for 1080x1920 vertical canvas
    """
    temp_dir = os.path.dirname(output_video)
    srt_path = os.path.join(temp_dir, "temp_subs.srt")
    ass_path = os.path.join(temp_dir, "temp_subs.ass")

    # 1. Prepare and chunk segments into punchy viral phrases (max 3 words, max 20 chars)
    chunked_srt = chunk_srt_to_viral_segments(srt_content, max_words=3, max_chars=20)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(chunked_srt)

    FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
    escaped_fonts_dir = os.path.abspath(FONTS_DIR).replace('\\', '/').replace(':', r'\:')
    escaped_ass = os.path.abspath(ass_path).replace('\\', '/').replace(':', r'\:')

    typo = typography or {}
    font_name = typo.get("font", "Montserrat")
    if font_name.lower() in ("fira", "fira condensed", "firasanscondensed"):
        font_name = "Fira Sans Condensed"

    # Font sizing & scaling (matching studio preview scale)
    scale_factor = float(typo.get("scale", 1.0))
    raw_font_size = float(typo.get("font_size", 16.5))
    if raw_font_size <= 25:
        font_size = max(48, int(raw_font_size * scale_factor * 3.75))
    else:
        font_size = max(48, int(raw_font_size * scale_factor * 2.55))

    # Font path for PIL bbox measurement
    font_file = os.path.join(FONTS_DIR, f"{font_name.replace(' ', '')}.ttf")
    if not os.path.exists(font_file):
        font_file = os.path.join(FONTS_DIR, "Montserrat.ttf")

    try:
        pil_font = ImageFont.truetype(font_file, font_size)
    except Exception:
        try:
            pil_font = ImageFont.truetype(os.path.join(FONTS_DIR, "Montserrat.ttf"), font_size)
        except Exception:
            pil_font = ImageFont.load_default()

    # Colors
    text_color_hex = typo.get("text_color", "#FFFFFF")
    active_color_hex = typo.get("active_color", typo.get("activeWordColor", "#FACC15"))
    stroke_color_hex = typo.get("decor_color", typo.get("stroke_color", "#000000"))
    box_color_hex = typo.get("box_color", "#000000")
    box_opacity = int(typo.get("box_opacity", 65))
    has_bg = typo.get("has_container_bg", True) and box_opacity > 0

    ass_text_color = hex_to_ass_bgr(text_color_hex, alpha=0)
    ass_active_color = hex_to_ass_bgr(active_color_hex, alpha=0)
    ass_stroke_color = hex_to_ass_bgr(stroke_color_hex, alpha=0)
    
    # ASS alpha: 0 = opaque, 255 = completely transparent
    ass_box_alpha = max(0, min(255, int(255 * (1.0 - (box_opacity / 100.0)))))
    ass_box_color = hex_to_ass_bgr(box_color_hex, alpha=ass_box_alpha)

    # Vertical position (% from top, matching UI default 72%)
    raw_pos_y = float(typo.get("pos_y", 72))
    center_y = int(1920 * (raw_pos_y / 100.0))

    # Build ASS Header
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: SubText,{font_name},{font_size},{ass_text_color},&H000000FF,{ass_stroke_color},&H80000000,-1,0,0,0,100,100,0,0,1,3.5,0,5,0,0,0,1\n"
        f"Style: SubBox,{font_name},{font_size},{ass_box_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events = []
    blocks = re.split(r"\n\s*\n", chunked_srt.strip())

    for b in blocks:
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if len(lines) < 2:
            continue

        time_idx = -1
        for i, l in enumerate(lines):
            if "-->" in l:
                time_idx = i
                break
        if time_idx == -1:
            continue

        m = re.match(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})", lines[time_idx])
        if not m:
            continue

        start_ms = time_to_ms(m.group(1))
        end_ms = time_to_ms(m.group(2))

        # Enforce rule: Subtitles must NOT show while the preview cover is displayed
        if min_start_ms > 0:
            if end_ms <= min_start_ms:
                continue
            if start_ms < min_start_ms:
                start_ms = min_start_ms

        cue_text = " ".join(lines[time_idx + 1:]).strip()
        words = cue_text.split()
        if not words:
            continue

        # Measure text width & height for container box
        try:
            bbox = pil_font.getbbox(cue_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w = len(cue_text) * int(font_size * 0.58)
            text_h = int(font_size * 1.1)

        pad_x = int(18 * (font_size / 56.0))
        pad_y = int(10 * (font_size / 56.0))
        box_w = text_w + pad_x * 2
        box_h = text_h + pad_y * 2
        r = int(16 * (font_size / 56.0))

        x1 = 540 - box_w // 2
        x2 = 540 + box_w // 2
        y1 = center_y - box_h // 2
        y2 = center_y + box_h // 2

        # Layer 0: Continuous rounded container box for entire cue duration
        if has_bg:
            bezier_path = f"m {x1+r} {y1} l {x2-r} {y1} b {x2} {y1} {x2} {y1+r} {x2} {y1+r} l {x2} {y2-r} b {x2} {y2} {x2-r} {y2} {x2-r} {y2} l {x1+r} {y2} b {x1} {y2} {x1} {y2-r} {x1} {y2-r} l {x1} {y1+r} b {x1} {y1} {x1+r} {y1} {x1+r} {y1}"
            events.append(
                f"Dialogue: 0,{ms_to_ass_time(start_ms)},{ms_to_ass_time(end_ms)},SubBox,,0,0,0,,{{\\p1}}{bezier_path}{{\\p0}}"
            )

        # Layer 1: Word-by-word karaoke highlighting
        dur = max(200, end_ms - start_ms)
        word_dur = dur / len(words)

        for w_i in range(len(words)):
            w_start = start_ms + int(w_i * word_dur)
            w_end = end_ms if w_i == len(words) - 1 else start_ms + int((w_i + 1) * word_dur)
            if w_start >= w_end:
                continue

            tagged_words = []
            for j, w in enumerate(words):
                if j == w_i:
                    tagged_words.append(f"{{\\c{ass_active_color}}}{w}{{\\c{ass_text_color}}}")
                else:
                    tagged_words.append(w)

            line_str = " ".join(tagged_words)
            events.append(
                f"Dialogue: 1,{ms_to_ass_time(w_start)},{ms_to_ass_time(w_end)},SubText,,0,0,0,,{{\\an5\\pos(540,{center_y})}}{line_str}"
            )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    # 3. Tone-mapping & FFmpeg filters
    hdr_trc = probe_video_color(input_video)
    color_args = get_color_args()

    if hdr_trc:
        tonemap_filter = get_tonemap_filter(hdr_trc)
        vf = f"{tonemap_filter},ass='{escaped_ass}':fontsdir='{escaped_fonts_dir}',format=yuv420p"
    else:
        vf = f"ass='{escaped_ass}':fontsdir='{escaped_fonts_dir}',format=yuv420p"

    # 4. Burn subtitles into video (CRF 20 high quality)
    cmd_burn = [
        "ffmpeg", "-y",
        "-i", os.path.abspath(input_video),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        *color_args,
        "-c:a", "copy",
        os.path.abspath(output_video)
    ]

    try:
        subprocess.run(cmd_burn, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_video
    except Exception as e:
        print(f"Subtitle burn error (trying audio transcode fallback): {e}")
        try:
            cmd_burn_fb = [
                "ffmpeg", "-y",
                "-i", os.path.abspath(input_video),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                *color_args,
                "-c:a", "aac",
                "-b:a", "192k",
                os.path.abspath(output_video)
            ]
            subprocess.run(cmd_burn_fb, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_video
        except Exception as e2:
            print(f"Subtitle burn fallback error: {e2}")
            return input_video
