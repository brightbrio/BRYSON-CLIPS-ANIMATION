#!/usr/bin/env python3
"""
EVOLUTION OPTIMIZER
Analyzes performance data and adjusts system parameters for continuous improvement.
Self-improving loop that runs daily.
"""

import json
import logging
import statistics
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

ADJUSTMENTS_FILE = Path("state/active_adjustments.json")
PROMPT_ADJUSTMENTS_FILE = Path("prompts/adjustments.md")


def analyze_and_adapt(performance_data: List[Dict]) -> Dict[str, str]:
    """
    Analyze last 7 days of performance data and generate prompt adjustments.
    Returns dict of {component: adjustment_text} to apply to next cycle.
    """
    if len(performance_data) < 5:
        return {"status": "insufficient_data", "count": str(len(performance_data))}
    
    adjustments = {}
    
    # Extract metrics
    hook_rates = [p.get("hook_3s", 0) for p in performance_data if p.get("hook_3s") is not None]
    retention_50 = [p.get("retention_50", 0) for p in performance_data if p.get("retention_50") is not None]
    completion = [p.get("completion", 0) for p in performance_data if p.get("completion") is not None]
    ctrs = [p.get("ctr", 0) for p in performance_data if p.get("ctr") is not None]
    revenues = [p.get("revenue_est", 0) for p in performance_data if p.get("revenue_est") is not None]
    
    avg_hook = statistics.mean(hook_rates) if hook_rates else 0
    avg_ret50 = statistics.mean(retention_50) if retention_50 else 0
    avg_comp = statistics.mean(completion) if completion else 0
    avg_ctr = statistics.mean(ctrs) if ctrs else 0
    avg_rev = statistics.mean(revenues) if revenues else 0
    
    logger.info(f"Performance averages: hook={avg_hook:.2%}, ret50={avg_ret50:.2%}, comp={avg_comp:.2%}, ctr={avg_ctr:.2%}, rev=${avg_rev:.2f}")
    
    # Thresholds from config
    THRESHOLDS = {
        "hook_3s": 0.70,
        "retention_50": 0.40,
        "completion": 0.30,
        "ctr": 0.05,
    }
    
    # 1. HOOK RETENTION (<70% at 3s)
    if avg_hook < THRESHOLDS["hook_3s"]:
        deficit = THRESHOLDS["hook_3s"] - avg_hook
        adjustments["ideation"] = (
            f"HOOK DEFICIT: {deficit:.0%} below target ({avg_hook:.0%} vs {THRESHOLDS['hook_3s']:.0%}). "
            f"ADJUSTMENT: Lead with VISUAL PROP + WEIRD RESULT in first sentence. "
            f"Make prop name CONCRETE and VISIBLE. First frame MUST show prop in action. "
            f"Cut all preamble. Start: 'A [PROP] [WEIRD RESULT].' No setup."
        )
    
    # 2. MID RETENTION (<40% at 50%)
    if avg_ret50 < THRESHOLDS["retention_50"]:
        deficit = THRESHOLDS["retention_50"] - avg_ret50
        adjustments["production"] = (
            f"MID RETENTION DEFICIT: {deficit:.0%} below target ({avg_ret50:.0%} vs {THRESHOLDS['retention_50']:.0%}). "
            f"ADJUSTMENT: Shorter shots (max 2.5s = 75 frames). More camera moves per shot. "
            f"Prop must appear/change state in EVERY shot. Add visual metaphor (shrink/grow/split). "
            f"Escalation beat: add physical obstacle visible on screen."
        )
    
    # 3. COMPLETION RATE (<30%)
    if avg_comp < THRESHOLDS["completion"]:
        deficit = THRESHOLDS["completion"] - avg_comp
        adjustments["story"] = (
            f"COMPLETION DEFICIT: {deficit:.0%} below target ({avg_comp:.0%} vs {THRESHOLDS['completion']:.0%}). "
            f"ADJUSTMENT: Tighter payoff. Twist question MUST reference prop DIRECTLY. "
            f"Cut all fluff after payoff. End at 58s for 60s video. "
            f"Final narration line: 'What else can a [PROP] change?' - exact format."
        )
    
    # 4. CTR (<5%)
    if avg_ctr < THRESHOLDS["ctr"]:
        deficit = THRESHOLDS["ctr"] - avg_ctr
        adjustments["thumbnail"] = (
            f"CTR DEFICIT: {deficit:.2%} below target ({avg_ctr:.2%} vs {THRESHOLDS['ctr']:.2%}). "
            f"ADJUSTMENT: Prop 50% of frame size. Character reaction EXTREME (mouth open, eyes wide). "
            f"High contrast: prop BRIGHT, background DARK. Text space top 25%. "
            f"Add 'impossible' visual cue (glow, spark, distortion) around prop."
        )
    
    # 5. REVENUE OPTIMIZATION
    if avg_rev < 50:  # Less than $50/day estimated
        adjustments["monetization"] = (
            f"LOW REVENUE: ${avg_rev:.2f}/day estimated. "
            f"ADJUSTMENT: Add affiliate link in pinned comment + description. "
            f"Create digital product (prompt pack) link in bio. "
            f"Cross-post to 4 platforms × 4 slots = 16 impressions/day. "
            f"Engage 60 min each post. Reply with QUESTION to drive comments."
        )
    
    # 6. POSITIVE REINFORCEMENT (what's working)
    working = []
    if avg_hook >= THRESHOLDS["hook_3s"]:
        working.append("hooks")
    if avg_ret50 >= THRESHOLDS["retention_50"]:
        working.append("mid-retention")
    if avg_comp >= THRESHOLDS["completion"]:
        working.append("completion")
    if avg_ctr >= THRESHOLDS["ctr"]:
        working.append("thumbnails")
    
    if working:
        adjustments["reinforce"] = f"KEEP DOING: {', '.join(working)} are hitting targets. Don't change these components."
    
    # Save adjustments
    adjustment_record = {
        "timestamp": datetime.now().isoformat(),
        "data_points": len(performance_data),
        "averages": {
            "hook_3s": round(avg_hook, 4),
            "retention_50": round(avg_ret50, 4),
            "completion": round(avg_comp, 4),
            "ctr": round(avg_ctr, 4),
            "revenue_est": round(avg_rev, 2)
        },
        "adjustments": adjustments
    }
    
    ADJUSTMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ADJUSTMENTS_FILE, "w") as f:
        json.dump(adjustment_record, f, indent=2)
    
    # Also save human-readable version
    _save_human_readable(adjustment_record)
    
    logger.info(f"Generated {len(adjustments)} adjustments")
    return adjustments


