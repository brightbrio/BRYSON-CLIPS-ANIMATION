# DEPLOYMENT GUIDE
## Run Bryson Clips Animation for $0/month forever

---

## OPTION 1: GitHub Actions (Recommended - Easiest)

### Prerequisites
- GitHub account
- Repository with this code pushed to `main` branch

### Setup Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Bryson Clips Animation automation"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/ricks-clips-automation.git
   git push -u origin main
   ```

2. **Add GitHub Secrets** (Settings → Secrets and variables → Actions)
   | Secret Name | Value | Required |
   |-------------|-------|----------|
   | `GLM_API_KEY` | Get from https://z.ai (free) | Yes |
   | `GEMINI_API_KEY` | Get from https://aistudio.google.com (free) | Yes |
   | `OLLAMA_HOST` | e.g., `http://localhost:11434` (if using local LLM) | No |

3. **Run Auth Setup Locally First**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   python auth_setup.py
   # Choose 'a' for all platforms, log in manually
   ```
   
   Then copy auth files to repo (or use a private repo):
   ```bash
   git add auth/
   git commit -m "Add auth states"
   git push
   ```
   **OR**: Use GitHub Actions cache (already configured in workflow) - auth persists across runs.

4. **Enable Workflow**
   - Go to Actions tab
   - Click "Bryson Clips Animation Orchestrator"
   - Click "Run workflow" → "Run workflow"
   - Or wait for scheduled runs (06:00, 12:00, 18:00, 00:00 UTC)

### Free Tier Limits (GitHub Actions)
- 2,000 minutes/month on private repos (unlimited on public)
- Ubuntu runners: 6 hours max per job
- Our job: ~30 min × 4/day = 2 hours/day = 60 hours/month
- **Well within free tier**

---

## OPTION 2: Oracle Cloud Free Tier (Always-On VM)

### Why Oracle?
- 4 ARM CPUs + 24 GB RAM **forever free**
- No time limits like GitHub Actions
- Persistent filesystem (no cache restore needed)
- Better for Playwright (full browser)

### Setup Steps

1. **Create Oracle Cloud Account**
   - Sign up at https://cloud.oracle.com
   - Verify phone + credit card (no charge for Always Free)

2. **Create VM Instance**
   - Shape: `VM.Standard.A1.Flex` (ARM)
   - OCPUs: 4
   - Memory: 24 GB
   - Image: Ubuntu 22.04 Minimal
   - SSH keys: Add your public key
   - Network: Allow ports 22 (SSH), 80, 443

3. **Connect & Setup**
   ```bash
   ssh ubuntu@YOUR_VM_IP
   
   # Install dependencies
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3.11 python3.11-venv nodejs npm ffmpeg \
     libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
     libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
     libxfixes3 libxrandr2 libgbm1 libasound2
   
   # Install Playwright deps
   sudo npx playwright install-deps chromium
   ```

4. **Deploy Code**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ricks-clips-automation.git
   cd ricks-clips-automation
   
   python3.11 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   playwright install chromium
   ```

5. **Run Auth Setup**
   ```bash
   # Option A: Forward X11 (if you have local display)
   ssh -X ubuntu@YOUR_VM_IP
   python auth_setup.py
   
   # Option B: Run headless with manual cookie copy
   # (Copy auth JSON files from local machine to VM's auth/ dir)
   ```

6. **Run as systemd Service (Auto-restart)**
   ```bash
   sudo tee /etc/systemd/system/ricks-clips.service << 'EOF'
   [Unit]
   Description=Bryson Clips Animation
   After=network.target
   
   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/ricks-clips-automation
   ExecStart=/home/ubuntu/ricks-clips-automation/venv/bin/python orchestrator.py
   Restart=always
   RestartSec=60
   Environment=PATH=/home/ubuntu/ricks-clips-automation/venv/bin:/usr/bin
   
   [Install]
   WantedBy=multi-user.target
   EOF
   
   sudo systemctl daemon-reload
   sudo systemctl enable ricks-clips
   sudo systemctl start ricks-clips
   
   # Check logs
   sudo journalctl -u ricks-clips -f
   ```

