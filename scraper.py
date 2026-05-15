"""
PENTAKILL WARS - Scraper (op.gg + Playwright)
Launches a real Chromium browser, loads each summoner's ARAM page,
and intercepts the Server Action POST response that contains the stats.

Requirements:
    pip install playwright
    playwright install chromium
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("❌ Run:  pip install playwright && playwright install chromium")
    sys.exit(1)

# ── Players ─────────────────────────────────────────────────────────────────
PLAYERS = {
    "hatz": {
        "name": "Hatz",
        "url":  "https://op.gg/lol/summoners/na/Hatz-7811?queue_type=ARAM",
    },
    "water": {
        "name": "Water",
        "url":  "https://op.gg/lol/summoners/na/Water-12356?queue_type=ARAM",
    },
}

DATA_FILE = Path(__file__).parent / "data.json"


# ── RSC parser ───────────────────────────────────────────────────────────────
def parse_rsc(text: str) -> dict | None:
    for line in text.splitlines():
        m = re.match(r"^\w+:(\{.*)", line)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict) and "penta_kill" in data:
                return data
        except json.JSONDecodeError:
            continue
    return None


# ── Single player fetch ──────────────────────────────────────────────────────
def fetch_player(info: dict, browser) -> dict:
    print(f"\n🔍 Fetching {info['name']}…")

    raw       = None
    responses = []

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()

    def on_response(response):
        """Intercept every response — grab ones that look like our stats."""
        if "queue_type=ARAM" in response.url and response.request.method == "POST":
            try:
                body = response.body().decode("utf-8", errors="ignore")
                candidate = parse_rsc(body)
                if candidate:
                    responses.append(candidate)
            except Exception:
                pass

    page.on("response", on_response)

    try:
        page.goto(info["url"], wait_until="domcontentloaded", timeout=30_000)
        # Wait up to 15 s for the Server Action POST to fire and come back
        page.wait_for_timeout(15_000)
    except PlaywrightTimeout:
        print("  ⚠️  Page load timed out — trying with whatever loaded")
    finally:
        context.close()

    if responses:
        raw = responses[-1]   # take the most recent stats response

    if not raw:
        print(f"  ❌ No stats captured for {info['name']}")
        sys.exit(1)

    # ── Parse into our schema ─────────────────────────────────────────────────
    kda    = raw.get("kda", {})
    champs = raw.get("champion_stats", [])[:5]

    result = {
        "name":       info["name"],
        "pentakills": raw.get("penta_kill", 0),
        "win_rate":   round(raw.get("win_rate", 0), 1),
        "games":      raw.get("play", 0),
        "wins":       raw.get("win", 0),
        "losses":     raw.get("lose", 0),
        "avg_kda": {
            "kills":   kda.get("avg_kill",   0),
            "deaths":  kda.get("avg_death",  0),
            "assists": kda.get("avg_assist", 0),
            "ratio":   round(kda.get("kda", 0), 2),
        },
        "multi_kills": {
            "double": raw.get("double_kill", 0),
            "triple": raw.get("triple_kill", 0),
            "quadra": raw.get("quadra_kill", 0),
        },
        "top_champs": [
            {
                "name":      c.get("name"),
                "image_url": c.get("image_url"),
                "win_rate":  c.get("win_rate", 0),
                "plays":     int(c.get("play", 0)),
                "kda":       round(c.get("kda", {}).get("kda", 0), 2),
            }
            for c in champs
        ],
    }

    print(
        f"  ✅ {info['name']}: {result['pentakills']} pentas | "
        f"{result['win_rate']}% WR | {result['games']} games | "
        f"{result['avg_kda']['ratio']} KDA"
    )
    return result


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  ⚡ PENTAKILL WARS SCRAPER (op.gg + Playwright) ⚡")
    print("=" * 55)
    now = datetime.now(timezone.utc)
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for key, info in PLAYERS.items():
            results[key] = fetch_player(info, browser)
            time.sleep(2)
        browser.close()

    payload = {**results, "lastUpdated": now.strftime("%Y-%m-%d %H:%M UTC")}
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'='*55}")
    print(f"  🗡️  Hatz  : {results['hatz']['pentakills']} pentas | {results['hatz']['win_rate']}% WR")
    print(f"  💧 Water  : {results['water']['pentakills']} pentas | {results['water']['win_rate']}% WR")
    print(f"  💾 Saved  → {DATA_FILE.name}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
