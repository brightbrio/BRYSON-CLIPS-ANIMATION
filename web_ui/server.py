"""
Bryson Clips Animation — Auth Server (Single-button Connect flow)
Click Connect → browser opens → user signs in → click Done → saved to auth/ folder
"""
import os, json, threading, uuid, time, mimetypes, subprocess, sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser

import browser_ctl

ROOT = Path(__file__).parent.parent
STATE_DIR = Path(__file__).parent / "../state/auth"
STATE_DIR.mkdir(parents=True, exist_ok=True)

WEB_DIR = Path(__file__).parent

PLATFORMS = {
    "youtube":   {"url": "https://studio.youtube.com",         "name": "YouTube Studio",     "icon": "📺"},
    "tiktok":    {"url": "https://www.tiktok.com/login",        "name": "TikTok",             "icon": "🎵"},
    "facebook":  {"url": "https://business.facebook.com",       "name": "Facebook Business",  "icon": "📘"},
    "instagram": {"url": "https://www.instagram.com/accounts/login/", "name": "Instagram",      "icon": "📸"},
    "google_flow": {"url": "https://flow.google.com",           "name": "Google Flow",        "icon": "🎬"},
    "capcut":    {"url": "https://www.capcut.com/editor",       "name": "CapCut Web",         "icon": "✂️"},
}

# Active sessions: pid -> {session_id, started_at, status}
sessions = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _json(self, data, status=200):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

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
            rel = self.path.lstrip("/")
            if not rel or rel == "index.html":
                rel = "index.html"
            fpath = (WEB_DIR / rel).resolve()
            if not str(fpath).startswith(str(WEB_DIR.resolve())):
                self._json({"error": "forbidden"}, 403); return
            if not fpath.exists() or not fpath.is_file():
                self._json({"error": "not found"}, 404); return
            content_type, _ = mimetypes.guess_type(str(fpath))
            if content_type is None:
                content_type = "application/octet-stream"
            data = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}

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

        elif self.path == "/api/launch":
            # Ensure the user's Hasahya Chrome is running with the CDP port.
            res = browser_ctl.ensure_chrome()
            self._json(res)

        elif self.path == "/api/open":
            pid = body.get("platform", "")
            res = browser_ctl.open_platform(pid)
            self._json(res)

        elif self.path == "/api/run":
            # Kick off one full local cycle (generate + post) in the background.
            if not getattr(self, "_run_started", False):
                threading.Thread(target=self._run_cycle, daemon=True).start()
                self._run_started = True
            self._json({"status": "running"})

        else:
            self._json({"error": "not found"}, 404)

    def _run_cycle(self):
        env = dict(os.environ)
        env["USE_FALLBACK"] = "false"
        try:
            subprocess.Popen(
                [sys.executable, "run_local.py"],
                cwd=str(ROOT), env=env,
                stdout=open(ROOT / "local_run.log", "a"),
                stderr=subprocess.STDOUT,
            )
        except Exception:
            pass


def open_browser():
    time.sleep(1)
    webbrowser.open("http://localhost:8081")

threading.Thread(target=open_browser, daemon=True).start()

PORT = 8081
print(f"Bryson Clips Animation Setup Wizard")
print(f"Running at http://127.0.0.1:{PORT}")
print("Press Ctrl+C to stop\n")
HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
