@echo off
cd /d "%~dp0"
echo Starting Bryson Clips Animation Web Setup Wizard...
echo.
python "web_ui/server.py"
pause