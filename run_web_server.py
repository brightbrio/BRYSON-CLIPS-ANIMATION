import http.server
import socketserver
import os
import webbrowser
import threading
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/web_ui")

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'[{"platform_id":"youtube","status":"pending","message":"Not connected"},{"platform_id":"tiktok","status":"pending","message":"Not connected"},{"platform_id":"facebook","status":"pending","message":"Not connected"},{"platform_id":"instagram","status":"pending","message":"Not connected"},{"platform_id":"google_flow","status":"pending","message":"Not connected"},{"platform_id":"google_ai_studio","status":"pending","message":"Not connected"},{"platform_id":"capcut","status":"pending","message":"Not connected"}]')
        elif self.path.startswith('/api/auth/'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"started"}')
        elif self.path == '/api/auth/all':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"started"}')
        elif self.path == '/api/deploy':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"started"}')
        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

PORT = 8081

def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")

threading.Thread(target=open_browser, daemon=True).start()

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Bryson Clips Animation Setup Wizard")
    print(f"Server running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop")
    httpd.serve_forever()