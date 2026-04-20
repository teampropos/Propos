"""
Propos Lead Scraper (Async, 2-Phase)
Phase 1: Scrape Google Maps for leads (5 parallel tabs — careful with Google)
Phase 2: Scrape business websites for emails (20 parallel tabs — no risk)

Usage: python3 scraper.py "restaurants in Sydney" "fast food in Melbourne"
       python3 scraper.py  (uses default searches defined below)

First run: a browser window will open — sign in to Google, then press Enter
in the terminal to continue. Your session is saved for future runs.
"""

import sys
import os
import re
import asyncio
import random
import csv
import logging
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ─── SETTINGS (edit these) ────────────────────────────────────────────────────

# Default search queries if none passed via CLI
DEFAULT_SEARCHES = [
    # Sydney CBD
    "restaurants in Sydney CBD",
    "cafes in Sydney CBD",
    "coffee shops in Sydney CBD",
    "fast food in Sydney CBD",
    # Inner city / east
    "restaurants in Surry Hills",
    "cafes in Surry Hills",
    "restaurants in Darlinghurst",
    "cafes in Darlinghurst",
    "restaurants in Paddington Sydney",
    "cafes in Paddington Sydney",
    "restaurants in Potts Point",
    "cafes in Potts Point",
    "restaurants in Redfern Sydney",
    "cafes in Redfern Sydney",
    "restaurants in Chippendale Sydney",
    "cafes in Chippendale Sydney",
    "restaurants in Waterloo Sydney",
    "cafes in Waterloo Sydney",
    "restaurants in Double Bay Sydney",
    "cafes in Double Bay Sydney",
    "restaurants in Woollahra",
    "cafes in Woollahra",
    "restaurants in Elizabeth Bay",
    "cafes in Elizabeth Bay",
    "restaurants in Rushcutters Bay",
    "cafes in Rushcutters Bay",
    "restaurants in Edgecliff",
    "cafes in Edgecliff",
    "restaurants in Rose Bay Sydney",
    "cafes in Rose Bay Sydney",
    "restaurants in Vaucluse Sydney",
    "cafes in Vaucluse Sydney",
    "restaurants in Bellevue Hill",
    "cafes in Bellevue Hill",
    # Inner west
    "restaurants in Newtown Sydney",
    "cafes in Newtown Sydney",
    "restaurants in Enmore Sydney",
    "cafes in Enmore Sydney",
    "restaurants in Marrickville Sydney",
    "cafes in Marrickville Sydney",
    "restaurants in Balmain Sydney",
    "cafes in Balmain Sydney",
    "restaurants in Leichhardt Sydney",
    "cafes in Leichhardt Sydney",
    "restaurants in Glebe Sydney",
    "cafes in Glebe Sydney",
    "restaurants in Rozelle Sydney",
    "cafes in Rozelle Sydney",
    "restaurants in Annandale Sydney",
    "cafes in Annandale Sydney",
    "restaurants in Dulwich Hill Sydney",
    "cafes in Dulwich Hill Sydney",
    "restaurants in Petersham Sydney",
    "cafes in Petersham Sydney",
    "restaurants in Stanmore Sydney",
    "cafes in Stanmore Sydney",
    "restaurants in Summer Hill Sydney",
    "cafes in Summer Hill Sydney",
    "restaurants in Ashfield Sydney",
    "cafes in Ashfield Sydney",
    "restaurants in Five Dock Sydney",
    "cafes in Five Dock Sydney",
    "restaurants in Drummoyne Sydney",
    "cafes in Drummoyne Sydney",
    "restaurants in Haberfield Sydney",
    "cafes in Haberfield Sydney",
    "restaurants in Camperdown Sydney",
    "cafes in Camperdown Sydney",
    "restaurants in Erskineville Sydney",
    "cafes in Erskineville Sydney",
    "restaurants in St Peters Sydney",
    "cafes in St Peters Sydney",
    "restaurants in Tempe Sydney",
    "cafes in Tempe Sydney",
    "restaurants in Sydenham Sydney",
    "cafes in Sydenham Sydney",
    # North shore
    "restaurants in Mosman Sydney",
    "cafes in Mosman Sydney",
    "restaurants in Neutral Bay",
    "cafes in Neutral Bay",
    "restaurants in Cremorne Sydney",
    "cafes in Cremorne Sydney",
    "restaurants in Chatswood",
    "cafes in Chatswood",
    "restaurants in Crows Nest Sydney",
    "cafes in Crows Nest Sydney",
    "restaurants in Lane Cove",
    "cafes in Lane Cove",
    "restaurants in Kirribilli",
    "cafes in Kirribilli",
    "restaurants in North Sydney",
    "cafes in North Sydney",
    "restaurants in Milsons Point",
    "cafes in Milsons Point",
    "restaurants in Willoughby Sydney",
    "cafes in Willoughby Sydney",
    "restaurants in Artarmon",
    "cafes in Artarmon",
    "restaurants in St Leonards Sydney",
    "cafes in St Leonards Sydney",
    "restaurants in Lindfield",
    "cafes in Lindfield",
    "restaurants in Roseville Sydney",
    "cafes in Roseville Sydney",
    "restaurants in Gordon Sydney",
    "cafes in Gordon Sydney",
    "restaurants in Pymble",
    "cafes in Pymble",
    "restaurants in Turramurra",
    "cafes in Turramurra",
    "restaurants in Wahroonga",
    "cafes in Wahroonga",
    "restaurants in Hornsby",
    "cafes in Hornsby",
    # Northern beaches
    "restaurants in Manly",
    "cafes in Manly",
    "restaurants in Dee Why",
    "cafes in Dee Why",
    "restaurants in Brookvale",
    "cafes in Brookvale",
    "restaurants in Freshwater Sydney",
    "cafes in Freshwater Sydney",
    "restaurants in Curl Curl",
    "cafes in Curl Curl",
    "restaurants in Narrabeen",
    "cafes in Narrabeen",
    "restaurants in Mona Vale",
    "cafes in Mona Vale",
    "restaurants in Avalon Sydney",
    "cafes in Avalon Sydney",
    "restaurants in Newport Sydney",
    "cafes in Newport Sydney",
    "restaurants in Palm Beach Sydney",
    "cafes in Palm Beach Sydney",
    "restaurants in Collaroy",
    "cafes in Collaroy",
    "restaurants in Balgowlah",
    "cafes in Balgowlah",
    "restaurants in Seaforth Sydney",
    "cafes in Seaforth Sydney",
    # Eastern beaches
    "restaurants in Bondi",
    "cafes in Bondi",
    "restaurants in Bondi Junction",
    "cafes in Bondi Junction",
    "restaurants in Bronte Sydney",
    "cafes in Bronte Sydney",
    "restaurants in Coogee Sydney",
    "cafes in Coogee Sydney",
    "restaurants in Randwick",
    "cafes in Randwick",
    "restaurants in Maroubra",
    "cafes in Maroubra",
    "restaurants in Kensington Sydney",
    "cafes in Kensington Sydney",
    "restaurants in Kingsford Sydney",
    "cafes in Kingsford Sydney",
    "restaurants in Clovelly Sydney",
    "cafes in Clovelly Sydney",
    # South / Shire
    "restaurants in Cronulla",
    "cafes in Cronulla",
    "restaurants in Hurstville",
    "cafes in Hurstville",
    "restaurants in Kogarah",
    "cafes in Kogarah",
    "restaurants in Miranda Sydney",
    "cafes in Miranda Sydney",
    "restaurants in Sutherland Sydney",
    "cafes in Sutherland Sydney",
    "restaurants in Caringbah",
    "cafes in Caringbah",
    "restaurants in Gymea",
    "cafes in Gymea",
    "restaurants in Engadine",
    "cafes in Engadine",
    "restaurants in Rockdale Sydney",
    "cafes in Rockdale Sydney",
    "restaurants in Sans Souci",
    "cafes in Sans Souci",
    "restaurants in Brighton Le Sands",
    "cafes in Brighton Le Sands",
    "restaurants in Arncliffe Sydney",
    "cafes in Arncliffe Sydney",
    "restaurants in Bexley Sydney",
    "cafes in Bexley Sydney",
    # South west
    "restaurants in Liverpool Sydney",
    "cafes in Liverpool Sydney",
    "restaurants in Campbelltown Sydney",
    "cafes in Campbelltown Sydney",
    "restaurants in Cabramatta",
    "cafes in Cabramatta",
    "restaurants in Fairfield Sydney",
    "cafes in Fairfield Sydney",
    "restaurants in Revesby",
    "cafes in Revesby",
    "restaurants in Punchbowl Sydney",
    "cafes in Punchbowl Sydney",
    "restaurants in Lakemba",
    "cafes in Lakemba",
    "restaurants in Canterbury Sydney",
    "cafes in Canterbury Sydney",
    "restaurants in Campsie",
    "cafes in Campsie",
    "restaurants in Belmore Sydney",
    "cafes in Belmore Sydney",
    # West
    "restaurants in Parramatta",
    "cafes in Parramatta",
    "restaurants in Burwood Sydney",
    "cafes in Burwood Sydney",
    "restaurants in Strathfield",
    "cafes in Strathfield",
    "restaurants in Auburn Sydney",
    "cafes in Auburn Sydney",
    "restaurants in Bankstown",
    "cafes in Bankstown",
    "restaurants in Homebush Sydney",
    "cafes in Homebush Sydney",
    "restaurants in Concord Sydney",
    "cafes in Concord Sydney",
    "restaurants in Rhodes Sydney",
    "cafes in Rhodes Sydney",
    "restaurants in Ryde Sydney",
    "cafes in Ryde Sydney",
    "restaurants in Eastwood Sydney",
    "cafes in Eastwood Sydney",
    "restaurants in Epping Sydney",
    "cafes in Epping Sydney",
    "restaurants in Macquarie Park",
    "cafes in Macquarie Park",
    "restaurants in Castle Hill Sydney",
    "cafes in Castle Hill Sydney",
    "restaurants in Bella Vista Sydney",
    "cafes in Bella Vista Sydney",
    "restaurants in Blacktown",
    "cafes in Blacktown",
    "restaurants in Penrith",
    "cafes in Penrith",
    "restaurants in Mount Druitt",
    "cafes in Mount Druitt",
    "restaurants in Wetherill Park",
    "cafes in Wetherill Park",
    # Harbour / city fringe
    "restaurants in Barangaroo",
    "cafes in Barangaroo",
    "restaurants in Pyrmont Sydney",
    "cafes in Pyrmont Sydney",
    "restaurants in Alexandria Sydney",
    "cafes in Alexandria Sydney",
    "restaurants in Mascot Sydney",
    "cafes in Mascot Sydney",
    "restaurants in Zetland Sydney",
    "cafes in Zetland Sydney",
    "restaurants in Rosebery Sydney",
    "cafes in Rosebery Sydney",
    "restaurants in Wolli Creek",
    "cafes in Wolli Creek",
    "restaurants in Green Square Sydney",
    "cafes in Green Square Sydney",
    # ─── MELBOURNE ────────────────────────────────────────────────────
    # Melbourne CBD
    "restaurants in Melbourne CBD",
    "cafes in Melbourne CBD",
    "coffee shops in Melbourne CBD",
    "fast food in Melbourne CBD",
    # Inner city
    "restaurants in Fitzroy Melbourne",
    "cafes in Fitzroy Melbourne",
    "restaurants in Collingwood Melbourne",
    "cafes in Collingwood Melbourne",
    "restaurants in Carlton Melbourne",
    "cafes in Carlton Melbourne",
    "restaurants in Richmond Melbourne",
    "cafes in Richmond Melbourne",
    "restaurants in South Yarra",
    "cafes in South Yarra",
    "restaurants in Prahran",
    "cafes in Prahran",
    "restaurants in Windsor Melbourne",
    "cafes in Windsor Melbourne",
    "restaurants in St Kilda",
    "cafes in St Kilda",
    "restaurants in South Melbourne",
    "cafes in South Melbourne",
    "restaurants in Albert Park Melbourne",
    "cafes in Albert Park Melbourne",
    "restaurants in Port Melbourne",
    "cafes in Port Melbourne",
    "restaurants in Southbank Melbourne",
    "cafes in Southbank Melbourne",
    "restaurants in Docklands Melbourne",
    "cafes in Docklands Melbourne",
    "restaurants in East Melbourne",
    "cafes in East Melbourne",
    "restaurants in West Melbourne",
    "cafes in West Melbourne",
    # Inner north
    "restaurants in Brunswick Melbourne",
    "cafes in Brunswick Melbourne",
    "restaurants in Brunswick East",
    "cafes in Brunswick East",
    "restaurants in Northcote Melbourne",
    "cafes in Northcote Melbourne",
    "restaurants in Thornbury Melbourne",
    "cafes in Thornbury Melbourne",
    "restaurants in Preston Melbourne",
    "cafes in Preston Melbourne",
    "restaurants in Coburg",
    "cafes in Coburg",
    "restaurants in North Melbourne",
    "cafes in North Melbourne",
    "restaurants in Parkville Melbourne",
    "cafes in Parkville Melbourne",
    "restaurants in Abbotsford Melbourne",
    "cafes in Abbotsford Melbourne",
    "restaurants in Clifton Hill Melbourne",
    "cafes in Clifton Hill Melbourne",
    # Inner east
    "restaurants in Hawthorn Melbourne",
    "cafes in Hawthorn Melbourne",
    "restaurants in Camberwell Melbourne",
    "cafes in Camberwell Melbourne",
    "restaurants in Kew Melbourne",
    "cafes in Kew Melbourne",
    "restaurants in Balwyn",
    "cafes in Balwyn",
    "restaurants in Toorak",
    "cafes in Toorak",
    "restaurants in Armadale Melbourne",
    "cafes in Armadale Melbourne",
    "restaurants in Malvern Melbourne",
    "cafes in Malvern Melbourne",
    "restaurants in Glen Iris Melbourne",
    "cafes in Glen Iris Melbourne",
    # Inner west
    "restaurants in Footscray",
    "cafes in Footscray",
    "restaurants in Seddon Melbourne",
    "cafes in Seddon Melbourne",
    "restaurants in Yarraville",
    "cafes in Yarraville",
    "restaurants in Williamstown Melbourne",
    "cafes in Williamstown Melbourne",
    "restaurants in Newport Melbourne",
    "cafes in Newport Melbourne",
    "restaurants in Spotswood Melbourne",
    "cafes in Spotswood Melbourne",
    # South east
    "restaurants in Brighton Melbourne",
    "cafes in Brighton Melbourne",
    "restaurants in Elsternwick",
    "cafes in Elsternwick",
    "restaurants in Caulfield",
    "cafes in Caulfield",
    "restaurants in Carnegie Melbourne",
    "cafes in Carnegie Melbourne",
    "restaurants in Bentleigh",
    "cafes in Bentleigh",
    "restaurants in Oakleigh",
    "cafes in Oakleigh",
    "restaurants in Clayton Melbourne",
    "cafes in Clayton Melbourne",
    "restaurants in Glen Waverley",
    "cafes in Glen Waverley",
    "restaurants in Chadstone",
    "cafes in Chadstone",
    # Bayside
    "restaurants in Sandringham Melbourne",
    "cafes in Sandringham Melbourne",
    "restaurants in Hampton Melbourne",
    "cafes in Hampton Melbourne",
    "restaurants in Cheltenham Melbourne",
    "cafes in Cheltenham Melbourne",
    "restaurants in Mentone",
    "cafes in Mentone",
    "restaurants in Mordialloc",
    "cafes in Mordialloc",
    "restaurants in Frankston",
    "cafes in Frankston",
    # East
    "restaurants in Box Hill Melbourne",
    "cafes in Box Hill Melbourne",
    "restaurants in Doncaster",
    "cafes in Doncaster",
    "restaurants in Templestowe",
    "cafes in Templestowe",
    "restaurants in Ringwood",
    "cafes in Ringwood",
    "restaurants in Burwood Melbourne",
    "cafes in Burwood Melbourne",
    # North
    "restaurants in Heidelberg Melbourne",
    "cafes in Heidelberg Melbourne",
    "restaurants in Ivanhoe Melbourne",
    "cafes in Ivanhoe Melbourne",
    "restaurants in Reservoir Melbourne",
    "cafes in Reservoir Melbourne",
    "restaurants in Bundoora",
    "cafes in Bundoora",
    "restaurants in Mill Park",
    "cafes in Mill Park",
    "restaurants in South Morang",
    "cafes in South Morang",
    # West
    "restaurants in Werribee",
    "cafes in Werribee",
    "restaurants in Point Cook",
    "cafes in Point Cook",
    "restaurants in Caroline Springs",
    "cafes in Caroline Springs",
    "restaurants in Sunshine Melbourne",
    "cafes in Sunshine Melbourne",
    "restaurants in St Albans Melbourne",
    "cafes in St Albans Melbourne",
    # ─── BOSTON, MA (USA) ────────────────────────────────────────
    # Downtown / central
    "restaurants in Downtown Boston",
    "cafes in Downtown Boston",
    "coffee shops in Downtown Boston",
    "fast food in Downtown Boston",
    "restaurants in Back Bay Boston",
    "cafes in Back Bay Boston",
    "restaurants in Beacon Hill Boston",
    "cafes in Beacon Hill Boston",
    "restaurants in North End Boston",
    "cafes in North End Boston",
    "restaurants in West End Boston",
    "cafes in West End Boston",
    "restaurants in South End Boston",
    "cafes in South End Boston",
    "restaurants in Chinatown Boston",
    "cafes in Chinatown Boston",
    "restaurants in Seaport Boston",
    "cafes in Seaport Boston",
    "restaurants in Fenway Boston",
    "cafes in Fenway Boston",
    "restaurants in Kenmore Boston",
    "cafes in Kenmore Boston",
    # Boston neighborhoods
    "restaurants in Allston Boston",
    "cafes in Allston Boston",
    "restaurants in Brighton Boston",
    "cafes in Brighton Boston",
    "restaurants in Jamaica Plain Boston",
    "cafes in Jamaica Plain Boston",
    "restaurants in Roslindale Boston",
    "cafes in Roslindale Boston",
    "restaurants in West Roxbury Boston",
    "cafes in West Roxbury Boston",
    "restaurants in Hyde Park Boston",
    "cafes in Hyde Park Boston",
    "restaurants in Mission Hill Boston",
    "cafes in Mission Hill Boston",
    "restaurants in Roxbury Boston",
    "cafes in Roxbury Boston",
    "restaurants in Dorchester Boston",
    "cafes in Dorchester Boston",
    "restaurants in Mattapan Boston",
    "cafes in Mattapan Boston",
    "restaurants in South Boston",
    "cafes in South Boston",
    "restaurants in East Boston",
    "cafes in East Boston",
    "restaurants in Charlestown Boston",
    "cafes in Charlestown Boston",
    # Cambridge / Somerville
    "restaurants in Cambridge MA",
    "cafes in Cambridge MA",
    "restaurants in Harvard Square Cambridge",
    "cafes in Harvard Square Cambridge",
    "restaurants in Central Square Cambridge",
    "cafes in Central Square Cambridge",
    "restaurants in Kendall Square Cambridge",
    "cafes in Kendall Square Cambridge",
    "restaurants in Inman Square Cambridge",
    "cafes in Inman Square Cambridge",
    "restaurants in Porter Square Cambridge",
    "cafes in Porter Square Cambridge",
    "restaurants in Somerville MA",
    "cafes in Somerville MA",
    "restaurants in Davis Square Somerville",
    "cafes in Davis Square Somerville",
    "restaurants in Union Square Somerville",
    "cafes in Union Square Somerville",
    # Inner suburbs
    "restaurants in Brookline MA",
    "cafes in Brookline MA",
    "restaurants in Coolidge Corner Brookline",
    "cafes in Coolidge Corner Brookline",
    "restaurants in Newton MA",
    "cafes in Newton MA",
    "restaurants in Newton Centre",
    "cafes in Newton Centre",
    "restaurants in Watertown MA",
    "cafes in Watertown MA",
    "restaurants in Arlington MA",
    "cafes in Arlington MA",
    "restaurants in Medford MA",
    "cafes in Medford MA",
    "restaurants in Malden MA",
    "cafes in Malden MA",
    "restaurants in Everett MA",
    "cafes in Everett MA",
    "restaurants in Chelsea MA",
    "cafes in Chelsea MA",
    "restaurants in Revere MA",
    "cafes in Revere MA",
    "restaurants in Winthrop MA",
    "cafes in Winthrop MA",
    # North shore
    "restaurants in Lynn MA",
    "cafes in Lynn MA",
    "restaurants in Saugus MA",
    "cafes in Saugus MA",
    "restaurants in Salem MA",
    "cafes in Salem MA",
    "restaurants in Beverly MA",
    "cafes in Beverly MA",
    "restaurants in Peabody MA",
    "cafes in Peabody MA",
    "restaurants in Danvers MA",
    "cafes in Danvers MA",
    "restaurants in Marblehead MA",
    "cafes in Marblehead MA",
    "restaurants in Swampscott MA",
    "cafes in Swampscott MA",
    "restaurants in Melrose MA",
    "cafes in Melrose MA",
    "restaurants in Wakefield MA",
    "cafes in Wakefield MA",
    "restaurants in Stoneham MA",
    "cafes in Stoneham MA",
    "restaurants in Woburn MA",
    "cafes in Woburn MA",
    "restaurants in Winchester MA",
    "cafes in Winchester MA",
    # South shore
    "restaurants in Quincy MA",
    "cafes in Quincy MA",
    "restaurants in Milton MA",
    "cafes in Milton MA",
    "restaurants in Braintree MA",
    "cafes in Braintree MA",
    "restaurants in Weymouth MA",
    "cafes in Weymouth MA",
    "restaurants in Hingham MA",
    "cafes in Hingham MA",
    "restaurants in Cohasset MA",
    "cafes in Cohasset MA",
    "restaurants in Dedham MA",
    "cafes in Dedham MA",
    "restaurants in Needham MA",
    "cafes in Needham MA",
    "restaurants in Wellesley MA",
    "cafes in Wellesley MA",
    # West
    "restaurants in Waltham MA",
    "cafes in Waltham MA",
    "restaurants in Belmont MA",
    "cafes in Belmont MA",
    "restaurants in Lexington MA",
    "cafes in Lexington MA",
    "restaurants in Burlington MA",
    "cafes in Burlington MA",
    "restaurants in Lincoln MA",
    "cafes in Lincoln MA",
    "restaurants in Natick MA",
    "cafes in Natick MA",
    "restaurants in Framingham MA",
    "cafes in Framingham MA",
]

