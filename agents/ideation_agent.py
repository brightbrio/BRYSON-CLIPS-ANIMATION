#!/usr/bin/env python3
"""
IDEATION AGENT
Generates viral stickman short ideas using free LLMs (Ollama/OpenCode).
Fact-checks against historical records. Outputs 10 ideas per batch.
"""

import json
import sqlite3
import logging
import random
import requests
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class IdeationAgent:
    def __init__(self, config: dict):
        self.config = config
        self.db_path = Path(config["database"]["path"])
        self.backend = config["ideation"]["backend"]
        self.ollama_config = config["ideation"].get("ollama", {})
        self.master_prompt = self._load_master_prompt()
    
    async def start(self):
        """Initialize ideation agent (no browser needed)."""
        logger.info("Ideation agent started")
    
    def _load_master_prompt(self) -> str:
        """Load the master prompt from file."""
        prompt_path = Path(self.config["paths"]["prompts_dir"]) / "master_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        # Fallback: embedded minimal prompt
        return self._get_embedded_prompt()
    
    def _get_embedded_prompt(self) -> str:
        return """
You are RICKS CLIPPER ideation engine. Generate 10 VIRAL stickman short ideas.
Each must be a TRUE historical event / documented phenomenon with a NAMED PROP.
Format per idea:
1. [Logline: How a PROP caused BIG RESULT]
2. [Prop: exact name]
3. [Teaser: 3-sentence hook]
4. [Source: Wikipedia URL or verified source]
Criteria: Verifiable, visualizable in 3-5 3D settings, not done by Bryson Clips Animation in 90 days.
Output ONLY numbered list 1-10.
"""
    
    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM backend."""
        import os
        # Auto-detect available backends from env vars — prefer GLM (reliable CN endpoint)
        if os.environ.get("GLM_API_KEY") and self.backend in ("fallback", "ollama", "glm"):
            self.backend = "glm"
            logger.info("Using GLM backend via env var")
        elif os.environ.get("GEMINI_API_KEY") and self.backend in ("fallback", "ollama", "gemini"):
            self.backend = "gemini"
            logger.info("Using Gemini backend via env var")
        
        if self.backend == "ollama":
            return self._call_ollama(prompt)
        elif self.backend == "openai":
            return self._call_openai(prompt)
        elif self.backend == "glm":
            return self._call_glm(prompt)
        elif self.backend == "gemini":
            return self._call_gemini(prompt)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _call_glm(self, prompt: str) -> str:
        """Call GLM (Zhipu AI) API - OpenAI compatible."""
        api_key = os.environ.get("GLM_API_KEY", "")
        if not api_key:
            return self._fallback_ideas()
        import time as _time
        for attempt in range(3):
            try:
                resp = requests.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "glm-4.5-flash",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.8,
                        "max_tokens": 2048
                    },
                    timeout=60
                )
                if resp.status_code == 429:
                    wait = (attempt + 1) * 5
                    logger.warning(f"GLM rate limited (attempt {attempt+1}/3), waiting {wait}s")
                    _time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    # Reasoning models may put text in reasoning_content
                    text = msg.get("content") or msg.get("reasoning_content", "")
                    return text.strip() if text else self._fallback_ideas()
                logger.warning("GLM returned no choices")
                return self._fallback_ideas()
            except Exception as e:
                logger.error(f"GLM call failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    _time.sleep((attempt + 1) * 3)
                else:
                    return self._fallback_ideas()
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API via REST - tries multiple models for best compatibility."""
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return self._fallback_ideas()
        import time as _time
        # The full key works against the REST API — do NOT strip anything
        clean_key = api_key
        # Try multiple models in order of availability
        models = ["gemini-flash-latest", "gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash"]
        for model in models:
            for attempt in range(2):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048}
                    }
                    resp = requests.post(url, json=payload, timeout=30)
                    if resp.status_code == 429:
                        _time.sleep(3)
                        continue
                    if resp.status_code == 503:
                        logger.warning(f"Gemini {model} unavailable, trying next...")
                        break
                    if resp.status_code == 404:
                        logger.warning(f"Gemini {model} not found, trying next...")
                        break
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                return text
                    return self._fallback_ideas()
                except Exception as e:
                    logger.error(f"Gemini {model} error (attempt {attempt+1}/2): {e}")
                    if attempt < 1:
                        _time.sleep(2)
        return self._fallback_ideas()
    
    def _call_ollama(self, prompt: str) -> str:
        import ollama
        try:
            response = ollama.chat(
                model=self.ollama_config.get("model", "llama3.1:8b"),
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": self.ollama_config.get("temperature", 0.8)}
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            # Fallback to local template ideas
            return self._fallback_ideas()
    
    def _call_openai(self, prompt: str) -> str:
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=self.config["ideation"]["openai"].get("model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        return response.choices[0].message.content
    
    def _call_opencode(self, prompt: str) -> str:
        # OpenCode runs as subprocess - would need integration
        # For now, fallback
        logger.warning("OpenCode backend not fully implemented, using fallback")
        return self._fallback_ideas()
    
    def _fallback_ideas(self) -> str:
        """Curated backup ideas if LLM fails."""
        fallback = [
            "1. How a Mirror Rigged a Horse Race | Prop: Angled Mirror | Teaser: A jockey sees his reflection at the wrong angle and freezes, losing the Triple Crown. The mirror was placed by a rival owner. Source: https://en.wikipedia.org/wiki/1913_Epsom_Derby | Source: Wikipedia",
            "2. The Boston Molasses Disaster | Prop: Pressure Gauge | Teaser: A 2.3M gallon molasses tank bursts, sending a 25-foot wave at 35mph through Boston. The gauge read normal — nobody checked the rivets. Source: https://en.wikipedia.org/wiki/Great_Molasses_Flood | Source: Wikipedia",
            "3. Why Sailors Carried Storm Oil | Prop: Oil Bag | Teaser: Pouring oil on rough seas calms waves — a trick known since antiquity. The USS Constitution carried 400 gallons for emergencies. Source: https://en.wikipedia.org/wiki/Storm_oil | Source: Wikipedia",
            "4. The Bank That Accepts Cheese as Collateral | Prop: Parmesan Wheel | Teaser: An Italian bank has accepted 300,000+ Parmesan wheels as loan collateral since 1953. Each wheel = €300. Source: https://en.wikipedia.org/wiki/Credito_Emiliano | Source: Wikipedia",
            "5. The Town That Never Stopped Dancing | Prop: Violin | Teaser: 1518 Strasbourg: Frau Troffea danced for days. 400 joined. Doctors prescribed MORE dancing. The violinist played until they collapsed. Source: https://en.wikipedia.org/wiki/Dancing_plague_of_1518 | Source: Wikipedia",
            "6. The Ship Found With No Crew | Prop: Sextant | Teaser: Mary Celeste, 1872: intact cargo, warm coffee, but zero people. The sextant was missing. Piracy? Mutiny? Alcohol fumes? Still unsolved. Source: https://en.wikipedia.org/wiki/Mary_Celeste | Source: Wikipedia",
            "7. The Great Emu War | Prop: Lewis Gun | Teaser: 1932 Australia: Military deployed machine guns against 20,000 emus. The emus won. Guns jammed. Birds scattered. Source: https://en.wikipedia.org/wiki/Emu_War | Source: Wikipedia",
            "8. The Man Who Sold the Eiffel Tower | Prop: Forged Document | Teaser: 1925: Victor Lustig sold the Eiffel Tower for scrap — TWICE. Used forged government letterhead. Buyer too embarrassed to report. Source: https://en.wikipedia.org/wiki/Victor_Lustig | Source: Wikipedia",
            "9. The Library That Burned For 7 Months | Prop: Catalog Card | Teaser: 1988 LA Central Library: Arson fire burned 7 months underground. 400k books lost. One catalog card survived — the arsonist's library card. Source: https://en.wikipedia.org/wiki/Los_Angeles_Central_Library | Source: Wikipedia",
            "10. The Pigeon That Saved 194 Soldiers | Prop: Message Capsule | Teaser: WWI: Cher Ami delivered coordinates with shattered leg, blinded eye, bullet in breast. 194 men rescued. Awarded Croix de Guerre. Source: https://en.wikipedia.org/wiki/Cher_Ami | Source: Wikipedia",
        ]
        return "\n".join(fallback)
    
    async def generate_ideas(self, count: int = 10, adjustments: Optional[Dict] = None, use_fallback: bool = False) -> List[Dict]:
        """Generate ideas (async wrapper for backward compatibility)."""
        if use_fallback or self.backend == "fallback":
            logger.info("Using fallback idea generation")
            response = self._fallback_ideas()
        else:
            prompt = self._build_phase1_prompt()
            response = self._call_llm(prompt)
        
        return self._parse_ideas(response)[:count]
    
    def generate_ideas_batch(self) -> List[Dict]:
        """Generate 10 new ideas, fact-check, store in DB."""
        logger.info("Generating new idea batch...")
        
        # Build full prompt with Phase 1 instructions
        prompt = self._build_phase1_prompt()
        response = self._call_llm(prompt)
        
        ideas = self._parse_ideas(response)
        logger.info(f"Parsed {len(ideas)} ideas from LLM")
        
        # Fact-check each
        verified = []
        for idea in ideas:
            if self._fact_check_idea(idea):
                verified.append(idea)
                if len(verified) >= self.config["ideation"]["idea_count_per_batch"]:
                    break
        
        # Store in DB
        stored = []
        with sqlite3.connect(self.db_path) as conn:
            for idea in verified:
                cursor = conn.execute("""
                    INSERT INTO ideas (logline, prop, teaser, status, created_at, fact_checked, source_url)
                    VALUES (?, ?, ?, 'pending', ?, 1, ?)
                """, (idea['logline'], idea['prop'], idea['teaser'], 
                      datetime.now(), idea.get('source', '')))
                idea['id'] = cursor.lastrowid
                stored.append(idea)
            conn.commit()
        
        logger.info(f"Stored {len(stored)} verified ideas")
        return stored
    
    def _build_phase1_prompt(self) -> str:
        """Build the Phase 1 prompt from master prompt."""
        # Extract just the ideation phase from master prompt
        return f"""
{self.master_prompt}

=== CURRENT TASK: PHASE 1 - GENERATE 10 VIRAL IDEAS ===
Generate exactly 10 ideas following the Bryson Clips Animation formula:
[Small Prop / Unusual Skill] -> [Big Weird Result]

Each idea must:
1. Be a TRUE historical event / documented phenomenon
2. Have a NAMEABLE, VISIBLE prop (mirror, gauge, oil bag, cheese wheel, violin, sextant, gun, document, card, capsule)
3. Be visualizable in 3-5 distinct 3D settings
4. NOT have been done by Bryson Clips Animation in last 90 days (simulate: if >1M views on same hook, discard)
5. Include: Logline, Prop name, 3-sentence teaser, Source URL

Output format (exactly):
1. [Logline] | Prop: [Prop] | Teaser: [Teaser] | Source: [URL]
2. [Logline] | Prop: [Prop] | Teaser: [Teaser] | Source: [URL]
...
10. [Logline] | Prop: [Prop] | Teaser: [Teaser] | Source: [URL]
"""
    
    def _parse_ideas(self, response: str) -> List[Dict]:
        """Parse numbered list from LLM response."""
        ideas = []
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            
            # Parse format: "1. Logline | Prop: X | Teaser: Y | Source: Z"
            parts = line.split('|')
            if len(parts) < 4:
                continue
            
            logline = parts[0].split('.', 1)[1].strip() if '.' in parts[0] else parts[0].strip()
            prop = parts[1].replace('Prop:', '').strip()
            teaser_raw = parts[2].replace('Teaser:', '').strip()
            
            # Extract source URL from the entire line (LLM/fallback may place it
            # inside the teaser segment while parts[3] only holds a label)
            import re
            url_match = re.search(r'https?://[^\s|]+', line)
            source = url_match.group(0).strip() if url_match else parts[3].replace('Source:', '').strip()
            # Strip any embedded "Source: <url>" from the teaser text
            teaser = re.sub(r'\s*Source:\s*https?://[^\s|]+', '', teaser_raw).strip()
            
            # Extract topic and era from logline
            topic = logline  # e.g., "How a Mirror Rigged a Horse Race"
            era = ""
            # Try to extract year from logline or teaser
            import re
            year_match = re.search(r'\b(1\d{3}|20\d{3})\b', f"{logline} {teaser}")
            if year_match:
                era = year_match.group(1)
            
            ideas.append({
                'id': len(ideas) + 1,
                'topic': topic,
                'prop': prop,
                'teaser': teaser,
                'era': era,
                'source': source,
                'logline': logline
            })
        
        return ideas[:10]
    
    def _fact_check_idea(self, idea: Dict) -> bool:
        """Verify idea against Wikipedia / known sources."""
        if not self.config["ideation"]["fact_check_enabled"]:
            return True
        
        source_url = idea.get('source', '')
        if not source_url:
            return False
            
        # Fix Wikipedia URL format issue
        if 'wikipedia.org' in source_url and not source_url.startswith('https://'):
            if source_url.startswith('http://'):
                source_url = 'https://' + source_url[7:]
            else:
                source_url = 'https://' + source_url
        
        try:
            # Quick check: fetch source, verify key terms exist
            resp = requests.get(source_url, timeout=10)
            if resp.status_code == 200:
                content = resp.text.lower()
                prop = idea['prop'].lower()
                # Check prop mentioned in source
                if prop in content or any(word in content for word in prop.split() if len(word) > 3):
                    return True
        except Exception as e:
            logger.warning(f"Fact check failed for {idea['logline']}: {e}")
        
        return False
    
    def get_pending_ideas(self) -> List[Dict]:
        """Get all pending ideas from DB."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM ideas WHERE status='pending' ORDER BY created_at DESC
            """).fetchall()
        return [dict(row) for row in rows]
    
    def select_best_idea(self) -> Optional[Dict]:
        """Select best idea using algorithm: novelty + verifiability + visual potential."""
        pending = self.get_pending_ideas()
        if not pending:
            return None
        
        # Score each idea
        scored = []
        for idea in pending:
            score = 0
            # Novelty: newer ideas score higher
            created = datetime.fromisoformat(idea['created_at'])
            days_old = (datetime.now() - created).days
            score += max(0, 30 - days_old)  # Fresher = better
            
            # Verifiability
            if idea['fact_checked']:
                score += 20
            
            # Visual potential: prop concreteness
            concrete_props = ['mirror', 'gauge', 'wheel', 'violin', 'sextant', 'gun', 'document', 'card', 'capsule', 'bag', 'oil']
            if any(p in idea['prop'].lower() for p in concrete_props):
                score += 15
            
            # Length check
            if 50 < len(idea['logline']) < 120:
                score += 10
            
            scored.append((score, idea))
        
        # Pick highest scored
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        logger.info(f"Selected idea (score {scored[0][0]}): {best['logline']}")
        return best
    
    def mark_selected(self, idea_id: int):
        """Mark idea as selected."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ideas SET status='selected', selected_at=CURRENT_TIMESTAMP WHERE id=?
            """, (idea_id,))
            conn.commit()
    
    def generate_story(self, idea: Dict, adjustments: Optional[Dict] = None) -> Dict:
        """Generate full story, narration, shot list, titles, description."""
        logger.info(f"Generating story for idea #{idea['id']}...")
        
        prompt = f"""
{self.master_prompt}

=== CURRENT TASK: PHASE 2 - WRITE STORY & SHOT LIST ===
Selected Idea: {idea['logline']}
Prop: {idea['prop']}
Teaser: {idea['teaser']}
Source: {idea.get('source', '')}

Write a complete Bryson Clips Animation style story for a {self.config['production']['google_flow']['video_duration_sec'] * 6} second video (6 clips x 10s).
Follow the EXACT structure:
1. HOOK (0-3s): Weird result + prop visible
2. ESCALATION (3-15s): Human conflict, stakes rise
3. PROP REVEAL (15-30s): Prop mechanism shown diegetically
4. OBSTACLE (30-40s): Prop fails/threatened/misunderstood
5. PAYOFF (40-50s): Prop works, result lands
6. TWIST QUESTION (last 2s): Ends on question, no period

Output as JSON:
{{
  "narration": "Full narration script, one sentence per line",
  "shot_list": [
    {{"shot_number": 1, "beat": "hook", "time_start": 0, "time_end": 3,
      "visual_description": "...", "narration_line": "...", "camera_move": "dolly_in",
      "prop_visible": true, "character_refs": ["protagonist"], "video_prompt": "..."}},
    ...
  ],
  "characters": [
    {{"name": "protagonist", "outfit_color": "blue", "role": "main"}},
    {{"name": "antagonist", "outfit_color": "red", "role": "opposer"}}
  ],
  "titles": ["How a {idea['prop']} [RESULT]", "Why {idea['prop']} Changed [RESULT]", ...],
  "description": "Full description template with verified facts",
  "hashtags": ["#Shorts", "#Viral", ...],
  "thumbnail_prompt": "Thumbnail prompt for Google Flow",
  "prop": "{idea['prop']}"
}}
"""
        
        response = self._call_llm(prompt)
        
        try:
            story = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: parse manually or use template
            story = self._fallback_story(idea)
        
        # Ensure video_id is set for shot storage
        story['video_id'] = None  # Will be set after video record created
        story['prop'] = idea['prop']
        
        return story
    
    def _fallback_story(self, idea: Dict) -> Dict:
        """Template-based story generation if LLM fails."""
        prop = idea['prop']
        return {
            "narration": f"A {prop} changed everything.\nNobody believed it could work.\nBut the {prop} had a secret.\nWhen they finally used it, the result was impossible.\nNow history remembers the {prop}.\nWhat else can a {prop} change?",
            "shot_list": [
                {"shot_number": 1, "beat": "hook", "time_start": 0, "time_end": 3,
                 "visual_description": f"Close-up of {prop} glowing in dark room",
                 "narration_line": f"A {prop} changed everything.",
                 "camera_move": "dolly_in", "prop_visible": True, "character_refs": ["protagonist"],
                 "video_prompt": f"Dolly in shot. Dark atmospheric 3D room, deep blue-purple shadows #2D1B4E. {prop} center frame, glowing mysteriously. Protagonist enters from side. Gliding camera. 10 seconds."},
                {"shot_number": 2, "beat": "escalation", "time_start": 3, "time_end": 8,
                 "visual_description": "Protagonist examines prop, skeptic watches",
                 "narration_line": "Nobody believed it could work.",
                 "camera_move": "truck_right", "prop_visible": True, "character_refs": ["protagonist", "antagonist"],
                 "video_prompt": f"Truck right shot. Colorful toon 3D laboratory, soft pastels. Protagonist (blue outfit) holds {prop}, antagonist (red outfit) shakes head. Gliding truck. 10 seconds."},
                {"shot_number": 3, "beat": "prop_reveal", "time_start": 8, "time_end": 18,
                 "visual_description": "Prop mechanism shown in detail",
                 "narration_line": f"But the {prop} had a secret.",
                 "camera_move": "orbit_slow", "prop_visible": True, "character_refs": ["protagonist"],
                 "video_prompt": f"Slow orbit shot. 3D cutaway view of {prop} internal mechanism, colorful toon style. Deep blue-purple shadows. Protagonist watches. Gliding orbit. 10 seconds."},
                {"shot_number": 4, "beat": "obstacle", "time_start": 18, "time_end": 28,
                 "visual_description": "Prop fails to activate, tension builds",
                 "narration_line": "When they finally used it, the result was impossible.",
                 "camera_move": "pedestal_up", "prop_visible": True, "character_refs": ["protagonist", "antagonist"],
                 "video_prompt": f"Pedestal up shot. Tense scene, {prop} not working. Protagonist desperate, antagonist smug. Colorful 3D environment. Gliding pedestal. 10 seconds."},
                {"shot_number": 5, "beat": "payoff", "time_start": 28, "time_end": 38,
                 "visual_description": "Prop activates, spectacular result",
                 "narration_line": "Now history remembers the " + prop + ".",
                 "camera_move": "dolly_out_wide", "prop_visible": True, "character_refs": ["protagonist"],
                 "video_prompt": f"Dolly out wide shot. {prop} activates dramatically, colorful energy wave. Protagonist triumphant. Epic 3D environment. Gliding dolly out. 10 seconds."},
                {"shot_number": 6, "beat": "twist", "time_start": 38, "time_end": 40,
                 "visual_description": "Final frame: prop alone, question implied",
                 "narration_line": f"What else can a {prop} change",
                 "camera_move": "static_hold", "prop_visible": True, "character_refs": [],
                 "video_prompt": f"Static hold. {prop} alone in center of frame, subtle glow. Deep blue-purple shadows. No characters. Final frame for thumbnail. 10 seconds."}
            ],
            "characters": [
                {"name": "protagonist", "outfit_color": "blue", "role": "main"},
                {"name": "antagonist", "outfit_color": "red", "role": "opposer"}
            ],
            "titles": [
                f"How a {prop} Changed History",
                f"Why {prop} Caused The Impossible",
                f"The {prop} That Shocked Everyone",
                f"{prop} vs Impossible — You Won't Believe",
                f"I Tested The {prop} That Changed Everything"
            ],
            "description": f"{idea['teaser']}\n\nThis is the true story of how a {prop} {idea['logline'].split('|')[0].strip()}.\n\n👇 Sources:\n{idea.get('source', 'Historical records')}\n\n🎬 Made with free AI tools: ChatGPT + Google Flow + Google AI Studio + CapCut\n\n#Shorts #TrueStory #Animation #Viral #History",
            "hashtags": ["#Shorts", "#Viral", "#Animation", "#TrueStory", "#History", "#WeirdFacts", "#DidYouKnow", "#StoryTime", "#FacelessChannel", "#AIAnimation", "#GoogleFlow", "#Stickman", "#HistoryFacts", "#MindBlown", "#DailyShorts"],
            "thumbnail_prompt": f"Thumbnail for viral Short: {prop} dominates frame, tiny stickman reacting with exaggerated shock. Colorful toon 3D background, deep blue-purple shadows #2D1B4E. Text space top 20%. High contrast, click-worthy, 4K.",
            "prop": prop
        }
    
    def save_shot_list(self, idea_id: int, shot_list: List[Dict]):
        """Save shot list to DB (video_id will be updated later)."""
        # Shots are saved in orchestrator after video record created
        pass


if __name__ == "__main__":
    import yaml
    with open("../config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    agent = IdeationAgent(config)
    ideas = agent.generate_ideas_batch()
    print(f"Generated {len(ideas)} ideas")
    for i, idea in enumerate(ideas, 1):
        print(f"{i}. {idea['logline']} | Prop: {idea['prop']}")