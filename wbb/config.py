"""Scraping configuration: URL building, team-specific configs, entity schemas.

Moved verbatim from ncaa/rosters/rosters.py: URLBuilder (L1435-1505),
TeamConfig (L1506-2083), ENTITY_CONFIGS (L2084-2127)."""

from typing import Any, Dict, Union

class URLBuilder:
    """Builds roster URLs for different site formats"""
    
    @staticmethod
    def build_url(base_url: str, season: str, url_format: str = "default", entity_type: str = 'player') -> str:
        """Build roster URL based on site format and entity type"""
        if f"/{season}" in base_url or url_format == "direct_url":
            return base_url + f"/{season}"
        
        # Remove trailing slash from base_url to avoid double slashes
        base_url = base_url.rstrip('/')
        
        # Determine path based on entity type
        path = "coaches" if entity_type == 'coach' else "roster"
        
        # For next year format: 2024-25 season -> 2025-26 URL
        next_year = str(int(season[:4]) + 1)
        next_year_short = str(int(season[-2:]) + 1).zfill(2)
        next_year_season = f"{next_year}-{next_year_short}"

        formats = {
            "default": f"{base_url}/{path}/{season}",
            "direct": f"{base_url}/{path}/",
            "season_first": f"{base_url}/{season}/{path}",
            "season_first_table": f"{base_url}/{season}/{path}?view=list",
            "season_path": f"{base_url}/{path}/season/{season}/",
            "season_path_table": f"{base_url}/{path}/season/{season}?view=table",
            "clemson": f"{base_url}/{path}/season/{season[:4]}",
            "iowa_table": f"{base_url}/{path}/season/{season}?view=table",
            "valpo": f"{base_url}/{path}/{season}/?view=list",
            "la_salle": f"{base_url}/{path}/{season}",
            "byu_table": f"{base_url}/{path}/season/{season[:4]}-{season[:2]}{season[-2:]}?view=table",
            "four_digit_year": f"{base_url}/{path}/{season[:4]}-{season[:2]}{season[-2:]}",
            "year_only": f"{base_url}/{path}/{season[:4]}",
            "next_year": f"{base_url}/{path}/{next_year_season}"
        }

        # Special cases
        if base_url.startswith('https://arkansasrazorbacks.com'):
            path_param = "w-baskbl/coaches" if entity_type == 'coach' else "w-baskbl/roster"
            return f"https://arkansasrazorbacks.com/sport/{path_param}/?season={season}"

        if base_url.startswith('https://goaztecs.com'):
            return f"https://goaztecs.com/sports/womens-basketball/{path}/season/{season}?view=table"

        # Miami uses roster path for both coaches and players
        if base_url.startswith('https://miamihurricanes.com'):
            return f"{base_url}/roster/season/{season}/"

        # Iowa uses wbball sport path with roster and view parameter
        if base_url.startswith('https://hawkeyesports.com'):
            if entity_type == 'coach':
                return f"{base_url}/roster/season/{season}?tab=coaches"
            else:
                # Iowa uses /wbball/ in the path, ensure it's included
                if '/wbball' in base_url:
                    return f"{base_url}/roster/season/{season}?view=table"
                else:
                    return f"{base_url.rstrip('/')}/sports/wbball/roster/season/{season}?view=table"

        # George Mason and Miami Ohio use roster path for both coaches and players
        if base_url.startswith('https://gomason.com') or base_url.startswith('https://miamiredhawks.com'):
            return f"{base_url}/roster/{season}"

        # Hawaii uses four-digit year format (2025-26 becomes 2025-2026)
        if base_url.startswith('https://hawaiiathletics.com'):
            return f"{base_url}/{path}/{season[:4]}-{season[:2]}{season[-2:]}"

        return formats.get(url_format, formats["default"])