# Filters
MIN_STARS = 3.6
MAX_STARS = 4.9
MIN_REVIEWS = 80
MAX_REPLY_RATE = 1.0  # 100% — no filter, keep everyone
REVIEW_SAMPLE_SIZE = 20
MAX_LEADS = 1000

# Parallelism
GOOGLE_WORKERS = 5     # tabs for Google Maps (keep low to avoid detection)
EMAIL_WORKERS = 20     # tabs for business websites (safe to go high)

# Large franchise blocklist (lowercase)
FRANCHISE_BLOCKLIST = [
    "mcdonald's", "mcdonalds", "kfc", "subway", "burger king", "hungry jack's",
    "hungry jacks", "domino's", "dominos", "pizza hut", "taco bell", "wendy's",
    "wendys", "starbucks", "nando's", "nandos", "grill'd", "grilld",
    "oporto", "red rooster", "el jannah", "zambrero", "guzman y gomez",
    "mad mex", "soul origin", "oliver brown", "the coffee club", "gloria jean's",
    "gloria jeans", "chatime", "gong cha", "sushi hub",
]

# Output
OUTPUT_FILE = "leads.csv"

# Session storage — keeps you signed in between runs
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".google_session")

# Completed searches tracker — skips searches that have already been fully scraped
COMPLETED_SEARCHES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "completed_searches.txt")

