#!/usr/bin/env python3
"""
Bryson Clips Animation - Web Setup Wizard
Run: python web_ui/main.py
Then open http://localhost:8080 in your browser
"""

import asyncio
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Add parent directory to path for config
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

with open(Path(__file__).parent.parent / "config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

AUTH_DIR = Path(__file__).parent.parent / CONFIG["paths"]["auth_dir"]
AUTH_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = [
    {"id": "youtube", "name": "YouTube Studio", "url": "https://studio.youtube.com", "icon": "📺"},
    {"id": "tiktok", "name": "TikTok", "url": "https://www.tiktok.com/login", "icon": "🎵"},
    {"id": "facebook", "name": "Facebook Business Suite", "url": "https://business.facebook.com", "icon": "📘"},
    {"id": "instagram", "name": "Instagram", "url": "https://www.instagram.com/accounts/login/", "icon": "📸"},
    {"id": "google_flow", "name": "Google Flow (Veo)", "url": "https://flow.google.com", "icon": "🎬"},
    {"id": "google_ai_studio", "name": "Google AI Studio", "url": "https://aistudio.google.com", "icon": "🤖"},
    {"id": "capcut", "name": "CapCut Web", "url": "https://www.capcut.com/editor", "icon": "✂️"},
]

app = FastAPI(title="Bryson Clips Animation Setup")

# Store active websockets for progress updates
active_connections: List[WebSocket] = []


class PlatformAuthRequest(BaseModel):
    platform_id: str


class AuthStatus(BaseModel):
    platform_id: str
    status: str  # pending, authenticating, success, error
    message: str = ""


async def broadcast(message: dict):
    """Send message to all connected websockets."""
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except:
            pass


def get_auth_status(platform_id: str) -> dict:
    """Check if platform has valid auth."""
    auth_file = AUTH_DIR / f"{platform_id}_auth.json"
    if not auth_file.exists():
        return {"platform_id": platform_id, "status": "pending", "message": "Not connected"}
    try:
        with open(auth_file) as f:
            data = json.load(f)
        # Check if cookies exist and are recent
        cookies = data.get("cookies", [])
        if cookies:
            return {"platform_id": platform_id, "status": "success", "message": "Connected ✓"}
        return {"platform_id": platform_id, "status": "error", "message": "Invalid auth file"}
    except:
        return {"platform_id": platform_id, "status": "error", "message": "Corrupted auth file"}


async def authenticate_platform(platform_id: str, ws: WebSocket):
    """Run Playwright auth for a platform."""
    platform = next(p for p in PLATFORMS if p["id"] == platform_id)
    auth_file = AUTH_DIR / f"{platform_id}_auth.json"

    await broadcast({
        "type": "auth_progress",
        "platform_id": platform_id,
        "status": "authenticating",
        "message": f"Opening {platform['name']}..."
    })

    try:
        # Run playwright auth in subprocess to avoid event loop conflicts
        script = f"""
import asyncio
import json
from playwright.async_api import async_playwright

async def auth():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("{platform['url']}")
        
        # Wait for user to log in manually
        print("WAITING_FOR_LOGIN")
        
        # Wait for common logged-in indicators
        selectors = [
            'a[href*="/channel/"]',  # YouTube
            'div[data-e2e="profile-icon"]',  # TikTok
            'div[aria-label="Your profile"]',  # Facebook
            'nav[role="navigation"]',  # Instagram
            'button:has-text("Create")',  # Google Flow / AI Studio
            'button:has-text("New project")',  # CapCut
        ]
        
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=300000)
                break
            except:
                continue
        
        await page.wait_for_timeout(3000)
        storage = await context.storage_state()
        
        with open("{auth_file}", "w") as f:
            json.dump(storage, f, indent=2)
        
        print("AUTH_SUCCESS")
        await browser.close()

asyncio.run(auth())
"""
        # Write temp script
        temp_script = AUTH_DIR / f"auth_{platform_id}.py"
        temp_script.write_text(script)

        # Run it
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(temp_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Monitor output
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line = line.decode().strip()
            if line == "WAITING_FOR_LOGIN":
                await broadcast({
                    "type": "auth_progress",
                    "platform_id": platform_id,
                    "status": "authenticating",
                    "message": f"Please log in to {platform['name']} in the browser window..."
                })
            elif line == "AUTH_SUCCESS":
                await broadcast({
                    "type": "auth_progress",
                    "platform_id": platform_id,
                    "status": "success",
                    "message": f"{platform['name']} connected! ✓"
                })

        await process.wait()
        temp_script.unlink(missing_ok=True)

        if process.returncode == 0:
            return True
        else:
            stderr = (await process.stderr.read()).decode()
            await broadcast({
                "type": "auth_progress",
                "platform_id": platform_id,
                "status": "error",
                "message": f"Failed: {stderr[:200]}"
            })
            return False

    except Exception as e:
        await broadcast({
            "type": "auth_progress",
            "platform_id": platform_id,
            "status": "error",
            "message": f"Error: {str(e)}"
        })
        return False


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = Path(__file__).parent / "index.html"
    return HTMLResponse(html_file.read_text())


@app.get("/api/status")
async def get_status():
    """Get auth status for all platforms."""
    return [get_auth_status(p["id"]) for p in PLATFORMS]


@app.post("/api/auth/{platform_id}")
async def start_auth(platform_id: str):
    """Start authentication for a platform."""
    # Run in background
    asyncio.create_task(authenticate_platform(platform_id, None))
    return {"status": "started"}


@app.post("/api/auth/all")
async def auth_all():
    """Authenticate all platforms sequentially."""
    asyncio.create_task(auth_all_platforms())
    return {"status": "started"}


async def auth_all_platforms():
    for platform in PLATFORMS:
        await broadcast({
            "type": "step",
            "message": f"Connecting {platform['name']}..."
        })
        await authenticate_platform(platform["id"], None)
        await asyncio.sleep(2)


@app.post("/api/deploy")
async def deploy():
    """Deploy to GitHub Actions."""
    asyncio.create_task(run_deploy())
    return {"status": "started"}


async def run_deploy():
    await broadcast({"type": "deploy_progress", "message": "Initializing git repo..."})
    
    repo_path = Path(__file__).parent.parent
    
    try:
        # Check if git exists
        result = subprocess.run(["git", "status"], cwd=repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            await broadcast({"type": "deploy_progress", "message": "Initializing git..."})
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Bryson Clips Animation automation"], cwd=repo_path, check=True)
        
        await broadcast({"type": "deploy_progress", "message": "Ready for GitHub push!"})
        await broadcast({
            "type": "deploy_complete",
            "message": "Repo ready. Now push to GitHub:\n\n1. Create repo at github.com/new\n2. Run these commands:\n   git remote add origin https://github.com/YOUR_USERNAME/bryson-clips-animation.git\n   git branch -M main\n   git push -u origin main\n\n3. Add secrets in GitHub Settings → Secrets → Actions:\n   - GLM_API_KEY (from z.ai)\n   - GEMINI_API_KEY (from aistudio.google.com)\n\n4. Workflow runs automatically 4x/day!"
        })
    except Exception as e:
        await broadcast({"type": "deploy_error", "message": f"Deploy failed: {e}"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        active_connections.remove(websocket)


# Serve static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def main():
    print("=" * 60)
    print("  Bryson Clips Animation - Web Setup Wizard")
    print("=" * 60)
    print(f"\nStarting server at http://localhost:8080")
    print("Opening browser automatically...\n")
    
    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:8080")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="warning")


if __name__ == "__main__":
    main()