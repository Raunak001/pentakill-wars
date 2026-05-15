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


def scrape_player(key, info, max_retries=3):
    """
    Launch a stealth Chromium instance, load the ARAM profile, extract pentakills.
    Retries up to max_retries times if the page returns an error or bot-block.
    """
    from playwright.sync_api import sync_playwright

    print(f"\n🔍 Scraping {info['name']} → {info['url']}")

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"  ↩️  Retry {attempt}/{max_retries}...")
            import time; time.sleep(5 * attempt)   # back off between retries

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1280,900",
                    "--disable-extensions",
                    "--disable-gpu",
                    "--lang=en-US",
                ],
            )
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,*/*;q=0.8"
                    ),
                },
            )

            # Hide headless fingerprints before every page load
            ctx.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            page = ctx.new_page()

            try:
                # Use domcontentloaded first — networkidle can hang on ad-heavy sites
                page.goto(info["url"], timeout=60_000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)   # let JS hydrate

                # Check for bot-block / error page before scrolling
                body_text = page.inner_text("body")
                if "error occured" in body_text.lower() or "please try again" in body_text.lower():
                    print(f"  ⚠️  Got error page on attempt {attempt}, will retry…")
                    browser.close()
                    continue

                # Scroll gradually to trigger lazy-loaded stat sections
                for _ in range(6):
                    page.evaluate("window.scrollBy(0, 800)")
                    page.wait_for_timeout(600)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2500)

                body_text = page.inner_text("body")
                result = extract_pentakills(body_text, info["name"])
                browser.close()
                return result

            except Exception as exc:
                print(f"  ❌ Exception on attempt {attempt}: {exc}")
                browser.close()
                continue

    print(f"  ❌ All {max_retries} attempts failed for {info['name']}. Returning 0.")
    return 0


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
