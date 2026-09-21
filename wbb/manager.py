"""Roster scraping orchestration.

RosterManager moved verbatim from ncaa/rosters/rosters.py L3429-3712, with
additive orchestration hooks only: TeamOutcome / on_team callback /
team_results, use_playwright threading, and CSV delegation to wbb.csvio.
Scraping, URL, and verification logic is unchanged."""

import json
import logging
from collections import namedtuple
from typing import Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup

from wbb.models import Player
from wbb.parsing import SeasonVerifier
from wbb.config import ENTITY_CONFIGS, TeamConfig, URLBuilder, TEAMS_FILE
from wbb.scrapers import ScraperFactory
from wbb import csvio

logger = logging.getLogger(__name__)

TeamOutcome = namedtuple('TeamOutcome', ['team_id', 'team', 'n_players', 'status', 'error'])

class RosterManager:
    """Main class for managing roster scraping operations"""

    def __init__(self, teams_file: Optional[str] = None, entity_type: str = 'player',
                 use_playwright: bool = False, on_team=None):
        self.teams_file = str(teams_file) if teams_file else str(TEAMS_FILE)
        self.teams_data = self._load_teams()
        self.zero_player_teams = []
        self.failed_year_check_teams = []
        self.entity_type = entity_type
        self.use_playwright = use_playwright
        self.on_team = on_team
        self.team_results: List[TeamOutcome] = []
        self.last_scraped: List[Player] = []

    def _load_teams(self) -> List[Dict]:
        """Load teams data from JSON file"""
        try:
            with open(self.teams_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Teams file not found: {self.teams_file}")
            return []

    def get_teams(self, team_ids: Optional[List[int]] = None) -> List[Dict]:
        """Get teams to scrape"""
        teams_with_urls = [t for t in self.teams_data if "url" in t]
        
        if team_ids:
            teams_with_urls = [t for t in teams_with_urls if t['ncaa_id'] in team_ids]
        
        return teams_with_urls

    def scrape_team_roster(self, team: Dict, season: str) -> List[Player]:
        """Scrape roster for a single team, trying different URL formats if season verification fails"""
        config = TeamConfig.get_config(team['ncaa_id'])
        scraper = ScraperFactory.create_scraper(config['type'], entity_type=self.entity_type,
                                                use_playwright=self.use_playwright)

        logger.info(f"Scraping {team['team']} (ID: {team['ncaa_id']}) for {season}")
        logger.info(f"Using config: {config}")

        # Define URL formats to try if season verification fails
        url_formats_to_try = ['default', 'four_digit_year', 'year_only', 'season_first']
        initial_format = config.get('url_format', 'default')
        
        # Start with the configured format, then try others if verification fails
        if initial_format in url_formats_to_try:
            url_formats_to_try.remove(initial_format)
        url_formats_to_try.insert(0, initial_format)

        last_exception = None
        for url_format in url_formats_to_try:
            try:
                logger.info(f"Trying URL format: {url_format}")
                
                if config['type'] == 'javascript':
                    selector = config.get('selector', 'nuxt_roster')
                    base_url = config.get('base_url', '')
                    players = scraper.scrape_roster(team, season, selector, url_format, base_url)
                elif config['type'] == 'table':
                    players = scraper.scrape_roster(team, season, url_format)
                elif config['type'] == 'vue_data':
                    players = scraper.scrape_roster(team, season, url_format)
                else:
                    players = scraper.scrape_roster(team, season, url_format)
                
                # Verify the season on the page
                if self._verify_team_season_with_format(team, season, url_format):
                    logger.info(f"Season verification successful with URL format: {url_format}")
                    return players
                else:
                    logger.warning(f"Season verification failed with URL format: {url_format}, trying next format")
                    continue
                    
            except Exception as e:
                logger.warning(f"Failed with URL format {url_format}: {e}")
                last_exception = e
                continue
        
        # If all formats failed, raise the last exception
        if last_exception:
            logger.error(f"Failed to scrape {team['team']} with all URL formats: {last_exception}")
        return []

    def scrape_multiple_teams(self, season: str, team_ids: Optional[List[int]] = None) -> List[Player]:
        """Scrape rosters for multiple teams"""
        teams = self.get_teams(team_ids)
        all_players = []
        entity_label = ENTITY_CONFIGS[self.entity_type]['entity_label']

        for team in teams:
            try:
                players = self.scrape_team_roster(team, season)
                all_players.extend(players)

                # Check for year verification failure first
                year_check_failed = not self._verify_team_season(team, season)

                if year_check_failed:
                    self.failed_year_check_teams.append({
                        'team_id': team['ncaa_id'],
                        'team_name': team['team'],
                        'url': team['url']
                    })
                    logger.warning(f"Year verification failed for {team['team']} (ID: {team['ncaa_id']})")

                # Only add to zero players if year check passed but no players found
                if len(players) == 0:
                    if not year_check_failed:
                        self.zero_player_teams.append({
                            'team_id': team['ncaa_id'],
                            'team_name': team['team']
                        })
                        logger.warning(f"No {entity_label} scraped from {team['team']} (ID: {team['ncaa_id']})")
                        self._record_outcome(TeamOutcome(team['ncaa_id'], team['team'], 0, 'zero', None))
                    else:
                        logger.info(f"No {entity_label} scraped from {team['team']} but year check failed - not counting as zero {entity_label}")
                        self._record_outcome(TeamOutcome(team['ncaa_id'], team['team'], 0, 'failed_verification', None))
                else:
                    logger.info(f"Scraped {len(players)} {entity_label} from {team['team']}")
                    status = 'failed_verification' if year_check_failed else 'ok'
                    self._record_outcome(TeamOutcome(team['ncaa_id'], team['team'], len(players), status, None))

            except Exception as e:
                logger.error(f"Failed to scrape {team['team']}: {e}")
                # Only add to zero players, not year check failures
                self.zero_player_teams.append({
                    'team_id': team['ncaa_id'],
                    'team_name': team['team']
                })
                self._record_outcome(TeamOutcome(team['ncaa_id'], team['team'], 0, 'error', str(e)))
                continue

        return all_players

    def _record_outcome(self, outcome: TeamOutcome):
        """Record a per-team result and notify the on_team hook (additive)."""
        self.team_results.append(outcome)
        if self.on_team:
            try:
                self.on_team(outcome)
            except Exception as e:  # never let a progress callback break scraping
                logger.debug(f"on_team callback error: {e}")

    def save_to_csv(self, players: List[Player], output_file: str):
        """Save players to CSV file (delegates to wbb.csvio.write_entities)"""
        team_state_map = csvio.build_team_state_map(self.teams_data)
        csvio.write_entities(players, self.entity_type, output_file, team_state_map)

    def save_zero_player_teams_to_csv(self, output_file: str):
        """Save teams with zero scraped players to CSV file (delegates to wbb.csvio)"""
        csvio.write_zero_players(self.zero_player_teams, output_file)

    def _verify_team_season(self, team: Dict, season: str) -> bool:
        """Verify that the team's roster page shows the correct season"""

        try:
            # Get the team's config to use the correct URL format
            config = TeamConfig.get_config(team['ncaa_id'])
            url_format = config.get('url_format', 'default') if config else 'default'
            
            url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
            html, status = self.fetch_html(url, return_status=True)
            
            # If 404 and using default format, try season_first as fallback
            if not html and status == 404 and url_format == "default":
                logger.info(f"Got 404 during season verification for {team['team']}, trying season_first URL format as fallback")
                url = URLBuilder.build_url(team['url'], season, "season_first", entity_type=self.entity_type)
                logger.info(f"Trying fallback URL: {url}")
                html = self.fetch_html(url)
            
            if not html:
                return False
                
            # Only verify season for Sidearm sites
            if SeasonVerifier.is_sidearm_site(html):
                return SeasonVerifier.verify_season_on_page(html, season, entity_type=self.entity_type, team_id=team['ncaa_id'])
            
            return True  # Assume OK for non-Sidearm sites
        except Exception as e:
            logger.warning(f"Failed to verify season for {team['team']}: {e}")
            return True  # Default to True if verification fails

    def _verify_team_season_with_format(self, team: Dict, season: str, url_format: str) -> bool:
        """Verify that the team's roster page is for the correct season using a specific URL format"""
        try:
            url = URLBuilder.build_url(team['url'], season, url_format, entity_type=self.entity_type)
            html = self.fetch_html(url)
            
            if not html:
                return False
                
            # Only verify season for Sidearm sites
            if SeasonVerifier.is_sidearm_site(html):
                return SeasonVerifier.verify_season_on_page(html, season, entity_type=self.entity_type, team_id=team['ncaa_id'])
            
            return True  # Assume OK for non-Sidearm sites
        except Exception as e:
            logger.warning(f"Failed to verify season for {team['team']} with format {url_format}: {e}")
            return False

    def fetch_html(self, url: str, return_status: bool = False) -> Optional[Union[BeautifulSoup, tuple]]:
        """Fetch and parse HTML from URL
        
        Args:
            url: URL to fetch
            return_status: If True, return (html, status_code) tuple instead of just html
        
        Returns:
            BeautifulSoup object if return_status=False, or (BeautifulSoup, status_code) tuple if return_status=True
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=30, verify=False)
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

    def save_failed_year_check_teams_to_csv(self, output_file: str):
        """Save teams that failed the year check to CSV file (delegates to wbb.csvio)"""
        csvio.write_failed_year_check(self.failed_year_check_teams, output_file)
