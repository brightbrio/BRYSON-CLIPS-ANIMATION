#!/usr/bin/env python3
"""
AUTH SETUP
One-time interactive login for all platforms.
Saves auth state (cookies, localStorage) to JSON files for headless reuse.
Run once per machine: python auth_setup.py
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
import yaml

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

AUTH_DIR = Path(config["paths"]["auth_dir"])
AUTH_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = {
    "youtube": {
        "name": "YouTube Studio",
        "login_url": "https://studio.youtube.com",
        "check_selector": 'a[href*="/channel/"]',  # Profile avatar
    },
    "tiktok": {
        "name": "TikTok",
        "login_url": "https://www.tiktok.com/login",
        "check_selector": 'div[data-e2e="profile-icon"]',
    },
    "facebook": {
        "name": "Facebook Business Suite",
        "login_url": "https://business.facebook.com",
        "check_selector": 'div[aria-label="Your profile"]',
    },
    "instagram": {
        "name": "Instagram",
        "login_url": "https://www.instagram.com/accounts/login/",
        "check_selector": 'nav[role="navigation"]',
    },
    "google_flow": {
        "name": "Google Flow (Veo)",
        "login_url": "https://flow.google.com",
        "check_selector": 'button:has-text("Create")',
    },
    "google_ai_studio": {
        "name": "Google AI Studio",
        "login_url": "https://aistudio.google.com",
        "check_selector": 'button:has-text("Create")',
    },
    "capcut": {
        "name": "CapCut Web",
        "login_url": "https://www.capcut.com/editor",
        "check_selector": 'button:has-text("New project")',
    },
}

async def setup_platform(playwright, platform_key: str, platform_config: dict):
    """Interactive login for one platform."""
    print(f"\n{'='*60}")
    print(f"Setting up: {platform_config['name']}")
    print(f"{'='*60}")
    
    auth_file = AUTH_DIR / f"{platform_key}_auth.json"
    
    # Check if already authenticated
    if auth_file.exists():
        overwrite = input(f"Auth file exists for {platform_key}. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print(f"Skipping {platform_key}")
            return True
    
    # Launch visible browser for login
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        print(f"Opening {platform_config['login_url']}...")
        await page.goto(platform_config["login_url"])
        
        print(f"\n>>> Please log in to {platform_config['name']} in the browser window.")
        print(f"    - Complete 2FA if prompted")
        print(f"    - Stay on the main dashboard after login")
        print(f"    - Do NOT close the browser")
        
        # Wait for login completion
        print(f"\nWaiting for login... (check selector: {platform_config['check_selector']})")
        await page.wait_for_selector(platform_config["check_selector"], timeout=300000)
        
        # Additional wait for full load
        await page.wait_for_timeout(3000)
        
        # Save storage state
        storage = await context.storage_state()
        auth_file.write_text(json.dumps(storage, indent=2))
        
        print(f"✓ Auth saved to {auth_file}")
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
        
    finally:
        await browser.close()

async def verify_auth(playwright, platform_key: str, platform_config: dict):
    """Verify saved auth works in headless mode."""
    auth_file = AUTH_DIR / f"{platform_key}_auth.json"
    
    if not auth_file.exists():
        print(f"✗ No auth file for {platform_key}")
        return False
    
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(auth_file))
        page = await context.new_page()
        
        await page.goto(platform_config["login_url"])
        await page.wait_for_selector(platform_config["check_selector"], timeout=30000)
        
        await browser.close()
        print(f"✓ {platform_key} auth verified")
        return True
        
    except Exception as e:
        print(f"✗ {platform_key} auth verification failed: {e}")
        return False

async def main():
    print("RICKS CLIPS AUTH SETUP")
    print("This will open browser windows for you to log in to each platform.")
    print("Auth states are saved for headless automation.\n")
    
    # Select platforms to set up
    print("Available platforms:")
    for i, (key, cfg) in enumerate(PLATFORMS.items(), 1):
        print(f"  {i}. {cfg['name']} ({key})")
    
    print("\nOptions:")
    print("  a) All platforms")
    print("  s) Select specific platforms")
    print("  v) Verify existing auth only")
    print("  q) Quit")
    
    choice = input("\nChoice (a/s/v/q): ").lower()
    
    async with async_playwright() as playwright:
        if choice == 'a':
            targets = list(PLATFORMS.keys())
        elif choice == 's':
            selection = input("Enter numbers separated by commas (e.g., 1,3,5): ")
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
            targets = [list(PLATFORMS.keys())[i] for i in indices if 0 <= i < len(PLATFORMS)]
        elif choice == 'v':
            print("\nVerifying all saved auth...")
            for key, cfg in PLATFORMS.items():
                await verify_auth(playwright, key, cfg)
            return
        elif choice == 'q':
            return
        else:
            print("Invalid choice")
            return
        
        # Setup selected platforms
        results = {}
        for key in targets:
            cfg = PLATFORMS[key]
            success = await setup_platform(playwright, key, cfg)
            results[key] = success
        
        # Summary
        print(f"\n{'='*60}")
        print("SETUP SUMMARY")
        print(f"{'='*60}")
        for key, success in results.items():
            status = "✓ Success" if success else "✗ Failed"
            print(f"  {PLATFORMS[key]['name']}: {status}")
        
        print(f"\nAuth files saved to: {AUTH_DIR.absolute()}")
        print("You can now run the orchestrator in headless mode.")

if __name__ == "__main__":
    asyncio.run(main())