# BRYSON CLIPS ANIMATION
**Fully automated viral stickman shorts pipeline — $0/month forever**

Generates Bryson Clips Animation-style videos (viral stickman format) using only FREE tools:
- **Google Flow (Veo 3)** — video generation
- **Google AI Studio (Gemini TTS)** — voiceover
- **CapCut Web** — editing
- **Playwright** — browser automation for posting
- **Local LLM / GLM 4 Flash** — ideation & optimization

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (4x/day)                    │
│  Scheduler → State DB → Cycle Log → Error Recovery          │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  IDEATION     │ │  PRODUCTION   │ │  DISTRIBUTION │
│  AGENT        │ │  AGENT        │ │  AGENT        │
│               │ │               │ │               │
│ • 10 ideas    │ │ • Char sheets │ │ • YouTube     │
│ • Fact check  │ │ • 10 clips    │ │ • TikTok      │
│ • Story gen   │ │ • TTS         │ │ • Facebook    │
│ • Score/rank  │ │ • CapCut edit │ │ • Instagram   │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
              ┌───────────────────────┐
              │  EVOLUTION OPTIMIZER  │
              │  (Daily analysis)     │
              │                       │
              │ • Hook > 70% @ 3s     │
              │ • Ret50 > 40%         │
              │ • Completion > 30%    │
              │ • CTR > 5%            │
              │ • Adjusts prompts     │
              └───────────────────────┘
```

---

## QUICK START

### 1. Install
```bash
cd ricks-clips-automation
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Auth Setup (one-time)
```bash
python auth_setup.py
# Choose 'a' for all platforms, log in manually in browser windows
```

### 3. Run
```bash
# Single cycle (for testing)
python orchestrator.py --single-cycle

# Or run forever (4x/day scheduled)
python orchestrator.py
```

### 4. Deploy Free Forever
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- **GitHub Actions** (easiest, 2000 min/mo free)
- **Oracle Cloud** (always-on VM, 4 ARM CPU + 24GB free)
- **Local machine** (old laptop, Pi, mini PC)

---

## FILES

```
ricks-clips-automation/
├── orchestrator.py          # Main scheduler + cycle runner
├── config.yaml              # All settings (free-tier tuned)
├── requirements.txt         # Python deps
├── auth_setup.py            # One-time login for all platforms
├── DEPLOYMENT_GUIDE.md      # Full deployment instructions
├── prompts/master_prompt.md      # The master prompt (8 phases)
├── QUICK_START_GUIDE.md     # Manual 5-min first video guide
├── agents/
│   ├── ideation_agent.py    # Ideas → stories (local LLM/GLM)
│   ├── production_agent.py  # Clips → TTS → Edit (Playwright)
│   └── distribution_agent.py # Cross-post + engagement
├── evolution/
│   └── optimizer.py         # Daily metrics → prompt adjustments
├── .github/workflows/
│   └── orchestrator.yml     # GitHub Actions CI/CD
├── state/                   # SQLite DB (auto-created)
├── auth/                    # Auth cookies (gitignored)
├── output/                  # Generated videos
└── logs/                    # Orchestrator logs
```

---

## HOW IT WORKS

### Cycle (runs 4x/day: 06:00, 12:00, 18:00, 00:00)

1. **IDEATION** (30s)
   - Generate 10 historical "weird prop" ideas
   - Fact-check each (Wikipedia/API)
   - Score: novelty × visual_potential × shareability
   - Pick top 1

2. **STORY** (15s)
   - Structure: Hook → Escalation → Prop Reveal → Obstacle → Payoff → Twist Question
   - ~3.8 words/sec narration pace
   - 10 shots × 6s = 60s total

3. **CHARACTER SHEETS** (10s)
   - Consistent stickman prompts for Google Flow
   - White circular heads, thick black outlines, #2D1B4E shadows

4. **VIDEO PROMPTS** (10s)
   - 10 detailed Veo 3 prompts (one per shot)
   - Camera moves, prop focus, visual metaphors

5. **PRODUCTION** (3-5 min)
   - Generate 10 clips via Google Flow (Veo 3, 720p, 10s)
   - Generate voiceover via Google AI Studio (Gemini TTS)
   - Edit in CapCut Web: hard cuts, captions, music, SFX
   - Export final 60s MP4 + thumbnail

6. **DISTRIBUTION** (2 min)
   - Post to YouTube Shorts, TikTok, Facebook Reels, Instagram Reels
   - Staggered 5 min apart
   - Platform-optimized titles/hashtags

7. **ENGAGEMENT** (60 min post)
   - Reply to comments with question templates
   - Drive comment velocity

8. **OPTIMIZATION** (daily 23:50)
   - Analyze last 7 days metrics
   - Generate prompt adjustments for weak metrics
   - Inject into next cycle's prompts

---

## FREE TIER USAGE (Per Day)

| Service | Limit | Our Usage | Headroom |
|---------|-------|-----------|----------|
| Google Flow (Veo 3) | 20/day | 40 clips (10×4) | Use queue/720p |
| Google AI Studio TTS | 1500/day | 4 requests | 99.7% free |
| CapCut Web Export | 50/day | 4 exports | 92% free |
| GitHub Actions | 2000 min/mo | ~60 min/day | 10% free |
| Playwright | No limit | 4 platforms | Unlimited |

---

## EVOLUTION METRICS (Target → Action)

| Metric | Target | If Below | Adjustment |
|--------|--------|----------|------------|
| Hook (3s) | >70% | Lead with prop+result in frame 1 |
| Retention (50%) | >40% | Shorter shots (2.5s), prop every shot |
| Completion | >30% | Tighter payoff, exact twist format |
| CTR | >5% | Prop 50% frame, extreme reaction |
| Revenue | >$50/day | Affiliate + digital product links |

---

## CUSTOMIZATION

Edit `config.yaml`:
- **Cycle times**: Change `orchestrator.cycle_times`
- **Platforms**: Enable/disable in `distribution.platforms`
- **Video style**: Modify `production.google_flow.style_prompt`
- **Thresholds**: Tune `evolution.thresholds`
- **LLM model**: Change `ideation.model` (GLM, Ollama, etc.)

---

## LOGS & DEBUG

```bash
# View live logs
tail -f logs/orchestrator.log

# Check database
sqlite3 state/rickclips.db "SELECT * FROM cycle_log ORDER BY id DESC LIMIT 5;"

# Manual cycle
python -c "
import asyncio
from orchestrator import Orchestrator
o = Orchestrator()
asyncio.run(o.start_agents())
asyncio.run(o.run_cycle())
asyncio.run(o.stop_agents())
"
```

---

## LICENSE

MIT — Use freely, modify, deploy, sell the output videos.

---

## CREDITS

Inspired by **Bryson Clips Animation** (viral stickman format)
Style: White circular marker heads, thick outlines, deep purple shadows, gliding camera, ~3.8 wps narration, 6-act structure.

Built with free tools only. No Higgsfield, no ElevenLabs, no paid APIs.