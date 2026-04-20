"""
Debug script — opens Google Maps, searches, and dumps the HTML
so we can find the right selectors for the scraper.
"""

import time
from playwright.sync_api import sync_playwright


def main():
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

        # Search
        page.goto("https://www.google.com/maps/search/restaurants+in+Sydney", wait_until="domcontentloaded")
        time.sleep(5)

        # Accept cookies
        try:
            btn = page.query_selector('button:has-text("Accept all")')
            if btn:
                btn.click()
                time.sleep(2)
        except Exception:
            pass

        # Dump the results panel HTML
        feed = page.query_selector('div[role="feed"]')
        if feed:
            html = feed.inner_html()
            with open("debug_feed.html", "w") as f:
                f.write(html)
            print(f"Saved feed HTML ({len(html)} chars) to debug_feed.html")

            # Count links
            links = feed.query_selector_all('a[href*="/maps/place/"]')
            print(f"Found {len(links)} place links in feed")

            # Print first few aria-labels
            for link in links[:5]:
                aria = link.get_attribute("aria-label") or "(no label)"
                href = link.get_attribute("href") or ""
                print(f"  - {aria}")
        else:
            print("No feed element found")
            # Try alternative selectors
            body_html = page.content()
            with open("debug_page.html", "w") as f:
                f.write(body_html)
            print("Saved full page HTML to debug_page.html")

        # Now click the first listing and dump its panel
        time.sleep(1)
        links = page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
        if links:
            print(f"\nClicking first listing: {links[0].get_attribute('aria-label')}")
            links[0].click()
            time.sleep(3)

            # Dump the detail panel
            page_html = page.content()
            with open("debug_detail.html", "w") as f:
                f.write(page_html)
            print("Saved detail page HTML to debug_detail.html")

            # Try various selectors for the business name
            for selector in ['h1', 'h1.fontHeadlineLarge', 'div[role="main"] h1', 'span.fontHeadlineLarge']:
                el = page.query_selector(selector)
                if el:
                    print(f"  {selector} → '{el.inner_text().strip()}'")
                else:
                    print(f"  {selector} → not found")

            # Rating
            for selector in ['div.fontDisplayLarge', 'span.fontDisplayLarge', 'div[role="main"] span[aria-hidden="true"]']:
                el = page.query_selector(selector)
                if el:
                    print(f"  {selector} → '{el.inner_text().strip()}'")

            # Review count
            for selector in ['button[jsaction*="reviewChart"] span', 'span[aria-label*="reviews"]', 'div[role="main"] button span']:
                els = page.query_selector_all(selector)
                for el in els[:3]:
                    txt = el.inner_text().strip()
                    if txt:
                        print(f"  {selector} → '{txt}'")

        browser.close()


if __name__ == "__main__":
    main()
