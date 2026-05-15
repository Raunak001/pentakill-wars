"""
PENTAKILL WARS - Scraper
Hits dpm.lol's internal API directly — no browser, no Riot API key needed.

Requirements:
    pip install requests
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PLAYERS = {
    "hatz": {
        "name": "Hatz",
        "url":  "https://dpm.lol/v1/players/0pva-D9tclnd7z5nAfecwuaInnXt-mYXAZO2IfQu4IMR7EjNP6K0GxvNCy-LsHpkmQs21tr5C13a2Q/aram",
    },
    "water": {
        "name": "Water",
        "url":  "https://dpm.lol/v1/players/BAYMopSpr47nyYbiu70mrqeNZQXNXiqyWDWqB6OB9mdTwLdprLwjOpPf0--quL3Ht0yf4XZyNRnWMw/aram",
    },
}

HEADERS = {
    "Referer":          "https://dpm.lol/",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":           "application/json",
    "Accept-Language":  "en-US,en;q=0.9",
}

DATA_FILE = Path(__file__).parent / "data.json"


def fetch_player(key: str, info: dict) -> dict:
    print(f"\n🔍 Fetching {info['name']}…")
    r = requests.get(info["url"], headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    pentakills     = data["stats"]["pentaKills"]
    top_champs     = data.get("top10Pentakills", [])   # bonus: which champs got the pentas

    print(f"  ✅ {info['name']}: {pentakills} pentakills")
    return {
        "name":       info["name"],
        "pentakills": pentakills,
        "topChamps":  top_champs,
    }


def main():
    print("=" * 50)
    print("  ⚡ PENTAKILL WARS SCRAPER ⚡")
    print("=" * 50)
    now = datetime.now(timezone.utc)
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    results = {}
    for key, info in PLAYERS.items():
        try:
            results[key] = fetch_player(key, info)
        except Exception as e:
            print(f"  ❌ Failed to fetch {info['name']}: {e}")
            sys.exit(1)
        time.sleep(1)  # be polite between requests

    payload = {
        **results,
        "lastUpdated": now.strftime("%Y-%m-%d %H:%M UTC"),
    }

    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"  🗡️  Hatz  : {results['hatz']['pentakills']} pentakills")
    print(f"  💧 Water  : {results['water']['pentakills']} pentakills")
    print(f"  💾 Saved  → {DATA_FILE.name}")
    print(f"{'='*50}")


if __name__ == "__main__":
    try:
        import requests  # noqa: F401
    except ImportError:
        print("❌ Run:  pip install requests")
        sys.exit(1)
    main()
