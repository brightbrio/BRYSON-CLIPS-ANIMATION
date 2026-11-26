@echo off
:: Launch the 'Hasahya' Chrome profile (Profile 1) with a remote-debugging port
:: so the automation can attach to the LIVE logged-in browser via CDP.
:: NOTE: Chrome must be (re)started with --remote-debugging-port to attach,
:: so this closes any open Chrome windows first (your logins persist in the profile).

echo Closing open Chrome windows...
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

set LOCAL_APP=%LOCALAPPDATA%
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%LOCAL_APP%\Google\Chrome\User Data" ^
  --profile-directory=Profile 1 ^
  --no-first-run

echo.
echo Hasahya Chrome is launching with remote debugging on port 9222.
echo Wait for the window to fully open (and enter your passphrase if prompted),
echo then run:  python run_local.py
echo.
pause