---

## OPTION 3: Local Machine (24/7)

Run on any always-on device (old laptop, Raspberry Pi 4+, mini PC):

```bash
# Same as Oracle setup but skip VM creation
git clone ...
cd ricks-clips-automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python auth_setup.py
python orchestrator.py
```

Keep running with `screen` or `tmux`:
```bash
screen -S ricks-clips
python orchestrator.py
# Ctrl+A, D to detach
```

---

## COST BREAKDOWN

| Component | GitHub Actions | Oracle Cloud | Local |
|-----------|----------------|--------------|-------|
| Compute | Free (2000 min/mo) | Free (4 ARM CPU, 24GB) | Electricity only |
| Storage | Free (cache) | Free (200GB block) | Your disk |
| Google Flow (Veo 3) | Free tier | Free tier | Free tier |
| Google AI Studio (TTS) | Free tier | Free tier | Free tier |
| CapCut Web | Free | Free | Free |
| **TOTAL** | **$0/month** | **$0/month** | **~$1-3/mo electricity** |

---

## FREE TIER LIMITS & WORKAROUNDS

### Google Flow (Veo 3)
- **Limit**: 20 generations/day, 600/month
- **Our usage**: 10 clips × 4 videos/day = 40/day
- **Workaround**: Use 720p, 10s clips. Spread across cycles. If hit limit, queue for next day.

### Google AI Studio (TTS)
- **Limit**: 1500 requests/day, 60 RPM
- **Our usage**: 1 voiceover/video × 4/day = 4/day
- **Plenty of headroom**

### CapCut Web
- **Limit**: 50 exports/day, 15 min max
- **Our usage**: 4 exports/day, 60s each
- **Plenty of headroom**

### YouTube/TikTok/FB/IG APIs
- Using Playwright (browser automation) not official APIs
- **No quota limits** (but respect rate limits)
- **Delay between posts**: 5 min stagger configured

---

## MONITORING & DEBUGGING

### View Logs
```bash
# GitHub Actions
# Go to Actions tab → Click run → View logs

# Oracle/Local
sudo journalctl -u ricks-clips -f
# Or
tail -f logs/orchestrator.log
```

### Check Database
```bash
sqlite3 state/rickclips.db "
SELECT * FROM cycle_log ORDER BY id DESC LIMIT 10;
SELECT * FROM videos ORDER BY id DESC LIMIT 5;
SELECT * FROM performance_log ORDER BY collected_at DESC LIMIT 10;
"
```

### Manual Cycle Run
```bash
# Force run one cycle now
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

## SCALING UP (When Free Tier Isn't Enough)

1. **More videos/day**: Add more cycle times in config.yaml
2. **Higher quality**: Upgrade to Veo 3 1080p (paid)
3. **Multiple channels**: Duplicate config, run separate instances
4. **Custom models**: Fine-tune on top performers (local GPU)

---

## TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| Playwright timeout | Increase `timeout_seconds` in config.yaml |
| Auth expired | Re-run `python auth_setup.py` for that platform |
| Rate limited | Increase `post_delay_minutes` in distribution config |
| Out of memory | Reduce `max_concurrent` in free_tier_limits |
| Video generation failed | Check Google Flow quota, retry next cycle |
| Low metrics | Check evolution/optimizer.py adjustments being applied |

---

## SECURITY NOTES

- **Never commit real auth files to public repo**
- Use GitHub Secrets for API keys
- Oracle Cloud: Use security lists to restrict SSH to your IP
- Rotate auth cookies monthly (re-run auth_setup.py)
- Monitor for unusual activity in platform analytics

---

## NEXT STEPS

1. Choose deployment option
2. Run auth_setup.py once
3. Push to GitHub / deploy to Oracle
4. Watch first videos generate automatically
5. Check metrics after 7 days
6. Review evolution adjustments in `prompts/adjustments.md`

**The system runs forever, improves itself daily, costs $0.**