class TeamConfig:
    """Simplified configuration for team-specific scraping"""
    
    # Teams using Nuxt.js data extraction (50+ teams)
    # Most use default URL format, but some need special handling (stored as dict with 'base_url' and 'url_format')
    NUXT_JS_TEAMS = {
        71: 'https://bgsufalcons.com', 83: 'https://gobison.com', 96: 'https://gobulldogs.com',
        99: 'https://longbeachstate.com',
        # 128: Central Florida - moved to CUSTOM_JS_TEAMS (uses sidearm-roster-player with Nuxt.js)
        164: 'https://uconnhuskies.com',
        176: 'https://depaulbluedemons.com', 180: 'https://bluehens.com', 191: 'https://drexeldragons.com',
        204: 'https://emueagles.com', 229: 'https://fausports.com', 234: 'https://seminoles.com',
        367: 'https://gocards.com', 418: 'https://mgoblue.com', 428: 'https://gophersports.com',
        458: 'https://charlotte49ers.com', 716: 'https://troytrojans.com', 718: 'https://tulanegreenwave.com',
        700: 'https://texastech.com', 355: 'https://libertyflames.com', 497: 'https://meangreensports.com',
        441: 'https://gogriz.com', 416: 'https://msuspartans.com', 509: 'https://nusports.com',
        522: 'https://soonersports.com', 454: 'https://goracers.com',
        404: 'https://gotigersgo.com', 671: 'https://ragincajuns.com',
        574: 'https://riceowls.com', 664: 'https://southernmiss.com', 575: 'https://richmondspiders.com',
        698: 'https://gofrogs.com', 288: 'https://uhcougars.com', 400: 'https://umassathletics.com',
        457: 'https://goheels.com', 156: 'https://csurams.com', 196: 'https://ecupirates.com',
        725: 'https://goarmywestpoint.com', 9: 'https://uabsports.com', 502: 'https://uncbears.com',
        456: 'https://uncabulldogs.com', 469: 'https://unhwildcats.com', 504: 'https://unipanthers.com',
        758: 'https://weberstatesports.com', 490: 'https://gopack.com', 690: 'https://owlsports.com',
        732: 'https://utahutes.com', 749: 'https://godeacs.com',
        1104: 'https://gculopes.com', 719: 'https://tulsahurricane.com', 772: 'https://wkusports.com',
        328: 'https://kuathletics.com', 635: 'https://shupirates.com', 86: 'https://ubbulls.com',
        694: 'https://utsports.com', 387: 'https://gomarquette.com', 545: 'https://pittsburghpanthers.com',
        721: 'https://goairforcefalcons.com', 51: 'https://baylorbears.com',
        419: 'https://goblueraiders.com', 688: 'https://cuse.com', 311: 'https://cyclones.com',
        129: 'https://cmuchippewas.com', 8: 'https://rolltide.com', 193: 'https://goduke.com', 649: 'https://gojacks.com',
        249: 'https://gwsports.com', 430: 'https://hailstate.com', 80: 'https://brownbears.com',
        257: 'https://georgiadogs.com', 317: 'https://jmusports.com', 66: 'https://broncosports.com',
        562: 'https://gobobcats.com', 659: 'https://siusalukis.com', 756: 'https://gohuskies.com',
        173: 'https://davidsonwildcats.com', 518: 'https://ohiostatebuckeyes.com',
        47: 'https://ballstatesports.com', 529: 'https://goducks.com', 676: 'https://sfajacks.com',
        30135: 'https://cbulancers.com', 414: 'https://miamiredhawks.com',
        434: 'https://mutigers.com', 440: 'https://msubobcats.com', 703: 'https://texassports.com',
        796: 'https://uwbadgers.com',  # Wisconsin - Nuxt.js with embedded JSON data
    }
    
    # Teams using .s-person-card structure
    S_PERSON_CARD_TEAMS = [67, 169, 157, 603]  # Boston College, Creighton, Colorado, St. John's
    
    # Table-based teams
    TABLE_BASED_TEAMS = {
        5: {'url_format': 'default'},
        32: {'url_format': 'season_path_table'},  # Arkansas-Little Rock - /roster/season/{season}?view=table
        110: {'url_format': 'season_path_table'},  # UCLA - /roster/season/{season}?view=table
        697: {'url_format': 'season_path_table'},  # Texas A&M - /roster/season/{season}?view=table
        26: {'url_format': 'season_first'},
        28: {'url_format': 'iowa_table'},
        31: {'url_format': 'default'},  # Arkansas
        37: {'url_format': 'iowa_table'},
        64: {'url_format': 'season_first'},
        76: {'url_format': 'season_first'},
        77: {'url_format': 'byu_table'},
        119: {'url_format': 'season_first'},
        125: {'url_format': 'season_first'},  # Centenary (LA) - PrestoSports table
        127: {'url_format': 'default'},
        128: {'url_format': 'season_path_table'},  # Central Florida - uses ?view=table
        140: {'url_format': 'iowa_table'},
        147: {'url_format': 'clemson'},
        161: {'url_format': 'season_first'},
        170: {'url_format': 'season_first'},
        186: {'url_format': 'season_first'},
        216: {'url_format': 'season_first'},
        218: {'url_format': 'season_first'},
        238: {'url_format': 'season_first'},
        255: {'url_format': 'season_path'},
        306: {'url_format': 'default'},  # Indiana - uses /roster/2024-25
        308: {'url_format': 'default'},
        312: {'url_format': 'iowa_table'},  # Iowa
        324: {'url_format': 'season_first'},
        334: {'url_format': 'season_path'},
        388: {'url_format': 'default'},
        433: {'url_format': 'default'},
        463: {'url_format': 'iowa_table'},
        473: {'url_format': 'season_path_table'},  # New Mexico - uses ?view=table
        513: {'url_format': 'season_path'},
        523: {'url_format': 'iowa_table'},
        539: {'url_format': 'iowa_table'},
        554: {'url_format': 'default'},
        556: {'url_format': 'default'},
        559: {'url_format': 'iowa_table'},
        626: {'url_format': 'default'},  # San Diego State
        657: {'url_format': 'default'},
        695: {'url_format': 'default'},
        736: {'url_format': 'season_path'},
        742: {'url_format': 'iowa_table'},
        777: {'url_format': 'season_first'},
        812: {'url_format': 'default'},
        674: {'url_format': 'iowa_table'},
        630: {'url_format': 'iowa_table'},
        706: {'url_format': 'iowa_table'},
        365: {'url_format': 'season_path'},
        692: {'url_format': 'season_first'},
        648: {'url_format': 'season_path'},
        127: {'url_format': 'season_first'},
        987: {'url_format': 'season_first'},
        1000: {'url_format': 'season_first'},
        1023: {'url_format': 'season_first'},  # Coker - /sports/wbkb/2025-26/roster
        1050: {'url_format': 'season_first'},
        1130: {'url_format': 'season_first'},
        1163: {'url_format': 'season_first'},
        1199: {'url_format': 'season_first'},
        1348: {'url_format': 'season_first'},
        1355: {'url_format': 'season_first'},
        1356: {'url_format': 'season_path_table'},  # Seattle U - uses ?view=table
        1460: {'url_format': 'season_first'},
        1467: {'url_format': 'season_first_table'},
        689: {'url_format': 'season_first'},  # Tampa - /sports/wbkb/2025-26/roster
        11036: {'url_format': 'season_first'},
        12830: {'url_format': 'season_first'},
        224: {'url_format': 'season_first'},
        227: {'url_format': 'season_first'},
        24317: {'url_format': 'season_first'},
        25719: {'url_format': 'season_first'},
        26107: {'url_format': 'season_first'},
        2798: {'url_format': 'season_first'},
        28594: {'url_format': 'season_first'},
        30042: {'url_format': 'season_first'},
        443: {'url_format': 'season_first'},
        30225: {'url_format': 'season_first'},
        325: {'url_format': 'season_first'},
        1315: {'url_format': 'season_first'},
        449: {'url_format': 'season_first'},
        455: {'url_format': 'season_first'},
        486: {'url_format': 'season_first'},
        510: {'url_format': 'season_first'},
        517: {'url_format': 'season_first'},
        525: {'url_format': 'season_first'},
        532: {'url_format': 'season_first'},
        538: {'url_format': 'season_first'},
        544: {'url_format': 'season_first'},
        569: {'url_format': 'season_first'},
        591: {'url_format': 'season_first'},
        641: {'url_format': 'season_first'},
        684: {'url_format': 'season_first'},
        74: {'url_format': 'season_first'},
        762: {'url_format': 'season_first'},
        785: {'url_format': 'season_first'},
        806: {'url_format': 'season_first'},
        809: {'url_format': 'season_first'},
        8981: {'url_format': 'season_first'},
        939: {'url_format': 'season_first'},
        953: {'url_format': 'season_first'},
        621: {'url_format': 'season_first'},
        8486: {'url_format': 'season_first'},
        8687: {'url_format': 'season_first'},
        8956: {'url_format': 'season_first'},
        30033: {'url_format': 'season_first'},
        30189: {'url_format': 'season_first'},
        11538: {'url_format': 'season_first'},  # Fontbonne - PrestoSports with DataTables

    }
    
    # PrestoSports teams with season_first URL format but standard card layout (not tables)
    PRESTOSPORTS_SEASON_FIRST = {
        30253: {
            'url_format': 'season_first',
            'player_selector': '.player-card-wrapper',  # Carlow - uses flipcard layout with data in .card-back
            'flipcard_format': True,  # Indicates data is in .card-back with label: value format
        },
    }
    
    # Teams that should have state abbreviation added to hometowns without state
    # Only hometowns without a comma will have ", STATE" appended (using team's team_state field)
    ADD_STATE_TO_HOMETOWN = {
        46,   # Baldwin Wallace - Ohio hometowns need ", OH" added
        98,   # Cal St. East Bay - California hometowns need ", CA" added
        100,  # Cal St. LA - California hometowns need ", CA" added
        168,  # Cortland - New York hometowns need ", NY" added
        200,  # Eastern Conn. St. - Connecticut hometowns need ", CT" added
        452,  # Mount Union - Ohio hometowns need ", OH" added
        455,  # Muskingum - Ohio hometowns need ", OH" added
        517,  # Ohio Northern - Ohio hometowns need ", OH" added
        525,  # Olivet - Michigan hometowns need ", MI" added
        531,  # Otterbein - Ohio hometowns need ", OH" added
        795,  # Wisconsin-La Crosse - Wisconsin hometowns need ", WI" added
        798,  # Wis.-Oshkosh - Wisconsin hometowns need ", WI" added
    }
    
    # Custom JavaScript teams
    CUSTOM_JS_TEAMS = {
        # 128: Central Florida - moved to TABLE_BASED_TEAMS (has ?view=table parameter)
        178: {'selector': 'sidearm_roster_player', 'url_format': 'default'},  # Delaware State - uses standard sidearm with Vue.js
        248: {'selector': 'wyoming_roster', 'url_format': 'default'},  # George Mason - uses roster-staff structure
        327: {'selector': 'nuxt_roster', 'url_format': 'default'},  # Kansas State
        414: {'selector': 'wyoming_roster', 'url_format': 'default'},  # Miami Ohio - uses roster-staff structure
        415: {'selector': 'miami_table_roster', 'url_format': 'season_path'},  # Miami - uses DataTable with full player data
        528: {'selector': 'oregon_state_roster', 'url_format': 'default'},
        129: {'selector': 'central_michigan_roster', 'url_format': 'default'},
        485: {'type': 'standard', 'url_format': 'four_digit_year'},  # Norfolk State - uses standard Sidearm with /roster/2024-2025
        670: {'type': 'standard', 'url_format': 'four_digit_year'},  # Texas State - uses standard Sidearm with /roster/2024-2025
        746: {'type': 'javascript', 'selector': 'virginia_roster_table', 'url_format': 'direct'},
        16: {'type': 'standard', 'url_format': 'four_digit_year'},  # Albright - uses standard Sidearm with /roster/2024-2025
        1013: {'type': 'standard', 'url_format': 'four_digit_year'},  # Charleston (WV) - uses standard Sidearm with /roster/2024-2025
        130: {'type': 'standard', 'url_format': 'four_digit_year'},  # Central Mo. - uses standard Sidearm with /roster/2024-2025
        16142: {'type': 'standard', 'url_format': 'four_digit_year'},  # Misericordia - uses standard Sidearm with /roster/2024-2025
        139: {'type': 'standard', 'url_format': 'four_digit_year'},  # Chris. Newport - uses standard Sidearm with /roster/2024-2025
        144: {'type': 'standard', 'url_format': 'year_only'},  # Clark Atlanta - uses standard Sidearm with /roster/2024
        209: {'type': 'standard', 'url_format': 'four_digit_year'},  # Edinboro - uses standard Sidearm with /roster/2024-2025
        211: {'type': 'standard', 'url_format': 'four_digit_year'},  # Elizabethtown - uses standard Sidearm with /roster/2024-2025
        154: {'type': 'standard', 'url_format': 'four_digit_year'},  # Colorado Col. - uses standard Sidearm with /roster/2024-2025
        1203: {'type': 'standard', 'url_format': 'four_digit_year'},  # Mary Hardin-Baylor - uses standard Sidearm with /roster/2024-2025
        21323: {'type': 'standard', 'url_format': 'four_digit_year'},  # Chestnut Hill - uses standard Sidearm with /roster/2024-2025
        21830: {'type': 'standard', 'url_format': 'four_digit_year'},  # Piedmont - uses standard Sidearm with /roster/2024-2025
        1254: {'type': 'standard', 'url_format': 'four_digit_year'},  # Neumann - uses standard Sidearm with /roster/2024-2025
        1390: {'type': 'standard', 'url_format': 'year_only'},  # Sul Ross St. - uses standard Sidearm with /roster/2024
        2699: {'type': 'standard', 'url_format': 'four_digit_year'},  # IUPUI - uses standard Sidearm with /roster/2024-2025
        2741: {'type': 'standard', 'url_format': 'four_digit_year'},  # Howard Payne - uses standard Sidearm with /roster/2024-2025
        1305: {'type': 'standard', 'url_format': 'four_digit_year'},  # Cairn - uses standard Sidearm with /roster/2024-2025
        1376: {'type': 'standard', 'url_format': 'four_digit_year'},  # Southern Ark. - uses standard Sidearm with /roster/2024-2025
        30013: {'type': 'standard', 'url_format': 'four_digit_year'},  # Lee - uses standard Sidearm with /roster/2024-2025
        30047: {'type': 'standard', 'url_format': 'four_digit_year'},  # Keystone - uses standard Sidearm with /roster/2024-2025
        442: {'type': 'standard', 'url_format': 'four_digit_year'},  # Montclair St. - uses standard Sidearm with /roster/2024-2025
        1445: {'type': 'standard', 'url_format': 'four_digit_year'},  # Western N.M. - uses standard Sidearm with /roster/2024-2025
        120: {'type': 'standard', 'url_format': 'four_digit_year'},  # Chatham - uses standard Sidearm with /roster/2024-2025
        30120: {'type': 'standard', 'url_format': 'four_digit_year'},  # William Jewell - uses standard Sidearm with /roster/2024-2025
        30140: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ursuline - uses standard Sidearm with /roster/2024-2025
        30147: {'type': 'standard', 'url_format': 'four_digit_year'},  # Fresno Pacific - uses standard Sidearm with /roster/2024-2025
        30151: {'type': 'standard', 'url_format': 'four_digit_year'},  # Shorter - uses standard Sidearm with /roster/2024-2025
        30160: {'type': 'standard', 'url_format': 'four_digit_year'},  # Houghton - uses standard Sidearm with /roster/2024-2025
        11403: {'type': 'standard', 'url_format': 'four_digit_year'},  # Colo. Christian - uses standard Sidearm with /roster/2024-2025
        11504: {'type': 'standard', 'url_format': 'four_digit_year'},  # Queens (NC) - uses standard Sidearm with /roster/2024-2025
        11839: {'type': 'standard', 'url_format': 'four_digit_year'},  # Pitt.-Greensburg - uses standard Sidearm with /roster/2024-2025
        12799: {'type': 'standard', 'url_format': 'four_digit_year'},  # Wheeling - uses standard Sidearm with /roster/2024-2025
        323: {'type': 'standard', 'url_format': 'four_digit_year'},  # Johnson C. Smith - uses standard Sidearm with /roster/2024-2025
        330: {'type': 'standard', 'url_format': 'four_digit_year'},  # Keene St. - uses standard Sidearm with /roster/2024-2025
        332: {'type': 'standard', 'url_format': 'four_digit_year'},  # Kentucky St. - uses standard Sidearm with /roster/2024-2025
        339: {'type': 'standard', 'url_format': 'four_digit_year'},  # Kutztown - uses standard Sidearm with /roster/2024-2025
        42: {'type': 'standard', 'url_format': 'four_digit_year'},  # Aurora - uses standard Sidearm with /roster/2024-2025
        423: {'type': 'standard', 'url_format': 'four_digit_year'},  # Millersville - uses standard Sidearm with /roster/2024-2025
        432: {'type': 'standard', 'url_format': 'four_digit_year'},  # MVSU - uses standard Sidearm with /roster/2024-2025
        546: {'type': 'standard', 'url_format': 'four_digit_year'},  # Pitt-Johnstown - uses standard Sidearm with /roster/2024-2025
        564: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        612: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        661: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        675: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        696: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        780: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        784: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        787: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        8875: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        929: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        30166: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        1332: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        8366: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        30150: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        347: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        359: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        437: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        492: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        555: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        1099: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        8600: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        403: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        12399: {'type': 'standard', 'url_format': 'four_digit_year'},  # Ramapo - uses standard Sidearm with /roster/2024-2025
        1255: {'type': 'standard', 'url_format': 'four_digit_year'},
        733: {'type': 'standard', 'url_format': 'four_digit_year'},
        475: {'type': 'standard', 'url_format': 'four_digit_year'},
        625: {'type': 'javascript', 'selector': 's_person_card', 'url_format': 'default'},  # Samford - uses /roster/2026-27
        2678: {'type': 'standard', 'url_format': 'year_only'},  # Arkansas-Pine Bluff - uses /roster/2022
        1072: {'type': 'standard', 'url_format': 'four_digit_year'},  # Erskine - uses /roster/2022-2023
        1079: {'type': 'standard', 'url_format': 'year_only'},  # Findlay - uses /roster/2022
        15882: {'type': 'standard', 'url_format': 'four_digit_year'},
        30123: {'type': 'standard', 'url_format': 'four_digit_year'},
        811: {'selector': 'wyoming_roster', 'url_format': 'default'}  # Wyoming - uses Vue.js with sidearm-roster-list-item
    }

    # Teams with roster data embedded in a Vue.js data object
    VUE_DATA_TEAMS = {
        406: {  # Mercer - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        90: {  # Cal Poly - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        172: {  # Dartmouth - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        610: {  # Saint Mary's (CA) - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        331: {  # Kent State - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        2711: {  # North Florida - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        101: {  # CSUN - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        235: {  # Florida - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        2707: {  # Kansas City - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        598: {  # St. Cloud St. - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        620: {  # St. Thomas (MN) - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        587: {  # Rutgers - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        253: {  # Georgia Southern - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        810: {  # Wright St. - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        709: {  # Toledo - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        158: {  # Columbia - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        1014: {  # College of Charleston - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        68: {  # Boston University - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        768: {  # West Virginia - uses Vue.js/Nuxt with modern data attributes
            'type': 'standard',  # Use standard scraper with shot-scraper rendering
            'url_format': 'default',
            'field_selectors': {
                'position': ['[data-test-id="s-person-details__bio-stats-person-position-short"]'],
                'height': ['[data-test-id="s-person-details__bio-stats-person-season"]'],
                'academic_year': ['[data-test-id="s-person-details__bio-stats-person-title"]'],
                'hometown': ['[data-test-id="s-person-card-list__content-location-person-hometown"]'],
                'high_school': ['[data-test-id="s-person-card-list__content-location-person-high-school"]']
            }
        },
        # 415: Miami moved back to CUSTOM_JS_TEAMS - uses DataTable with full data
        # 811: {'url_format': 'default'}, # Wyoming - moved to NUXT_JS_TEAMS
        # 248: {'url_format': 'default'}, # George Mason - uses standard sidearm-roster-staff structure
        72: {'url_format': 'default'},
        731: {'url_format': 'default'},
        # 277: Hawaii - uses standard Sidearm scraper, URL format handled in URLBuilder
    }

    @classmethod
    def get_config(cls, team_id: int) -> Dict[str, Any]:
        """Get configuration for team"""

        # PrestoSports teams with season_first URL but standard layout
        if team_id in cls.PRESTOSPORTS_SEASON_FIRST:
            return {
                'type': 'standard',
                **cls.PRESTOSPORTS_SEASON_FIRST[team_id]
            }

        # Nuxt.js teams (most common)
        if team_id in cls.NUXT_JS_TEAMS:
            team_config = cls.NUXT_JS_TEAMS[team_id]
            # Handle dict format for teams with special URL formats
            if isinstance(team_config, dict):
                return {
                    'type': 'javascript',
                    'selector': 'nuxt_roster',
                    'url_format': team_config.get('url_format', 'default'),
                    'base_url': team_config.get('base_url', '')
                }
            # Handle string format (just base_url, use default URL format)
            return {
                'type': 'javascript',
                'selector': 'nuxt_roster',
                'url_format': 'default',
                'base_url': team_config  # The string IS the base_url
            }
        
        # S-person-card teams
        if team_id in cls.S_PERSON_CARD_TEAMS:
            return {
                'type': 'javascript',
                'selector': 's_person_card',
                'url_format': 'default'
            }
        
        # Table-based teams
        if team_id in cls.TABLE_BASED_TEAMS:
            return {
                'type': 'table',
                **cls.TABLE_BASED_TEAMS[team_id]
            }
        
        # Custom JavaScript teams
        if team_id in cls.CUSTOM_JS_TEAMS:
            return {
                'type': 'javascript',
                **cls.CUSTOM_JS_TEAMS[team_id]
            }
        
        # Vue data teams
        if team_id in cls.VUE_DATA_TEAMS:
            return {
                'type': 'vue_data',
                **cls.VUE_DATA_TEAMS[team_id]
            }
        
        if team_id in [340]:
            return {
                'type': 'standard',
                'url_format': 'la_salle'
            }
        
        if team_id in [77]:
            return {
                'type': 'table',
                'url_format': 'byu_table'
            }

        if team_id in [352]:
            return {
                'type': 'javascript',
                'url_format': 'four_digit_year'
            }

        if team_id in [521]:
            return {
                'type': 'javascript',
                'selector': 's_person_card',
                'url_format': 'year_only'
            }

        # Default fallback
        return {'type': 'standard', 'url_format': 'default'}


