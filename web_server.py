#!/usr/bin/env python3
"""
Web UI Server with Playwright Auth Backend
Run: python web_server.py
Then open: http://127.0.0.1:8081
Click "Connect" buttons - browser opens, you log in, click "Save Auth" in UI
"""
import asyncio
import json
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI()

# Auth directory
AUTH_DIR = Path("auth")
AUTH_DIR.mkdir(exist_ok=True)

# Active browser sessions
active_sessions = {}

class ConnectRequest(BaseModel):
    platform: str

class SaveAuthRequest(BaseModel):
    platform: str

PLATFORMS = {
    "youtube": {"name": "YouTube Studio", "url": "https://studio.youtube.com", "icon": "📺"},
    "tiktok": {"name": "TikTok", "url": "https://www.tiktok.com/login", "icon": "🎵"},
    "facebook": {"name": "Facebook Business", "url": "https://business.facebook.com", "icon": "📘"},
    "instagram": {"name": "Instagram", "url": "https://www.instagram.com/accounts/login/", "icon": "📸"},
    "google_flow": {"name": "Google Flow", "url": "https://flow.google.com", "icon": "🎬"},
    "google_ai_studio": {"name": "Google AI Studio", "url": "https://aistudio.google.com", "icon": "🤖"},
    "capcut": {"name": "CapCut Web", "url": "https://www.capcut.com/editor", "icon": "✂️"},
}

@app.get("/")
async def root():
    return FileResponse("web_ui/index.html")

@app.get("/api/platforms")
async def get_platforms():
    result = {}
    for pid, info in PLATFORMS.items():
        auth_file = AUTH_DIR / f"{pid}_auth.json"
        result[pid] = {
            **info,
            "connected": auth_file.exists(),
            "auth_file": str(auth_file) if auth_file.exists() else None
        }
    return result

@app.post("/api/auth/start")
async def start_auth(req: ConnectRequest):
    """Launch visible browser - copy user's Chrome profile to temp dir to avoid 'already in use' error"""
    if req.platform not in PLATFORMS:
        raise HTTPException(404, "Platform not found")
    
    platform = PLATFORMS[req.platform]
    
    import os
    import shutil
    import tempfile
    
    # Copy user's Chrome profile to a temp directory so Playwright can use it
    chrome_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    profile_dir = "Default"
    source_profile = os.path.join(chrome_user_data, profile_dir)
    
    # Create temp directory for this session
    temp_dir = tempfile.mkdtemp(prefix=f"playwright_{req.platform}_")
    target_profile = os.path.join(temp_dir, "Profile")
    
    # Copy the profile (ignore lock files)
    try:
        shutil.copytree(source_profile, target_profile, ignore=shutil.ignore_patterns(
            "Singleton*", "lock", "*.lock", "Crashpad", "GPUCache", "ShaderCache", "DawnCache"
        ))
    except Exception as e:
        print(f"Profile copy warning: {e}")
        # If copy fails, just use clean profile
        target_profile = temp_dir
    
    playwright = await async_playwright().start()
    
    # Use persistent context with COPIED profile
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=target_profile,
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check"
        ]
    )
    
    page = await context.new_page()
    
    try:
        await page.goto(platform["url"], wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"Navigation warning for {platform['name']}: {e}")
    
    # Store session
    session_id = f"{req.platform}_{int(asyncio.get_event_loop().time() * 1000)}"
    active_sessions[session_id] = {
        "platform": req.platform,
        "browser": None,
        "context": context,
        "page": page,
        "playwright": playwright,
        "temp_dir": temp_dir  # Track for cleanup
    }
    
    return {"session_id": session_id, "message": f"Opened {platform['name']} with YOUR copied Chrome profile. Log in there (passwords/2FA work), then click 'Save Auth'."}

@app.post("/api/auth/save")
async def save_auth(req: SaveAuthRequest):
    """Save auth state from active session"""
    # Find active session for this platform
    session_id = None
    for sid, sess in active_sessions.items():
        if sess["platform"] == req.platform:
            session_id = sid
            break
    
    if not session_id:
        raise HTTPException(404, "No active session for this platform. Click 'Connect' first.")
    
    session = active_sessions[session_id]
    context = session["context"]
    
    # Save storage state
    auth_file = AUTH_DIR / f"{req.platform}_auth.json"
    await context.storage_state(path=str(auth_file))
    
    # Close context (persistent context) and playwright
    await context.close()
    await session["playwright"].stop()
    
    # Clean up temp directory
    import shutil
    if "temp_dir" in session:
        try:
            shutil.rmtree(session["temp_dir"], ignore_errors=True)
        except:
            pass
    
    del active_sessions[session_id]
    
    return {"success": True, "message": f"{PLATFORMS[req.platform]['name']} auth saved!", "auth_file": str(auth_file)}

@app.post("/api/auth/cancel")
async def cancel_auth(req: SaveAuthRequest):
    """Cancel auth session without saving"""
    session_id = None
    for sid, sess in active_sessions.items():
        if sess["platform"] == req.platform:
            session_id = sid
            break
    
    if session_id:
        session = active_sessions[session_id]
        await session["browser"].close()
        await session["playwright"].stop()
        del active_sessions[session_id]
    
    return {"success": True, "message": "Session cancelled"}

@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    connected = []
    for pid in PLATFORMS:
        if (AUTH_DIR / f"{pid}_auth.json").exists():
            connected.append(pid)
    
    return {
        "connected_platforms": connected,
        "total_connected": len(connected),
        "total_platforms": len(PLATFORMS),
        "ready_for_deploy": len(connected) >= 1  # At least YouTube
    }

if __name__ == "__main__":
    print("=" * 60)
    print("  BRYSON CLIPS ANIMATION - WEB SETUP SERVER")
    print("=" * 60)
    print()
    print("  Starting server at: http://127.0.0.1:8081")
    print("  Open this URL in your browser")
    print()
    print("  Click 'Connect' for YouTube and TikTok")
    print("  Browser windows will open - log in to HM Recaps & Hasahya Motivated")
    print("  Click 'Save Auth' in the web UI after logging in")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="info")