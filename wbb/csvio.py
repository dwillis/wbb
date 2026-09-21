"""CSV input/output for scraped entities.

Extracted from ncaa/rosters/rosters.py: the bodies of RosterManager.save_to_csv
(L3548-3599), save_zero_player_teams_to_csv (L3602-3617) and
save_failed_year_check_teams_to_csv (L3694-3711), plus the row normalization
they perform. RosterManager's save methods delegate here.
"""

import csv
import logging
from pathlib import Path

from wbb.parsing import FieldExtractors
from wbb.config import ENTITY_CONFIGS, TeamConfig

logger = logging.getLogger(__name__)


def build_team_state_map(teams_data):
    """Build team_id -> team_state mapping (from RosterManager.save_to_csv)."""
    return {team['ncaa_id']: team.get('team_state', '') for team in teams_data}


def normalize_row(player, entity_type, team_state_map=None):
    """Apply the save_to_csv field post-processing to one entity row.

    Returns the dict ready for CSV (and DB) output.
    """
    pdata = player.to_dict()
    pdata['name'] = FieldExtractors.clean_field_labels(pdata.get('name', ''))

    # For coaches, map position to title
    if entity_type == 'coach':
        pdata['title'] = pdata.get('position', '')
    else:
        # Only clean player-specific fields if we're saving players
        pdata['hometown'] = FieldExtractors.clean_field_labels(pdata.get('hometown', ''))
        pdata['high_school'] = FieldExtractors.clean_field_labels(pdata.get('high_school', ''))
        pdata['previous_school'] = FieldExtractors.clean_field_labels(pdata.get('previous_school', ''))
        pdata['academic_year'] = FieldExtractors.clean_field_labels(pdata.get('academic_year', ''))

        # Add state abbreviation to hometown if not already present (opt-in only)
        team_id = pdata.get('team_id')
        if team_state_map and team_id in TeamConfig.ADD_STATE_TO_HOMETOWN:
            hometown = pdata.get('hometown', '')
            if hometown and ',' not in hometown:
                # Hometown doesn't have state - add team's state abbreviation
                team_state = team_state_map.get(team_id)
                if team_state:
                    pdata['hometown'] = f"{hometown}, {team_state}"

    return pdata


def write_entities(players, entity_type, output_file, team_state_map=None):
    """Save entities to CSV file (body of RosterManager.save_to_csv)."""
    if not players:
        logger.warning("No players to save")
        return False

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # Use entity-specific fieldnames
    fieldnames = ENTITY_CONFIGS[entity_type]['output_fields']
    entity_label = ENTITY_CONFIGS[entity_type]['entity_label']

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for player in players:
            writer.writerow(normalize_row(player, entity_type, team_state_map))

    logger.info(f"Saved {len(players)} {entity_label} to {output_file}")
    return True


def write_zero_players(zero_teams, output_file):
    """Save teams with zero scraped players to CSV file (body of
    RosterManager.save_zero_player_teams_to_csv)."""
    if not zero_teams:
        logger.info("No teams with zero players to save")
        return False

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['team_id', 'team_name']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for team in zero_teams:
            writer.writerow(team)

    logger.info(f"Saved {len(zero_teams)} teams with zero players to {output_file}")
    return True


def write_failed_year_check(failed_teams, output_file):
    """Save teams that failed the year check to CSV file (body of
    RosterManager.save_failed_year_check_teams_to_csv)."""
    if not failed_teams:
        logger.info("No teams failed the year check")
        return False

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['team_id', 'team_name', 'url']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for team in failed_teams:
            writer.writerow(team)

    logger.info(f"Saved {len(failed_teams)} teams that failed year check to {output_file}")
    return True