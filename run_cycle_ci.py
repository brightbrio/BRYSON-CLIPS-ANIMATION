#!/usr/bin/env python3
"""CI entrypoint: run one orchestrator cycle with visible logging + summary."""
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
)

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from orchestrator import Orchestrator  # noqa: E402


def summarize(db_path: str) -> None:
    import sqlite3
    try:
        with sqlite3.connect(db_path) as conn:
            for table in ("cycle_log", "ideas", "videos", "characters", "posts"):
                try:
                    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    print(f"[SUMMARY] {table}: {n} rows")
                except sqlite3.Error as e:
                    print(f"[SUMMARY] {table}: missing ({e})")
            try:
                rows = conn.execute(
                    "SELECT cycle_id, status, videos_generated FROM cycle_log ORDER BY id DESC LIMIT 3"
                ).fetchall()
                for r in rows:
                    print(f"[SUMMARY] cycle {r[0]} status={r[1]} videos={r[2]}")
            except sqlite3.Error:
                pass
    except Exception as e:
        print(f"[SUMMARY] db read failed: {e}")


async def main() -> int:
    print(f"[CI] cwd={os.getcwd()}")
    print(f"[CI] USE_FALLBACK={os.environ.get('USE_FALLBACK')}")
    orch = Orchestrator()
    print(f"[CI] backend={orch.config['ideation'].get('backend')}")
    await orch.run_cycle()
    print("[CI] cycle finished")
    summarize(orch.db_path.as_posix() if hasattr(orch.db_path, "as_posix") else str(orch.db_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
