"""Text/HTML field extraction, header mapping, and season verification.

Moved verbatim from ncaa/rosters/rosters.py: FieldExtractors (L71-309),
SeasonVerifier (L310-422), HeaderMapper (L1392-1434)."""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

class FieldExtractors:
    """Common utilities for extracting player fields from text and HTML"""
    
    @staticmethod
    def extract_jersey_number(text: str) -> str:
        """Extract jersey number from various text patterns"""
        patterns = [
            r'Jersey Number (\d+)',
            r'#(\d{1,2})\b',
            r'\b(\d{1,2})\s+(?=\w)',  # Number followed by name
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ''
    
    @staticmethod
    def extract_height(text: str) -> str:
        """Extract height from various formats"""
        patterns = [
            r"(\d+'\s*\d+\")",     # 6'2"
            r"(\d+[′']\s*\d+[″\"])", # Unicode quotes
            r"Height:\s*([^,\n]+)", # Height: label format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ''
    
    @staticmethod
    def extract_position(text: str) -> str:
        """Extract position from text"""
        # Look for position patterns - including two-letter positions (PG, SG, SF, PF, CG)
        # Also supports non-traditional positions like S (Shooter), BP (Ball Player), etc.
        # Matches: Common position codes (1-2 uppercase letters) and combinations
        position_match = re.search(r'\b([A-Z]{1,2}(?:/[A-Z]{1,2})?)\b', text)
        if position_match:
            # Return any valid 1-2 letter position code
            return position_match.group(1)
        
        # Look for full position names
        text_upper = text.upper()
        if 'GUARD' in text_upper:
            return 'G'
        elif 'FORWARD' in text_upper:
            return 'F' 
        elif 'CENTER' in text_upper:
            return 'C'
        
        return ''
    
    @staticmethod
    def normalize_academic_year(year_text: str) -> str:
        """Normalize academic year abbreviations to full forms"""
        if not year_text:
            return ''
        
        year_map = {
            'Fr': 'Freshman', 'Fr.': 'Freshman',
            'So': 'Sophomore', 'So.': 'Sophomore', 
            'Jr': 'Junior', 'Jr.': 'Junior',
            'Sr': 'Senior', 'Sr.': 'Senior',
            'Gr': 'Graduate', 'Gr.': 'Graduate Student',
            'R-Fr': 'Redshirt Freshman', 'R-Fr.': 'Redshirt Freshman',
            'Rf': 'Redshirt Freshman', 'Rf.': 'Redshirt Freshman',
            'R-So': 'Redshirt Sophomore', 'R-So.': 'Redshirt Sophomore',
            'R-Jr': 'Redshirt Junior', 'R-Jr.': 'Redshirt Junior',
            'R-Sr': 'Redshirt Senior', 'R-Sr.': 'Redshirt Senior'
        }
        
        cleaned = year_text.strip()
        return year_map.get(cleaned, year_text)
    
    @staticmethod
    def parse_hometown_school(text: str) -> Dict[str, str]:
        """Parse hometown and school information from combined text"""
        result = {'hometown': '', 'high_school': '', 'previous_school': ''}
        
        if not text:
            return result
        
        # Clean the text
        text = re.sub(r'\s*(Instagram|Twitter|Opens in a new window).*$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Handle format with slashes: "City, State / High School / Previous College"
        if ' / ' in text:
            parts = [p.strip() for p in text.split(' / ')]
            if len(parts) >= 1:
                result['hometown'] = parts[0]
            if len(parts) >= 2 and parts[1]:
                result['high_school'] = parts[1]
            if len(parts) >= 3 and parts[2]:
                result['previous_school'] = parts[2]
            return result
        
        # Pattern: City, State followed by school info
        state_pattern = r'(.+?),\s*([A-Z][a-z]+\.?|[A-Z]{2})\s+(.*)'
        match = re.match(state_pattern, text)
        
        if match:
            city, state, school_info = match.groups()
            result['hometown'] = f"{city.strip()}, {state.strip()}"
            
            # Try to separate high school from previous school
            college_indicators = ['University', 'College', 'State', 'Tech']
            for indicator in college_indicators:
                if indicator in school_info:
                    parts = school_info.split(indicator, 1)
                    result['high_school'] = parts[0].strip()
                    result['previous_school'] = (indicator + parts[1]).strip()
                    break
            else:
                result['high_school'] = school_info.strip()
        else:
            result['hometown'] = text
        
        return result
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())

        # Remove common unwanted elements
        cleaned = re.sub(r'\s*(Full Bio|Instagram|Twitter|Opens in a new window).*$', '', cleaned)

        # Strip common labelled prefixes that appear on some smaller sites (e.g. "Class: Freshman")
        cleaned = FieldExtractors.clean_field_labels(cleaned)

        return cleaned

    @staticmethod
    def clean_field_labels(text: str) -> str:
        """Remove label prefixes like 'Class:', 'Hometown:', 'High school:', 'Ht.:', 'Pos.:'

        This helps with sites that dump labelled content into table cells or bio blocks.
        """
        if not text:
            return text

        # Common label patterns to strip
        # NOTE: More specific patterns MUST come first to avoid partial matches
        patterns = [
            # Multi-word patterns first (most specific)
            r'^\s*Hometown / Previous School / High School:\s*', r'\bHometown / Previous School / High School:\s*',
            r'^Hometown / Previous School /\s*', r'\bHometown / Previous School /\s*',
            r'^Hometown/High School \(Former School\):\s*', r'\bHometown/High School \(Former School\):\s*',
            r'^Hometown / High School:\s*', r'\bHometown / High School:\s*',  # For Olivet-style tables
            r'^High School/Previous School:\s*', r'\bHigh School/Previous School:\s*',
            r'^High School/\s*', r'\bHigh School/\s*',
            # Slash-format labels (Ohio Northern style)
            r'^Hometown/\s*', r'\bHometown/\s*',  # Match "Hometown/" prefix
            # Single-word patterns (less specific)
            r'\bClass:\s*', r'\bPrevious College:\s*',
            r'\bPrevious School:\s*', r'\bHt\.:\s*', r'\bPos\.:\s*', r'^High school:\s*',
            r'\bNo\.:\s*', r'\bYr\.:\s*', r'^No\.:\s*', r'^Yr\.:\s*',
            r'\bCl\.:\s*', r'^Cl\.:\s*',
            # Match standalone labels (just the word with optional colon)
            r'^\s*Hometown\s*:?\s*$',  # Match "Hometown" or "Hometown:" as entire cell content
            # These must be last as they're most general
            r'\bHigh school:\s*', r'\bHometown:\s*', r'^Hometown:\s*'
        ]

        for p in patterns:
            text = re.sub(p, '', text, flags=re.IGNORECASE).strip()

        # Remove accidental duplicate full-name repeats like "Harmony Sullivan Harmony Sullivan"
        words = text.split()
        if len(words) >= 4:
            # if first half equals second half, collapse
            half = len(words) // 2
            if words[:half] == words[half:half*2]:
                text = ' '.join(words[:half])

        return text

    @staticmethod
    def looks_like_height(text: str) -> bool:
        """Return True if text looks like a height (examples: 6-1, 6'1\" , 5-10)"""
        if not text:
            return False
        t = text.strip()
        # common patterns: 6-1, 6'1", 5-10, 6 ft 1 in
        patterns = [r'^\d+\s*-\s*\d+$', r"^\d+\s*'\s*\d+(?:\"|$)", r'^\d+\s*ft', r'^\d+\.?\d+\s*"?$']
        for p in patterns:
            if re.search(p, t):
                return True
        return False

    @staticmethod
    def looks_like_academic_year(text: str) -> bool:
        """Return True if text looks like an academic year (Fr, So, Jr, Sr, Redshirt etc.)"""
        if not text:
            return False
        t = text.strip().lower()
        # common abbreviations or full names
        patterns = [r'^(fr|fr\.|so|so\.|jr|jr\.|sr|sr\.|r-?fr|r-?so|r-?jr|r-?sr)$',
                    r'^(freshman|sophomore|junior|senior|redshirt|graduate|grad)']
        for p in patterns:
            if re.search(p, t):
                return True
        return False

    @staticmethod
    def is_visible_cell(cell) -> bool:
        """Check if a table cell is visible (not hidden by responsive classes)"""
        classes = cell.get('class', [])
        # Check for Bootstrap responsive visibility classes that hide cells
        # d-none = display none (hidden on all sizes)
        # d-md-none = hidden on medium+ screens
        # d-lg-none = hidden on large+ screens
        # d-xl-none = hidden on extra large+ screens
        hidden_patterns = ['d-none', 'd-md-none', 'd-lg-none', 'd-xl-none']
        
        # If cell has any of these classes, it's hidden on desktop
        # We want to keep cells visible on desktop (d-none d-md-table-cell means hidden on mobile, visible on desktop)
        if 'd-none' in classes:
            # Check if it's made visible again on larger screens
            visible_patterns = ['d-md-table-cell', 'd-lg-table-cell', 'd-xl-table-cell', 'd-md-block', 'd-lg-block', 'd-xl-block']
            if any(pattern in classes for pattern in visible_patterns):
                return True  # Hidden on mobile but visible on desktop
            return False  # Hidden everywhere
        
        # Check for d-md-none, d-lg-none (hidden on medium+ screens)
        if any(pattern in classes for pattern in ['d-md-none', 'd-lg-none', 'd-xl-none']):
            return False  # Hidden on desktop
            
        return True  # Visible


class SeasonVerifier:
    """Centralized season verification logic"""
    
    @staticmethod
    def verify_season_on_page(html, expected_season: str, entity_type: str = 'player', team_id: int = None) -> bool:
        """Verify that the roster page is for the expected season
        
        For players, requires both season and 'roster' text
        For coaches, only requires season text (since coaching pages may not use 'roster')
        """
        try:
            elements_to_check = []
            
            # Check h1, h2, and title elements
            for tag in ['h1', 'h2']:
                elements = html.find_all(tag) if hasattr(html, 'find_all') else []
                elements_to_check.extend(elements)
            
            title = html.find('title') if hasattr(html, 'find') else None
            if title:
                elements_to_check.append(title)
            
            # Generate alternative season formats: "2024-25" -> ["2024-25", "2024-2025", "2024 - 2025"]
            season_variations = [expected_season]
            if '-' in expected_season and len(expected_season.split('-')) == 2:
                parts = expected_season.split('-')
                # Determine if we have short format (2024-25) or long format (2024-2025)
                if len(parts[1]) == 2:
                    # Short format: "2024-25" -> also check "2024-2025"
                    full_year_no_spaces = f"{parts[0]}-{parts[0][:2]}{parts[1]}"
                    season_variations.append(full_year_no_spaces)
                elif len(parts[1]) == 4:
                    # Long format: "2024-2025" -> also check "2024-25"
                    short_format = f"{parts[0]}-{parts[1][2:]}"
                    season_variations.append(short_format)
                # Add full year format with spaces: "2024-45" -> "2024 - 2025"
                full_year_spaces = f"{parts[0]} - {parts[0][:2]}{parts[1]}" if len(parts[1]) == 2 else f"{parts[0]} - {parts[1]}"
                season_variations.append(full_year_spaces)
                # Add just the starting year for teams that use year_only URL format
                if team_id in [377, 8530, 1079, 2678, 144, 1390]:  # MacMurray, Walsh, Findlay, Arkansas-Pine Bluff, Clark Atlanta, Sul Ross St.
                    season_variations.append(parts[0])
            
            logger.debug(f"Checking season variations: {season_variations}")
            
            for element in elements_to_check:
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)
                # For coaches, just check for season; for players, also require 'roster' (except for certain teams)
                if entity_type == 'coach':
                    if any(season in text for season in season_variations):
                        logger.info(f"Season verification successful - found: '{text.strip()}'")
                        return True
                else:
                    # Teams that don't use "roster" in their headers
                    if team_id == 549:  # Pomona-Pitzer
                        if any(season in text for season in season_variations):
                            logger.info(f"Season verification successful - found: '{text.strip()}'")
                            return True
                    elif any(season in text for season in season_variations) and 'roster' in text.lower():
                        logger.info(f"Season verification successful - found: '{text.strip()}'")
                        return True
                    
            if entity_type == 'coach':
                logger.info(f"Season verification failed - no header found with any of {season_variations}")
            else:
                logger.info(f"Season verification failed - no header found with any of {season_variations} and 'roster'")
            return False
        except Exception as e:
            logger.warning(f"Failed to verify season: {e}")
            return True  # Default to True if verification fails

    @staticmethod
    def is_sidearm_site(html) -> bool:
        """Check if this is a Sidearm-based site"""
        try:
            sidearm_indicators = [
                html.find('li', {'class': 'sidearm-roster-player'}),
                html.find('div', {'class': 'sidearm-roster-list-item'}),
                html.find('span', {'class': 'sidearm-roster-player-name'}),
                html.find_all('div', class_=lambda x: x and 'sidearm' in x)
            ]
            
            return any(indicator for indicator in sidearm_indicators)
        except Exception as e:
            logger.warning(f"Failed to detect Sidearm site: {e}")
            return False

    @staticmethod
    def create_season_check_js(selector_code: str) -> str:
        """Wrap JavaScript selector with season verification"""
        return f"""
        (() => {{
            const h2Elements = document.querySelectorAll('h2');
            const expectedSeason = '{{{{SEASON}}}}';
            let correctSeason = false;
            
            for (const h2 of h2Elements) {{
                const text = h2.textContent || h2.innerText || '';
                if (text.includes(expectedSeason) && text.toLowerCase().includes('roster')) {{
                    correctSeason = true;
                    break;
                }}
            }}
            
            if (!correctSeason) {{
                console.log('Season verification failed - expected:', expectedSeason);
                return [];
            }}
            
            {selector_code}
        }})()
        """


class HeaderMapper:
    """Maps various header formats to standardized field names"""
    
    HEADER_MAP = {
        'No.': 'jersey', 'Name': 'name', 'Full Name': 'name', 'NAME': 'name',
        'Cl.': 'academic_year', 'Academic Year': 'academic_year', 'Class': 'academic_year',
        'Number': 'jersey', 'High school': 'high_school', 'Previous School': 'previous_school',
        'Pos.': 'position', 'Ht.': 'height', 'Hometown/High School': 'town',
        'Hometown / High School': 'town', 'Hometown/Last School': 'town',
        'Num': 'jersey', 'Yr': 'academic_year', 'Ht': 'height', 'Hometown': 'hometown',
        'High School/Previous School': 'high_school', 'Pos': 'position',
        'Hometown/Previous School': 'town',
        # Treat explicit "Exp" / "Exp." columns as 'experience' (e.g., transfer/eligibility info)
        # and prefer 'Year' (or Yr) as the canonical academic_year field. This avoids
        # accidentally mapping 'Exp' values into academic_year (fixes team 433 / Ole Miss).
        'Exp.': 'experience', 'Exp': 'experience',
        'Position': 'position', 'HT.': 'height', 'YEAR': 'academic_year',
        'HOMETOWN': 'hometown', 'LAST SCHOOL': 'high_school', 'Yr.': 'academic_year',
        'Hometown/High School/Last School': 'town', 'Previous College': 'previous_school',
        'Hometown/High School/Previous College': 'town', 'Hometown / High School / Previous College': 'town',
        'Cl.-Exp.': 'academic_year', '#': 'jersey', 'High School': 'high_school',
        'Hometown / Previous School': 'town', 'No': "jersey",
        'Hometown/High School/Previous School': 'town', 'Cl.:': 'academic_year',
        'Hometown / High School / Last College': 'town', 'Year': 'academic_year',
        'Height': 'height', 'Cl': 'academic_year', 'Prev. Coll.': 'previous_school',
        'Hgt.': 'height', 'Hometown/ High School': 'town', 'YR': 'academic_year',
        'POS': 'position', 'HT': 'height', 'Player': 'name', 'NO.': 'jersey',
        'YR.': 'academic_year', 'POS.': 'position', 'HIGH SCHOOL': 'high_school',
        'NO': 'jersey', 'HOMETOWN/HIGH SCHOOL': 'town', 'Academic Yr.': 'academic_year',
        'POSITION': 'position', '#Jersey Number': 'jersey', 'NumberJersey Number': 'jersey',
        'Yr.': 'academic_year', 'Yr': 'academic_year',
        'Hometown / Previous School / High School': 'town',
        'Major': 'major', 'Wt.': 'weight',
        'Hometown/High School (Former School)': 'town',
        'Ltrs.': 'letters',
        # Spaced/case variants seen on live Sidearm sites during the 2026-27
        # needs_hs diagnosis (Duquesne, Michigan State, Rhode Island, Saint Louis,
        # Vermont, Adelphi, Western Ky.). Same targets as the existing unspaced
        # entries; 'High School/Previous' follows the 'High School/Previous School'
        # convention above it.
        'Hometown / Last School': 'town',
        'HOMETOWN / HIGH SCHOOL (LAST SCHOOL)': 'town',
        'Hometown (High School)': 'town',
        'Hometown / High School (Previous School)': 'town',
        'Hometown / Highschool (Previous School)': 'town',
        'High School/Previous': 'high_school',
    }

    @classmethod
    def map_headers(cls, headers: List[str]) -> List[str]:
        """Map raw headers to standardized field names"""
        return [cls.HEADER_MAP.get(h, h.lower().replace(' ', '_')) for h in headers]
