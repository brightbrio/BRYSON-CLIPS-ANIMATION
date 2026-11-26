"""Quick diagnostic: attach via CDP to the live Hasahya Chrome, open YouTube
Studio + TikTok, and report whether they're logged in."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print("CDP CONNECT FAILED:", e)
            return
        print(f"Attached. contexts={len(browser.contexts)}")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        print(f"Existing pages in ctx: {len(ctx.pages)}")

        # YouTube
        page = await ctx.new_page()
        try:
            await page.goto("https://studio.youtube.com", timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(5000)
            has_channel = "youtube" in page.url and "sign_in" not in page.url
            print(f"YT url: {page.url}")
            print(f"YT logged in? {has_channel}  title: {await page.title()}")
        except Exception as e:
            print("YT error:", str(e)[:150])
        try:
            await page.close()
        except Exception:
            pass

        # TikTok
        try:
            tp = await ctx.new_page()
            await tp.goto("https://www.tiktok.com", timeout=60000)
            await tp.wait_for_load_state("domcontentloaded")
            await tp.wait_for_timeout(3000)
            print(f"TT url: {tp.url}  login? {'login' not in tp.url}")
            await tp.close()
        except Exception as e:
            print("TT error:", str(e)[:150])

        # do NOT close the user's browser
        try:
            await browser.close()  # disconnect only
        except Exception:
            pass
    print("DIAGNOSTIC DONE")


if __name__ == "__main__":
    asyncio.run(main())