# Entity-specific configurations for players and coaches
ENTITY_CONFIGS = {
    'player': {
        'sidearm_selectors': [
            '.sidearm-roster-player',
            '.sidearm-roster-list-item',
            '.s-person-card',  # Used by some teams
            '.player-card'  # PrestoSports card layout
        ],
        'sidearm_container': '.sidearm-roster-players',
        'field_selectors': {
            'name': ['.sidearm-roster-player-name', 'h3 a', '.sidearm-roster-player-name-link', '.name'],  # .name for PrestoSports
            'jersey': ['.sidearm-roster-player-jersey-number', '.sidearm-roster-player-jersey'],
            'position': ['.sidearm-roster-player-position', '.position'],  # .position for PrestoSports
            'height': ['.sidearm-roster-player-height', '.height'],  # .height for PrestoSports
            'academic_year': ['.sidearm-roster-player-academic-year', '.sidearm-roster-player-academic-year-long', '.year'],  # .year for PrestoSports
            'hometown': ['.sidearm-roster-player-hometown', '.hometown'],  # .hometown for PrestoSports
            'high_school': ['.sidearm-roster-player-highschool', '.sidearm-roster-player-high-school', '.high-school']  # .high-school for PrestoSports
        },
        'output_fields': ['team', 'team_id', 'season', 'jersey', 'name', 'position', 
                         'height', 'academic_year', 'hometown', 'high_school', 'previous_school', 'url'],
        'csv_prefix': 'rosters',
        'entity_label': 'players'
    },
    'coach': {
        'sidearm_selectors': [
            '.sidearm-roster-coach',
            '.sidearm-roster-coaches-card',
            '.sidearm-roster-staff-item',  # Wyoming uses this structure
            '.s-person-card--list',  # Newer Sidearm design (e.g., Baylor)
            '.s-person-card'  # Some sites reuse player cards for staff listings
        ],
        'sidearm_container': '.sidearm-roster-coaches',
        'field_selectors': {
            'name': ['.sidearm-roster-coach-name', '.sidearm-roster-staff-name', '.s-person-details__personal-single-line', 'h3', 'h4', 'strong a', 'a'],
            'title': ['.sidearm-roster-coach-title', '.sidearm-roster-staff-title', '.sidearm-roster-coach-position', '.s-person-details__position', '.title'],
            'experience': ['.sidearm-roster-coach-seasons', '.sidearm-roster-coach-experience'],
            'alma_mater': ['.sidearm-roster-coach-college', '.sidearm-roster-coach-alma-mater']
        },
        'output_fields': ['team_id', 'team', 'name', 'title', 'url', 'season'],
        'csv_prefix': 'coaches',
        'entity_label': 'coaches'
    }
}


# ---------------------------------------------------------------------------
# Default path resolution (replaces hardcoded absolute paths in old main() /
# RosterManager). Repo-relative so the package works from any cwd under uv.
# ---------------------------------------------------------------------------
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "ncaa" / "rosters"
TEAMS_FILE = REPO_ROOT / "ncaa" / "teams" / "teams.json"
DB_PATH = REPO_ROOT / "ncaa" / "rosters" / "rosters.db"


def resolve_output_dir(out_dir=None):
    """Resolve the CSV output directory: --out-dir flag, $WBB_OUTPUT_DIR, or ncaa/rosters."""
    return Path(out_dir or os.environ.get("WBB_OUTPUT_DIR") or OUTPUT_DIR)
