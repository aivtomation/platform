import os
import subprocess
import requests
import re
from PIL import Image, ImageDraw, ImageFont
from config import OPENAI_API_KEY
from .color_utils import probe_video_color, get_tonemap_filter, get_color_args

def hex_to_rgb(hex_str: str, default=(0, 0, 0)):
    try:
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 3:
            hex_str = "".join([c*2 for c in hex_str])
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return default

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')

FONT_MAP = {
    'montserrat': 'Montserrat.ttf',
    'oswald': 'Oswald.ttf',
    'rubik': 'Rubik.ttf',
    'unbounded': 'Unbounded.ttf',
    'inter': 'Inter.ttf',
    'fira': 'FiraSansCondensed.ttf',
    'fira condensed': 'FiraSansCondensed.ttf',
    'manrope': 'Manrope.ttf',
    'comfortaa': 'Comfortaa.ttf',
}

FONT_DEFAULT_WEIGHTS = {
    'montserrat': 900,
    'oswald': 700,
    'rubik': 800,
    'unbounded': 800,
    'inter': 900,
    'fira': 900,
    'fira condensed': 900,
    'manrope': 800,
    'comfortaa': 700,
}

def render_cover_with_pillow(frame_path: str, cover_image_path: str, text: str, typography: dict = None, overlay_png_path: str = None):
    """
    Renders high-impact viral cover text on the captured video frame using Pillow:
    - Supports audited Google Fonts (Montserrat, Oswald, Rubik, etc.) with bold weights (900/800)
    - True 1080x1920 scaled typography matching Studio WYSIWYG monitor
    - Supports decor_mode (stroke or rounded box), colors, and positions
    - Also outputs transparent overlay PNG for seamless video overlay
    """
    typo = typography or {}
    font_name = (typo.get("font") or "montserrat").lower().strip()
    font_file = FONT_MAP.get(font_name, "Montserrat.ttf")
    font_path = os.path.join(FONTS_DIR, font_file)
    if not os.path.exists(font_path):
        font_path = os.path.join(FONTS_DIR, "Montserrat.ttf")
    if not os.path.exists(font_path):
        linux_font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        win_font = "C:/Windows/Fonts/arialbd.ttf"
        font_path = linux_font if os.path.exists(linux_font) else win_font

    text_color = typo.get("text_color", "#FACC15")
    decor_mode = typo.get("decor_mode", "box")
    decor_color = typo.get("decor_color", "#2563EB")
    decor_rgb = hex_to_rgb(decor_color, (37, 99, 235))
    border_color = typo.get("border_color") or typo.get("bg_stroke_color") or "#FFFFFF"
    border_rgb = hex_to_rgb(border_color, (255, 255, 255))
    text_stroke_color = typo.get("text_stroke_color", "#000000")

    # Word wrapping: max width ~780px so text fits cleanly on 1080px canvas without clipping
    raw_lines = [l.strip().upper() for l in text.strip().split("\n") if l.strip()]
    if not raw_lines:
        raw_lines = ["ВАЖЛИВО ЗНАТИ!"]

    # Initial font setup
    requested_size = float(typo.get("font_size", 14))
    scale = float(typo.get("scale", 1.0))
    if requested_size <= 25:
        base_font_size = max(42, int(requested_size * scale * 3.692))
    else:
        base_font_size = max(44, int(requested_size * scale * 1.85))
    weight = int(typo.get("weight") or FONT_DEFAULT_WEIGHTS.get(font_name, 900))

    try:
        font = ImageFont.truetype(font_path, base_font_size)
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass
    except Exception:
        font = ImageFont.load_default()

    dummy_img = Image.new("RGB", (1080, 1920))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # Auto-wrap words (max width ~820px to fit on 1080px canvas cleanly)
    wrapped_lines = []
    max_line_width = int(820 * scale)
    for r_line in raw_lines:
        words = r_line.split()
        curr_words = []
        for w in words:
            candidate = " ".join(curr_words + [w])
            bbox = dummy_draw.textbbox((0, 0), candidate, font=font)
            if (bbox[2] - bbox[0]) <= max_line_width or not curr_words:
                curr_words.append(w)
            else:
                wrapped_lines.append(" ".join(curr_words))
                curr_words = [w]
        if curr_words:
            wrapped_lines.append(" ".join(curr_words))

    lines = wrapped_lines[:4]

    line_heights = []
    line_widths = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    pos_y_pct = float(typo.get("pos_y", 18))
    target_center_y = int(1920 * (pos_y_pct / 100.0))

    line_gap = int(base_font_size * 0.20)
    pad_x = int(36 * scale)
    pad_y = int(18 * scale)
    box_radius = int(28 * scale)
    stroke_width = int(float(typo.get("stroke_width", 4)))

    total_text_h = sum(line_heights) + (len(lines) - 1) * line_gap
    card_w = max(line_widths) + (pad_x * 2)
    card_h = total_text_h + (pad_y * 2)

    card_left = (1080 - card_w) // 2
    card_top = max(40, target_center_y - (card_h // 2))
    card_right = card_left + card_w
    card_bottom = card_top + card_h

    def draw_elements(d):
        if decor_mode in ("box", "badge"):
            # Subtle dark drop-shadow for 3D depth
            d.rounded_rectangle(
                [card_left + 4, card_top + 6, card_right + 4, card_bottom + 6],
                radius=box_radius,
                fill=(0, 0, 0, 110)
            )
            # Draw unified card container with rounded corners and white outline
            d.rounded_rectangle(
                [card_left, card_top, card_right, card_bottom],
                radius=box_radius,
                fill=(*decor_rgb, 255),
                outline=(*border_rgb, 255),
                width=5
            )

        curr_y = card_top + pad_y
        for i, line in enumerate(lines):
            w = line_widths[i]
            x = (1080 - w) // 2
            d.text(
                (x, curr_y),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=text_stroke_color
            )
            curr_y += line_heights[i] + line_gap

    # 1. Render thumbnail with author frame
    if frame_path and os.path.exists(frame_path):
        with Image.open(frame_path) as img:
            img = img.convert("RGB")
            if img.size != (1080, 1920):
                img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(img)
            draw_elements(draw)
            img.save(cover_image_path, "JPEG", quality=95)

    # 2. Render transparent overlay PNG
    if overlay_png_path:
        ovl_img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        ovl_draw = ImageDraw.Draw(ovl_img)
        draw_elements(ovl_draw)
        ovl_img.save(overlay_png_path, "PNG")

def generate_and_apply_cover(input_video: str, output_video: str, caption_or_topic: str = "", custom_cover_text: str = "", frame_source_video: str = None, duration_sec: float = 2.0, typography: dict = None) -> str:
    """
    1. Extracts high-quality screenshot frame of author/hero from second 1.5.
    2. Renders cover text positioned 20% below center (Y=1344).
    3. Overlays this cover graphic onto the video for the exact first duration_sec (default 2.0s).
       Original video motion and audio play uninterrupted; subtitles are suppressed during this time.
    """
    temp_dir = os.path.dirname(output_video)
    frame_path = os.path.join(temp_dir, "author_frame.jpg")
    cover_image_path = os.path.join(temp_dir, "final_cover.jpg")
    cover_overlay_path = os.path.join(temp_dir, "cover_overlay.png")

    src_for_frame = frame_source_video if (frame_source_video and os.path.exists(frame_source_video)) else input_video

    # Step 1: Capture clear frame from second 1.5
    hdr_trc = probe_video_color(src_for_frame)
    if hdr_trc:
        vf_frame = get_tonemap_filter(hdr_trc)
        cmd_frame = [
            "ffmpeg", "-y",
            "-ss", "00:00:01.5",
            "-i", src_for_frame,
            "-vf", vf_frame,
            "-vframes", "1",
            "-q:v", "2",
            frame_path
        ]
    else:
        cmd_frame = [
            "ffmpeg", "-y",
            "-ss", "00:00:01.5",
            "-i", src_for_frame,
            "-vframes", "1",
            "-q:v", "2",
            frame_path
        ]
    subprocess.run(cmd_frame, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # Step 2: Determine Cover Headline
    headline_text = ""
    if custom_cover_text and custom_cover_text.strip():
        headline_text = custom_cover_text.strip()
    elif caption_or_topic and caption_or_topic.strip():
        first_line = caption_or_topic.strip().split("\n")[0]
        cleaned = re.sub(r"[#*_!🚨💡🔥👉🔑]", "", first_line).strip()
        if len(cleaned) > 5:
            headline_text = cleaned[:50]

    if not headline_text:
        headline_text = "ВАЖЛИВО ЗНАТИ!"

    # Render with Pillow (both thumbnail JPG and transparent overlay PNG)
    try:
        render_cover_with_pillow(
            frame_path=frame_path,
            cover_image_path=cover_image_path,
            text=headline_text,
            typography=typography,
            overlay_png_path=cover_overlay_path
        )
    except Exception as e:
        print(f"Pillow render cover error: {e}")
        cover_image_path = frame_path

    if not os.path.exists(cover_overlay_path):
        return input_video

    # Step 3: Overlay cover banner on top of first duration_sec of video
    has_audio = True
    try:
        probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", input_video]
        probe_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "audio" not in probe_res.stdout:
            has_audio = False
    except Exception:
        has_audio = True

    input_hdr_trc = probe_video_color(input_video)
    if input_hdr_trc:
        main_vf = f"{get_tonemap_filter(input_hdr_trc)},scale=1080:1920,setsar=1,fps=30"
    else:
        main_vf = "scale=1080:1920,setsar=1,fps=30,format=yuv420p"

    color_args = get_color_args()
    dur_val = max(0.3, float(duration_sec or 2.0))

    if has_audio:
        filter_complex = (
            f"[0:v]{main_vf}[base];"
            f"[1:v]scale=1080:1920[ovl];"
            f"[base][ovl]overlay=0:0:enable='between(t,0,{dur_val})':format=auto[v]"
        )
        cmd_overlay = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-loop", "1", "-t", str(dur_val), "-i", cover_overlay_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
            "-shortest",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            *color_args,
            "-c:a", "copy",
            output_video
        ]
    else:
        filter_complex = (
            f"[0:v]{main_vf}[base];"
            f"[1:v]scale=1080:1920[ovl];"
            f"[base][ovl]overlay=0:0:enable='between(t,0,{dur_val})':format=auto[v]"
        )
        cmd_overlay = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-loop", "1", "-t", str(dur_val), "-i", cover_overlay_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-shortest",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            *color_args,
            output_video
        ]

    try:
        subprocess.run(cmd_overlay, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_video
    except Exception as e:
        print(f"Cover overlay error: {e}")
        return input_video
