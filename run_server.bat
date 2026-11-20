@echo off
cd /d "%~dp0"
python -c "import socket; import threading; import time; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', 8081)); s.listen(5); print('Server listening on 0.0.0.0:8081'); import sys; sys.stdout.flush(); while True: conn, addr = s.accept(); print('Connection from', addr); request = conn.recv(4096); print('Request:', request[:200]); response = b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Test Works!</h1></body></html>'; conn.send(response); conn.close()"
pause