# Timing (seconds)
MIN_DELAY = 1
MAX_DELAY = 2
BETWEEN_SEARCHES_DELAY = 45  # pause between search queries to look human

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("propos")

# ─── HELPERS ──────────────────────────────────────────────────────────────────


async def random_delay():
    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def clean_name(name):
    """Strip Google Maps aria-label junk like '-Visited link' suffix."""
    name = re.sub(r'\s*[-·]?\s*Visited link$', '', name)
    return name.strip()


def is_franchise(name):
    name_lower = name.lower()
    return any(f in name_lower for f in FRANCHISE_BLOCKLIST)


def is_junk_email(email):
    """Check if an email is a placeholder/template/junk address."""
    junk = ["@sentry", "@example", "@wix", "@squarespace", "@wordpress",
            ".png", ".jpg", ".webp", "@2x", "@3x", "@media", "@import",
            "user@domain", "@domain.com", "email@example", "name@example",
            "info@example", "@staging", "noreply@", "no-reply@",
            "test@", "@placeholder", "@email.com", "yourname@", "your@",
            "someone@", "john@doe", "jane@doe", "sample@"]
    return any(x in email.lower() for x in junk)


def extract_emails_from_text(text):
    """Pull all valid emails from HTML text, filtering out junk."""
    emails = set()

    # mailto: links first (most reliable)
    mailto = re.findall(
        r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', text
    )
    for email in mailto:
        if not is_junk_email(email):
            emails.add(email.lower())

    # Plain email addresses
    found = re.findall(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text
    )
    for email in found:
        if not is_junk_email(email):
            emails.add(email.lower())

    return emails


