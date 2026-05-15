"""
PENTAKILL WARS - Scraper (op.gg edition)
Uses op.gg's Next.js Server Action endpoint — no Riot key needed.
Pulls 2026 season ARAM stats only.

If the scraper suddenly returns "action not found" errors, op.gg has redeployed
and the NEXT_ACTION hash below needs updating. To get the new hash:
  1. Open https://op.gg/lol/summoners/na/Hatz-7811?queue_type=ARAM in Chrome
  2. DevTools → Network → Fetch/XHR → click the Hatz-7811?queue_type=ARAM POST
  3. Headers → Request Headers → copy the "Next-Action" value
  4. Paste it below.

Requirements:
    pip install requests
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── op.gg Server Action hash ────────────────────────────────────────────────
# Update this if op.gg redeploys (see instructions above).
NEXT_ACTION = "4083b09b01c122d0dd8c73f045fb7efb4c400120f9"

# ── Players ─────────────────────────────────────────────────────────────────
PLAYERS = {
    "hatz": {
        "name":   "Hatz",
        "slug":   "Hatz-7811",
        "puuid":  "sDot1K6G5HQKYS5_hhU2s8_eYBrr6XNj0vqL3yRG3lvCjWUdR_iAyvJ1W3Jh3HuXtJbaBtTUZTmtaQ",
        "region": "na",
    },
    "water": {
        "name":   "Water",
        "slug":   "Water-12356",
        "puuid":  "OqWUXEmhFFe1J314MnL7AxMi4jAfvSZLnslAvClVfclVVHrE9xFBR-QXm64fkyTioaGTIukxMd6P3g",
        "region": "na",
    },
}

BASE_URL = "https://op.gg/lol/summoners/na"

HEADERS = {
    "Accept":               "text/x-component",
    "Accept-Encoding":      "gzip, deflate, br",
    "Accept-Language":      "en-US,en;q=0.9",
    "Content-Type":         "text/plain;charset=UTF-8",
    "Next-Action":          NEXT_ACTION,
    # Minimal router state tree op.gg expects
    "Next-Router-State-Tree": (
        "%5B%22%22%2C%7B%22children%22%3A%5B%22%22%2C%7B%22children%22"
        "%3A%5B%22locale%22%2C%22en%22%2C%22%2F%22%5D%7D%5D%7D%5D"
    ),
    "Referer":    "https://op.gg/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

DATA_FILE = Path(__file__).parent / "data.json"


# ── RSC response parser ──────────────────────────────────────────────────────
def parse_rsc(text: str) -> dict | None:
    """
    Next.js text/x-component lines look like:
        0:[...react tree...]
        1:{"year":2026,"penta_kill":14,...}
    Scan every line for the JSON object that contains penta_kill.
    """
    for line in text.splitlines():
        m = re.match(r"^\d+:(\{.*)", line)
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
def post_action(slug: str, puuid: str, region: str, year: int = 2026) -> dict | None:
    url      = f"{BASE_URL}/{slug}?queue_type=ARAM"
    body_obj = {"locale": "en", "region": region, "puuid": puuid, "year": year}
    body = json.dumps([body_obj])

    r = requests.post(url, headers=HEADERS, data=body.encode(), timeout=20)
    r.raise_for_status()
    return parse_rsc(r.text)


def fetch_player(key: str, info: dict) -> dict:
    print(f"\n🔍 Fetching {info['name']}…")

    try:
        raw = post_action(info["slug"], info["puuid"], info["region"])
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        raw = None

    if not raw:
        print(
            "\n💡 TIP: If you see action-not-found errors, the NEXT_ACTION hash\n"
            "   in scraper.py is stale. See instructions at the top of the file."
        )
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
            "kills":   kda.get("avg_kill",  0),
            "deaths":  kda.get("avg_death", 0),
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
    print("  ⚡ PENTAKILL WARS SCRAPER (op.gg) ⚡")
    print("=" * 55)
    now = datetime.now(timezone.utc)
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    results = {}
    for key, info in PLAYERS.items():
        results[key] = fetch_player(key, info)
        time.sleep(1)   # be polite between requests

    payload = {**results, "lastUpdated": now.strftime("%Y-%m-%d %H:%M UTC")}
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'='*55}")
    print(f"  🗡️  Hatz  : {results['hatz']['pentakills']} pentas | {results['hatz']['win_rate']}% WR")
    print(f"  💧 Water  : {results['water']['pentakills']} pentas | {results['water']['win_rate']}% WR")
    print(f"  💾 Saved  → {DATA_FILE.name}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    try:
        import requests  # noqa: F401
    except ImportError:
        print("❌ Run:  pip install requests")
        sys.exit(1)
    main()
