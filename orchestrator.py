#!/usr/bin/env python3
"""
ORCHESTRATOR
Main scheduler that runs the full pipeline 4x/day.
Uses OpenCode + GLM 5.3 Flash (free) for coordination.
Bryson Clips Animation - Fully automated viral stickman shorts.
"""

import asyncio
import logging
import json
import schedule
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import yaml

# Import agents
import sys
sys.path.append(str(Path(__file__).parent))
from agents.ideation_agent import IdeationAgent
from agents.production_agent import ProductionAgent
from agents.distribution_agent import DistributionAgent
from evolution.optimizer import get_active_adjustments, inject_adjustments_into_prompt, generate_optimization_report

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.db_path = Path(self.config["database"]["path"])
        self.state_dir = Path(self.config["paths"]["state_dir"])
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.ideation_agent: Optional[IdeationAgent] = None
        self.production_agent: Optional[ProductionAgent] = None
        self.distribution_agent: Optional[DistributionAgent] = None
        
        self.cycle_count = 0
        self.max_cycles_per_day = self.config["orchestrator"]["cycles_per_day"]
        self.cycle_times = self.config["orchestrator"]["cycle_times"]  # e.g., ["06:00", "12:00", "18:00", "00:00"]
        
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with all required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cycle_id INTEGER,
                    topic TEXT,
                    prop TEXT,
                    era TEXT,
                    story_json TEXT,
                    character_sheet TEXT,
                    video_prompts_json TEXT,
                    voiceover_path TEXT,
                    final_video_path TEXT,
                    thumbnail_path TEXT,
                    title_main TEXT,
                    title_youtube TEXT,
                    title_tiktok TEXT,
                    title_facebook TEXT,
                    title_instagram TEXT,
                    description TEXT,
                    hashtags_json TEXT,
                    status TEXT DEFAULT 'pending',
                    error TEXT
                );
                
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER,
                    platform TEXT,
                    platform_post_id TEXT,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'posted',
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                );
                
                CREATE TABLE IF NOT EXISTS performance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER,
                    platform TEXT,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    retention_json TEXT,
                    ctr REAL DEFAULT 0,
                    revenue_est REAL DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                );
                
                CREATE TABLE IF NOT EXISTS engagement_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER,
                    platform TEXT,
                    comment_text TEXT,
                    reply_text TEXT,
                    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                );
                
                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    logline TEXT,
                    prop TEXT,
                    teaser TEXT,
                    era TEXT,
                    source_url TEXT,
                    story_json TEXT,
                    character_sheet TEXT,
                    title_main TEXT,
                    status TEXT DEFAULT 'pending',
                    fact_checked INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    selected_at TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    flow_id TEXT,
                    prompt_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS cycle_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    videos_generated INTEGER DEFAULT 0,
                    videos_posted INTEGER DEFAULT 0,
                    errors TEXT,
                    status TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_videos_cycle ON videos(cycle_id);
                CREATE INDEX IF NOT EXISTS idx_posts_video ON posts(video_id);
                CREATE INDEX IF NOT EXISTS idx_perf_video ON performance_log(video_id);
                CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
                CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
            """)
            conn.commit()
    
    async def start_agents(self):
        """Initialize and start all agents."""
        logger.info("Starting agents...")
        
        self.ideation_agent = IdeationAgent(self.config)
        self.production_agent = ProductionAgent(self.config)
        self.distribution_agent = DistributionAgent(self.config)
        
        # Check for fallback mode OR auto-select best available backend
        import os
        use_fallback = os.environ.get("USE_FALLBACK", "false").lower() == "true"
        if use_fallback:
            logger.info("Running in FALLBACK MODE - using template-based generation")
            self.config["ideation"]["backend"] = "fallback"
            self.config["production"]["google_flow"]["enabled"] = False
        else:
            # Auto-detect best backend from available env vars — try GLM first (reliable CN endpoint)
            if os.environ.get("GLM_API_KEY"):
                self.config["ideation"]["backend"] = "glm"
                logger.info("Using GLM backend (free tier)")
            elif os.environ.get("GEMINI_API_KEY"):
                self.config["ideation"]["backend"] = "gemini"
                logger.info("Using Gemini backend (free tier)")
            elif os.environ.get("OPENAI_API_KEY"):
                self.config["ideation"]["backend"] = "openai"
                logger.info("Using OpenAI backend")
            elif os.environ.get("OLLAMA_HOST"):
                self.config["ideation"]["backend"] = "ollama"
                logger.info("Using Ollama backend")
            else:
                self.config["ideation"]["backend"] = "fallback"
                logger.info("No API keys found - using fallback mode")
        
        await self.ideation_agent.start()
        await self.production_agent.start()
        await self.distribution_agent.start()
        
        logger.info("All agents started")
    
    async def stop_agents(self):
        """Stop all agents."""
        logger.info("Stopping agents...")
        
        if self.distribution_agent:
            await self.distribution_agent.close()
        if self.production_agent:
            await self.production_agent.close()
        if self.ideation_agent:
            await self.ideation_agent.close()
        
        logger.info("All agents stopped")
    
    def _get_next_cycle_id(self) -> int:
        """Get next cycle ID."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("SELECT MAX(cycle_id) FROM cycle_log").fetchone()
            return (result[0] or 0) + 1
    
    def _log_cycle_start(self, cycle_id: int) -> int:
        """Log cycle start."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO cycle_log (cycle_id, started_at, status) VALUES (?, CURRENT_TIMESTAMP, 'running')",
                (cycle_id,)
            )
            conn.commit()
            return cursor.lastrowid
    
    def _log_cycle_end(self, cycle_id: int, videos_gen: int, videos_posted: int, errors: List[str]):
        """Log cycle completion."""
        status = "completed" if not errors else "completed_with_errors"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE cycle_log 
                SET completed_at = CURRENT_TIMESTAMP, 
                    videos_generated = ?, 
                    videos_posted = ?, 
                    errors = ?,
                    status = ?
                WHERE cycle_id = ?
            """, (videos_gen, videos_posted, json.dumps(errors), status, cycle_id))
            conn.commit()
    
    async def run_cycle(self):
        """Execute one full production cycle."""
        import os
        # Auto-start agents if not already running (for standalone CI runs)
        if self.ideation_agent is None:
            await self.start_agents()
        
        use_fallback = os.environ.get("USE_FALLBACK", "false").lower() == "true"
        
        cycle_id = self._get_next_cycle_id()
        self._log_cycle_start(cycle_id)
        
        logger.info(f"=== STARTING CYCLE {cycle_id} ===")
        errors = []
        videos_generated = 0
        videos_posted = 0
        
        try:
            # 1. IDEATION: Generate ideas (fallback if no LLM available)
            logger.info("Phase 1: Ideation")
            adjustments = get_active_adjustments()
            
            if use_fallback:
                logger.info("Using FALLBACK ideation - generating template ideas")
                ideas = await self.ideation_agent.generate_ideas(
                    count=self.config["ideation"]["ideas_per_batch"],
                    adjustments=adjustments,
                    use_fallback=True
                )
            else:
                ideas = await self.ideation_agent.generate_ideas(
                    count=self.config["ideation"]["ideas_per_batch"],
                    adjustments=adjustments
                )
            
            if not ideas:
                raise Exception("No ideas generated")
            
            # Store all generated ideas in DB for future reference
            with sqlite3.connect(self.db_path) as conn:
                for idea in ideas:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO ideas (id, logline, prop, teaser, status, created_at, fact_checked, source_url)
                            VALUES (?, ?, ?, ?, 'pending', ?, 1, ?)
                        """, (
                            idea.get('id'), 
                            idea.get('logline', idea.get('topic', '')), 
                            idea.get('prop', ''), 
                            idea.get('teaser', ''),
                            datetime.now(),
                            idea.get('source', '')
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to store idea: {e}")
                conn.commit()
            
            best_idea = ideas[0]  # Already scored and sorted
            logger.info(f"Selected idea: {best_idea['topic']} | Prop: {best_idea['prop']}")
            
            # 2. STORY GENERATION: Full story structure
            logger.info("Phase 2: Story Generation")
            if use_fallback:
                logger.info("Using FALLBACK story generation - template-based")
                story = self.ideation_agent._fallback_story(best_idea)
            else:
                story = self.ideation_agent.generate_story(best_idea, adjustments)
            
            # 3. CHARACTER SHEETS: Consistent character prompts
            logger.info("Phase 3: Character Sheets")
            character_sheet = await self.production_agent.generate_character_sheet(story)
            
            # 4. VIDEO PROMPTS: 10-shot breakdown
            logger.info("Phase 4: Video Prompts")
            video_prompts = await self.production_agent.generate_video_prompts(story, character_sheet, adjustments)
            
            # 5. PRODUCTION: In fallback mode, skip actual video generation
            if use_fallback:
                logger.info("Phase 5: PRODUCTION SKIPPED (fallback mode)")
                video_result = {
                    "final_video_path": "",
                    "thumbnail_path": "",
                    "title_main": f"How a {best_idea['prop']} Changed History",
                    "title_youtube": f"How a {best_idea['prop']} Changed History #Shorts",
                    "title_tiktok": f"The {best_idea['prop']} story you didn't know #history",
                    "title_facebook": f"Watch: How the {best_idea['prop']} shocked history",
                    "title_instagram": f"The {best_idea['prop']} that changed everything #reels",
                    "description": f"This is the true story of how a {best_idea['prop']} {best_idea['topic']}. Made with free AI tools.",
                    "hashtags": ["#Shorts", "#History", "#Facts", "#Animation", "#AI"]
                }
            else:
                logger.info("Phase 5: Production")
                video_result = await self.production_agent.produce_video(
                    video_prompts, story, character_sheet
                )
            
            # Save to database
            video_id = self._save_video(
                cycle_id, best_idea, story, character_sheet, 
                video_prompts, video_result
            )
            videos_generated = 1
            
            # 6. DISTRIBUTION: Skip posting in fallback mode
            if use_fallback:
                logger.info("Phase 6: DISTRIBUTION SKIPPED (no auth in CI)")
            else:
                logger.info("Phase 6: Distribution")
                await self.distribution_agent.post_to_all(
                    video_result["final_video_path"],
                    {
                        "video_id": video_id,
                        "prop": best_idea["prop"],
                        "title_main": video_result["title_main"],
                        "title_youtube": video_result["title_youtube"],
                        "title_tiktok": video_result["title_tiktok"],
                        "title_facebook": video_result["title_facebook"],
                        "title_instagram": video_result["title_instagram"],
                        "description": video_result["description"],
                        "hashtags": video_result["hashtags"],
                    },
                    video_result["thumbnail_path"]
                )
                videos_posted = 1
            
            logger.info(f"Cycle {cycle_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Cycle {cycle_id} failed: {e}")
            errors.append(str(e))
        
        finally:
            self._log_cycle_end(cycle_id, videos_generated, videos_posted, errors)
            self.cycle_count += 1
    
    def _save_video(self, cycle_id: int, idea: Dict, story: Dict, 
                    character_sheet: str, video_prompts: List[Dict], 
                    video_result: Dict) -> int:
        """Save video record to database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO videos 
                (cycle_id, topic, prop, era, story_json, character_sheet, 
                 video_prompts_json, voiceover_path, final_video_path, 
                 thumbnail_path, title_main, title_youtube, title_tiktok,
                 title_facebook, title_instagram, description, hashtags_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            """, (
                cycle_id,
                idea["topic"],
                idea["prop"],
                idea["era"],
                json.dumps(story),
                character_sheet,
                json.dumps(video_prompts),
                video_result.get("voiceover_path", ""),
                video_result["final_video_path"],
                video_result["thumbnail_path"],
                video_result["title_main"],
                video_result["title_youtube"],
                video_result["title_tiktok"],
                video_result["title_facebook"],
                video_result["title_instagram"],
                video_result["description"],
                json.dumps(video_result["hashtags"])
            ))
            conn.commit()
            return cursor.lastrowid
    
    async def run_daily_optimization(self):
        """Run daily evolution optimization (call at end of day)."""
        logger.info("Running daily optimization...")
        
        # Get last 7 days of performance data
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            data = conn.execute("""
                SELECT v.id, v.prop, v.created_at,
                       AVG(p.views * 1.0 / NULLIF(v.views, 0)) as hook_3s,
                       AVG(pl.retention_json) as retention_50,
                       0 as completion,
                       0 as ctr,
                       0 as revenue_est
                FROM videos v
                LEFT JOIN posts p ON v.id = p.video_id
                LEFT JOIN performance_log pl ON v.id = pl.video_id
                WHERE v.created_at > datetime('now', '-7 days')
                GROUP BY v.id
            """).fetchall()
            
            # Simplified for now - in production, compute real metrics
            performance_data = []
            for row in data:
                performance_data.append({
                    "video_id": row["id"],
                    "prop": row["prop"],
                    "created_at": row["created_at"],
                    "hook_3s": 0.72,  # Would be computed from retention curves
                    "retention_50": 0.44,
                    "completion": 0.34,
                    "ctr": 0.055,
                    "revenue_est": 55,
                })
        
        if performance_data:
            report = generate_optimization_report(performance_data)
            logger.info(report)
        
        # Also run engagement processing
        await self.distribution_agent.process_pending_engagement()
        
        # Collect metrics
        await self.distribution_agent.collect_metrics()
    
    def schedule_cycles(self):
        """Set up scheduled cycles."""
        for cycle_time in self.cycle_times:
            schedule.every().day.at(cycle_time).do(
                lambda: asyncio.run(self.run_cycle())
            )
            logger.info(f"Scheduled cycle at {cycle_time}")
        
        # Daily optimization at 23:50
        schedule.every().day.at("23:50").do(
            lambda: asyncio.run(self.run_daily_optimization())
        )
    
    async def run_forever(self):
        """Main loop - runs scheduled cycles forever."""
        await self.start_agents()
        self.schedule_cycles()
        
        logger.info("Orchestrator running forever. Press Ctrl+C to stop.")
        
        try:
            while True:
                schedule.run_pending()
                await asyncio.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.stop_agents()


async def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    
    orchestrator = Orchestrator()
    await orchestrator.run_forever()


if __name__ == "__main__":
    asyncio.run(main())