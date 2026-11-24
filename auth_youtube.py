#!/usr/bin/env python3
"""
Quick YouTube auth script - run this ONCE to log in and save auth state.
Opens browser, you sign in to HM Recaps, saves auth/youtube_auth.json
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    auth_dir = Path("auth")
    auth_dir.mkdir(exist_ok=True)
    auth_file = auth_dir / "youtube_auth.json"
    
    print("[AUTH] Starting YouTube auth for HM Recaps...")
    print(f"[DIR] Will save auth to: {auth_file}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # VISIBLE browser
        context = await browser.new_context()
        page = await context.new_page()
        
        print("[WEB] Opening YouTube Studio...")
        await page.goto("https://studio.youtube.com")
        
        print()
        print("=" * 60)
        print("MANUAL STEP REQUIRED:")
        print("   1. Sign in to your HM Recaps Google account")
        print("   2. Complete any 2FA if prompted")
        print("   3. Once you see the YouTube Studio dashboard, COME BACK HERE")
        print("   4. Press ENTER in this terminal")
        print("=" * 60)
        print()
        
        # Wait for user to complete login
        input("Press ENTER after you're logged in to YouTube Studio... ")
        
        # Save auth state
        await context.storage_state(path=str(auth_file))
        print(f"[OK] Auth saved to {auth_file}")
        
        await browser.close()
        print("[DONE] Done! You can now run the pipeline.")

if __name__ == "__main__":
    asyncio.run(main())