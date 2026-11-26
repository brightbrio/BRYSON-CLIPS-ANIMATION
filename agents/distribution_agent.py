#!/usr/bin/env python3
"""
DISTRIBUTION AGENT
Cross-platform posting to YouTube Shorts, TikTok, Facebook Reels, Instagram Reels.
Handles scheduling, engagement replies, and analytics collection.
"""
from __future__ import annotations

import asyncio
import logging
import json
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


class DistributionAgent:
    PLATFORMS = {
        "youtube": {
            "name": "YouTube Shorts",
            "url": "https://studio.youtube.com",
            "upload_url": "https://studio.youtube.com/upload",
            "selectors": {
                "upload_input": 'input[name="Filedata"]',
                "title": '#textbox[aria-label="Title"]',
                "description": '#textbox[aria-label="Description"]',
                "thumbnail": 'input[name="thumbnail"]',
                "shorts_toggle": 'tp-yt-paper-checkbox[aria-label*="Shorts"]',
                "next_button": 'button:has-text("Next")',
                "publish_button": 'button:has-text("Publish")',
                "visibility_radio": 'tp-yt-paper-radio-button[name="PUBLIC"]',
            }
        },
        "tiktok": {
            "name": "TikTok",
            "url": "https://www.tiktok.com/upload",
            "selectors": {
                "upload_input": 'input[type="file"][accept*="video"]',
                "caption": 'div[contenteditable="true"][data-text="true"]',
                "hashtag_input": 'div[contenteditable="true"]',
                "post_button": 'button:has-text("Post")',
                "schedule_toggle": 'button:has-text("Schedule")',
            }
        },
        "facebook": {
            "name": "Facebook Reels",
            "url": "https://business.facebook.com/latest/composer",
            "selectors": {
                "upload_input": 'input[type="file"][accept*="video"]',
                "caption": 'div[contenteditable="true"][role="textbox"]',
                "reels_tab": 'button:has-text("Reels")',
                "post_button": 'button:has-text("Publish")',
            }
        },
        "instagram": {
            "name": "Instagram Reels",
            "url": "https://www.instagram.com/reels/upload",
            "selectors": {
                "upload_input": 'input[type="file"][accept*="video"]',
                "caption": 'textarea[aria-label="Caption"]',
                "cover_selector": 'button:has-text("Cover")',
                "share_button": 'button:has-text("Share")',
            }
        }
    }
    
    ENGAGEMENT_TEMPLATES = [
        "What would YOU do with this {prop}? 🤔",
        "Wild, right? The {prop} changed everything.",
        "History is stranger than fiction. What's your take?",
        "Ever heard of this before? 👇",
        "The {prop} is the real MVP here. Agree?",
        "Mind = blown. What would you have done?",
        "This {prop} wrote history. What's next?",
        "Truth > fiction. The {prop} proves it.",
    ]
    
    def __init__(self, config: dict):
        self.config = config
        self.db_path = Path(config["database"]["path"])
        self.auth_dir = Path(config["paths"]["auth_dir"])
        self.assets_dir = Path(config["paths"]["assets_dir"])
        
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        
        self.enabled_platforms = [
            p for p, cfg in config["distribution"]["platforms"].items() 
            if cfg.get("enabled", True)
        ]
        self.current_prop = ""
        self.current_video_id = 0
    
    async def start(self):
        """Launch browser with per-platform auth states."""
        if not HAS_PLAYWRIGHT:
            logger.info("Distribution agent started (no playwright available)")
            return
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        
        for platform in self.enabled_platforms:
            auth_file = self.auth_dir / f"{platform}_auth.json"
            if auth_file.exists():
                self.contexts[platform] = await self.browser.new_context(storage_state=str(auth_file))
            else:
                self.contexts[platform] = await self.browser.new_context()
            
            self.pages[platform] = await self.contexts[platform].new_page()
            self.pages[platform].set_default_timeout(120000)
        
        logger.info(f"Distribution agent started for: {', '.join(self.enabled_platforms)}")
    
    async def close(self):
        """Clean shutdown."""
        for ctx in self.contexts.values():
            await ctx.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        logger.info("Distribution agent closed")
    
    # ==================== MAIN POSTING ====================
    
    async def post_to_all(self, video_path: str, metadata: Dict, thumbnail_path: str):
        """Post video to all enabled platforms with platform-specific metadata."""
        self.current_video_id = metadata["video_id"]
        self.current_prop = metadata["prop"]
        
        # Guard: if no browser pages are set up (e.g. CI without Playwright or
        # missing auth state), skip posting gracefully instead of crashing.
        if not self.pages:
            logger.warning(
                "No browser pages available (Playwright not installed or no auth "
                "state). Skipping distribution to %s. Run locally with real auth "
                "to post to HM Recaps / Hasahya Motivated.",
                ", ".join(self.enabled_platforms),
            )
            return
        
        logger.info(f"Posting video {self.current_video_id} to {len(self.enabled_platforms)} platforms...")
        
        tasks = []
        for platform in self.enabled_platforms:
            task = self._post_single(platform, video_path, metadata, thumbnail_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for platform, result in zip(self.enabled_platforms, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to post to {platform}: {result}")
            else:
                logger.info(f"Posted to {platform}: {result}")
        
        # Schedule engagement
        await self._schedule_engagement()
    
    async def _post_single(self, platform: str, video_path: str, metadata: Dict, thumbnail_path: str) -> str:
        """Post to a single platform."""
        page = self.pages[platform]
        config = self.PLATFORMS[platform]
        selectors = config["selectors"]
        
        # Navigate to upload page
        await page.goto(config.get("upload_url", config["url"]))
        await page.wait_for_load_state("networkidle")
        
        # Platform-specific prep
        if platform == "facebook":
            # Switch to Reels tab
            await page.click(selectors["reels_tab"])
            await page.wait_for_timeout(2000)
        
        # Upload video
        await page.set_input_files(selectors["upload_input"], video_path)
        
        # Wait for upload processing
        await self._wait_for_upload_complete(page, platform)
        
        # Fill metadata
        await self._fill_metadata(page, platform, metadata, selectors)
        
        # Set thumbnail (YouTube only)
        if platform == "youtube" and thumbnail_path:
            await page.set_input_files(selectors["thumbnail"], thumbnail_path)
        
        # Publish
        await self._publish(page, platform, selectors)
        
        # Log success
        self._log_post(platform, metadata["video_id"])
        
        return f"success_{platform}"
    
    async def _wait_for_upload_complete(self, page: Page, platform: str):
        """Wait for video upload to complete processing."""
        if platform == "youtube":
            # YouTube shows "Upload complete" then processes
            await page.wait_for_selector('text="Upload complete"', timeout=300000)
            # Wait for "Checks complete" or similar
            await page.wait_for_selector('text="Checks complete", text="No issues found"', timeout=300000)
        elif platform == "tiktok":
            await page.wait_for_selector('text="Video uploaded"', timeout=180000)
        elif platform == "facebook":
            await page.wait_for_selector('text="Video ready"', timeout=180000)
        elif platform == "instagram":
            await page.wait_for_selector('text="Ready to share"', timeout=180000)
        
        await page.wait_for_timeout(3000)  # Buffer
    
    async def _fill_metadata(self, page: Page, platform: str, metadata: Dict, selectors: Dict):
        """Fill title, description, hashtags per platform."""
        title_key = f"title_{platform}"
        title = metadata.get(title_key, metadata.get("title_main", ""))
        
        if platform == "youtube":
            await page.fill(selectors["title"], title[:100])  # YT Shorts title limit
            await page.fill(selectors["description"], metadata["description"][:5000])
            # Enable Shorts toggle
            try:
                await page.click(selectors["shorts_toggle"])
            except:
                pass  # May already be enabled for vertical videos
        
        elif platform == "tiktok":
            # TikTok: caption + hashtags in one field
            caption = f"{title}\n\n{metadata['description'][:200]}\n\n{' '.join(metadata['hashtags'][:10])}"
            await page.fill(selectors["caption"], caption[:2200])
        
        elif platform == "facebook":
            caption = f"{title}\n\n{metadata['description'][:500]}\n\n{' '.join(metadata['hashtags'][:10])}"
            await page.fill(selectors["caption"], caption[:2000])
        
        elif platform == "instagram":
            caption = f"{title}\n\n{metadata['description'][:500]}\n\n{' '.join(metadata['hashtags'][:15])}"
            await page.fill(selectors["caption"], caption[:2200])
    
    async def _publish(self, page: Page, platform: str, selectors: Dict):
        """Click publish/post button."""
        if platform == "youtube":
            # YouTube: Next -> Next -> Public -> Publish
            for _ in range(2):
                await page.click(selectors["next_button"])
                await page.wait_for_timeout(2000)
            await page.click(selectors["visibility_radio"])
            await page.wait_for_timeout(1000)
            await page.click(selectors["publish_button"])
            await page.wait_for_selector('text="Published"', timeout=60000)
        
        elif platform == "tiktok":
            await page.click(selectors["post_button"])
            await page.wait_for_selector('text="Posted"', timeout=60000)
        
        elif platform == "facebook":
            await page.click(selectors["post_button"])
            await page.wait_for_selector('text="Published"', timeout=60000)
        
        elif platform == "instagram":
            await page.click(selectors["share_button"])
            await page.wait_for_selector('text="Shared"', timeout=60000)
    
    def _log_post(self, platform: str, video_id: int):
        """Log successful post to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO posts (video_id, platform, posted_at, status)
                VALUES (?, ?, CURRENT_TIMESTAMP, 'posted')
            """, (video_id, platform))
            conn.commit()
    
    # ==================== ENGAGEMENT ====================
    
    async def _schedule_engagement(self):
        """Schedule engagement task for 60 minutes after posting."""
        # In production, use a task queue. For now, run immediately for testing.
        await self.process_pending_engagement()
    
    async def process_pending_engagement(self):
        """Check for new comments on recent videos and reply."""
        logger.info("Processing engagement...")
        
        for platform in self.enabled_platforms:
            try:
                await self._engage_platform(platform)
            except Exception as e:
                logger.error(f"Engagement failed for {platform}: {e}")
    
    async def _engage_platform(self, platform: str):
        """Reply to comments on recent videos for one platform."""
        if not self.pages:
            logger.warning("No browser pages available; skipping engagement for %s.", platform)
            return
        page = self.pages[platform]
        
        # Get recent video IDs from DB (last 24h)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            videos = conn.execute("""
                SELECT v.id, v.prop, p.platform_post_id
                FROM videos v
                JOIN posts p ON v.id = p.video_id
                WHERE p.platform = ? AND p.posted_at > datetime('now', '-1 day')
                AND v.id NOT IN (
                    SELECT DISTINCT video_id FROM engagement_log 
                    WHERE platform = ? AND replied_at > datetime('now', '-1 hour')
                )
            """, (platform, platform)).fetchall()
        
        for video in videos:
            await self._engage_video(platform, page, video["id"], video["prop"], video["platform_post_id"])
    
    async def _engage_video(self, platform: str, page: Page, video_id: int, prop: str, platform_post_id: str):
        """Reply to comments on a specific video."""
        # Navigate to video comments
        comment_urls = {
            "youtube": f"https://studio.youtube.com/video/{platform_post_id}/comments",
            "tiktok": f"https://www.tiktok.com/@user/video/{platform_post_id}",
            "facebook": f"https://business.facebook.com/latest/comments?video_id={platform_post_id}",
            "instagram": f"https://www.instagram.com/p/{platform_post_id}/",
        }
        
        if platform not in comment_urls:
            return
        
        await page.goto(comment_urls[platform])
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        
        # Find unreplied comments
        comment_selectors = {
            "youtube": 'ytcp-comment-thread:not(.replied)',
            "tiktok": '.comment-item:not(.replied)',
            "facebook": '[data-testid="comment"]:not(.replied)',
            "instagram": 'article:not(.replied)',
        }
        
        comments = await page.query_selector_all(comment_selectors.get(platform, '.comment:not(.replied)'))
        
        for i, comment in enumerate(comments[:self.config["distribution"]["max_replies_per_platform"]]):
            try:
                # Extract comment text
                text_elem = await comment.query_selector('text, span, div')
                comment_text = await text_elem.text_content() if text_elem else ""
                
                # Generate reply
                reply = self._generate_reply(comment_text, prop)
                
                # Post reply
                await self._post_reply(page, platform, comment, reply)
                
                # Log
                self._log_engagement(video_id, platform, comment_text, reply)
                
                # Mark as replied
                await comment.evaluate("el => el.classList.add('replied')")
                
                await page.wait_for_timeout(2000)  # Rate limit
                
            except Exception as e:
                logger.warning(f"Failed to reply to comment {i}: {e}")
    
    def _generate_reply(self, comment_text: str, prop: str) -> str:
        """Generate engagement reply."""
        template = random.choice(self.ENGAGEMENT_TEMPLATES)
        return template.format(prop=prop)
    
    async def _post_reply(self, page: Page, platform: str, comment_el, reply: str):
        """Post a reply to a comment."""
        if platform == "youtube":
            await comment_el.click('button:has-text("Reply")')
            await page.fill('textarea[placeholder*="Reply"]', reply)
            await page.click('button:has-text("Reply"):not([disabled])')
        
        elif platform == "tiktok":
            await comment_el.click('button:has-text("Reply")')
            await page.fill('input[placeholder*="Reply"]', reply)
            await page.keyboard.press("Enter")
        
        elif platform == "facebook":
            await comment_el.click('button:has-text("Reply")')
            await page.fill('div[contenteditable="true"][role="textbox"]', reply)
            await page.keyboard.press("Enter")
        
        elif platform == "instagram":
            await comment_el.click('button:has-text("Reply")')
            await page.fill('textarea[placeholder*="Reply"]', reply)
            await page.keyboard.press("Enter")
    
    def _log_engagement(self, video_id: int, platform: str, comment: str, reply: str):
        """Log engagement action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO engagement_log (video_id, platform, comment_text, reply_text)
                VALUES (?, ?, ?, ?)
            """, (video_id, platform, comment[:500], reply))
            conn.commit()
    
    # ==================== ANALYTICS ====================
    
    async def collect_metrics(self):
        """Collect analytics from all platforms."""
        logger.info("Collecting metrics...")
        
        for platform in self.enabled_platforms:
            try:
                await self._collect_platform_metrics(platform)
            except Exception as e:
                logger.error(f"Metrics collection failed for {platform}: {e}")
    
    async def _collect_platform_metrics(self, platform: str):
        """Collect metrics for one platform."""
        page = self.pages[platform]
        
        # Get videos posted in last 7 days
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            videos = conn.execute("""
                SELECT v.id, v.prop, p.platform_post_id
                FROM videos v
                JOIN posts p ON v.id = p.video_id
                WHERE p.platform = ? AND p.posted_at > datetime('now', '-7 days')
            """, (platform,)).fetchall()
        
        for video in videos:
            metrics = await self._fetch_video_metrics(page, platform, video["platform_post_id"])
            
            if metrics:
                self._save_metrics(video["id"], platform, metrics)
    
    async def _fetch_video_metrics(self, page: Page, platform: str, post_id: str) -> Optional[Dict]:
        """Fetch metrics for a specific video."""
        # This would use platform analytics pages or APIs
        # Simplified for now - returns mock structure
        return {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "retention": {"3s": 0, "15s": 0, "50pct": 0, "100pct": 0},
            "ctr": 0.0,
        }
    
    def _save_metrics(self, video_id: int, platform: str, metrics: Dict):
        """Save metrics to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO performance_log 
                (video_id, platform, views, likes, comments, shares, retention_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                video_id, platform,
                metrics.get("views", 0),
                metrics.get("likes", 0),
                metrics.get("comments", 0),
                metrics.get("shares", 0),
                json.dumps(metrics.get("retention", {}))
            ))
            conn.commit()


# ==================== MAIN FOR TESTING ====================

async def main():
    import yaml
    with open("../config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    agent = DistributionAgent(config)
    await agent.start()
    
    try:
        # Test posting (requires actual video file)
        print("Distribution agent ready. Platforms:", agent.enabled_platforms)
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())