# ─── BROWSER SETUP ────────────────────────────────────────────────────────────


async def setup_browser(playwright):
    """Launch browser with persistent session. Prompts for sign-in on first run."""
    first_run = not os.path.exists(SESSION_DIR)

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=SESSION_DIR,
        headless=False,
        viewport={"width": 1280, "height": 900},
        locale="en-AU",
        timezone_id="Australia/Sydney",
        args=["--disable-blink-features=AutomationControlled"],
    )

    page = context.pages[0] if context.pages else await context.new_page()
    page.set_default_timeout(15000)

    if first_run:
        log.info("First run — please sign in to Google in the browser window.")
        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
        input("\n>>> Sign in to Google in the browser, then press ENTER here to continue...\n")
        log.info("Session saved. You won't need to sign in again.")

    return context, page


# ─── PHASE 1: GOOGLE MAPS SCRAPING ───────────────────────────────────────────


async def scroll_results_list(page, max_scrolls=25):
    """Scroll the Google Maps results panel to load more listings."""
    try:
        await page.wait_for_selector('div[role="feed"]', timeout=10000)
    except PlaywrightTimeout:
        log.warning("No results feed found")
        return

    prev_count = 0
    stale_rounds = 0
    for i in range(max_scrolls):
        await page.evaluate(
            '''() => {
                const feed = document.querySelector('div[role="feed"]');
                if (feed) feed.scrollTop = feed.scrollHeight;
            }'''
        )
        await asyncio.sleep(1.2)

        links = await page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
        count = len(links)
        if count == prev_count:
            stale_rounds += 1
            if stale_rounds >= 3:
                break
        else:
            stale_rounds = 0
        prev_count = count

    log.info(f"  Scrolled, {prev_count} listings loaded")


