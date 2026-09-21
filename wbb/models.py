"""Player data model — moved verbatim from ncaa/rosters/rosters.py L46-70."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

@dataclass
class Player:
    """Player data structure"""
    team_id: int
    team: str
    player_id: Optional[str] = None
    name: str = ""
    year: str = ""
    hometown: str = ""
    high_school: str = ""
    previous_school: str = ""
    height: str = ""
    position: str = ""
    jersey: str = ""
    url: str = ""
    season: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV output"""
        d = asdict(self)
        # Map 'year' field to 'academic_year' for CSV output
        d['academic_year'] = d.pop('year', '')
        return d
