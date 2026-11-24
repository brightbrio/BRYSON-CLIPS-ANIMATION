#!/usr/bin/env python3
"""
Quick TikTok auth script - run this ONCE to log in and save auth state.
Opens browser, you sign in to Hasahya Motivated, saves auth/tiktok_auth.json
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    auth_dir = Path("auth")
    auth_dir.mkdir(exist_ok=True)
    auth_file = auth_dir / "tiktok_auth.json"
    
    print("[AUTH] Starting TikTok auth for Hasahya Motivated...")
    print(f"[DIR] Will save auth to: {auth_file}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # VISIBLE browser
        context = await browser.new_context()
        page = await context.new_page()
        
        print("[WEB] Opening TikTok...")
        await page.goto("https://www.tiktok.com/login")
        
        print()
        print("=" * 60)
        print("MANUAL STEP REQUIRED:")
        print("   1. Sign in to your Hasahya Motivated TikTok account")
        print("   2. Complete any 2FA if prompted")
        print("   3. Once you see the TikTok feed/profile, COME BACK HERE")
        print("   4. Press ENTER in this terminal")
        print("=" * 60)
        print()
        
        # Wait for user to complete login
        input("Press ENTER after you're logged in to TikTok... ")
        
        # Save auth state
        await context.storage_state(path=str(auth_file))
        print(f"[OK] Auth saved to {auth_file}")
        
        await browser.close()
        print("[DONE] Done! TikTok auth saved for Hasahya Motivated.")

if __name__ == "__main__":
    asyncio.run(main())