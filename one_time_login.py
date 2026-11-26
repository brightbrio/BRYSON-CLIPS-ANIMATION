#!/usr/bin/env python3
"""One-time login for the DEDICATED automation browser.

Opens a clean Chrome (stored in ./chrome_profile, separate from your daily
browser). You sign into YouTube Studio and TikTok ONCE. Those logins are
saved and reused by run_local.py on every future run — no more logging in.

Usage:
    python one_time_login.py
"""
import asyncio
from pathlib import Path
import yaml
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent


def load_cfg() -> dict:
    return yaml.safe_load(open(ROOT / "config.yaml", "r", encoding="utf-8"))


async def main() -> None:
    cfg = load_cfg()
    cp = cfg["distribution"]["chrome_profile"]
    user_data_dir = cp.get(
        "user_data_dir",
        str(Path(ROOT) / "chrome_profile"),
    )
    channel = cp.get("channel", "chrome")

    sites = [
        ("YouTube Studio (HM Recaps)", "https://studio.youtube.com"),
        ("TikTok (Hasahya Motivated)", "https://www.tiktok.com/login"),
    ]

    print("=" * 60)
    print(" ONE-TIME LOGIN — dedicated automation browser")
    print("=" * 60)
    print(f"Profile dir: {user_data_dir}")
    print("A Chrome window will open. Sign into EACH site below, then come")
    print("back here and press ENTER after each one. Cookies are saved to the")
    print("profile so future runs post automatically.")
    print("=" * 60)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir,
            channel=channel,
            headless=False,
            viewport=None,
            args=["--start-maximized", "--no-first-run"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        for name, url in sites:
            await page.goto(url)
            print(f"\n>>> Sign in to {name} in the browser window...")
            input("    Press ENTER here when you're signed in: ")

        print("\nAll done. Cookies saved to the profile dir.")
        input("Press ENTER to close the browser and finish...")
        await ctx.close()

    print("Next time: just run  python run_local.py  — it reuses these logins.")


if __name__ == "__main__":
    asyncio.run(main())
