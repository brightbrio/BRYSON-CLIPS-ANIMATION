#!/usr/bin/env python3
"""
ONE-TIME login. Run this on your machine, sign in where prompted, press ENTER.
Saves real Playwright cookie sessions so the pipeline can post to your channels.
  - YouTube  -> HM Recaps
  - TikTok   -> Hasahya Motivated
"""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

AUTH_DIR = Path("auth")
AUTH_DIR.mkdir(exist_ok=True)

SITES = {
    "youtube": ("https://studio.youtube.com", "auth/youtube_auth.json", "Sign in to your HM Recaps Google account."),
    "tiktok":  ("https://www.tiktok.com/login", "auth/tiktok_auth.json", "Sign in to your Hasahya Motivated account."),
}


async def auth_site(name, url, auth_file, hint):
    print("\n" + "=" * 60)
    print(f"  {name.upper()} AUTH -> {auth_file}")
    print(f"  {hint}")
    print("=" * 60)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(url)
        input(f"  >> {name}: finish login, then press ENTER ... ")
        await ctx.storage_state(path=str(Path(auth_file).resolve()))
        await browser.close()
        print(f"  [OK] saved -> {auth_file}")


def main():
    which = [s for s in sys.argv[1:]] or list(SITES.keys())
    for name in which:
        url, auth_file, hint = SITES[name]
        asyncio.run(auth_site(name, url, auth_file, hint))
    print("\nAll done. Now run:  python run_local.py")


if __name__ == "__main__":
    main()