def _save_human_readable(record: Dict):
    """Save adjustments as markdown for human review."""
    lines = [
        f"# Evolution Adjustments - {record['timestamp'][:10]}",
        f"",
        f"**Data Points:** {record['data_points']} videos",
        f"",
        f"## Averages",
        f"- Hook (3s): {record['averages']['hook_3s']:.1%}",
        f"- Retention (50%): {record['averages']['retention_50']:.1%}",
        f"- Completion: {record['averages']['completion']:.1%}",
        f"- CTR: {record['averages']['ctr']:.2%}",
        f"- Est. Revenue: ${record['averages']['revenue_est']:.2f}/day",
        f"",
        f"## Adjustments",
    ]
    
    for component, text in record['adjustments'].items():
        lines.append(f"### {component.upper()}")
        lines.append(f"{text}")
        lines.append(f"")
    
    PROMPT_ADJUSTMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_ADJUSTMENTS_FILE.write_text("\n".join(lines))


def get_active_adjustments() -> Dict[str, str]:
    """Load current active adjustments for injection into prompts."""
    if ADJUSTMENTS_FILE.exists():
        with open(ADJUSTMENTS_FILE, "r") as f:
            return json.load(f).get("adjustments", {})
    return {}


def inject_adjustments_into_prompt(base_prompt: str, adjustments: Dict[str, str]) -> str:
    """Inject active adjustments into master prompt for next cycle."""
    if not adjustments:
        return base_prompt
    
    injection = "\n\n=== ACTIVE OPTIMIZATION ADJUSTMENTS (APPLY THESE) ===\n"
    for component, text in adjustments.items():
        if component != "reinforce":  # Don't inject reinforcement as instruction
            injection += f"\n[{component.upper()}] {text}\n"
    
    injection += "\n=== END ADJUSTMENTS ===\n"
    
    # Insert before the final workflow section
    if "=== MASTER PROMPT END ===" in base_prompt:
        return base_prompt.replace("=== MASTER PROMPT END ===", injection + "=== MASTER PROMPT END ===")
    else:
        return base_prompt + injection


