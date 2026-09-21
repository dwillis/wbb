"""wbb — NCAA women's basketball roster scraping toolkit.

Extracted from ncaa/rosters/rosters.py; all scraping logic moved verbatim.
"""
from wbb.models import Player
from wbb.config import ENTITY_CONFIGS, TeamConfig, URLBuilder
from wbb.scrapers import ScraperFactory
from wbb.manager import RosterManager

__version__ = "0.1.0"
__all__ = ["Player", "RosterManager", "TeamConfig", "ScraperFactory", "ENTITY_CONFIGS"]
