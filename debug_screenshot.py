"""Quick debug: load Google Maps search, screenshot, dump HTML structure."""
import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-AU",
        timezone_id="Australia/Sydney",
    )
    page = context.new_page()
    page.set_default_timeout(15000)

    page.goto("https://www.google.com/maps/search/restaurants+in+Sydney", wait_until="domcontentloaded")
    time.sleep(5)

    # Screenshot
    page.screenshot(path="debug_screenshot.png")
    print("Screenshot saved")

    # Check for consent / cookie dialogs
    for selector in [
        'form[action*="consent"]',
        'button:has-text("Accept")',
        'button:has-text("Reject")',
        'button:has-text("Before you continue")',
        'div[role="dialog"]',
    ]:
        el = page.query_selector(selector)
        if el:
            print(f"Found: {selector} -> visible={el.is_visible()}")
            # Try to get text
            try:
                print(f"  text: {el.inner_text()[:200]}")
            except:
                pass

    # Check what's on the page
    print("\nAll role=feed:", len(page.query_selector_all('div[role="feed"]')))
    print("All a[href*=place]:", len(page.query_selector_all('a[href*="/maps/place/"]')))

    # Look at top-level structure
    html = page.content()
    with open("debug_full.html", "w") as f:
        f.write(html)
    print(f"Full page HTML saved ({len(html)} chars)")

    # Try waiting longer for the feed
    print("\nWaiting 5 more seconds...")
    time.sleep(5)
    print("role=feed after wait:", len(page.query_selector_all('div[role="feed"]')))
    print("a[href*=place] after wait:", len(page.query_selector_all('a[href*="/maps/place/"]')))

    browser.close()
