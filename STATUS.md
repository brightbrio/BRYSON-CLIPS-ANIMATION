# Bryson Clips Animation - Status Report
Generated: 2026-11-24

## Pipeline Status: ✅ OPERATIONAL (Template Mode)

### Automated Runs
- **GitHub Actions**: Running every 6h (06:00/12:00/18:00/00:00 UTC)
- **Latest**: Run 45394554404 — SUCCESS (5min 21s, fell back to templates)
- **Next**: Nov 25, 2026 at 06:00 UTC

### What Works
| Phase | Status | Notes |
|-------|--------|-------|
| Ideation | ✅ 10 ideas/cycle | Template-based (reliable) |
| Story Generation | ✅ Complete | Full narrative per idea |
| Character Sheets | ⏭️ Skipped | Requires Google Flow browser |
| Video Prompts | ✅ Generated | Shot-by-shot prompts ready |
| Production | ⏭️ Skipped | Needs Playwright + API credits |
| Distribution | ⏭️ Skipped | Needs platform auth |

### Database (SQLite: state/rickclips.db)
- Ideas table: 10 new ideas per cycle, stored persistently
- Videos table: 1 complete video record per cycle
- Total cycles completed: 10+

### API Key Status
| Service | Key Status | Error | Fix Needed |
|---------|-----------|-------|------------|
| GLM (Zhipu AI) | Auth OK | 429 rate limit → then timeout | Key has free-tier daily quota exhausted; CN infra blocks from US/EU CI |
| Gemini | Auth OK | 429 quota exceeded / 503 high demand | Need paid plan or fresh account with higher limits |

### What Happens When LLM Fails
The pipeline gracefully falls back to template-based ideation:
```
GLM rate limited (attempt 1/3), waiting 5s
→ GLM call failed (attempt 2/3): Read timed out
→ GLM call failed (attempt 3/3): Read timed out
→ Using fallback idea generation
→ Selected idea: How a Mirror Rigged a Horse Race | Prop: Angled Mirror
```

---

## To Unlock Real LLM Ideation

### Option A: Fix Gemini (Easiest)
Get a fresh Gemini API key with available quota:
1. Go to https://aistudio.google.com/app/apikey
2. Create a NEW project (not the existing one that's over quota)
3. Copy the key (starts with `AIzaSy...`)
4. Update secret: `gh secret set GEMINI_API_KEY --body "AIzaSy..." --repo brightbrio/BRYSON-CLIPS-ANIMATION`

### Option B: Use GLM with Paid Plan
Upgrade the Zhipu AI account to paid tier (https://open.bigmodel.cn/usercenter/subscription)
Or deploy the workflow on a server in China to avoid CN-China firewall issues.

### Option C: Switch to OpenRouter
Sign up at https://openrouter.ai/ (free tier available)
- One API key works for 50+ models including GPT-4o, Claude Sonnet, Gemini
- Better rate limits than free tiers
- Set as GLM_API_KEY env var and update the model endpoint

---

## Next Steps
1. ✅ All CI fixes committed (retry logic, multi-model fallback)
2. 🔧 Get valid Gemini/GLM quota or switch to OpenRouter
3. 🌐 Connect YouTube/TikTok via http://127.0.0.1:8081 web UI
4. 📤 Enable full distribution pipeline once auth is configured
