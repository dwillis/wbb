import requests
import xml.etree.ElementTree as ET
import json

# URL from which to fetch the XML data
xml_url = 'https://stats.hawkeyesports.com/api/v1/game/xml/347901'

# Fetching the XML content from the URL
response = requests.get(xml_url)
xml_content_from_url = response.text

# Parse the XML content
root = ET.fromstring(xml_content_from_url)

# Updated data structures for game information
game_info_updated = {
    "players": [],
    "plays": []
}

# Extracting all attributes for players
for team in root.findall('.//team'):
    team_id = team.get('id')
    team_name = team.get('name')

    for player in team.findall('.//player'):
        player_attributes = player.attrib  # Get all attributes of the player element
        player_attributes['team_id'] = team_id
        player_attributes['team_name'] = team_name
        stats_element = player.find('.//stats')
        if stats_element is not None:
            player_attributes['statistics'] = stats_element.attrib
        else:
            player_attributes['statistics'] = {}
        game_info_updated["players"].append(player_attributes)

# Extracting all attributes for plays
for period in root.findall('.//period'):
    period_plays = []
    period_attributes = period.attrib  # Get all attributes of the period element

    for play in period.findall('.//play'):
        play_attributes = play.attrib  # Get all attributes of the play element
        period_plays.append(play_attributes)

    game_info_updated["plays"].append({
        "period_info": period_attributes,
        "plays": period_plays
    })

json_file_path = '347901.json'
with open(json_file_path, 'w') as json_file:
    json.dump(game_info_updated, json_file, indent=4)
