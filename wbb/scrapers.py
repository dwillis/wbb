"""Roster scraper classes.

Moved verbatim from ncaa/rosters/rosters.py L2130-3428: BaseScraper,
StandardScraper, TableScraper, JavaScriptScraper, VueDataScraper, ScraperFactory."""

import json
import logging
import re
import subprocess
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings for sites with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Optional imports for advanced scraping
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from requests_html import HTMLSession
    REQUESTS_HTML_AVAILABLE = True
except ImportError:
    REQUESTS_HTML_AVAILABLE = False

from wbb.models import Player
from wbb.parsing import FieldExtractors, HeaderMapper, SeasonVerifier
from wbb.templates import JSTemplates
from wbb.config import ENTITY_CONFIGS, TeamConfig, URLBuilder

logger = logging.getLogger(__name__)

class BaseScraper:
    """Base class for all roster scrapers"""
    
    def __init__(self, session: Optional[requests.Session] = None, entity_type: str = 'player'):
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36'
        })
        self.entity_type = entity_type
        self.entity_config = ENTITY_CONFIGS[entity_type]

    def fetch_html(self, url: str, return_status: bool = False) -> Optional[Union[BeautifulSoup, tuple]]:
        """Fetch and parse HTML from URL
        
        Args:
            url: URL to fetch
            return_status: If True, return (html, status_code) tuple instead of just html
        
        Returns:
            BeautifulSoup object if return_status=False, or (BeautifulSoup, status_code) tuple if return_status=True
        """
        try:
            response = self.session.get(url, timeout=30, verify=False)
            status_code = response.status_code  # Capture before raise_for_status()
            response.raise_for_status()
            html = BeautifulSoup(response.text, 'html.parser')
            return (html, status_code) if return_status else html
        except requests.HTTPError as e:
            if return_status:
                logger.error(f"Failed to fetch {url}: {e}")
                return (None, status_code)  # Use the status_code we captured
            logger.error(f"Failed to fetch {url}: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return (None, None) if return_status else None
    
    def fetch_html_with_javascript(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch HTML using shot-scraper to execute JavaScript"""
        import subprocess
        import tempfile
        import os
        
        try:
            logger.info(f"Using shot-scraper to render JavaScript for {url}")
            
            # Use shot-scraper via uv to get fully rendered HTML
            result = subprocess.run(
                ['uv', 'run', 'shot-scraper', 'html', url, '--wait', '3000'],
                capture_output=True,
                text=True,
                timeout=45
            )
            
            if result.returncode == 0 and result.stdout:
                logger.info("Successfully rendered HTML with JavaScript")
                return BeautifulSoup(result.stdout, 'html.parser')
            else:
                logger.warning(f"shot-scraper failed with return code {result.returncode}")
                if result.stderr:
                    logger.warning(f"shot-scraper stderr: {result.stderr[:200]}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"shot-scraper timed out for {url}")
            return None
        except FileNotFoundError:
            logger.error("uv or shot-scraper not found. Install with: uv add shot-scraper")
            return None
        except Exception as e:
            logger.error(f"Error using shot-scraper: {e}")
            return None

    def build_player_url(self, base_url: str, relative_url: str) -> str:
        """Build complete player URL"""
        if not relative_url:
            return ""
        if relative_url.startswith('http'):
            return relative_url
        
        return urljoin(base_url, relative_url)


class StandardScraper(BaseScraper):
    """Scraper for standard sidearm-roster-player layouts"""
    
    def scrape_roster(self, team: Dict, season: str, url_format: str = "default") -> List[Player]:
        """Scrape roster using standard sidearm layout"""
        # Store team config for custom field selectors
        team_id = team.get('ncaa_id')
        if team_id in TeamConfig.VUE_DATA_TEAMS:
            self.team_config = TeamConfig.VUE_DATA_TEAMS[team_id]
        elif team_id in TeamConfig.PRESTOSPORTS_SEASON_FIRST:
            self.team_config = TeamConfig.PRESTOSPORTS_SEASON_FIRST[team_id]
        else:
            self.team_config = {}
        
        url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
        
        # Use shot-scraper for Vue.js teams to handle JavaScript rendering
        if team.get('ncaa_id') in [51, 406, 90, 172, 610, 331, 2711, 101, 235, 2707, 598, 620, 587, 253, 810]:  # Baylor, Mercer, Cal Poly, Dartmouth, Saint Mary's (CA), Kent State, North Florida, CSUN, Florida, Kansas City, St. Cloud St., St. Thomas (MN), Rutgers, Georgia Southern, Wright St.
            html = self.fetch_html_with_javascript(url)
            status = 200 if html else None  # Set status for JavaScript-rendered pages
            if not html:
                logger.warning(f"shot-scraper failed for {team['team']}, falling back to regular fetch")
                html, status = self.fetch_html(url, return_status=True)
        else:
            html, status = self.fetch_html(url, return_status=True)
        
        # Debug logging
        logger.debug(f"Fetch result: html={'present' if html else 'None'}, status={status}, url_format={url_format}")
        
        # If 404 and using default format, try season_first as fallback
        if not html and status == 404 and url_format == "default":
            logger.info(f"Got 404 for {team['team']} at {url}, trying season_first URL format as fallback")
            url = URLBuilder.build_url(team['url'], season, "season_first", entity_type=self.entity_type)
            logger.info(f"Trying fallback URL: {url}")
            html = self.fetch_html(url)
        
        if not html:
            return []
        
        # Cache HTML for JSON data extraction
        self._last_html = html
        self._nuxt_data_cache = None  # Reset cache for new page

        # Verify season if it's a Sidearm site
        if SeasonVerifier.is_sidearm_site(html):
            if not SeasonVerifier.verify_season_on_page(html, season, entity_type=self.entity_type, team_id=team['ncaa_id']):
                logger.warning(f"Season verification failed for {team['team']} - expected {season}")
                return []

        # Find player/coach elements
        elements = self._find_player_elements(html)
        entity_label = self.entity_config['entity_label']
        logger.info(f"Found {len(elements)} {entity_label} for {team['team']}")
        
        roster = []
        seen_coaches = set()
        for elem in elements:
            try:
                # Extract based on entity type
                if self.entity_type == 'player':
                    entity = self._extract_player_data(elem, team, season)
                else:  # coach
                    entity = self._extract_coach_data(elem, team, season)
                
                if entity:
                    if self.entity_type == 'coach':
                        dedupe_key = (
                            (entity.url or '').lower(),
                            entity.name.lower(),
                            entity.position.lower()
                        )
                        if dedupe_key in seen_coaches:
                            continue
                        seen_coaches.add(dedupe_key)
                    roster.append(entity)
            except Exception as e:
                logger.warning(f"Failed to parse {self.entity_type} for {team['team']}: {e}")
                continue
                
        return roster

    def _get_nuxt_player_data(self, player_name: str, player_url: str) -> Optional[Dict]:
        """Extract player data from __NUXT__ JSON embedded in page (for Baylor-style sites)
        
        NOTE: This method currently cannot parse Baylor's window.__NUXT__ format because
        it uses a complex deduplicated array structure that requires the actual JavaScript
        values to be resolved. BeautifulSoup sees the raw HTML source, not the rendered data.
        
        FUTURE: This could be enhanced with shot-scraper or Playwright:
        - Use shot-scraper to execute: `return JSON.stringify(window.__NUXT__)`
        - Parse the returned JSON and use the existing search logic below
        - Or use shot-scraper to render the HTML fully, then extract from DOM elements
        
        Example shot-scraper command:
            shot-scraper javascript URL 'return window.__NUXT__' --output data.json
        """
        if not hasattr(self, '_nuxt_data_cache'):
            # Cache the NUXT data for this page load
            self._nuxt_data_cache = None
            
        if self._nuxt_data_cache is None:
            # Try to parse NUXT data from the current page
            try:
                if hasattr(self, '_last_html') and self._last_html:
                    import json
                    import re
                    
                    # Look for window.__NUXT__ data
                    html_text = str(self._last_html)
                    nuxt_match = re.search(r'window\.__NUXT__\s*=\s*({.+?});?\s*</script>', html_text, re.DOTALL)
                    if nuxt_match:
                        try:
                            nuxt_json = json.loads(nuxt_match.group(1))
                            self._nuxt_data_cache = nuxt_json
                            logger.debug("Successfully parsed __NUXT__ data")
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to parse __NUXT__ JSON: {e}")
            except Exception as e:
                logger.debug(f"Error extracting __NUXT__ data: {e}")
        
        # Search for player data in the cached NUXT data
        if self._nuxt_data_cache:
            try:
                # Navigate the NUXT data structure to find roster data
                # The structure varies but typically: state.data or state.roster
                def search_for_player(obj, depth=0):
                    """Recursively search for player data"""
                    if depth > 10:  # Prevent infinite recursion
                        return None
                    
                    if isinstance(obj, dict):
                        # Check if this dict looks like player data
                        if 'firstName' in obj and 'lastName' in obj:
                            full_name = f"{obj.get('firstName', '')} {obj.get('lastName', '')}".strip()
                            if full_name.lower() == player_name.lower():
                                return obj
                        
                        # Recurse into dict values
                        for value in obj.values():
                            result = search_for_player(value, depth + 1)
                            if result:
                                return result
                    
                    elif isinstance(obj, list):
                        # Recurse into list items
                        for item in obj:
                            result = search_for_player(item, depth + 1)
                            if result:
                                return result
                    
                    return None
                
                return search_for_player(self._nuxt_data_cache)
            except Exception as e:
                logger.debug(f"Error searching __NUXT__ data: {e}")
        
        return None

    def _find_player_elements(self, html):
        """Find player/coach elements using entity-specific selectors"""
        search_context = html

        # Check for custom player selector in team config
        team_config = getattr(self, 'team_config', {})
        custom_player_selector = team_config.get('player_selector')
        
        if custom_player_selector:
            elements = search_context.select(custom_player_selector)
            if elements:
                logger.info(f"Found {len(elements)} {self.entity_type} elements with custom selector: {custom_player_selector}")
                return elements

        # For Wyoming-style sites, try #roster-staff for coaches first
        if self.entity_type == 'coach':
            # Try coaching staff specific containers
            coaching_container = html.select_one('#coaching-staff, #roster-staff')
            if coaching_container:
                search_context = coaching_container
                logger.info(f"Found coach container")
            else:
                # Try regular coach container
                container_selector = self.entity_config.get('sidearm_container')
                if container_selector:
                    container = html.select_one(container_selector)
                    if container:
                        search_context = container
                        logger.info(f"Found {self.entity_type} container: {container_selector}")
                    else:
                        logger.warning(f"Container {container_selector} not found, searching entire page")
        else:
            # For players, try panel-based containers first (Baylor style)
            player_container = html.select_one('#cardPanel, #listPanel, #tablePanel')
            if player_container:
                search_context = player_container
                logger.info(f"Found player panel container")
            else:
                # Try regular player container
                container_selector = self.entity_config.get('sidearm_container')
                if container_selector:
                    container = html.select_one(container_selector)
                    if container:
                        search_context = container
                        logger.info(f"Found {self.entity_type} container: {container_selector}")
                    else:
                        logger.warning(f"Container {container_selector} not found, searching entire page")
        
        # Use entity-specific selectors from config
        selectors = self.entity_config['sidearm_selectors']
        elements = []
        
        for selector in selectors:
            # Try CSS selector first
            if selector.startswith('.'):
                # Use select() instead of find_all() to support full CSS selectors
                elements = search_context.select(selector)
                if elements:
                    logger.info(f"Found {len(elements)} {self.entity_type} elements with selector: {selector}")
                    break
                else:
                    logger.debug(f"No elements found with selector: {selector}")
        
        # Fallback: Try text-wrapper pattern (South Carolina style) for players only
        if not elements and self.entity_type == 'player':
            text_wrappers = search_context.find_all('div', {'class': 'text-wrapper'})
            if text_wrappers:
                elements = [div.parent for div in text_wrappers 
                          if div.parent and div.parent.name == 'li']
        
        return elements

    def _extract_prestosports_flipcard_field(self, player_elem, field_label: str) -> str:
        """Extract field from PrestoSports flipcard format where data is in .card-back with 'Label: value' format"""
        # player_elem is .player-card-wrapper, need to find .card-back inside .player-card
        card_back = player_elem.select_one('.player-card .card-back .bio-data')
        if not card_back:
            return ""
        
        # Find all list items (they're inside a ul, so use recursive=True)
        list_items = card_back.find_all('li')
        for li in list_items:
            # Check if this list item has the label we're looking for
            text = li.get_text(separator=' ', strip=True)
            if text.startswith(field_label + ':'):
                # Extract the value after the label
                value = text.replace(field_label + ':', '').strip()
                return value
        
        return ""

    def _extract_player_data(self, player_elem, team: Dict, season: str) -> Optional[Player]:
        """Extract player data using field extractors"""
        try:
            # Skip coach/staff elements when scraping players
            full_text = player_elem.get_text(separator=' ', strip=True)
            if player_elem.find('a'):
                href = player_elem.find('a').get('href', '')
                if '/coaches/' in href or '/staff/' in href:
                    return None
            
            # Extract name - try field selectors first
            name = ""
            name_selectors = self.entity_config['field_selectors']['name']
            for selector in name_selectors:
                name_elem = player_elem.select_one(selector)
                if name_elem:
                    # Special handling: if this is .sidearm-roster-player-name, check for nested <a> or <h3> first
                    # This handles cases like CMSV where jersey number is nested inside the name div
                    if 'sidearm-roster-player-name' in selector:
                        # Try to get name from nested link or h3 to avoid picking up nested jersey number
                        nested_link = name_elem.select_one('h3 a, a[href*="/roster/"]')
                        if nested_link:
                            name = FieldExtractors.clean_text(nested_link.get_text())
                            if name:
                                break
                    # If no special handling or it didn't work, use the element text
                    if not name:
                        name = FieldExtractors.clean_text(name_elem.get_text())
                    if name:
                        break
            
            # Fallback to aria-label if no name found
            if not name and player_elem.find('a') and 'aria-label' in player_elem.find('a').attrs:
                aria_label = player_elem.find('a')['aria-label']
                # Skip aria-labels that are for images
                if 'image thumbnail' not in aria_label.lower():
                    # Handle different aria-label formats
                    if ' - ' in aria_label:
                        name = aria_label.split(' - ')[0].strip()
                    else:
                        # For formats like "Name jersey number X full bio", extract just the name
                        # Remove common suffixes
                        name = aria_label.replace(' full bio', '').strip()
                        # Extract name before "jersey number" if present
                        if ' jersey number ' in name.lower():
                            name = name.split(' jersey number ')[0].strip()
            
            if not name or 'Instagram' in name:
                return None

            # Check if this is a PrestoSports flipcard format
            team_config = getattr(self, 'team_config', {})
            is_flipcard = team_config.get('flipcard_format', False)
            
            if is_flipcard:
                # Extract from flipcard format with label: value structure
                # Jersey from .card-back-head .number (e.g., "#1")
                jersey_elem = player_elem.select_one('.player-card .card-back-head .number')
                jersey = jersey_elem.get_text().strip().replace('#', '') if jersey_elem else ""
                
                fields = {
                    'previous_school': self._extract_prestosports_flipcard_field(player_elem, 'Previous School'),
                    'high_school': self._extract_prestosports_flipcard_field(player_elem, 'Highschool'),
                    'height': self._extract_prestosports_flipcard_field(player_elem, 'Height'),
                    'hometown': self._extract_prestosports_flipcard_field(player_elem, 'Hometown'),
                    'jersey': jersey,
                    'year': self._extract_prestosports_flipcard_field(player_elem, 'Class'),
                    'position': self._extract_prestosports_flipcard_field(player_elem, 'Position')
                }
            else:
                # Extract other fields from HTML elements
                # Use custom selectors if available, otherwise use default classes
                fields = {
                    'previous_school': self._get_field_with_custom_selectors(player_elem, 'previous_school', 'sidearm-roster-player-previous-school'),
                    'high_school': self._get_field_with_custom_selectors(player_elem, 'high_school', 'sidearm-roster-player-highschool'),
                    'height': self._get_field_with_custom_selectors(player_elem, 'height', 'sidearm-roster-player-height'),
                    'hometown': self._get_field_with_custom_selectors(player_elem, 'hometown', 'sidearm-roster-player-hometown'),
                    'jersey': self._get_field_with_custom_selectors(player_elem, 'jersey', 'sidearm-roster-player-jersey-number'),
                    'year': self._get_academic_year(player_elem, season),
                    'position': self._get_position(player_elem)
                }

            # Build player URL - we'll use this to match with JSON data
            player_url = ""
            if player_elem.find('a'):
                relative_url = player_elem.find('a').get('href', '')
                player_url = self.build_player_url(team['url'], relative_url)
            
            # For Baylor and similar sites, try to enrich data from JSON if fields are empty
            # NOTE: Currently non-functional without JavaScript execution (see _get_nuxt_player_data)
            # This provides the framework for a future shot-scraper/Playwright enhancement
            if player_url and not all([fields.get('position'), fields.get('height'), fields.get('hometown')]):
                json_data = self._get_nuxt_player_data(name, player_url)
                if json_data:
                    if not fields.get('position'):
                        fields['position'] = json_data.get('positionShort') or json_data.get('positionLong', '')
                    if not fields.get('height'):
                        # Try to format height from feet/inches if available
                        height_str = json_data.get('height', '')
                        if not height_str and 'heightFeet' in json_data:
                            try:
                                feet = int(json_data['heightFeet']) if json_data.get('heightFeet') else 0
                                inches = int(json_data['heightInches']) if json_data.get('heightInches') else 0
                                # Only format if values seem reasonable (not IDs)
                                if 4 <= feet <= 7 and 0 <= inches <= 11:
                                    height_str = f"{feet}-{inches}"
                            except (ValueError, TypeError):
                                pass
                        fields['height'] = height_str
                    if not fields.get('hometown'):
                        fields['hometown'] = json_data.get('hometown', '')
                    if not fields.get('high_school'):
                        fields['high_school'] = json_data.get('highSchool', '')
                    if not fields.get('previous_school'):
                        fields['previous_school'] = json_data.get('previousSchool', '')

            # If certain fields weren't found on the roster list item, try the individual
            # player bio page (Sidearm/Presto sites often put Class / Hometown / High School
            # on the bio page). We attempt to fetch and extract missing fields non-fatally.
            if player_url and (not fields.get('year') or not fields.get('hometown') or not fields.get('high_school') or not fields.get('previous_school')):
                try:
                    player_page = self.fetch_html(player_url)
                    if player_page:
                        # Look for labels like '<span class="sidearm-roster-player-field-label">Class</span>'
                        for label in player_page.find_all(class_='sidearm-roster-player-field-label'):
                            label_text = label.get_text(strip=True).lower()
                            if 'class' in label_text:
                                # Value is usually the next sibling span
                                val = None
                                # Try immediate next sibling element
                                sib = label.find_next_sibling()
                                if sib:
                                    val = FieldExtractors.clean_text(sib.get_text())

                                # As a fallback, check for the parent container pattern
                                if not val:
                                    parent = label.parent
                                    if parent:
                                        # find span elements inside parent that aren't the label
                                        spans = [s for s in parent.find_all('span') if s is not label]
                                        if spans:
                                            val = FieldExtractors.clean_text(spans[0].get_text())

                                if val:
                                    # Normalize using existing helper and set
                                    norm = self._normalize_class_text(val, season) or FieldExtractors.normalize_academic_year(val)
                                    fields['year'] = norm
                                    break

                        # If we still need hometown/high_school/previous_school, try to locate them
                        # on the bio page using similar label patterns.
                        def extract_bio_label(lbls):
                            """Try to find any of the label strings in lbls and return the associated value."""
                            for label in player_page.find_all(class_='sidearm-roster-player-field-label'):
                                label_text = label.get_text(strip=True).lower()
                                for target in lbls:
                                    if target in label_text:
                                        # value is usually the next sibling element
                                        v = None
                                        sib = label.find_next_sibling()
                                        if sib and sib.get_text(strip=True):
                                            v = FieldExtractors.clean_text(sib.get_text())
                                        if not v:
                                            parent = label.parent
                                            if parent:
                                                spans = [s for s in parent.find_all('span') if s is not label]
                                                if spans and spans[0].get_text(strip=True):
                                                    v = FieldExtractors.clean_text(spans[0].get_text())
                                        if v:
                                            return v
                            return ''

                        if not fields.get('hometown'):
                            home_val = extract_bio_label(['hometown'])
                            if home_val:
                                fields['hometown'] = home_val

                        if not fields.get('high_school'):
                            hs_val = extract_bio_label(['high school', 'highschool', 'high school/last school', 'last school', 'high school(s)'])
                            if hs_val:
                                fields['high_school'] = hs_val

                        if not fields.get('previous_school'):
                            prev_val = extract_bio_label(['previous school', 'previous institution', 'transfer'])
                            if prev_val:
                                fields['previous_school'] = prev_val
                except Exception:
                    # Non-fatal: just continue if we couldn't fetch or parse the player page
                    logger.debug(f"Unable to fetch/parse player bio for {player_url}")

            return Player(
                team_id=team['ncaa_id'],
                team=team['team'],
                player_id=player_elem.get('data-player-id'),
                name=name,
                year=fields['year'],
                hometown=fields['hometown'],
                high_school=fields['high_school'],
                previous_school=fields['previous_school'],
                height=fields['height'],
                position=fields['position'],
                jersey=fields['jersey'],
                url=player_url,
                season=season
            )

        except Exception as e:
            logger.error(f"Error extracting player data: {e}")
            return None

    def _get_text_by_class(self, element, class_name: str) -> str:
        """Get text from element with class name"""
        # Try any element type with the class, not just span
        found = element.find(class_=class_name)
        return FieldExtractors.clean_text(found.get_text()) if found else ""

    def _get_academic_year(self, player_elem, season: str = None) -> str:
        """Extract academic year"""
        # Try custom selectors first, then fall back to default
        year_text = self._get_field_with_custom_selectors(player_elem, 'academic_year', 'sidearm-roster-player-academic-year')
        if year_text:
            return year_text

        # Fallbacks: Some Sidearm templates store the year in custom1/custom2 spans
        for cls in ('sidearm-roster-player-custom1', 'sidearm-roster-list-item-custom1', 'sidearm-roster-player-custom2', 'sidearm-roster-list-item-custom2'):
            txt = self._get_text_by_class(player_elem, cls)
            if txt:
                # Normalize the value: common Sidearm patterns are like "'28" (two-digit grad year)
                normalized = self._normalize_class_text(txt, season)
                if normalized:
                    return normalized

        return ""

    def _normalize_class_text(self, text: str, season: str = None) -> str:
        """Try to convert text that looks like a graduation year or class into an
        academic-year token (FR, SO, JR, SR, GRAD). Examples handled:
        - "'28", "28", "2028" -> compute class-of mapping relative to season (e.g. FR/SO/JR/SR)
        - "freshman", "jr", etc -> normalized to standard tokens via FieldExtractors
        Returns empty string if normalization is not possible.
        """
        if not text:
            return ''
        t = text.strip().lower()

        # If it already looks like an academic-year label, return canonical upper-case
        if FieldExtractors.looks_like_academic_year(t):
            return t.upper().replace('.', '')

        # Match short forms like '28 or 28 or 2028
        m = re.match(r"^'?(\d{2,4})$", t)
        if m:
            yr = int(m.group(1))
            if yr < 100:  # two-digit -> convert 00-99 to 2000+yr
                yr = 2000 + yr

            # Need season context to map to FR/SO/JR/SR
            if season:
                # season may be like '2025-26' or '2025'
                try:
                    if '-' in season:
                        end_year = int(season.split('-')[-1])
                        # handle two-digit part like '25->2025' if needed
                        if len(season.split('-')[-1]) == 2:
                            end_year = int(str(season[:4])[:2] + season.split('-')[-1])
                    else:
                        # season '2025' -> treat as ending in same year
                        end_year = int(season)
                except Exception:
                    end_year = None

                if end_year:
                    diff = yr - end_year
                    # Map diff -> academic standing for typical 4-year programs
                    if diff <= 0:
                        return 'SR'
                    if diff == 1:
                        return 'JR'
                    if diff == 2:
                        return 'SO'
                    if diff >= 3:
                        return 'FR'

            # Without season info return the numeric year string (e.g., 2028)
            return str(yr)

        return ''

    def _extract_coach_data(self, coach_elem, team: Dict, season: str) -> Optional[Player]:
        """Extract coach information from a coach element"""
        try:
            full_text = coach_elem.get_text(separator=' ', strip=True) if coach_elem else ''
            # Some sites list players and coaches with the same card component; skip player cards
            if 'Jersey Number' in full_text:
                return None
            
            # Extract name using entity-specific selectors
            name = None
            for selector in self.entity_config['field_selectors']['name']:
                if selector.startswith('.'):
                    class_name = selector[1:]
                    name_elem = coach_elem.find(class_=class_name)
                    if name_elem:
                        name = FieldExtractors.clean_text(name_elem.get_text())
                        break
                else:
                    # Try as tag name (h3, h4, etc)
                    name_elem = coach_elem.find(selector)
                    if name_elem:
                        name = FieldExtractors.clean_text(name_elem.get_text())
                        break
            
            if not name:
                return None
            
            # Extract title
            title = ""
            for selector in self.entity_config['field_selectors']['title']:
                if selector.startswith('.'):
                    class_name = selector[1:]
                    title_elem = coach_elem.find(class_=class_name)
                    if title_elem:
                        title = FieldExtractors.clean_text(title_elem.get_text())
                        break
            
            # Extract experience
            experience = ""
            for selector in self.entity_config['field_selectors']['experience']:
                if selector.startswith('.'):
                    class_name = selector[1:]
                    exp_elem = coach_elem.find(class_=class_name)
                    if exp_elem:
                        experience = FieldExtractors.clean_text(exp_elem.get_text())
                        break
            
            # Extract alma mater
            alma_mater = ""
            for selector in self.entity_config['field_selectors']['alma_mater']:
                if selector.startswith('.'):
                    class_name = selector[1:]
                    alma_elem = coach_elem.find(class_=class_name)
                    if alma_elem:
                        alma_mater = FieldExtractors.clean_text(alma_elem.get_text())
                        break
            
            # Build coach URL
            coach_url = ""
            if coach_elem.find('a'):
                relative_url = coach_elem.find('a').get('href', '')
                coach_url = self.build_player_url(team['url'], relative_url)
            
            # Create Player object (reusing same dataclass for coaches)
            # Map coach fields to player fields
            return Player(
                team_id=team['ncaa_id'],
                team=team['team'],
                player_id=None,
                name=name,
                year=experience,  # Map experience to year field
                hometown=alma_mater,  # Map alma_mater to hometown field
                high_school='',
                previous_school='',
                height='',
                position=title,  # Map title to position field
                jersey='',  # Coaches don't have jersey numbers
                url=coach_url,
                season=season
            )
        
        except Exception as e:
            logger.error(f"Error extracting coach data: {e}")
            return None

    def _get_field_with_custom_selectors(self, player_elem, field_name: str, default_class: str = None) -> str:
        """Extract a field using custom selectors if available, otherwise fall back to default class"""
        # Check if team has custom field selectors
        team_config = getattr(self, 'team_config', {})
        custom_selectors = team_config.get('field_selectors', {}).get(field_name, [])
        
        # Try custom selectors first
        for selector in custom_selectors:
            elem = player_elem.select_one(selector)
            if elem:
                text = FieldExtractors.clean_text(elem.get_text())
                # Remove <sr-only> hidden text content
                sr_only = elem.find('span', {'class': 'sr-only'})
                if sr_only:
                    sr_text = sr_only.get_text()
                    text = text.replace(sr_text, '').strip()
                if text:
                    # Normalize academic year if that's the field being extracted
                    if field_name == 'academic_year':
                        text = FieldExtractors.normalize_academic_year(text)
                    # Sidearm next-gen cards prefix the value with the label
                    # ("Previous School: Duke", "Previous: Lindenwood"); strip it
                    if field_name == 'previous_school':
                        text = re.sub(r'^(?:previous(?: school)?)\s*:\s*', '', text, flags=re.IGNORECASE)
                    return text
        
        # Fall back to default class if no custom selector worked
        if default_class:
            text = self._get_text_by_class(player_elem, default_class)
            # Normalize academic year if that's the field being extracted
            if text and field_name == 'academic_year':
                text = FieldExtractors.normalize_academic_year(text)
            return text
        
        return ""
    
    def _get_position(self, player_elem) -> str:
        """Extract position"""
        # First try to find position in a nested .text-bold span within .sidearm-roster-player-position
        # This handles cases like CMSV where position and height are in the same parent element
        pos_container = player_elem.select_one('.sidearm-roster-player-position')
        if pos_container:
            # Look for position in .text-bold span
            text_bold = pos_container.select_one('.text-bold, span.text-bold')
            if text_bold:
                position_text = FieldExtractors.clean_text(text_bold.get_text())
                if position_text:
                    return FieldExtractors.extract_position(position_text)
        
        # Try custom selectors first, then fall back to default
        position_text = self._get_field_with_custom_selectors(player_elem, 'position', 'sidearm-roster-player-position')
        if position_text:
            return FieldExtractors.extract_position(position_text)
        return ""


class TableScraper(BaseScraper):
    """Scraper for table-based rosters"""
    
    def scrape_roster(self, team: Dict, season: str, url_format: str = "default") -> List[Player]:
        """Scrape roster from table format"""
        url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
        html, status = self.fetch_html(url, return_status=True)
        
        # If 404 and using default format, try season_first as fallback
        if not html and status == 404 and url_format == "default":
            logger.info(f"Got 404 for {team['team']} at {url}, trying season_first URL format as fallback")
            url = URLBuilder.build_url(team['url'], season, "season_first", entity_type=self.entity_type)
            logger.info(f"Trying fallback URL: {url}")
            html = self.fetch_html(url)
        
        if not html:
            return []

        # Verify season for Sidearm sites
        if SeasonVerifier.is_sidearm_site(html):
            if not SeasonVerifier.verify_season_on_page(html, season, entity_type=self.entity_type, team_id=team['ncaa_id']):
                logger.warning(f"Season {season} not found on page for {team['team']}")
                return []

        # For coaches, look for coach-specific tables or sections
        if self.entity_type == 'coach':
            return self._scrape_coaches(html, team, season, url)
        
        # Player scraping logic
        table = html.find('table', {'id': 'players-table__general'})
        if not table:
            table = html.find('table')

        if not table:
            logger.warning(f"No table found for {team['team']} at {url}")
            return []

        headers, rows = self._parse_table(table)
        if not headers or not rows:
            logger.warning(f"Could not parse headers or rows for {team['team']}")
            return []

        mapped_headers = HeaderMapper.map_headers(headers)
        
        roster = []
        for row in rows:
            try:
                player = self._extract_table_player(row, mapped_headers, team, season)
                if player:
                    roster.append(player)
            except Exception as e:
                logger.warning(f"Failed to parse table row for {team['team']}: {e}")
                continue

        return roster
    
    def _scrape_coaches(self, html, team: Dict, season: str, url: str) -> List[Player]:
        """Scrape coaches from table or coach-specific sections"""
        coaches = []
        
        # Try to find coach-specific headers or sections
        coach_headers = html.find_all(['h2', 'h3', 'h4'], 
                                      string=lambda s: s and 'coach' in s.lower() if s else False)
        
        if coach_headers:
            # Find table after coach header
            for header in coach_headers:
                table = header.find_next('table')
                if table:
                    coaches = self._parse_coach_table(table, team, season, url)
                    if coaches:
                        return coaches
        
        # Try finding coaches in the main table by looking for coach-like positions
        table = html.find('table', {'id': 'players-table__general'})
        if not table:
            table = html.find('table')
        
        if table:
            headers, rows = self._parse_table(table)
            if headers and rows:
                # Check if any row has coach titles
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Look for coach indicators in any cell
                        row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                        if any(keyword in row_text.lower() for keyword in ['head coach', 'assistant coach', 'director', 'coordinator']):
                            coach = self._extract_coach_from_row(row, team, season, url)
                            if coach:
                                coaches.append(coach)
        
        return coaches
    
    def _parse_coach_table(self, table, team: Dict, season: str, url: str) -> List[Player]:
        """Parse a table containing coaches"""
        coaches = []
        headers, rows = self._parse_table(table)
        
        for row in rows:
            coach = self._extract_coach_from_row(row, team, season, url)
            if coach:
                coaches.append(coach)
        
        return coaches
    
    def _extract_coach_from_row(self, row, team: Dict, season: str, base_url: str) -> Optional[Player]:
        """Extract coach data from a table row"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            # Extract name (usually first or second cell)
            name = ''
            title = ''
            coach_url = base_url
            
            # Try to find name link
            link = row.find('a')
            if link:
                name = FieldExtractors.clean_text(link.get_text())
                coach_url = self.build_player_url(team['url'], link.get('href', ''))
            else:
                name = FieldExtractors.clean_text(cells[0].get_text())
            
            # Extract title - look for coach keywords
            for cell in cells:
                cell_text = FieldExtractors.clean_text(cell.get_text())
                if any(keyword in cell_text.lower() for keyword in ['coach', 'director', 'coordinator']):
                    title = cell_text
                    break
            
            if not name or not title:
                return None
            
            # Map to Player object with coach data
            return Player(
                team=team['team'],
                team_id=str(team['ncaa_id']),
                season=season,
                name=name,
                jersey='',
                position=title,  # Map title to position
                height='',
                year='',
                hometown='',
                high_school='',
                previous_school='',
                url=coach_url
            )
        except Exception as e:
            logger.warning(f"Error extracting coach from row: {e}")
            return None

    def _parse_table(self, table) -> tuple:
        """Parse table headers and rows"""
        # Extract headers
        header_row = table.find('thead')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
        else:
            first_row = table.find('tr')
            headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

        # Clean headers - keep empty headers to maintain cell alignment
        unwanted = ['Social', 'Pronounciation', 'Pronouns']
        # Replace empty headers with placeholder to maintain alignment
        headers = [h if h else '_empty_' for h in headers]
        headers = [h for h in headers if h not in unwanted]

        # Extract rows
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]

        return headers, rows

    def _extract_table_player(self, row, headers: List[str], team: Dict, season: str) -> Optional[Player]:
        """Extract player data from table row"""
        all_cells = row.find_all(['td', 'th'])
        # Filter out hidden cells (responsive tables may have duplicate cells for mobile/desktop)
        cells = [cell for cell in all_cells if FieldExtractors.is_visible_cell(cell)]
        if len(cells) < len(headers):
            return None

        # Handle team-specific formats
        if team.get('ncaa_id') in [529, 31]:  # Oregon, Arkansas
            return self._extract_special_format(row, cells, team, season)
        
        return self._extract_standard_format(row, cells, headers, team, season)

    def _extract_special_format(self, row, cells, team: Dict, season: str) -> Optional[Player]:
        """Handle special table formats for specific teams"""
        team_id = team.get('ncaa_id')
        
        if team_id in [529, 31]:  # Oregon, Arkansas
            data = {
                'name': FieldExtractors.clean_text(cells[1].get_text()),
                'jersey': FieldExtractors.clean_text(cells[0].get_text()),
                'position': FieldExtractors.clean_text(cells[2].get_text()),
                'height': FieldExtractors.clean_text(cells[3].get_text()),
                'year': FieldExtractors.clean_text(cells[4].get_text()),
                'hometown': FieldExtractors.clean_text(cells[5].get_text()),
                'high_school': FieldExtractors.clean_text(cells[6].get_text()) if len(cells) > 6 else '',
                'previous_school': FieldExtractors.clean_text(cells[7].get_text()) if len(cells) > 7 else '',
            }
        else:
            return None
        
        # Extract URL
        link = row.find('a')
        player_url = self.build_player_url(team['url'], link.get('href', '')) if link else ""

        # Detect if height/year are reversed (some tables put year before height)
        if FieldExtractors.looks_like_academic_year(data.get('height', '')) and FieldExtractors.looks_like_height(data.get('year', '')):
            data['height'], data['year'] = data['year'], data['height']

        return Player(
            team_id=team['ncaa_id'], team=team['team'], name=data['name'],
            year=data['year'], hometown=data['hometown'], high_school=data['high_school'],
            previous_school=data['previous_school'], height=data['height'],
            position=data['position'], jersey=data['jersey'], url=player_url, season=season
        )

    def _extract_standard_format(self, row, cells, headers: List[str], team: Dict, season: str) -> Optional[Player]:
        """Extract from standard table format"""
        data = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                data[header] = FieldExtractors.clean_text(cells[i].get_text())

        # Handle hometown/high school splitting
        hometown_data = FieldExtractors.parse_hometown_school(data.get('town', ''))
        if not hometown_data['hometown']:
            hometown_data['hometown'] = data.get('hometown', '')
            hometown_data['high_school'] = data.get('high_school', '')

        link = row.find('a')
        player_url = self.build_player_url(team['url'], link.get('href', '')) if link else ""

        # Detect and fix swapped height vs academic_year (e.g., some tables have these columns reversed)
        height_raw = data.get('height', '')
        year_raw = data.get('academic_year', '')
        if FieldExtractors.looks_like_academic_year(height_raw) and FieldExtractors.looks_like_height(year_raw):
            # swap
            data['height'], data['academic_year'] = year_raw, height_raw

        return Player(
            team_id=team['ncaa_id'], team=team['team'], name=data.get('name', ''),
            year=FieldExtractors.normalize_academic_year(data.get('academic_year', '')),
            hometown=hometown_data['hometown'], high_school=hometown_data['high_school'],
            previous_school=hometown_data['previous_school'] or data.get('previous_school', ''),
            height=data.get('height', ''), position=data.get('position', ''),
            jersey=data.get('jersey', ''), url=player_url, season=season
        )


class JavaScriptScraper(BaseScraper):
    """Scraper using JavaScript execution for dynamic content"""
    
    def __init__(self, use_playwright: bool = False, entity_type: str = 'player'):
        super().__init__(entity_type=entity_type)
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE

    def scrape_roster(self, team: Dict, season: str, js_selector: str, url_format: str = "default", base_url: str = "") -> List[Player]:
        """Scrape roster using JavaScript with templates"""
        url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
        
        # Get JavaScript code from templates based on entity type
        if js_selector == 'nuxt_roster':
            if self.entity_type == 'coach':
                # Try coaching-staff section first, fallback to __NUXT_DATA__
                js_code = JSTemplates.coaching_staff_template()
                result = self._scrape_with_shot_scraper(url, js_code, team, season, base_url) if not self.use_playwright else self._scrape_with_playwright(url, js_code, team, season, base_url)
                
                # If no coaches found, try __NUXT_DATA__ approach
                if not result:
                    logger.info(f"No coaches found in #coaching-staff, trying __NUXT_DATA__ for {team['team']}")
                    js_code = JSTemplates.nuxt_data_coaches_template()
                else:
                    return result
            else:
                js_code = JSTemplates.nuxt_data_template()
        elif js_selector == 's_person_card':
            if self.entity_type == 'coach':
                js_code = JSTemplates.s_person_card_coaches_template()
            else:
                js_code = JSTemplates.s_person_card_template()
        else:
            # Handle custom selectors with coach support
            if self.entity_type == 'coach':
                # Try coach-specific version first
                coach_selector = f"{js_selector}_coaches"
                js_code = JSTemplates.get_custom_selector(team['ncaa_id'], coach_selector)
                if not js_code:
                    # Fall back to regular selector
                    logger.info(f"No coach-specific selector found for {js_selector}, trying regular selector")
                    js_code = JSTemplates.get_custom_selector(team['ncaa_id'], js_selector)
            else:
                js_code = JSTemplates.get_custom_selector(team['ncaa_id'], js_selector)
        
        if not js_code:
            logger.error(f"No JavaScript code found for selector: {js_selector}")
            return []
        
        # Replace season placeholder
        if '{{SEASON}}' in js_code:
            js_code = js_code.replace('{{SEASON}}', season)
        
        if self.use_playwright:
            return self._scrape_with_playwright(url, js_code, team, season, base_url)
        else:
            return self._scrape_with_shot_scraper(url, js_code, team, season, base_url)

    def _scrape_with_shot_scraper(self, url: str, js_code: str, team: Dict, season: str, base_url: str = "") -> List[Player]:
        """Scrape using shot-scraper"""
        try:
            cmd = ['uv', 'run', 'shot-scraper', 'javascript', url, js_code, '--user-agent', 'Firefox', '--bypass-csp']
            result = subprocess.check_output(cmd, timeout=120)
            data = json.loads(result.decode('utf-8'))
            
            return self._process_js_result(data, team, season, base_url)
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            logger.error(f"Shot-scraper failed for {url}: {e}")
            return []

    def _scrape_with_playwright(self, url: str, js_code: str, team: Dict, season: str, base_url: str = "") -> List[Player]:
        """Scrape using Playwright"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                page.wait_for_timeout(2000)
                
                result = page.evaluate(js_code)
                browser.close()
                
                return self._process_js_result(result, team, season, base_url)
        except Exception as e:
            logger.error(f"Playwright scraping failed for {url}: {e}")
            return []

    def _process_js_result(self, data: List[Dict], team: Dict, season: str, base_url: str = "") -> List[Player]:
        """Process JavaScript scraping result"""
        roster = []
        # Use team URL as fallback for base_url if not provided
        url_base = base_url if base_url else team['url']
        
        for entity_data in data:
            try:
                player_url = entity_data.get('url', '')
                # Convert relative URLs to absolute URLs
                if player_url and player_url.startswith('/'):
                    player_url = urljoin(url_base, player_url)
                
                # Pre-initialize and normalize any 'year' field so it's available
                # for both coach and player branches. Some JS sources put the
                # value in different properties; prefer 'year' when present.
                raw_year = entity_data.get('year', '')
                normalized_year = raw_year
                if raw_year:
                    try:
                        normalized = self._normalize_class_text(raw_year, season)
                        if normalized:
                            normalized_year = normalized
                    except Exception:
                        # Don't let normalization errors block processing; keep raw
                        normalized_year = raw_year

                # Handle coach data differently
                if self.entity_type == 'coach':
                    # Normalize any year value that looks like a graduation year (e.g., "'28")
                    raw_year = entity_data.get('year', '')
                    normalized_year = raw_year
                    if raw_year:
                        try:
                            normalized = self._normalize_class_text(raw_year, season)
                            if normalized:
                                normalized_year = normalized
                        except Exception:
                            normalized_year = raw_year

                    player = Player(
                        team_id=team['ncaa_id'],
                        team=team['team'],
                        player_id=entity_data.get('id'),
                        name=entity_data.get('name', ''),
                        year=entity_data.get('experience', ''),  # Map experience to year
                        hometown=entity_data.get('alma_mater', ''),  # Map alma_mater to hometown
                        high_school='',
                        previous_school='',
                        height='',
                        position=entity_data.get('title', ''),  # Map title to position
                        jersey='',
                        url=player_url,
                        season=season
                    )
                else:
                    # Player data
                    # Clean and extract position abbreviation from full text
                    position_text = entity_data.get('position', '')
                    position = FieldExtractors.extract_position(position_text) if position_text else ''
                    
                    player = Player(
                        team_id=team['ncaa_id'],
                        team=team['team'],
                        player_id=entity_data.get('id'),
                        name=entity_data.get('name', ''),
                        year=normalized_year,
                        hometown=entity_data.get('hometown', ''),
                        high_school=entity_data.get('high_school', ''),
                        previous_school=entity_data.get('previous_school', ''),
                        height=entity_data.get('height', ''),
                        position=position,
                        jersey=entity_data.get('jersey', ''),
                        url=player_url,
                        season=season
                    )
                roster.append(player)
            except Exception as e:
                logger.warning(f"Failed to process JS {self.entity_type} data: {e}")
                continue
        
        return roster


class VueDataScraper(BaseScraper):
    """Scraper for sites with roster data in a Vue.js data object."""

    def scrape_roster(self, team: Dict, season: str, url_format: str = "default") -> List[Player]:
        url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            html_text = response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return []

        # Regex to find the roster data object within the script tag
        match = re.search(r'roster:\s*({.*?}),\s*roster_settings:', html_text, re.DOTALL)
        if not match:
            logger.warning(f"Could not find Vue roster data for {team['team']}")
            return []

        json_str = match.group(1)
        
        try:
            roster_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {team['team']}: {e}")
            return []

        # Get players or coaches depending on entity type
        if self.entity_type == 'coach':
            entities_list = roster_data.get('coaches', [])
            entity_label = 'coaches'
        else:
            entities_list = roster_data.get('players', [])
            entity_label = 'players'

        if not entities_list:
            logger.warning(f"No {entity_label} found in the JSON data for {team['team']}")
            return []

        roster = []
        for p_data in entities_list:
            try:
                full_name = f"{p_data.get('first_name', '')} {p_data.get('last_name', '')}".strip()

                # Construct entity URL
                slug = re.sub(r'\s+', '-', full_name.lower()).strip()
                slug = re.sub(r'[^\w\-]+', '', slug)

                if self.entity_type == 'coach':
                    relative_url = f"/sports/womens-basketball/roster/coaches/{slug}/{p_data.get('rp_id')}"
                else:
                    relative_url = f"/sports/womens-basketball/roster/{slug}/{p_data.get('rp_id')}"

                player_url = self.build_player_url(team['url'], relative_url)

                if self.entity_type == 'coach':
                    # For coaches, map title to position field
                    player = Player(
                        team_id=team['ncaa_id'],
                        team=team['team'],
                        player_id=str(p_data.get('rp_id')),
                        name=full_name,
                        position=p_data.get('title', ''),  # Use title as position
                        url=player_url,
                        season=season
                    )
                else:
                    # For players, use full player data
                    height = ""
                    if p_data.get('height_feet') is not None and p_data.get('height_inches') is not None:
                        height = f"{p_data['height_feet']}'{p_data['height_inches']}\""

                    player = Player(
                        team_id=team['ncaa_id'],
                        team=team['team'],
                        player_id=str(p_data.get('rp_id')),
                        name=full_name,
                        year=FieldExtractors.normalize_academic_year(p_data.get('academic_year_short', '')),
                        hometown=p_data.get('hometown', ''),
                        high_school=p_data.get('highschool', ''),
                        previous_school=p_data.get('previous_school', '') or '',
                        height=height,
                        position=p_data.get('position_short', ''),
                        jersey=p_data.get('jersey_number', ''),
                        url=player_url,
                        season=season
                    )
                roster.append(player)
            except Exception as e:
                logger.warning(f"Failed to process player data for {team['team']}: {p_data.get('first_name')} - {e}")
                continue
        
        return roster


class ScraperFactory:
    """Factory for creating appropriate scrapers"""
    
    @classmethod
    def create_scraper(cls, scraper_type: str, entity_type: str = 'player', **kwargs) -> BaseScraper:
        """Create appropriate scraper based on type"""
        if scraper_type == "standard":
            return StandardScraper(entity_type=entity_type)
        elif scraper_type == "table":
            return TableScraper(entity_type=entity_type)
        elif scraper_type == "javascript":
            return JavaScriptScraper(entity_type=entity_type, use_playwright=kwargs.get('use_playwright', False))
        elif scraper_type == "vue_data":
            return VueDataScraper(entity_type=entity_type)
        else:
            return StandardScraper(entity_type=entity_type)