def analyze_trends(performance_data: List[Dict], window_days: int = 14) -> Dict[str, Any]:
    """Analyze trends over longer window."""
    if len(performance_data) < 10:
        return {"status": "insufficient_data"}
    
    # Sort by date
    sorted_data = sorted(performance_data, key=lambda x: x.get("created_at", ""))
    
    # Split into two halves
    mid = len(sorted_data) // 2
    first_half = sorted_data[:mid]
    second_half = sorted_data[mid:]
    
    trends = {}
    for metric in ["hook_3s", "retention_50", "completion", "ctr", "revenue_est"]:
        first_vals = [p.get(metric, 0) for p in first_half if p.get(metric) is not None]
        second_vals = [p.get(metric, 0) for p in second_half if p.get(metric) is not None]
        
        if first_vals and second_vals:
            first_avg = statistics.mean(first_vals)
            second_avg = statistics.mean(second_vals)
            change = second_avg - first_avg
            trends[metric] = {
                "first_half": round(first_avg, 4),
                "second_half": round(second_avg, 4),
                "change": round(change, 4),
                "direction": "improving" if change > 0 else "declining" if change < 0 else "stable"
            }
    
    return trends


def generate_optimization_report(performance_data: List[Dict]) -> str:
    """Generate full optimization report for logging."""
    adjustments = analyze_and_adapt(performance_data)
    trends = analyze_trends(performance_data)
    
    report = [
        "=" * 60,
        "EVOLUTION OPTIMIZATION REPORT",
        f"Generated: {datetime.now().isoformat()}",
        "=" * 60,
        "",
        "CURRENT ADJUSTMENTS:",
    ]
    
    for comp, text in adjustments.items():
        report.append(f"  [{comp}] {text[:100]}...")
    
    report.append("")
    report.append("TRENDS (14-day window):")
    for metric, data in trends.items():
        report.append(f"  {metric}: {data['direction']} ({data['change']:+.2%})")
    
    return "\n".join(report)


if __name__ == "__main__":
    # Test with mock data
    import logging
    logging.basicConfig(level=logging.INFO)
    
    mock_data = [
        {"hook_3s": 0.65, "retention_50": 0.38, "completion": 0.28, "ctr": 0.04, "revenue_est": 30, "created_at": "2026-11-10"},
        {"hook_3s": 0.68, "retention_50": 0.42, "completion": 0.32, "ctr": 0.05, "revenue_est": 45, "created_at": "2026-11-11"},
        {"hook_3s": 0.72, "retention_50": 0.45, "completion": 0.35, "ctr": 0.06, "revenue_est": 60, "created_at": "2026-11-12"},
        {"hook_3s": 0.70, "retention_50": 0.43, "completion": 0.33, "ctr": 0.05, "revenue_est": 55, "created_at": "2026-11-13"},
        {"hook_3s": 0.69, "retention_50": 0.41, "completion": 0.31, "ctr": 0.04, "revenue_est": 40, "created_at": "2026-11-14"},
        {"hook_3s": 0.71, "retention_50": 0.44, "completion": 0.34, "ctr": 0.05, "revenue_est": 50, "created_at": "2026-11-15"},
        {"hook_3s": 0.73, "retention_50": 0.46, "completion": 0.36, "ctr": 0.06, "revenue_est": 65, "created_at": "2026-11-16"},
    ]
    
    adjustments = analyze_and_adapt(mock_data)
    print(json.dumps(adjustments, indent=2))
    
    report = generate_optimization_report(mock_data)
    print("\n" + report)