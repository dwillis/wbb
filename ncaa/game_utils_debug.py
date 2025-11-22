"""
Enhanced version of game_utils with better error handling and debugging for Penn State.
"""

import os
import re
import csv
import json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("WARNING: Playwright is not installed")


def fetch_game_ids_playwright_debug(url, timeout=10000):
    """
    Enhanced version of fetch_game_ids_playwright with debugging output.

    Args:
        url: The URL to fetch game IDs from
        timeout: Timeout in milliseconds for waiting/clicking (default 10 seconds)

    Returns:
        list: Game IDs extracted from the page
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright is required but not installed")

    print(f"\n{'='*80}")
    print(f"DEBUG: fetch_game_ids_playwright_debug")
    print(f"{'='*80}")
    print(f"URL: {url}")
    print(f"Timeout: {timeout}ms")

    with sync_playwright() as p:
        print("\n[1/7] Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"\n[2/7] Navigating to URL...")
            response = page.goto(url, wait_until='networkidle', timeout=30000)
            print(f"  Response status: {response.status if response else 'None'}")
            print(f"  Final URL: {page.url}")

            if response and response.status != 200:
                print(f"  WARNING: Non-200 status code: {response.status}")
                if response.status == 404:
                    raise Exception(f"Page not found (404): {url}")
                elif response.status == 403:
                    raise Exception(f"Access forbidden (403): {url}")

            # Wait for page to load
            print(f"\n[3/7] Waiting for page to load...")
            page.wait_for_timeout(3000)

            # Check page title
            title = page.title()
            print(f"  Page title: {title}")

            # Look for the Game-By-Game button/tab
            print(f"\n[4/7] Looking for 'Game-By-Game' element...")

            # Try different selectors
            selectors_to_try = [
                ("text=Game-By-Game", "Exact text match (case-sensitive)"),
                ("text=Game-by-Game", "Text with lowercase 'by'"),
                ("text=game-by-game", "All lowercase"),
                ("text=/game.by.game/i", "Case-insensitive regex"),
                ("[data-tab='game-by-game']", "Data attribute"),
                ("button:has-text('Game')", "Button containing 'Game'"),
                ("a:has-text('Game')", "Link containing 'Game'"),
            ]

            found_selector = None
            for selector, description in selectors_to_try:
                try:
                    print(f"  Trying: {description} - selector: {selector}")
                    element = page.locator(selector).first
                    if element.count() > 0:
                        print(f"    ✓ FOUND!")
                        found_selector = selector
                        break
                    else:
                        print(f"    ✗ Not found")
                except Exception as e:
                    print(f"    ✗ Error: {e}")

            if not found_selector:
                print(f"\n  ERROR: Could not find 'Game-By-Game' element with any selector")
                print(f"\n  Saving page HTML to debug_page_content.html for inspection...")

                html_content = page.content()
                with open('/home/user/wbb/debug_page_content.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)

                # Look for any tabs or navigation elements
                print(f"\n  Looking for any tab-like elements...")
                tab_selectors = ["[role='tab']", ".tab", "[class*='tab']", "button", "a"]
                for tab_sel in tab_selectors:
                    try:
                        tabs = page.locator(tab_sel).all()
                        if tabs:
                            print(f"    Found {len(tabs)} elements matching '{tab_sel}':")
                            for i, tab in enumerate(tabs[:10]):  # Show first 10
                                try:
                                    text = tab.inner_text()[:50]
                                    print(f"      {i+1}. {text}")
                                except:
                                    pass
                    except:
                        pass

                raise Exception("Could not find 'Game-By-Game' tab/button on the page")

            # Click the element
            print(f"\n[5/7] Clicking on 'Game-By-Game' element...")
            page.click(found_selector, timeout=timeout)
            print(f"  Clicked successfully")

            # Wait for content to load
            print(f"\n[6/7] Waiting for game content to load...")
            page.wait_for_timeout(3000)

            # Find game links
            print(f"\n[7/7] Extracting game links...")
            game_links = page.locator("a[href*='boxscore']").all()
            print(f"  Found {len(game_links)} links containing 'boxscore'")

            # Extract IDs
            ids = []
            for i, link in enumerate(game_links):
                href = link.get_attribute("href")
                if href:
                    print(f"    Link {i+1}: {href}")
                    # Try to extract ID from href
                    parts = href.rstrip("/").split("/")
                    if parts and parts[-1].isdigit():
                        game_id = parts[-1]
                        ids.append(game_id)
                        print(f"      → Extracted ID: {game_id}")
                    elif "=" in href:
                        try:
                            game_id = href.split("=")[1].replace("&path", '').replace("&path=wbball", '')
                            if game_id.isdigit():
                                ids.append(game_id)
                                print(f"      → Extracted ID: {game_id}")
                        except:
                            pass

            print(f"\n  Total game IDs extracted: {len(ids)}")
            print(f"  IDs: {ids[:10]}" + (" ..." if len(ids) > 10 else ""))

            browser.close()
            print(f"\n{'='*80}")
            print(f"SUCCESS: Extracted {len(ids)} game IDs")
            print(f"{'='*80}\n")

            return ids

        except Exception as e:
            print(f"\n{'='*80}")
            print(f"ERROR: {type(e).__name__}: {e}")
            print(f"{'='*80}\n")
            browser.close()
            raise


def fetch_season_playwright_season_debug(season, base_url, slug):
    """
    Enhanced version of fetch_season_playwright_season with debugging.
    """
    from ncaa.game_utils import validate_season, parse_domain, parse_games

    print(f"\n{'='*80}")
    print(f"fetch_season_playwright_season_debug")
    print(f"{'='*80}")
    print(f"Season: {season}")
    print(f"Base URL: {base_url}")
    print(f"Slug: {slug}")

    validate_season(season)
    stats_url = base_url + f"/stats/season/{season}"

    print(f"\nConstructed stats URL: {stats_url}")

    game_ids = fetch_game_ids_playwright_debug(stats_url)
    domain = parse_domain(stats_url)

    print(f"\nDomain: {domain}")
    print(f"Game IDs: {game_ids}")
    print(f"\nProceeding to parse_games...")

    parse_games(season, domain, game_ids, slug)

    print(f"\n{'='*80}")
    print(f"COMPLETED: fetch_season_playwright_season_debug")
    print(f"{'='*80}\n")
