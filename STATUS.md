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

## 🔑 CURRENT ISSUE: Gemini Keys Are Wrong Format

Both keys you've provided are **OAuth access tokens** (`AQ.` prefix), not REST API keys. The Gemini REST API requires keys starting with `AIzaSy...`.

### How to Get a Real API Key

The keys from https://aistudio.google.com/app/apikey are **access tokens** — they work inside the Gemini website/app but NOT for the REST API.

**To get a real REST API key:**

1. Go to **Google Cloud Console**: https://console.cloud.google.com/apis/credentials
2. Click **+ CREATE CREDENTIALS** → **API key**
3. This creates a key like: `AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4. Then go to the same page and click on your new API key → **Restrict key** → Add restrictions
5. For Gemini: Add restriction `generativelanguage.googleapis.com`
6. Copy the `AIzaSy...` key
7. Update GitHub secret:
   ```
   gh secret set GEMINI_API_KEY --body "AIzaSy..." --repo brightbrio/BRYSON-CLIPS-ANIMATION
   ```

**Alternative: Use OpenRouter (Recommended)**
- Single sign-up at https://openrouter.ai/
- Free tier: 50K tokens/day
- One key works for: GPT-4o, Claude 3.5 Sonnet, Gemini Pro, Llama 3.1
- No per-project setup needed

---

## Next Steps
1. ✅ All CI fixes committed (retry logic, multi-model fallback)
2. 🔧 Get valid Gemini/GLM quota or switch to OpenRouter
3. 🌐 Connect YouTube/TikTok via http://127.0.0.1:8081 web UI
4. 📤 Enable full distribution pipeline once auth is configured
