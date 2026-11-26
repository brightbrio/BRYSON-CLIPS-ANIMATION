"""Browser control for the web UI. Lets the user log in in their OWN Chrome
(the 'Hasahya' Default profile) and have the automation attach to it via CDP."""
import subprocess
import time
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"
PROFILE = "Default"          # 'Hasahya' default profile (from Hasahya - Chrome.lnk)
PORT = 9222

PLATFORM_URLS = {
    "youtube": "https://studio.youtube.com",
    "tiktok": "https://www.tiktok.com/upload",
    "facebook": "https://business.facebook.com",
    "instagram": "https://www.instagram.com",
}


def cdp_up() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def ensure_chrome() -> dict:
    """Make sure the Hasahya Chrome is running with the CDP port."""
    if cdp_up():
        return {"ok": True, "started": False}
    # Chrome already open without the port? Relaunch it with the port.
    subprocess.run(["taskkill", "/f", "/im", "chrome.exe"],
                   capture_output=True)
    time.sleep(3)
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}",
         f"--user-data-dir={USER_DATA}", f"--profile-directory={PROFILE}",
         "--no-first-run", "--disable-session-crashed-bubble",
         "--no-default-browser-check"],
    )
    for _ in range(20):
        time.sleep(2)
        if cdp_up():
            return {"ok": True, "started": True}
    return {"ok": False, "error": "Chrome did not open with the debug port"}


def open_platform(platform: str) -> dict:
    """Open a platform login/upload page in the user's Chrome so they can log in."""
    if not cdp_up():
        return {"ok": False, "error": "CDP not up"}
    url = PLATFORM_URLS.get(platform, "about:blank")
    # Create a new tab via CDP HTTP endpoint.
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{url}", timeout=5)
        return {"ok": True, "url": url,
                "note": f"Now log in to {platform} in the open Chrome window."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
