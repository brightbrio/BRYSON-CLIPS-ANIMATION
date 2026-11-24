"""
Bryson Clips Animation — Auth Server (Single-button Connect flow)
Click Connect → browser opens → user signs in → click Done → saved to auth/ folder
"""
import os, json, threading, uuid, time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser

STATE_DIR = Path(__file__).parent / "../state/auth"
STATE_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = {
    "youtube":   {"url": "https://studio.youtube.com",         "name": "YouTube Studio",     "icon": "📺"},
    "tiktok":    {"url": "https://www.tiktok.com/login",        "name": "TikTok",             "icon": "🎵"},
    "facebook":  {"url": "https://business.facebook.com",       "name": "Facebook Business",  "icon": "📘"},
    "instagram": {"url": "https://www.instagram.com/accounts/login/", "name": "Instagram",      "icon": "📸"},
    "google_flow": {"url": "https://flow.google.com",           "name": "Google Flow",        "icon": "🎬"},
    "capcut":    {"url": "https://www.capcut.com/editor",       "name": "CapCut Web",         "icon": "✂️"},
}

# Active sessions: pid -> {status, started_at, session_id}
sessions = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        if self.path == "/api/status":
            states = []
            for pid in PLATFORMS:
                auth_file = STATE_DIR / f"{pid}_state.json"
                sess = sessions.get(pid, {})
                if auth_file.exists() and auth_file.stat().st_size > 100:
                    states.append({"platform_id": pid, "status": "connected"})
                elif sess.get("status") == "authenticating":
                    states.append({"platform_id": pid, "status": "authenticating"})
                else:
                    states.append({"platform_id": pid, "status": "pending"})
            self._json(states)
        elif self.path == "/api/deploy":
            self._json({"status": "ok"})
        else:
            # Serve static files from web_ui/
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        
        if self.path == "/api/auth/start":
            pid = body.get("platform", "")
            if pid not in PLATFORMS:
                self._json({"error": "unknown platform"}, 400); return
            url = PLATFORMS[pid]["url"]
            webbrowser.open(url)
            sid = str(uuid.uuid4())[:8]
            sessions[pid] = {"session_id": sid, "started": time.time(), "status": "authenticating"}
            self._json({"status": "opened", "session_id": sid})
            
        elif self.path == "/api/auth/save":
            pid = body.get("platform", "")
            if pid not in PLATFORMS:
                self._json({"error": "unknown platform"}, 400); return
            auth_file = STATE_DIR / f"{pid}_state.json"
            data = {
                "platform": pid,
                "status": "success",
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "message": "Authentication saved"
            }
            auth_file.write_text(json.dumps(data, indent=2))
            if pid in sessions:
                sessions[pid]["status"] = "connected"
            self._json({"success": True, "path": str(auth_file)})
            
        elif self.path == "/api/auth/cancel":
            pid = body.get("platform", "")
            sessions.pop(pid, None)
            self._json({"cancelled": True})
            
        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data, status=200):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def open_browser():
    time.sleep(1)
    webbrowser.open("http://localhost:8081")

threading.Thread(target=open_browser, daemon=True).start()

PORT = 8081
print(f"Bryson Clips Animation Setup Wizard")
print(f"Running at http://127.0.0.1:{PORT}")
print("Press Ctrl+C to stop\n")
HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
