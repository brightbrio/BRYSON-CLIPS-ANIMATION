#!/usr/bin/env python3
"""
BRYSON CLIPS — LOCAL RUNNER (post to HM Recaps / Hasahya Motivated)

Run this ONCE, in order:
  1.  python one_time_auth.py          # sign in to YouTube + TikTok (one-time)
  2.  python run_local.py             # generate a real video + post it

What it does:
  - Generates a viral idea + story (Gemini key, free tier; falls back to templates)
  - Renders a REAL 9:16 MP4 locally (moviepy + PIL + ffmpeg — no paid tools)
  - Uploads + publishes to every channel you logged into (HM Recaps / Hasahya)
  - Records everything in state/rickclips.db
"""
import asyncio, os, sys
from pathlib import Path

# Make sure we run from the project root
os.chdir(Path(__file__).parent)

# Real mode: NOT fallback, so we generate a real video and actually post
os.environ["USE_FALLBACK"] = "false"

# Your Gemini key lives in local .env or as a shell env var (NEVER committed).
# A local .env always wins over any OS env var so the known-good key is used.
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()
if not os.environ.get("GEMINI_API_KEY"):
    print("[note] GEMINI_API_KEY not set — using free template ideation. "
          "Put it in a local .env file to use Gemini.")

from orchestrator import Orchestrator


async def main():
    orch = Orchestrator()
    # We render video locally with video_gen, so no Google Flow browser needed.
    orch.config["production"]["google_flow"]["enabled"] = False

    await orch.start_agents()
    try:
        print("\n=== RUNNING ONE FULL LOCAL CYCLE ===")
        await orch.run_cycle()
        print("=== CYCLE DONE ===")
    finally:
        await orch.stop_agents()

    # Show the latest post results
    import sqlite3
    with sqlite3.connect(orch.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT video_id, platform, status, posted_at FROM posts "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
    print(f"\nLatest posts recorded in {Path(orch.db_path).name}:")
    if rows:
        for r in rows:
            print(f"  video {r['video_id']} -> {r['platform']} ({r['status']}) at {r['posted_at']}")
    else:
        print("  (none yet — if your auth was missing, run one_time_auth.py then retry)")


if __name__ == "__main__":
    asyncio.run(main())
