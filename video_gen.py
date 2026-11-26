"""
Local video generator — renders a REAL 9:16 MP4 from a story, using ONLY free
tools (moviepy + PIL + ffmpeg). No Google Flow sign-in needed. This is what makes
posting to HM Recaps actually work.

Style DNA (Bryson / Ricks Clips):
  - 9:16 vertical, #2D1B4E deep blue-purple background
  - white circular marker head stickman, thick black outlines
  - big white caption text, hard cuts, 2.5D parallax feel
"""
import os, json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import moviepy as mp

# Style DNA constants (from config style_dna)
BG = (45, 27, 78)          # #2D1B4E deep blue-purple
INK = (0, 0, 0)            # #000000
HEAD = (255, 255, 255)     # white marker head
CAPTION = (255, 255, 255)
ACCENT = (255, 107, 53)    # Bryson orange accent

WIDTH, HEIGHT, FPS = 1080, 1920, 30


def _draw_stickman(w=WIDTH, h=HEIGHT, pose="stand", wobble=0.0, accent=ACCENT):
    """Draw a 2D marker stickman on a transparent frame."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w // 2
    head_r = int(w * 0.11)
    head_cy = int(h * 0.32)
    # wobble
    hx = cx + int(math.sin(wobble) * 10)
    # head (white circle, thick black outline)
    d.ellipse([hx - head_r, head_cy - head_r, hx + head_r, head_cy + head_r],
              fill=HEAD, outline=INK, width=8)
    # body
    hip_cy = int(h * 0.62)
    d.line([hx, head_cy + head_r, cx, hip_cy], fill=INK, width=14)
    # arms
    if pose == "point":
        d.line([cx, int((head_cy + hip_cy) / 2), cx + int(w * 0.18), head_cy + head_r], fill=INK, width=12)
    else:
        d.line([cx, int((head_cy + hip_cy) / 2), cx - int(w * 0.16), hip_cy], fill=INK, width=12)
    d.line([cx, int((head_cy + hip_cy) / 2), cx + int(w * 0.14), hip_cy], fill=INK, width=12)
    # legs
    d.line([cx, hip_cy, cx - int(w * 0.14), int(h * 0.82)], fill=INK, width=14)
    d.line([cx, hip_cy, cx + int(w * 0.14), int(h * 0.82)], fill=INK, width=14)
    # prop accent (orange block) to mark "prop reveal"
    if pose == "prop":
        d.rectangle([cx + int(w * 0.2), int(h * 0.5), cx + int(w * 0.34), int(h * 0.64)],
                    fill=accent + (255,), outline=INK, width=6)
    return img


def _make_shot_frame(text, prop, pose):
    """One static frame: background + stickman + caption + prop label."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    # subtle parallax grid (2.5D feel)
    d = ImageDraw.Draw(img)
    for i in range(0, HEIGHT, 160):
        d.line([(0, i), (WIDTH, i)], fill=(70, 50, 110, 255), width=1)
    img = Image.alpha_composite(img, _draw_stickman(pose=pose))
    d = ImageDraw.Draw(img)
    # caption (big white text near bottom)
    try:
        font = ImageFont.truetype("arialbd.ttf", 84)
        small = ImageFont.truetype("arialbd.ttf", 44)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    # word-wrap caption
    words, lines, cur = text.split(), [], ""
    for wds in words:
        if len(cur + " " + wds) > 14:
            lines.append(cur); cur = wds
        else:
            cur = (cur + " " + wds).strip()
    lines.append(cur)
    y = HEIGHT - int(HEIGHT * 0.16)
    for ln in lines[-3:]:
        d.text((60, y), ln, font=font, fill=CAPTION, stroke_width=4, stroke_fill=INK)
        y += 96
    if prop:
        d.text((60, 120), prop.upper(), font=small, fill=ACCENT, stroke_width=3, stroke_fill=INK)
    return img


def render_story_video(story, out_path):
    """Render a full vertical video from a story dict. Returns out_path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prop = story.get("prop", "")
    narration = story.get("narration", [])
    shots = [n for n in narration if n][:10] or ["A surprising true story..."]
    pose_map = {0: "prop", 1: "point", 2: "stand"}
    seg_dur = max(2.0, 60.0 / len(shots))

    clips = []
    tmp_dir = out_path.parent / "_tmp_frames"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i, line in enumerate(shots):
        pose = pose_map.get(i % 3, "stand")
        frame = _make_shot_frame(line, prop, pose)
        tmp_png = tmp_dir / f"shot_{i}.png"
        frame.convert("RGB").save(tmp_png)
        clip = mp.ImageClip(str(tmp_png)).with_duration(seg_dur)
        clips.append(clip)

    video = mp.concatenate_videoclips(clips, method="chain")
    video = video.with_fps(FPS)
    print(f"[VIDEO] Rendering {out_path} ({len(shots)} shots, ~{len(shots) * seg_dur:.0f}s)...")
    video.write_videofile(str(out_path), codec="libx264", fps=FPS,
                          preset="ultrafast", threads=4, logger=None)
    video.close()
    return str(out_path)


def make_thumbnail(out_path):
    img = _make_shot_frame("You won't believe this...", "", "point")
    img.convert("RGB").save(out_path)
    return str(out_path)


if __name__ == "__main__":
    import sys
    story = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
        "prop": "Mirror", "narration": [
            "They rigged a mirror to win a horse race",
            "The light bent in a way nobody expected",
            "And it changed everything",
        ]
    }
    p = render_story_video(story, "output/test_video.mp4")
    print("Rendered:", p)