async def parse_listing_from_panel(page, aria_name=""):
    """Extract business info from an open Google Maps listing panel."""
    info = {}
    try:
        info["name"] = aria_name or ""

        rating_el = await page.query_selector('div.fontDisplayLarge')
        if rating_el:
            try:
                info["stars"] = float((await rating_el.inner_text()).strip())
            except ValueError:
                info["stars"] = 0.0
        else:
            star_el = await page.query_selector('span[aria-label*="stars"]')
            if star_el:
                label = await star_el.get_attribute("aria-label") or ""
                nums = re.findall(r"[\d.]+", label)
                info["stars"] = float(nums[0]) if nums else 0.0
            else:
                info["stars"] = 0.0

        info["total_reviews"] = 0
        for selector in [
            'button[jsaction*="reviewChart"] span',
            'span[aria-label*="reviews"]',
        ]:
            el = await page.query_selector(selector)
            if el:
                text = await el.get_attribute("aria-label") or await el.inner_text() or ""
                nums = re.findall(r"[\d,]+", text)
                if nums:
                    info["total_reviews"] = int(nums[0].replace(",", ""))
                    break

        addr_el = await page.query_selector('button[data-item-id="address"] div.fontBodyMedium')
        info["address"] = (await addr_el.inner_text()).strip() if addr_el else ""

        phone_el = await page.query_selector('button[data-item-id*="phone"] div.fontBodyMedium')
        info["phone"] = (await phone_el.inner_text()).strip() if phone_el else ""

        website_el = await page.query_selector('a[data-item-id="authority"]')
        info["website"] = await website_el.get_attribute("href") if website_el else ""

    except Exception as e:
        log.warning(f"Error parsing listing: {e}")

    return info


