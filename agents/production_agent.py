#!/usr/bin/env python3
"""
PRODUCTION AGENT
Browser automation for Google Flow, Google AI Studio, CapCut web.
Generates character sheets, video clips, voiceovers, edits final video.
"""

import asyncio
import logging
import json
import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class ProductionAgent:
    def __init__(self, config: dict):
        self.config = config
        self.db_path = Path(config["database"]["path"])
        self.auth_dir = Path(config["paths"]["auth_dir"])
        self.assets_dir = Path(config["paths"]["assets_dir"])
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Style DNA from config
        self.style = config["production"]["style_dna"]
        self.flow_config = config["production"]["google_flow"]
        self.capcut_config = config["production"]["capcut"]
    
    async def start(self):
        """Launch browser with persisted auth states."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        
        # Load auth state for Google services
        auth_file = self.auth_dir / "flow_google_com_auth.json"
        if auth_file.exists():
            self.context = await self.browser.new_context(storage_state=str(auth_file))
        else:
            self.context = await self.browser.new_context()
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(120000)  # 2 min for generations
        logger.info("Production agent browser started")
    
    async def close(self):
        """Clean shutdown."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        logger.info("Production agent closed")
    
    # ==================== CHARACTER SHEETS ====================
    
    async def lock_characters(self, characters: List[Dict]) -> Dict[str, str]:
        """Ensure all characters have locked reference images. Returns {name: flow_id}."""
        locked = {}
        
        for char in characters:
            name = char["name"]
            
            # Check if already locked in DB
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT flow_id FROM characters WHERE name=?", (name,)
                ).fetchone()
            
            if row and row[0]:
                locked[name] = row[0]
                logger.info(f"Character {name} already locked: {row[0]}")
                continue
            
            # Generate new character sheet
            flow_id = await self.generate_character_sheet(char)
            locked[name] = flow_id
            
            # Save to DB
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO characters (name, flow_id, outfit_color, props_held, reference_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, flow_id, char.get("outfit_color", "blue"), 
                      json.dumps(char.get("props", [])), ""))
                conn.commit()
        
        return locked
    
    async def generate_character_sheet(self, char_spec: Dict) -> str:
        """Generate character sheet in Google Flow, return Flow image ID."""
        # Fallback: return placeholder if browser not available
        if not hasattr(self, 'page') or self.page is None:
            return f"char_{char_spec['name']}_fallback"
        
        await self.page.goto("https://flow.google.com")
        await self.page.wait_for_load_state("networkidle")
        
        # Click New Project -> Image
        await self.page.click('button:has-text("New project")')
        await self.page.wait_for_selector('button:has-text("Image")', timeout=10000)
        await self.page.click('button:has-text("Image")')
        
        # Configure settings
        await self.page.select_option('select[name="model"]', self.flow_config["image_model"])
        await self.page.select_option('select[name="aspectRatio"]', "9:16")
        await self.page.select_option('select[name="variants"]', str(self.flow_config["image_variants"]))
        
        # Build prompt
        prompt = self._build_character_prompt(char_spec)
        await self.page.fill('textarea[placeholder*="prompt"]', prompt)
        
        # Generate
        await self.page.click('button:has-text("Generate")')
        
        # Wait for results
        await self.page.wait_for_selector('[data-testid="generated-image"]', timeout=180000)
        
        # Auto-select best variant (first one for now)
        # In production, could use CLIP scoring or human-in-loop
        await self.page.click('[data-testid="generated-image"]:first-child button:has-text("Save")')
        
        # Get Flow ID from response
        flow_id = await self.page.evaluate("""
            () => {
                const saveBtn = document.querySelector('[data-testid="generated-image"]:first-child button:has-text("Save")');
                return saveBtn?.dataset?.imageId || `char_${Date.now()}`;
            }
        """)
        
        logger.info(f"Generated character sheet for {char_spec['name']}: {flow_id}")
        return flow_id
    
    async def generate_video_prompts(self, story: Dict, character_sheet: str, adjustments: Optional[Dict] = None) -> List[Dict]:
        """Generate shot-by-shot video prompts from story."""
        # Fallback: create prompts from story structure
        shots = []
        narration_lines = story.get("narration", [])
        
        for i, line in enumerate(narration_lines[:10]):
            shots.append({
                "shot_number": i + 1,
                "beat": ["hook", "escalation", "prop_reveal", "obstacle", "payoff", "twist"][i % 6],
                "time_start": i * 6,
                "time_end": (i + 1) * 6,
                "visual_description": f"Stickman scene with prop visible, cinematic lighting",
                "narration_line": line,
                "camera_move": ["dolly_in", "truck_right", "orbit_slow", "pedestal_up", "dolly_out_wide", "static_hold"][i % 6],
                "prop_visible": i in [0, 2, 4],
                "prop_name": story.get("prop", "unknown"),
                "character_refs": ["protagonist"],
                "video_prompt": f"Stickman animation shot {i+1}: {line}"
            })
        
        # Pad to 10 shots if needed
        while len(shots) < 10:
            shots.append({
                "shot_number": len(shots) + 1,
                "beat": "filler",
                "time_start": len(shots) * 6,
                "time_end": (len(shots) + 1) * 6,
                "visual_description": "Stickman scene",
                "narration_line": "",
                "camera_move": "static_hold",
                "prop_visible": False,
                "prop_name": "",
                "character_refs": [],
                "video_prompt": "Stickman animation filler"
            })
        
        return shots
    
    async def produce_video(self, video_prompts: List[Dict], story: Dict, character_sheet: str) -> Dict:
        """Produce final video from clips."""
        # Fallback: return metadata only
        prop = story.get("prop", "Unknown")
        return {
            "final_video_path": "",
            "thumbnail_path": "",
            "title_main": f"How a {prop} Changed History",
            "title_youtube": f"How a {prop} Changed History #Shorts",
            "title_tiktok": f"The {prop} story you didn't know #history",
            "title_facebook": f"Watch: How the {prop} shocked history",
            "title_instagram": f"The {prop} that changed everything #reels",
            "description": f"This is the true story of how a {prop} changed history. Made with free AI tools.",
            "hashtags": ["#Shorts", "#History", "#Facts", "#Animation", "#AI"]
        }
    
    def _build_character_prompt(self, char: Dict) -> str:
        """Build character sheet prompt per style DNA."""
        outfit = char.get("outfit_color", "blue")
        role = char.get("role", "main")
        
        return f"""
Character sheet, {char['name']}, 2D stickman marker style:
- White circular marker head (1/3 body height, ~33% ratio)
- Thick black outline 3px
- Solid {outfit} outfit (single color, no patterns)
- Thin black limbs 1.5px
- Head wobble ±2 degrees per frame (subtle)
- Multiple poses: front, 3/4, side, back, close-up head
- Expressions: neutral, surprised, determined, scared, thinking
- Turnaround reference
- Clean white background
- High contrast, 4K
- Consistent proportions across all poses
- Role: {role}
Style reference: Bryson Clips Animation - 2D marker characters in 3D toon worlds
""".strip()
    
    # ==================== VIDEO CLIPS ====================
    
    async def generate_video_clip(self, shot: Dict, prev_frame_id: str = None) -> Tuple[str, str]:
        """Generate one 10s video clip in Google Flow. Returns (local_path, last_frame_id)."""
        await self.page.goto("https://flow.google.com")
        await self.page.wait_for_load_state("networkidle")
        
        # New project -> Video
        await self.page.click('button:has-text("New project")')
        await self.page.wait_for_selector('button:has-text("Video")', timeout=10000)
        await self.page.click('button:has-text("Video")')
        
        # Configure
        await self.page.select_option('select[name="model"]', self.flow_config["video_model"])
        await self.page.select_option('select[name="duration"]', str(self.flow_config["video_duration_sec"]))
        await self.page.select_option('select[name="aspectRatio"]', self.flow_config["aspect_ratio"])
        await self.page.select_option('select[name="variants"]', str(self.flow_config["video_variants"]))
        
        # Attach character references via Ingredients
        for char_name in shot.get("character_refs", []):
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT flow_id FROM characters WHERE name=?", (char_name,)).fetchone()
            if row:
                await self.page.click('button:has-text("Add ingredient")')
                await self.page.fill('input[placeholder*="ingredient"]', row[0])
                await self.page.keyboard.press("Enter")
                await self.page.wait_for_timeout(500)
        
        # Attach previous frame for continuity
        if prev_frame_id:
            await self.page.click('button:has-text("Add reference frame")')
            await self.page.fill('input[placeholder*="reference"]', prev_frame_id)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(500)
        
        # Build and submit prompt
        prompt = self._build_video_prompt(shot)
        await self.page.fill('textarea[placeholder*="prompt"]', prompt)
        
        # Generate
        await self.page.click('button:has-text("Generate")')
        
        # Wait for video
        await self.page.wait_for_selector('video[data-testid="generated-video"]', timeout=300000)
        
        # Download
        clip_path = await self._download_generated_video(shot["shot_number"])
        
        # Save last frame for next clip
        last_frame_id = await self._save_last_frame(clip_path, shot["shot_number"])
        
        logger.info(f"Generated clip {shot['shot_number']}: {clip_path}")
        return clip_path, last_frame_id
    
    def _build_video_prompt(self, shot: Dict) -> str:
        """Build video generation prompt with style DNA enforced."""
        char_refs = ", ".join(shot.get("character_refs", []))
        prop = shot.get("prop_visible", False)
        
        return f"""
{shot['visual_description']}

TECHNICAL SPECS:
- Camera: {shot['camera_move']} ONLY (gliding, no cuts, no jumps)
- Duration: 10 seconds, 30fps
- Style: 2D marker stickman characters in colorful toon-shaded 3D world
- Shadows: Deep blue-purple #2D1B4E, NEVER pure black
- Lighting: Cinematic, soft, ambient occlusion
- Characters: {char_refs} - white circular heads (1/3 body), thick 3px black outlines, thin 1.5px limbs
- Head wobble: ±2° per frame
- Prop visible: {str(prop).lower()} - {shot.get('prop_name', 'the key prop')} must be clearly visible
- Environment: Colorful pastel 3D, soft shadows, toon shading
- Aspect: 9:16 vertical
- No text overlays, no jump cuts, no instant pans
- Narration sync: {shot['narration_line']}
""".strip()
    
    async def _download_generated_video(self, shot_number: int) -> str:
        """Download the generated video clip."""
        # Click download on first variant
        await self.page.click('video[data-testid="generated-video"] ~ button:has-text("Download")')
        
        # Wait for download
        download = await self.page.wait_for_event("download", timeout=30000)
        clip_dir = self.assets_dir / "clips"
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = clip_dir / f"shot_{shot_number:02d}_{download.suggested_filename}"
        await download.save_as(str(clip_path))
        
        return str(clip_path)
    
    async def _save_last_frame(self, clip_path: str, shot_number: int) -> str:
        """Extract and save last frame as reference for next clip."""
        # Use Flow's "save frame" feature or extract via ffmpeg
        # For automation, we'll use Flow's UI
        await self.page.click('button:has-text("Save frame")')
        await self.page.wait_for_timeout(2000)
        
        frame_id = await self.page.evaluate("() => window.lastSavedFrameId || `frame_${Date.now()}`")
        return frame_id
    
    # ==================== VOICEOVER ====================
    
    async def generate_voiceover(self, narration: str) -> str:
        """Generate voiceover using Google AI Studio TTS."""
        await self.page.goto("https://aistudio.google.com")
        await self.page.wait_for_load_state("networkidle")
        
        # Navigate to TTS
        await self.page.click('button:has-text("Generate")')
        await self.page.click('text="Text to Speech"')
        
        # Configure voice
        await self.page.select_option('select[name="voice"]', self.config["production"]["google_ai_studio"]["tts_voice"])
        await self.page.fill('input[name="speed"]', str(self.config["production"]["google_ai_studio"]["tts_speed"]))
        
        # Input narration
        await self.page.fill('textarea[placeholder*="text"]', narration)
        
        # Generate
        await self.page.click('button:has-text("Generate")')
        await self.page.wait_for_selector('audio[src*="blob:"]', timeout=60000)
        
        # Download
        download = await self.page.wait_for_event("download", timeout=30000)
        voice_dir = self.assets_dir / "voiceovers"
        voice_dir.mkdir(parents=True, exist_ok=True)
        voice_path = voice_dir / f"narration_{download.suggested_filename}"
        await download.save_as(str(voice_path))
        
        logger.info(f"Generated voiceover: {voice_path}")
        return str(voice_path)
    
    # ==================== CAPCUT EDIT ====================
    
    async def edit_in_capcut(self, clips: List[str], voiceover: str, shot_list: List[Dict]) -> str:
        """Edit clips + voiceover in CapCut web. Returns final MP4 path."""
        await self.page.goto("https://www.capcut.com/editor")
        await self.page.wait_for_load_state("networkidle")
        
        # Create new 9:16 project
        await self.page.click('button:has-text("Create new")')
        await self.page.click('text="9:16"')
        await self.page.wait_for_selector('[data-testid="timeline"]', timeout=10000)
        
        # Upload all media
        for clip in clips:
            await self._upload_media(clip)
        await self._upload_media(voiceover)
        
        # Add clips to timeline in order
        for i, clip in enumerate(clips):
            await self._add_to_timeline(clip, track="video", position=i)
        
        # Add voiceover to audio track
        await self._add_to_timeline(voiceover, track="audio", position=0)
        
        # Trim clips to match shot timing
        await self._sync_clips_to_narration(shot_list)
        
        # Auto-captions
        await self._add_auto_captions()
        
        # Audio levels
        await self._set_audio_levels()
        
        # Add foley
        await self._add_foley(shot_list)
        
        # Transitions
        await self._add_transitions()
        
        # Color grade
        await self._apply_color_grade()
        
        # Export
        final_path = await self._export_video()
        
        return final_path
    
    async def _upload_media(self, file_path: str):
        """Upload media file to CapCut."""
        await self.page.set_input_files('input[type="file"][accept*="video"], input[type="file"][accept*="audio"]', file_path)
        await self.page.wait_for_selector(f'text="{Path(file_path).name}"', timeout=60000)
    
    async def _add_to_timeline(self, file_path: str, track: str, position: int):
        """Add media to timeline at position."""
        # CapCut web: drag from media pool to timeline
        media_name = Path(file_path).name
        await self.page.drag_and_drop(
            f'[data-testid="media-item"]:has-text("{media_name}")',
            f'[data-testid="timeline-track-{track}"] >> nth={position}'
        )
    
    async def _sync_clips_to_narration(self, shot_list: List[Dict]):
        """Trim each clip to match narration timing."""
        for shot in shot_list:
            duration = shot["time_end"] - shot["time_start"]
            # CapCut: select clip, set duration
            await self.page.click(f'[data-testid="timeline-clip"] >> nth={shot["shot_number"]-1}')
            await self.page.fill('input[name="clip-duration"]', str(duration))
    
    async def _add_auto_captions(self):
        """Generate auto-captions with Quick style."""
        await self.page.click('button:has-text("Captions")')
        await self.page.click('button:has-text("Auto captions")')
        await self.page.click('text="Quick"')
        await self.page.fill('input[name="caption-size"]', str(self.capcut_config["caption_size_pct"]))
        await self.page.click('button:has-text("Generate")')
        await self.page.wait_for_selector('[data-testid="caption-track"]', timeout=30000)
    
    async def _set_audio_levels(self):
        """Set voiceover to 0dB, music to -18dB."""
        await self.page.click('[data-testid="audio-track-voiceover"]')
        await self.page.fill('input[name="volume"]', str(self.capcut_config["voice_volume_db"]))
        
        await self.page.click('[data-testid="audio-track-music"]')
        await self.page.fill('input[name="volume"]', str(self.capcut_config["music_volume_db"]))
    
    async def _add_foley(self, shot_list: List[Dict]):
        """Add foley sounds at key moments."""
        foley_dir = self.assets_dir / "foley"
        foley_map = {
            "dolly_in": "whoosh",
            "dolly_out_wide": "woosh_swoosh",
            "truck_right": "whoosh",
            "truck_left": "whoosh",
            "pedestal_up": "swing_whoosh",
            "pedestal_down": "swing_whoosh",
            "orbit_slow": "magic_chime",
            "static_hold": "rise_drone",
        }
        
        for shot in shot_list:
            move = shot["camera_move"]
            foley_name = foley_map.get(move, "whoosh")
            foley_path = foley_dir / f"{foley_name}.wav"
            
            if foley_path.exists():
                await self._upload_media(str(foley_path))
                # Add at shot start
                await self._add_to_timeline(str(foley_path), track="audio", position=shot["shot_number"])
                # Set foley volume lower
                await self.page.click(f'[data-testid="timeline-clip-audio"] >> nth={shot["shot_number"]}')
                await self.page.fill('input[name="volume"]', "-12")
    
    async def _add_transitions(self):
        """Add cross-dissolve transitions between clips."""
        await self.page.click('button:has-text("Transitions")')
        await self.page.click(f'text="{self.capcut_config["transition"]}"')
        
        # Apply between all video clips
        clip_count = await self.page.locator('[data-testid="timeline-track-video"] [data-testid="timeline-clip"]').count()
        for i in range(clip_count - 1):
            await self.page.click(f'[data-testid="timeline-gap"] >> nth={i}')
            await self.page.fill('input[name="transition-duration"]', str(self.capcut_config["transition_duration"]))
    
    async def _apply_color_grade(self):
        """Apply subtle color grade: warmth +5, contrast +5, saturation +5."""
        await self.page.click('button:has-text("Adjust")')
        await self.page.fill('input[name="temperature"]', "5")
        await self.page.fill('input[name="contrast"]', "5")
        await self.page.fill('input[name="saturation"]', "5")
        await self.page.click('button:has-text("Apply to all")')
    
    async def _export_video(self) -> str:
        """Export final video."""
        await self.page.click('button:has-text("Export")')
        await self.page.select_option('select[name="resolution"]', self.capcut_config["resolution"])
        await self.page.select_option('select[name="framerate"]', str(self.capcut_config["framerate"]))
        await self.page.select_option('select[name="bitrate"]', self.capcut_config["bitrate"])
        await self.page.click('button:has-text("Export")')
        
        download = await self.page.wait_for_event("download", timeout=300000)
        export_dir = self.assets_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        final_path = export_dir / f"final_{download.suggested_filename}"
        await download.save_as(str(final_path))
        
        logger.info(f"Exported final video: {final_path}")
        return str(final_path)
    
    # ==================== THUMBNAIL ====================
    
    async def generate_thumbnail(self, prompt: str) -> str:
        """Generate thumbnail in Google Flow Image mode."""
        await self.page.goto("https://flow.google.com")
        await self.page.wait_for_load_state("networkidle")
        
        await self.page.click('button:has-text("New project")')
        await self.page.click('button:has-text("Image")')
        
        await self.page.select_option('select[name="model"]', self.flow_config["image_model"])
        await self.page.select_option('select[name="aspectRatio"]', "9:16")
        await self.page.select_option('select[name="variants"]', "4")
        
        await self.page.fill('textarea[placeholder*="prompt"]', prompt)
        await self.page.click('button:has-text("Generate")')
        
        await self.page.wait_for_selector('[data-testid="generated-image"]', timeout=120000)
        
        # Download first variant
        await self.page.click('[data-testid="generated-image"]:first-child button:has-text("Download")')
        
        download = await self.page.wait_for_event("download", timeout=30000)
        thumb_dir = self.assets_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"thumb_{download.suggested_filename}"
        await download.save_as(str(thumb_path))
        
        logger.info(f"Generated thumbnail: {thumb_path}")
        return str(thumb_path)


# ==================== MAIN FOR TESTING ====================

async def main():
    import yaml
    with open("../config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    agent = ProductionAgent(config)
    await agent.start()
    
    try:
        # Test character generation
        chars = [
            {"name": "protagonist", "outfit_color": "blue", "role": "main"},
            {"name": "antagonist", "outfit_color": "red", "role": "opposer"}
        ]
        locked = await agent.lock_characters(chars)
        print(f"Locked characters: {locked}")
        
        # Test video clip
        shot = {
            "shot_number": 1,
            "beat": "hook",
            "visual_description": "Dark room, mysterious glowing artifact on pedestal",
            "narration_line": "A mirror changed a horse race.",
            "camera_move": "dolly_in",
            "prop_visible": True,
            "prop_name": "mirror",
            "character_refs": ["protagonist"]
        }
        clip, frame = await agent.generate_video_clip(shot)
        print(f"Clip: {clip}, Frame: {frame}")
        
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())