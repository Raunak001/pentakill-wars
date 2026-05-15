"""
PENTAKILL WARS - Nightly Scraper
Scrapes dpm.lol ARAM pages for Hatz and Water's pentakill counts.
Writes data.json in the same directory — consumed by index.html (GitHub Pages).

Requirements:
    pip install playwright
    playwright install chromium --with-deps
"""

import re
import json
import os
import sys
from datetime import datetime, timezone

PLAYERS = {
    "hatz": {
        "name": "Hatz",
        "url": "https://dpm.lol/Hatz-7811/aram",
    },
    "water": {
        "name": "Water",
        "url": "https://dpm.lol/Water-12356/aram",
    },
}


def extract_pentakills(text, name):
    """
    Search rendered page text for a pentakill count.
    Tries multiple regex patterns to handle different dpm.lol layouts.
    """
    patterns = [
        r'(\d+)\s*[Pp]enta\s*[Kk]ills?',
        r'[Pp]enta\s*[Kk]ills?\s*[:\-]?\s*(\d+)',
        r'[Pp]enta\s*[Kk]ills?\s*\n\s*(\d+)',
        r'(\d+)\s*\n\s*[Pp]enta\s*[Kk]ills?',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            count = int(m.group(1))
            print(f"  ✅ {name}: {count} pentakills")
            return count

    # Debug output to help diagnose layout changes
    idx = text.lower().find("penta")
    if idx != -1:
        snippet = text[max(0, idx - 50): idx + 120]
        print(f"  ⚠️  No match for {name}. Context around 'penta':\n    {repr(snippet)}")
    else:
        print(f"  ❌ 'penta' not found on {name}'s page.")
        print(f"     First 500 chars:\n    {repr(text[:500])}")

    return 0


def scrape_player(key, info):
    """Launch headless Chromium, load the ARAM profile, extract pentakills."""
    from playwright.sync_api import sync_playwright

    print(f"\n🔍 Scraping {info['name']} → {info['url']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        try:
            page.goto(info["url"], timeout=60_000)
            page.wait_for_load_state("networkidle", timeout=45_000)

            # Scroll down in steps to trigger any lazy-loaded stat panels
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 900)")
                page.wait_for_timeout(700)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            body_text = page.inner_text("body")
            return extract_pentakills(body_text, info["name"])

        except Exception as exc:
            print(f"  ❌ Error scraping {info['name']}: {exc}")
            return 0
        finally:
            browser.close()


def main():
    print("=" * 55)
    print("  ⚡ PENTAKILL WARS — NIGHTLY SCRAPER ⚡")
    print("=" * 55)
    now = datetime.now(timezone.utc)
    print(f"  Started: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    results = {}
    for key, info in PLAYERS.items():
        results[key] = {
            "name": info["name"],
            "pentakills": scrape_player(key, info),
        }

    payload = {
        **results,
        "lastUpdated": now.strftime("%Y-%m-%d %H:%M UTC"),
    }

    # Write data.json next to this script
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "data.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\n" + "=" * 55)
    print(f"  💾 Saved  → {out_path}")
    print(f"  🗡️  Hatz  : {results['hatz']['pentakills']} pentakills")
    print(f"  💧 Water  : {results['water']['pentakills']} pentakills")
    print(f"  🕐 At     : {payload['lastUpdated']}")
    print("=" * 55)


if __name__ == "__main__":
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("❌ Playwright is not installed!")
        print("   Run:  pip install playwright && playwright install chromium --with-deps")
        sys.exit(1)

    main()