async def get_reply_rate(page, sample_size=REVIEW_SAMPLE_SIZE):
    """Click into reviews tab and sample recent reviews to estimate reply rate."""
    replied = 0
    sampled = 0

    try:
        reviews_tab = await page.query_selector('button[aria-label*="Reviews"]')
        if reviews_tab:
            await reviews_tab.click()
            await asyncio.sleep(1.5)

        for _ in range(3):
            await page.evaluate(
                '''() => {
                    const panels = document.querySelectorAll('div[role="main"]');
                    const panel = panels[panels.length - 1];
                    if (panel) panel.scrollTop += 1500;
                }'''
            )
            await asyncio.sleep(0.8)

        review_elements = await page.query_selector_all('div[data-review-id]')

        for review_el in review_elements[:sample_size]:
            sampled += 1
            html = await review_el.inner_html()
            if "Response from the owner" in html or "response from" in html.lower():
                replied += 1

    except Exception as e:
        log.warning(f"Error sampling reviews: {e}")

    if sampled == 0:
        return 0, 0, 1.0

    rate = replied / sampled
    return replied, sampled, rate


async def process_listing(context, listing, leads, lock):
    """Process a single listing in its own browser tab (NO email scraping)."""
    name = clean_name(listing["name"])
    href = listing["href"]
    page = await context.new_page()
    page.set_default_timeout(15000)

    try:
        await page.goto(href, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        info = await parse_listing_from_panel(page, aria_name=name)

        # Filter: stars
        stars = info.get("stars", 0)
        if stars < MIN_STARS or stars > MAX_STARS:
            log.info(f"  SKIP (stars {stars}): {name}")
            return None

        # Filter: review count
        total = info.get("total_reviews", 0)
        if total < MIN_REVIEWS:
            log.info(f"  SKIP ({total} reviews): {name}")
            return None

        log.info(f"  Checking reply rate: {name} ({stars}*, {total} reviews)")

        # Filter: reply rate
        replied, sampled, rate = await get_reply_rate(page, REVIEW_SAMPLE_SIZE)
        if sampled == 0:
            log.info(f"  SKIP (couldn't read reviews): {name}")
            return None
        if rate > MAX_REPLY_RATE:
            log.info(f"  SKIP (reply rate {rate:.0%}, {replied}/{sampled}): {name}")
            return None

        lead = {
            "business_name": name,
            "address": info.get("address", ""),
            "phone": info.get("phone", ""),
            "email": "",  # filled in Phase 2
            "website": info.get("website", "") or "",
            "total_reviews": total,
            "replied_count": replied,
            "reply_rate": f"{rate:.0%}",
            "star_rating": stars,
        }

        async with lock:
            leads.append(lead)
            count = len(leads)

        log.info(
            f"  LEAD #{count}: {name} — {stars}*, {total} reviews, "
            f"{rate:.0%} reply rate"
        )
        return lead

    except PlaywrightTimeout:
        log.warning(f"  Timeout: {name}")
        return None
    except Exception as e:
        log.warning(f"  Error on {name}: {e}")
        return None
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def collect_listings(page, query):
    """Search Google Maps and scroll to collect all listing URLs."""
    log.info(f"Searching: {query}")
    search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Accept cookies if prompted
    try:
        accept_btn = await page.query_selector('button:has-text("Accept all")')
        if accept_btn:
            await accept_btn.click()
            await asyncio.sleep(1)
    except Exception:
        pass

    await scroll_results_list(page, max_scrolls=25)

    listing_links = await page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
    listings = []
    for link in listing_links:
        aria = await link.get_attribute("aria-label") or ""
        href = await link.get_attribute("href") or ""
        if aria and href:
            listings.append({"name": aria, "href": href})

    log.info(f"Found {len(listings)} listings for '{query}'")
    return listings


async def process_batch(context, batch, leads, lock):
    """Process a batch of listings in parallel tabs."""
    tasks = [
        process_listing(context, listing, leads, lock)
        for listing in batch
    ]
    await asyncio.gather(*tasks)


# ─── PHASE 2: EMAIL SCRAPING (business websites, not Google) ─────────────────


async def scrape_email_for_lead(context, lead, semaphore):
    """Open a business website in a browser tab and find their email.
    Strategy: load homepage, check for emails, then find and click
    the Contact/About link (works for any site structure)."""
    website = lead.get("website", "")
    if not website:
        return

    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(8000)

        try:
            await asyncio.wait_for(_scrape_email_body(page, lead), timeout=45)
        except asyncio.TimeoutError:
            log.warning(f"  Timeout scraping {lead.get('business_name', '?')}")
        except Exception:
            pass
        finally:
            try:
                await page.close()
            except Exception:
                pass


async def _scrape_email_body(page, lead):
    """Inner email scrape logic — wrapped with an overall timeout."""
    website = lead.get("website", "")
    emails = set()

    # Step 1: Check homepage
    await page.goto(website, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await asyncio.sleep(0.5)

    text = await page.content()
    emails = extract_emails_from_text(text)
    if emails:
        lead["email"] = list(emails)[0]
        log.info(f"  EMAIL: {lead['business_name']} → {lead['email']}")
        return

    # Step 2: Find and click Contact/About links on the page
    # This handles any URL structure (/contact, /pages/contact, /get-in-touch, etc.)
    link_patterns = [
        'a:has-text("Contact")',
        'a:has-text("CONTACT")',
        'a:has-text("Get in Touch")',
        'a:has-text("Get In Touch")',
        'a:has-text("About")',
        'a:has-text("ABOUT")',
        'a:has-text("Enquire")',
        'a:has-text("ENQUIRE")',
        'a:has-text("Enquiry")',
        'a:has-text("Book")',
    ]

    for selector in link_patterns:
        if emails:
            break
        try:
            link = await page.query_selector(selector)
            if link:
                href = await link.get_attribute("href") or ""
                # Skip external links, anchors, and mailto
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0]
                    if not is_junk_email(email):
                        emails.add(email.lower())
                        break
                if href.startswith("#") or href.startswith("tel:"):
                    continue

                await link.click()
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(0.5)

                text = await page.content()
                emails = extract_emails_from_text(text)

                if emails:
                    break

                # Go back for the next link attempt
                await page.go_back()
                await asyncio.sleep(1)
        except Exception:
            try:
                await page.goto(website, wait_until="domcontentloaded")
                await asyncio.sleep(1)
            except Exception:
                pass
            continue

    if emails:
        lead["email"] = list(emails)[0]
        log.info(f"  EMAIL: {lead['business_name']} → {lead['email']}")


async def scrape_all_emails(context, leads):
    """Scrape emails for all leads in parallel using a semaphore to limit tabs."""
    leads_with_websites = [l for l in leads if l.get("website")]
    log.info(f"Phase 2: Scraping emails for {len(leads_with_websites)} leads ({EMAIL_WORKERS} parallel tabs)...")

    semaphore = asyncio.Semaphore(EMAIL_WORKERS)
    tasks = [
        scrape_email_for_lead(context, lead, semaphore)
        for lead in leads_with_websites
    ]
    await asyncio.gather(*tasks)

    found = sum(1 for l in leads if l.get("email"))
    log.info(f"  Found emails for {found}/{len(leads)} leads")


# ─── SEARCH TRACKER ───────────────────────────────────────────────────────────


def load_completed_searches():
    """Load list of searches that have already been fully scraped."""
    completed = set()
    if os.path.exists(COMPLETED_SEARCHES_FILE):
        with open(COMPLETED_SEARCHES_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    completed.add(line)
    return completed


def mark_search_completed(query):
    """Mark a search query as completed so we don't repeat it."""
    with open(COMPLETED_SEARCHES_FILE, "a") as f:
        f.write(query + "\n")


# ─── CSV ──────────────────────────────────────────────────────────────────────


FIELDNAMES = [
    "business_name", "address", "phone", "email", "website",
    "total_reviews", "replied_count", "reply_rate", "star_rating",
]


def load_existing_leads():
    """Load existing leads from CSV so we don't scrape them again."""
    existing = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row.get("business_name", "").strip().lower())
        log.info(f"Loaded {len(existing)} existing leads from {OUTPUT_FILE}")
    return existing


def save_leads(new_leads, existing_count):
    """Append new leads to CSV (creates file with header if it doesn't exist)."""
    if not new_leads:
        log.info("No new leads to save.")
        return

    file_exists = os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_leads)

    total = existing_count + len(new_leads)
    log.info(f"Added {len(new_leads)} new leads to {OUTPUT_FILE} ({total} total)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────


async def main():
    searches = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_SEARCHES
    leads = []
    lock = asyncio.Lock()

    # Load existing leads so we skip businesses we've already scraped
    existing_leads = load_existing_leads()
    seen_names = set(existing_leads)

    # Load completed searches so we don't repeat them
    completed_searches = load_completed_searches()
    remaining_searches = [s for s in searches if s not in completed_searches]

    if completed_searches:
        log.info(f"Skipping {len(completed_searches)} already-completed searches")

    log.info(f"Starting Propos scraper (2-phase) — target: {MAX_LEADS} new leads")
    log.info(f"  Phase 1: Google Maps ({GOOGLE_WORKERS} tabs) — {len(remaining_searches)} searches queued")
    log.info(f"  Phase 2: Email scraping ({EMAIL_WORKERS} tabs)")
    log.info(f"Filters: {MIN_STARS}–{MAX_STARS}*, {MIN_REVIEWS}+ reviews, <{MAX_REPLY_RATE:.0%} reply rate")

    t_start = time.time()

    async with async_playwright() as p:
        context, page = await setup_browser(p)

        # ── PHASE 1: Collect leads from Google Maps ──
        log.info("═══ PHASE 1: Scraping Google Maps ═══")
        phase1_start = time.time()

        for qi, query in enumerate(remaining_searches):
            if len(leads) >= MAX_LEADS:
                break

            all_listings = await collect_listings(page, query)

            # Deduplicate and filter franchises
            filtered = []
            for listing in all_listings:
                if clean_name(listing["name"]).lower() in seen_names:
                    continue
                seen_names.add(clean_name(listing["name"]).lower())
                if is_franchise(listing["name"]):
                    log.info(f"  SKIP (franchise): {listing['name']}")
                    continue
                filtered.append(listing)

            remaining = MAX_LEADS - len(leads)
            filtered = filtered[:remaining]

            for i in range(0, len(filtered), GOOGLE_WORKERS):
                if len(leads) >= MAX_LEADS:
                    break
                batch = filtered[i:i + GOOGLE_WORKERS]
                log.info(f"  Processing batch {i // GOOGLE_WORKERS + 1} ({len(batch)} listings)...")
                await process_batch(context, batch, leads, lock)
                await random_delay()

            # Mark this search as done
            mark_search_completed(query)
            log.info(f"Finished '{query}' — {len(leads)} leads so far ({qi+1}/{len(remaining_searches)} searches)")

            # Pause between searches to look human (skip if last search)
            if qi < len(remaining_searches) - 1 and len(leads) < MAX_LEADS:
                pause = random.uniform(BETWEEN_SEARCHES_DELAY * 0.7, BETWEEN_SEARCHES_DELAY * 1.3)
                log.info(f"  Pausing {pause:.0f}s before next search...")
                await asyncio.sleep(pause)

        phase1_time = time.time() - phase1_start
        log.info(f"Phase 1 done: {len(leads)} leads in {phase1_time:.0f}s")

        # ── PHASE 2: Scrape emails from business websites ──
        log.info("═══ PHASE 2: Scraping business websites for emails ═══")
        phase2_start = time.time()

        await scrape_all_emails(context, leads)

        phase2_time = time.time() - phase2_start
        log.info(f"Phase 2 done: emails scraped in {phase2_time:.0f}s")

        await context.close()

    save_leads(leads, len(existing_leads))

    total_time = time.time() - t_start
    emails_found = sum(1 for l in leads if l.get("email"))
    log.info(f"Done! {len(leads)} leads, {emails_found} emails, {total_time:.0f}s total")


if __name__ == "__main__":
    asyncio.run(main())
