#!/usr/bin/env python3
"""
NCAA Women's Basketball Roster Scraper - Refactored
A clean, modular scraper for NCAA women's basketball rosters
"""

import os
import re
import csv
import json
import argparse
import logging
import subprocess
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import tldextract
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


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
            
            # Generate alternative season formats: "2025-26" -> ["2025-26", "2025 - 2026", "2025-2026"]
            season_variations = [expected_season]
            if '-' in expected_season and len(expected_season.split('-')) == 2:
                parts = expected_season.split('-')
                # Add full year format with spaces: "2025-26" -> "2025 - 2026"
                full_year_spaces = f"{parts[0]} - {parts[0][:2]}{parts[1]}"
                season_variations.append(full_year_spaces)
                # Add full year format without spaces: "2025-26" -> "2025-2026"
                full_year_no_spaces = f"{parts[0]}-{parts[0][:2]}{parts[1]}"
                season_variations.append(full_year_no_spaces)
                # Add just the starting year for MacMurray: "2025-26" -> "2025"
                if team_id == 377 or team_id == 8530:
                    season_variations.append(parts[0])
            
            for element in elements_to_check:
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)
                # For coaches, just check for season; for players, also require 'roster'
                if entity_type == 'coach':
                    if any(season in text for season in season_variations):
                        logger.info(f"Season verification successful - found: '{text.strip()}'")
                        return True
                else:
                    if any(season in text for season in season_variations) and 'roster' in text.lower():
                        logger.info(f"Season verification successful - found: '{text.strip()}'")
                        return True
                    
            if entity_type == 'coach':
                logger.info(f"Season verification failed - no header found with '{expected_season}'")
            else:
                logger.info(f"Season verification failed - no header found with '{expected_season}' and 'roster'")
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


class JSTemplates:
    """Templates for common JavaScript selector patterns"""
    
    @staticmethod
    def coaching_staff_template():
        """Template for coaching-staff div extraction (used by some Nuxt sites)"""
        return """
        (() => {
            try {
                const coachingSection = document.getElementById('coaching-staff');
                if (!coachingSection) {
                    console.log('No coaching-staff section found');
                    return [];
                }

                // Try multiple coach card structures
                let coachCards = coachingSection.querySelectorAll('.roster-card');
                if (!coachCards.length) {
                    // Try li.sidearm-roster-coach (Delaware State style)
                    coachCards = coachingSection.querySelectorAll('li.sidearm-roster-coach');
                }
                if (!coachCards.length) {
                    console.log('No coach cards found');
                    return [];
                }

                return Array.from(coachCards).map(card => {
                    // Extract name - check multiple patterns
                    let nameElem = card.querySelector('.roster-card__name, .sidearm-roster-coach-name, h3, .name');
                    let name = nameElem ? nameElem.textContent.trim() : '';

                    // For li.sidearm-roster-coach, name might be in a link
                    if (!name) {
                        const linkElem = card.querySelector('a');
                        if (linkElem) {
                            name = linkElem.textContent.trim();
                        }
                    }

                    // Extract title/position
                    const titleElem = card.querySelector('.roster-card__title, .sidearm-roster-coach-title, .title, .position');
                    const title = titleElem ? titleElem.textContent.trim() : '';

                    // Extract bio link/URL
                    const linkElem = card.querySelector('a[href*="/roster/"], a[href*="/coaches/"], a');
                    const url = linkElem ? linkElem.href : '';

                    // Extract additional info if available
                    const infoElems = card.querySelectorAll('.roster-card__info, .info, .bio-info');
                    let experience = '';
                    let alma_mater = '';

                    infoElems.forEach(elem => {
                        const text = elem.textContent.trim();
                        if (text.includes('Season') || text.includes('Year')) {
                            experience = text;
                        } else if (text.match(/\b(University|College)\b/i)) {
                            alma_mater = text;
                        }
                    });

                    return {
                        name: name,
                        title: title,
                        experience: experience,
                        alma_mater: alma_mater,
                        url: url
                    };
                }).filter(coach => coach && coach.name && coach.name.length > 2);

            } catch (error) {
                console.error('Error extracting coaching staff:', error);
                return [];
            }
        })()
        """
    
    @staticmethod
    def nuxt_data_coaches_template():
        """Template for Nuxt.js coach data extraction from table rows"""
        return """
        (() => {
            try {
                const coaches = [];

                // Find all table rows
                const allRows = document.querySelectorAll('tr');

                for (const row of allRows) {
                    const text = row.textContent.toLowerCase();

                    // Check if this row mentions coach-related terms (case insensitive)
                    if (text.includes('head coach') || text.includes('assistant coach') ||
                        text.includes('director of') || text.includes('coach')) {

                        // Extract cells from this row
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            // Find which cells contain name and title
                            // Name: cell with text that doesn't contain "coach" or "director"
                            // Title: cell with text that contains "coach"
                            let name = '', title = '', url = '';

                            for (let i = 0; i < cells.length; i++) {
                                const cellText = cells[i]?.textContent.trim() || '';
                                const cellLower = cellText.toLowerCase();

                                // Skip empty cells
                                if (!cellText || cellText.length < 3) continue;

                                // If cell contains "coach", it's probably the title
                                if (cellLower.includes('coach') || cellLower.includes('director')) {
                                    if (!title) title = cellText;
                                }
                                // Otherwise, if it doesn't look like a header, it's probably the name
                                else if (!cellLower.includes('name') &&
                                         !cellLower.includes('title') &&
                                         !cellLower.includes('email') &&
                                         !cellLower.includes('phone')) {
                                    // Skip email addresses themselves
                                    if (!cellText.includes('@') && !name) {
                                        name = cellText;
                                        // Try to find a link in this cell
                                        const link = cells[i]?.querySelector('a');
                                        if (link && link.href) {
                                            url = link.href;
                                        }
                                    }
                                }
                            }

                            // Skip if name or title is empty, or if it's a header row
                            if (name && title &&
                                !name.toLowerCase().includes('name') &&
                                !name.toLowerCase().includes('title') &&
                                !title.toLowerCase().includes('name') &&
                                !title.toLowerCase().includes('title') &&
                                name.length > 2 &&
                                title.toLowerCase().includes('coach')) {
                                coaches.push({
                                    name: name,
                                    title: title,
                                    experience: '',
                                    alma_mater: '',
                                    url: url
                                });
                            }
                        }
                    }
                }

                return coaches;

            } catch (error) {
                console.error('Error extracting coaches:', error);
                return [];
            }
        })()
        """

    @staticmethod
    def nuxt_data_template():
        """Template for Nuxt.js data extraction (used by 50+ teams)"""
        return """
        (() => {
            try {
                const nuxtData = JSON.parse(document.getElementById('__NUXT_DATA__').textContent);
                
                function resolveValue(value) {
                    if (typeof value === 'number' && nuxtData[value] !== undefined) {
                        const resolved = nuxtData[value];
                        if (resolved === null || resolved === undefined || resolved === '' || resolved === 15 || resolved === 21) {
                            return '';
                        }
                        return resolved;
                    }
                    return value || '';
                }
                
                let players = [];
                
                for (const key in nuxtData) {
                    const item = nuxtData[key];
                    if (item && typeof item === 'object' && 
                        item.firstName && item.lastName && 
                        item.rosterPlayerId) {
                        players.push(item);
                    }
                }
                
                if (players.length === 0) {
                    console.log('No player data found');
                    return [];
                }
                
                return players.map(player => {
                    const firstName = resolveValue(player.firstName) || '';
                    const lastName = resolveValue(player.lastName) || '';
                    const fullName = (firstName + ' ' + lastName).trim();
                    const jersey = resolveValue(player.jerseyNumber) || '';
                    const position = resolveValue(player.positionShort) || resolveValue(player.positionLong) || '';
                    const year = resolveValue(player.academicYearLong) || resolveValue(player.academicYearShort) || '';
                    const heightFeet = resolveValue(player.heightFeet) || '';
                    const heightInches = resolveValue(player.heightInches) || '';
                    const height = heightFeet && heightInches ? heightFeet + "'" + heightInches + '"' : '';
                    const hometown = resolveValue(player.hometown) || '';
                    const high_school = resolveValue(player.highSchool) || '';
                    const previous_school = resolveValue(player.previousSchool) || '';
                    const url = resolveValue(player.call_to_action) || '';
                    
                    return {
                        name: fullName,
                        jersey: jersey.toString(),
                        position: position,
                        year: year,
                        height: height,
                        hometown: hometown,
                        high_school: high_school,
                        previous_school: previous_school,
                        url: url
                    };
                }).filter(player => player && player.name && player.name.length > 2);
                
            } catch (error) {
                console.error('Error extracting roster:', error);
                return [];
            }
        })()
        """

    @staticmethod
    def s_person_card_template():
        """Template for .s-person-card based sites"""
        return """
        Array.from(document.querySelectorAll('.s-person-card'), card => {
            const fullText = card.textContent || '';
            
            const link = card.querySelector('a[href*="/roster/"]');
            if (!link || link.href.includes('/coaches/') || link.href.includes('/staff/')) {
                return null;
            }
            
            const jerseyMatch = fullText.match(/Jersey Number (\\d+)/);
            const jersey = jerseyMatch ? jerseyMatch[1] : '';
            
            const nameMatch = fullText.match(/Jersey Number \\d+([^P]+?)Position/);
            const name = nameMatch ? nameMatch[1].trim() : '';
            
            const positionMatch = fullText.match(/Position ([GFC])/);
            const position = positionMatch ? positionMatch[1] : '';
            
            const yearMatch = fullText.match(/Academic Year ([^H]+?)Height/);
            let year = yearMatch ? yearMatch[1].trim().replace(/\\.$/, '') : '';
            
            // Convert year abbreviations
            const yearMap = {'Fr': 'Freshman', 'So': 'Sophomore', 'Jr': 'Junior', 'Sr': 'Senior', 'Gr': 'Graduate'};
            year = yearMap[year] || year;
            
            const heightMatch = fullText.match(/Height ([^H]+?)Hometown/);
            const height = heightMatch ? heightMatch[1] : '';
            
            const hometownMatch = fullText.match(/Hometown ([^L]+?)Last School/);
            const hometown = hometownMatch ? hometownMatch[1].trim() : '';
            
            const schoolMatch = fullText.match(/Last School ([^F]+?)Full Bio/);
            const high_school = schoolMatch ? schoolMatch[1].trim() : '';
            
            return {
                name: name || '',
                jersey: jersey || '',
                position: position || '',
                year: year || '',
                height: height || '',
                hometown: hometown || '',
                high_school: high_school || '',
                previous_school: '',
                url: link.href || ''
            };
        }).filter(player => player && player.name && player.name.length > 2)
        """

    @staticmethod
    def sidearm_roster_player_template():
        """Template for standard sidearm-roster-player elements (used by many Vue.js sites)"""
        return """
        Array.from(document.querySelectorAll('.sidearm-roster-player'), player => {
            // Get link first
            const link = player.querySelector('a[href*="/roster/"]');
            const url = link ? link.href : '';
            
            // Get name from aria-label or link text
            let name = '';
            if (link && link.getAttribute('aria-label')) {
                const ariaLabel = link.getAttribute('aria-label');
                // Extract name from "Name - View Full Bio" format
                name = ariaLabel.replace(/ - View Full Bio.*$/i, '').trim();
            }
            if (!name && link) {
                // Fallback to link text content (but skip if it's just the image)
                const linkText = link.textContent.trim();
                if (linkText && linkText.length > 2 && !linkText.includes('http')) {
                    name = linkText;
                }
            }
            
            // Skip if no name
            if (!name) {
                return null;
            }
            
            // Get jersey number
            const jerseyElem = player.querySelector('.sidearm-roster-player-jersey-number, .sidearm-roster-player-jersey');
            const jersey = jerseyElem ? jerseyElem.textContent.trim().replace('#', '') : '';
            
            // Get position - check nested .text-bold first (for CMSV, Delaware State structure)
            const positionElem = player.querySelector('.sidearm-roster-player-position');
            let position = '';
            if (positionElem) {
                // First try to get position from nested .text-bold span
                const textBold = positionElem.querySelector('.text-bold, span.text-bold');
                if (textBold) {
                    position = textBold.textContent.trim();
                } else {
                    // Fallback: Get only direct text nodes, not text from child elements like height
                    for (const node of positionElem.childNodes) {
                        if (node.nodeType === Node.TEXT_NODE) {
                            const text = node.textContent.trim();
                            if (text && !text.match(/^\d+['"]?\d*["']?$/)) {  // Skip if it looks like height
                                position = text;
                                break;
                            }
                        }
                    }
                }
            }
            
            // Get academic year
            const yearElem = player.querySelector('.sidearm-roster-player-academic-year, .sidearm-roster-player-academic-year-long');
            let year = yearElem ? yearElem.textContent.trim() : '';
            
            // Get height
            const heightElem = player.querySelector('.sidearm-roster-player-height');
            const height = heightElem ? heightElem.textContent.trim() : '';
            
            // Get hometown
            const hometownElem = player.querySelector('.sidearm-roster-player-hometown');
            const hometown = hometownElem ? hometownElem.textContent.trim() : '';
            
            // Get high school
            const highSchoolElem = player.querySelector('.sidearm-roster-player-highschool, .sidearm-roster-player-high-school');
            const high_school = highSchoolElem ? highSchoolElem.textContent.trim() : '';
            
            // Get previous school
            const prevSchoolElem = player.querySelector('.sidearm-roster-player-previous-school');
            const previous_school = prevSchoolElem ? prevSchoolElem.textContent.trim() : '';
            
            return {
                name: name,
                jersey: jersey,
                position: position,
                year: year,
                height: height,
                hometown: hometown,
                high_school: high_school,
                previous_school: previous_school,
                url: url
            };
        }).filter(player => player && player.name && player.name.length > 2)
        """

    @staticmethod
    def wyoming_roster_template():
        """Template for Wyoming-style Vue.js roster (uses sidearm-roster-list-item)"""
        return """
        Array.from(document.querySelectorAll('.sidearm-roster-list-item'), item => {
            // Get name
            const nameElem = item.querySelector('.sidearm-roster-list-item-name, .sidearm-roster-player-name');
            const name = nameElem ? nameElem.textContent.trim() : '';
            
            // Get link
            const link = item.querySelector('a[href*="/roster/"]');
            const url = link ? link.href : '';
            
            // Skip if no name or if it's a coach
            if (!name || url.includes('/coaches/') || url.includes('/staff/')) {
                return null;
            }
            
            // Get jersey number
            const jerseyElem = item.querySelector('.sidearm-roster-list-item-number, .sidearm-roster-player-jersey-number');
            const jersey = jerseyElem ? jerseyElem.textContent.trim() : '';
            
            // Get position
            const positionElem = item.querySelector('.sidearm-roster-list-item-position, .sidearm-roster-player-position');
            const position = positionElem ? positionElem.textContent.trim() : '';
            
            // Get academic year
            const yearElem = item.querySelector('.sidearm-roster-list-item-year, .sidearm-roster-list-item-academic-year, .sidearm-roster-player-academic-year');
            let year = yearElem ? yearElem.textContent.trim() : '';
            
            // Get height
            const heightElem = item.querySelector('.sidearm-roster-list-item-height, .sidearm-roster-player-height');
            const height = heightElem ? heightElem.textContent.trim() : '';
            
            // Get hometown
            const hometownElem = item.querySelector('.sidearm-roster-list-item-hometown, .sidearm-roster-player-hometown');
            const hometown = hometownElem ? hometownElem.textContent.trim() : '';
            
            // Get high school
            const highSchoolElem = item.querySelector('.sidearm-roster-list-item-highschool, .sidearm-roster-player-highschool');
            const high_school = highSchoolElem ? highSchoolElem.textContent.trim() : '';
            
            // Get previous school
            const prevSchoolElem = item.querySelector('.sidearm-roster-list-item-previous-school, .sidearm-roster-player-previous-school');
            const previous_school = prevSchoolElem ? prevSchoolElem.textContent.trim() : '';
            
            return {
                name: name,
                jersey: jersey,
                position: position,
                year: year,
                height: height,
                hometown: hometown,
                high_school: high_school,
                previous_school: previous_school,
                url: url
            };
        }).filter(player => player && player.name && player.name.length > 2)
        """

    @staticmethod
    def s_person_card_coaches_template():
        """Template for .s-person-card based sites - coaches version"""
        return """
        (() => {
            const coaches = [];
            const seenNames = new Set();
            
            document.querySelectorAll('.s-person-card').forEach(card => {
                const fullText = card.textContent || '';
                
                // For coaches, we want links that include /coaches/ or /staff/
                const link = card.querySelector('a[href*="/roster/coaches/"], a[href*="/staff/"], a[href*="/roster/"]');
                if (!link) {
                    return;
                }
                
                // Skip if it looks like a player (has jersey number)
                if (fullText.match(/Jersey Number \\d+/)) {
                    return;
                }
                
                // Extract name - try multiple patterns
                let name = '';
                const nameElem = card.querySelector('.s-person-card__header__person-details-personal, h3, .name');
                if (nameElem) {
                    name = nameElem.textContent.trim();
                } else {
                    // Fallback to link text
                    name = link.textContent.trim();
                }
                
                // Skip if we've already seen this name (avoid duplicates)
                if (seenNames.has(name)) {
                    return;
                }
                seenNames.add(name);
                
                // Extract title/position - clean up extra text
                let title = '';
                const titleMatch = fullText.match(/Title\\s+([^\\n]+)/);
                if (titleMatch) {
                    title = titleMatch[1].trim();
                } else {
                    // Look for common coach titles
                    const coachTitleMatch = fullText.match(/((?:Head |Assistant |Associate Head |Director of |Coordinator of )?(?:Coach|Director|Coordinator|Operations|Performance)[^Phone^Full^Email]*)/i);
                    if (coachTitleMatch) {
                        title = coachTitleMatch[1]
                            .replace(/Phone.*$/i, '')
                            .replace(/Full Bio.*$/i, '')
                            .replace(/Email.*$/i, '')
                            .replace(/\\(\\d{3}\\).*$/i, '')
                            .replace(/[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}.*$/i, '')
                            .trim();
                    }
                }
                
                // Extract experience/seasons
                let experience = '';
                const expMatch = fullText.match(/(\\d+(?:st|nd|rd|th)?\\s+Season|\\d+\\s+Years?)/i);
                if (expMatch) {
                    experience = expMatch[0].trim();
                }
                
                // Extract alma mater
                let alma_mater = '';
                const almaMatch = fullText.match(/Alma Mater\\s+([^\\n]+)/);
                if (almaMatch) {
                    alma_mater = almaMatch[1].trim();
                } else {
                    // Look for university/college mentions
                    const collegeMatch = fullText.match(/([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\s+(?:University|College))/);
                    if (collegeMatch) {
                        alma_mater = collegeMatch[0].trim();
                    }
                }
                
                coaches.push({
                    name: name || '',
                    title: title || '',
                    experience: experience || '',
                    alma_mater: alma_mater || '',
                    url: link.href || ''
                });
            });
            
            return coaches.filter(coach => coach && coach.name && coach.name.length > 2);
        })()
        """

    @staticmethod
    def get_custom_selector(team_id: int, selector_name: str) -> str:
        """Get custom selectors for specific teams that need special handling"""
        custom_selectors = {
            'sidearm_roster_player': JSTemplates.sidearm_roster_player_template(),
            'wyoming_roster': JSTemplates.wyoming_roster_template(),
            'auburn_roster': """
            Array.from(document.querySelectorAll('a[href*="/roster/player/"]'), el => {
                if (el.href.includes('/staff/')) return null;
                
                const name = el.innerText.trim();
                const url = el.href;
                let container = el.closest('div');
                
                while (container && !container.innerText.includes('#')) {
                    container = container.parentElement;
                }
                
                if (!container) container = el.parentElement;
                const fullText = container.innerText;
                
                const jerseyMatch = fullText.match(/#(\\d+)/);
                const jersey = jerseyMatch ? jerseyMatch[1] : '';
                
                const positionMatch = fullText.match(/\\b(G|F|C|GUARD|FORWARD|CENTER|G\\/F|F\\/C)\\b/i);
                const position = positionMatch ? positionMatch[1] : '';
                
                const heightMatch = fullText.match(/(\\d+[′']\\d+[″"])/);
                const height = heightMatch ? heightMatch[1] : '';
                
                const yearMatch = fullText.match(/\\b(Freshman|Sophomore|Junior|Senior|Redshirt\\s+\\w+)\\b/i);
                const year = yearMatch ? yearMatch[1] : '';
                
                return {name, jersey, position, height, year, hometown: '', high_school: '', previous_school: '', url};
            }).filter(player => player && player.name)
            """,
            'oregon_state_roster': """
            Array.from(document.querySelectorAll('.s-table-body__row'), el => {
                const tds = el.querySelectorAll('td');
                const jersey = tds[0]?.textContent?.trim() || '';
                const name = tds[1]?.querySelector('a')?.textContent?.trim() || tds[1]?.textContent?.trim() || '';
                const position = tds[2]?.textContent?.trim() || '';
                const height = tds[3]?.textContent?.trim() || '';
                const year = tds[4]?.textContent?.trim() || '';
                const hometown = tds[5]?.textContent?.trim() || '';
                const url = tds[1]?.querySelector('a')?.href || '';
                
                if (!jersey || jersey === '') return null;
                
                return {name, jersey, position, height, year, hometown, high_school: '', previous_school: '', url};
            }).filter(player => player !== null)
            """,
            'virginia_roster_table': """
(() => {
    const table = document.querySelector('#players-table');
    if (!table) {
        console.log('No players table found');
        return [];
    }
    
    const rows = table.querySelectorAll('tbody tr');
    console.log('Found table rows:', rows.length);
    
    return Array.from(rows).map(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 6) return null;
        
        const jersey = cells[0] ? cells[0].textContent.trim() : '';
        const nameCell = cells[1];
        const nameLink = nameCell ? nameCell.querySelector('a') : null;
        const name = nameLink ? nameLink.textContent.trim() : (nameCell ? nameCell.textContent.trim() : '');
        const year = cells[2] ? cells[2].textContent.trim() : '';
        const position = cells[3] ? cells[3].textContent.trim() : '';
        const height = cells[4] ? cells[4].textContent.trim() : '';
        const hometown = cells[5] ? cells[5].textContent.trim() : '';
        const high_school = cells[6] ? cells[6].textContent.trim() : '';
        const previous_school = cells.length > 9 && cells[9] ? cells[9].textContent.trim() : '';
        const url = nameLink ? nameLink.href : '';
        
        return {
            name: name,
            jersey: jersey,
            position: position,
            height: height,
            year: year,
            hometown: hometown,
            high_school: high_school,
            previous_school: previous_school,
            url: url
        };
    }).filter(player => player && player.name && player.name.length > 2);
})()
            """,
            'miami_table_roster': """
new Promise((resolve) => {
    // Wait for DataTables to initialize
    setTimeout(() => {
        const table = document.querySelector('#players-table');
        if (!table) {
            console.log('No players table found');
            resolve([]);
            return;
        }
        
        const rows = table.querySelectorAll('tbody tr');
        console.log('Found table rows:', rows.length);
        
        const players = Array.from(rows).map(row => {
            const cells = row.querySelectorAll('td');
            console.log('Cell count:', cells.length);
            if (cells.length < 5) return null;
            
            // Extract text content from cells
            const jersey = cells[0] ? cells[0].textContent.trim() : '';
            const nameCell = cells[1];
            const nameLink = nameCell ? nameCell.querySelector('a') : null;
            const name = nameLink ? nameLink.textContent.trim() : (nameCell ? nameCell.textContent.trim() : '');
            const position = cells[2] ? cells[2].textContent.trim() : '';
            
            // Height with data-sort attribute
            const heightCell = cells[3];
            const height = heightCell ? heightCell.textContent.trim() : '';
            
            // Class/Year - use data-sort attribute if available for cleaner value
            const yearCell = cells[4];
            const year = yearCell ? (yearCell.getAttribute('data-sort') || yearCell.textContent.trim()) : '';
            
            // Hometown, high school, previous school
            const hometown = cells[5] ? cells[5].textContent.trim() : '';
            const high_school = cells[6] ? cells[6].textContent.trim() : '';
            const previous_school = cells.length > 7 && cells[7] ? cells[7].textContent.trim() : '';
            
            const url = nameLink ? nameLink.href : '';
            
            console.log('Player:', name, 'Year:', year);
            
            return {
                name: name,
                jersey: jersey,
                position: position,
                height: height,
                year: year,
                hometown: hometown,
                high_school: high_school,
                previous_school: previous_school,
                url: url
            };
        }).filter(player => player && player.name && player.name.length > 2);
        
        resolve(players);
    }, 3000);  // Wait 3 seconds for DataTables to load
})
            """,
            'auburn_roster_coaches': """
            // NOTE: Auburn-specific coach scraping - may need manual verification
            Array.from(document.querySelectorAll('a[href*="/roster/coaches/"], a[href*="/staff/"]'), el => {
                const name = el.innerText.trim();
                const url = el.href;
                let container = el.closest('div');
                
                // Find the container with coach information
                while (container && !container.innerText.match(/Head Coach|Assistant|Director|Coordinator/i)) {
                    container = container.parentElement;
                    if (!container || container === document.body) break;
                }
                
                if (!container || container === document.body) container = el.parentElement;
                const fullText = container.innerText;
                
                // Extract title
                const titleMatch = fullText.match(/(Head Coach|Assistant Coach|Associate Head Coach|Director[^\\n]*|Coordinator[^\\n]*)/i);
                const title = titleMatch ? titleMatch[1].trim() : '';
                
                // Extract experience/seasons
                const expMatch = fullText.match(/(\\d+(?:st|nd|rd|th)?\\s+Season|\\d+\\s+Years?)/i);
                const experience = expMatch ? expMatch[0].trim() : '';
                
                // Extract alma mater
                const almaMatch = fullText.match(/([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\s+(?:University|College))/);
                const alma_mater = almaMatch ? almaMatch[0].trim() : '';
                
                return {name, title, experience, alma_mater, url};
            }).filter(coach => coach && coach.name && coach.name.length > 2)
            """,
            'oregon_state_roster_coaches': """
            Array.from(document.querySelectorAll('.s-table-body__row'), el => {
                const tds = el.querySelectorAll('td');
                
                // Check if this looks like a coach row (no jersey number or has title)
                const firstCell = tds[0]?.textContent?.trim() || '';
                const secondCell = tds[1]?.textContent?.trim() || '';
                
                // If first cell is a number, it's probably a player
                if (firstCell.match(/^\\d+$/)) return null;
                
                const name = tds[0]?.querySelector('a')?.textContent?.trim() || tds[0]?.textContent?.trim() || 
                             tds[1]?.querySelector('a')?.textContent?.trim() || tds[1]?.textContent?.trim() || '';
                const title = tds[1]?.textContent?.trim() || tds[2]?.textContent?.trim() || '';
                const url = tds[0]?.querySelector('a')?.href || tds[1]?.querySelector('a')?.href || '';
                
                // Look for typical coach titles
                if (!title.match(/Coach|Director|Coordinator/i)) return null;
                
                return {name, title, experience: '', alma_mater: '', url};
            }).filter(coach => coach !== null && coach.name && coach.name.length > 2)
            """,
            'virginia_roster_table_coaches': """
(() => {
    // Look for coaching staff section or table
    const coachHeaders = document.querySelectorAll('h2, h3, h4');
    let coachSection = null;
    
    for (const header of coachHeaders) {
        if (header.textContent.match(/coach|staff/i)) {
            coachSection = header;
            break;
        }
    }
    
    if (!coachSection) {
        console.log('No coaching staff section found');
        return [];
    }
    
    // Find table or list after the header
    let table = coachSection.nextElementSibling;
    while (table && table.tagName !== 'TABLE' && !table.classList.contains('roster')) {
        table = table.nextElementSibling;
        if (!table) break;
    }
    
    if (!table) {
        // Try looking for coach cards or divs
        const coachCards = document.querySelectorAll('.coach-card, .staff-card, [class*="coach"]');
        return Array.from(coachCards).map(card => {
            const nameElem = card.querySelector('h3, h4, .name, a');
            const name = nameElem ? nameElem.textContent.trim() : '';
            const titleElem = card.querySelector('.title, .position, [class*="title"]');
            const title = titleElem ? titleElem.textContent.trim() : '';
            const linkElem = card.querySelector('a[href*="/coaches/"], a[href*="/staff/"]');
            const url = linkElem ? linkElem.href : '';
            
            return {name, title, experience: '', alma_mater: '', url};
        }).filter(coach => coach && coach.name && coach.name.length > 2);
    }
    
    // Parse table
    const rows = table.querySelectorAll('tbody tr, tr');
    return Array.from(rows).map(row => {
        const cells = row.querySelectorAll('td, th');
        if (cells.length < 2) return null;
        
        const nameCell = cells[0];
        const nameLink = nameCell ? nameCell.querySelector('a') : null;
        const name = nameLink ? nameLink.textContent.trim() : (nameCell ? nameCell.textContent.trim() : '');
        const title = cells[1] ? cells[1].textContent.trim() : '';
        const url = nameLink ? nameLink.href : '';
        
        // Skip if no name or if it looks like column headers
        if (!name || name.match(/^Name$/i)) return null;
        
        return {name, title, experience: '', alma_mater: '', url};
    }).filter(coach => coach && coach.name && coach.name.length > 2);
})()
            """,
            'wyoming_roster_coaches': """
(() => {
    // Wyoming uses sidearm-roster-staff structure
    const coaches = [];
    const seenNames = new Set();

    // Get all staff items from the ul.sidearm-roster-staff-list
    const staffItems = document.querySelectorAll('ul.sidearm-roster-staff-list li.sidearm-roster-staff-item');

    if (staffItems.length === 0) {
        console.log('No staff items found');
        return [];
    }

    console.log('Found', staffItems.length, 'staff items');

    for (const item of staffItems) {
        // Get the name from .sidearm-roster-staff-name div
        const nameElem = item.querySelector('.sidearm-roster-staff-name');
        if (!nameElem) continue;

        const name = nameElem.textContent.trim();

        // Skip if empty or if we've seen this name
        if (!name || name.length < 3 || seenNames.has(name)) continue;

        // Skip if it's contact info (email or phone)
        if (name.includes('@') || name.match(/\\(\\d{3}\\)/) || name.match(/^\\d{3}/) || name.match(/\\d{3}-\\d{3}/)) continue;

        seenNames.add(name);

        // Get URL from the link
        const linkElem = item.querySelector('a.sidearm-roster-staff-link');
        const url = linkElem ? linkElem.href : '';

        // Get title from .sidearm-roster-staff-title div
        const titleElem = item.querySelector('.sidearm-roster-staff-title');
        const title = titleElem ? titleElem.textContent.trim() : '';

        coaches.push({
            name: name,
            title: title,
            experience: '',
            alma_mater: '',
            url: url
        });
    }

    return coaches.filter(coach => coach && coach.name && coach.name.length > 2);
})()
            """,
            'delaware_state_roster_coaches': """
(() => {
    // Delaware State uses li.sidearm-roster-coach with specific class names
    const coaches = [];
    const seenNames = new Set();

    // Get all coach items
    const coachItems = document.querySelectorAll('li.sidearm-roster-coach');

    if (coachItems.length === 0) {
        console.log('No coach items found');
        return [];
    }

    console.log('Found', coachItems.length, 'coach items');

    for (const item of coachItems) {
        // Get the name from .sidearm-roster-coach-name div
        const nameElem = item.querySelector('.sidearm-roster-coach-name');
        if (!nameElem) continue;

        const name = nameElem.textContent.trim();

        // Skip if empty or if we've seen this name
        if (!name || name.length < 3 || seenNames.has(name)) continue;

        // Skip if it's contact info (email or phone)
        if (name.includes('@') || name.match(/\\(\\d{3}\\)/) || name.match(/^\\d{3}/) || name.match(/\\d{3}-\\d{3}/)) continue;

        seenNames.add(name);

        // Get URL from the link
        const linkElem = item.querySelector('a');
        const url = linkElem ? linkElem.href : '';

        // Get title from .sidearm-roster-coach-title div
        const titleElem = item.querySelector('.sidearm-roster-coach-title');
        const title = titleElem ? titleElem.textContent.trim() : '';

        coaches.push({
            name: name,
            title: title,
            experience: '',
            alma_mater: '',
            url: url
        });
    }

    return coaches.filter(coach => coach && coach.name && coach.name.length > 2);
})()
            """,
            'iowa_roster_coaches': """
(() => {
    // Iowa uses tabs, need to wait for content to load
    const coaches = [];
    const seenNames = new Set();

    // Look for coaches in roster cards or person cards
    const coachCards = document.querySelectorAll('.s-person-card, .roster-card, [class*="coach"]');

    for (const card of coachCards) {
        const fullText = card.textContent || '';

        // Check if this is a coach (has coach-related keywords)
        if (!fullText.match(/Head Coach|Assistant Coach|Associate|Director|Coordinator/i)) continue;

        // Find name
        let nameElem = card.querySelector('.s-person-card__name, .roster-card__name, h3, h4, a');
        if (!nameElem) continue;

        let name = nameElem.textContent.trim();

        // Skip if empty or already seen
        if (!name || name.length < 3 || seenNames.has(name)) continue;

        // Skip contact info
        if (name.includes('@') || name.match(/\\d{3}-\\d{3}/)) continue;

        seenNames.add(name);

        // Get URL
        const linkElem = card.querySelector('a[href*="/coaches/"], a[href*="/roster/"]');
        const url = linkElem ? linkElem.href : '';

        // Get title
        const titleElem = card.querySelector('.s-person-card__title, .roster-card__title, .title, [class*="title"]');
        let title = '';

        if (titleElem) {
            title = titleElem.textContent.trim();
        } else {
            // Extract from full text
            const titleMatch = fullText.match(/(Head Coach|Assistant Coach|Associate Head Coach|Associate Coach|Director[^\\n]*|Coordinator[^\\n]*)/i);
            title = titleMatch ? titleMatch[1].trim() : '';
        }

        coaches.push({
            name: name,
            title: title,
            experience: '',
            alma_mater: '',
            url: url
        });
    }

    return coaches.filter(coach => coach && coach.name && coach.name.length > 2);
})()
            """
        }

        return custom_selectors.get(selector_name, '')


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
        'Hometown/Previous School': 'town', 'Exp.': 'academic_year',
        'Position': 'position', 'HT.': 'height', 'YEAR': 'academic_year',
        'HOMETOWN': 'hometown', 'LAST SCHOOL': 'high_school', 'Yr.': 'academic_year',
        'Hometown/High School/Last School': 'town', 'Previous College': 'previous_school',
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
        'Ltrs.': 'letters'
    }

    @classmethod
    def map_headers(cls, headers: List[str]) -> List[str]:
        """Map raw headers to standardized field names"""
        return [cls.HEADER_MAP.get(h, h.lower().replace(' ', '_')) for h in headers]


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
            "la_salle": f"{base_url}/{path}/{season[:4]}-{season[:2]}{season[-2:]}",
            "byu_table": f"{base_url}/{path}/season/{season[:4]}-{season[:2]}{season[-2:]}?view=table",
            "four_digit_year": f"{base_url}/{path}/{season[:4]}-{season[:2]}{season[-2:]}",
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
        521: 'https://okstate.com', 522: 'https://soonersports.com', 454: 'https://goracers.com',
        404: 'https://gotigersgo.com', 671: 'https://ragincajuns.com',
        574: 'https://riceowls.com', 664: 'https://southernmiss.com', 575: 'https://richmondspiders.com',
        698: 'https://gofrogs.com', 288: 'https://uhcougars.com', 400: 'https://umassathletics.com',
        457: 'https://goheels.com', 156: 'https://csurams.com', 196: 'https://ecupirates.com',
        725: 'https://goarmywestpoint.com', 9: 'https://uabsports.com', 502: 'https://uncbears.com',
        456: 'https://uncabulldogs.com', 469: 'https://unhwildcats.com', 504: 'https://unipanthers.com',
        758: 'https://weberstatesports.com', 490: 'https://gopack.com', 690: 'https://owlsports.com',
        732: 'https://utahutes.com', 749: 'https://godeacs.com', 110: 'https://uclabruins.com',
        1104: 'https://gculopes.com', 719: 'https://tulsahurricane.com', 772: 'https://wkusports.com',
        328: 'https://kuathletics.com', 635: 'https://shupirates.com', 86: 'https://ubbulls.com',
        694: 'https://utsports.com', 387: 'https://gomarquette.com', 545: 'https://pittsburghpanthers.com',
        721: 'https://goairforcefalcons.com', 51: 'https://baylorbears.com',
        419: 'https://goblueraiders.com', 688: 'https://cuse.com', 311: 'https://cyclones.com',
        129: 'https://cmuchippewas.com', 8: 'https://rolltide.com', 193: 'https://goduke.com', 649: 'https://gojacks.com',
        249: 'https://gwsports.com', 430: 'https://hailstate.com', 80: 'https://brownbears.com',
        257: 'https://georgiadogs.com', 317: 'https://jmusports.com', 66: 'https://broncosports.com',
        562: 'https://gobobcats.com', 659: 'https://siusalukis.com', 756: 'https://gohuskies.com',
        697: 'https://12thman.com', 173: 'https://davidsonwildcats.com', 518: 'https://ohiostatebuckeyes.com',
        47: 'https://ballstatesports.com', 529: 'https://goducks.com', 676: 'https://sfajacks.com',
        30135: 'https://cbulancers.com', 414: 'https://miamiredhawks.com',
        434: 'https://mutigers.com', 440: 'https://msubobcats.com', 703: 'https://texassports.com',
        796: 'https://uwbadgers.com'  # Wisconsin - Nuxt.js with embedded JSON data
    }
    
    # Teams using .s-person-card structure
    S_PERSON_CARD_TEAMS = [67, 169, 157, 603]  # Boston College, Creighton, Colorado, St. John's
    
    # Table-based teams
    TABLE_BASED_TEAMS = {
        5: {'url_format': 'default'},
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
        746: {'type': 'javascript', 'selector': 'virginia_roster_table', 'url_format': 'direct'},
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
                'url_format': 'la_salle'
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
        if team.get('ncaa_id') in [51, 406, 90, 172, 610, 331, 2711, 101, 235, 2707, 598, 620]:  # Baylor, Mercer, Cal Poly, Dartmouth, Saint Mary's (CA), Kent State, North Florida, CSUN, Florida, Kansas City, St. Cloud St., St. Thomas (MN)
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
            # Use transformed season for four_digit_year format teams
            verification_season = season
            if (team['ncaa_id'] in [209, 339, 340, 77, 670, 1013, 11403, 11504] or
                team['url'].startswith('https://hawaiiathletics.com')):
                verification_season = f"{season[:4]}-{season[:2]}{season[-2:]}"
            if not SeasonVerifier.verify_season_on_page(html, verification_season, entity_type=self.entity_type, team_id=team['ncaa_id']):
                logger.warning(f"Season verification failed for {team['team']} - expected {verification_season}")
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
                    'year': self._get_academic_year(player_elem),
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

    def _get_academic_year(self, player_elem) -> str:
        """Extract academic year"""
        # Try custom selectors first, then fall back to default
        year_text = self._get_field_with_custom_selectors(player_elem, 'academic_year', 'sidearm-roster-player-academic-year')
        return year_text if year_text else ""

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
            verification_season = season
            # Teams using four_digit_year format (2025-26 becomes 2025-2026)
            if (team['ncaa_id'] in [209, 339, 340, 77, 670, 1013, 11403, 11504] or 
                url_format == 'four_digit_year' or
                team['url'].startswith('https://hawaiiathletics.com')):
                verification_season = f"{season[:4]}-{season[:2]}{season[-2:]}"
            if not SeasonVerifier.verify_season_on_page(html, verification_season, entity_type=self.entity_type, team_id=team['ncaa_id']):
                logger.warning(f"Season {verification_season} not found on page for {team['team']}")
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
                
                # Handle coach data differently
                if self.entity_type == 'coach':
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
                        year=entity_data.get('year', ''),
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


class RosterManager:
    """Main class for managing roster scraping operations"""
    
    def __init__(self, teams_file: str = "/Users/dwillis/code/wbb/ncaa/teams.json", entity_type: str = 'player'):
        self.teams_file = teams_file
        self.teams_data = self._load_teams()
        self.zero_player_teams = []
        self.failed_year_check_teams = []
        self.entity_type = entity_type

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
        """Scrape roster for a single team"""
        config = TeamConfig.get_config(team['ncaa_id'])
        scraper = ScraperFactory.create_scraper(config['type'], entity_type=self.entity_type)

        logger.info(f"Scraping {team['team']} (ID: {team['ncaa_id']}) for {season}")
        logger.info(f"Using config: {config}")

        try:
            if config['type'] == 'javascript':
                selector = config.get('selector', 'nuxt_roster')
                url_format = config.get('url_format', 'default')
                base_url = config.get('base_url', '')
                return scraper.scrape_roster(team, season, selector, url_format, base_url)
            elif config['type'] == 'table':
                url_format = config.get('url_format', 'default')
                return scraper.scrape_roster(team, season, url_format)
            elif config['type'] == 'vue_data':
                url_format = config.get('url_format', 'default')
                return scraper.scrape_roster(team, season, url_format)
            else:
                url_format = config.get('url_format', 'default')
                return scraper.scrape_roster(team, season, url_format)
        except Exception as e:
            logger.error(f"Failed to scrape {team['team']}: {e}")
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
                    else:
                        logger.info(f"No {entity_label} scraped from {team['team']} but year check failed - not counting as zero {entity_label}")
                else:
                    logger.info(f"Scraped {len(players)} {entity_label} from {team['team']}")

            except Exception as e:
                logger.error(f"Failed to scrape {team['team']}: {e}")
                # Only add to zero players, not year check failures
                self.zero_player_teams.append({
                    'team_id': team['ncaa_id'],
                    'team_name': team['team']
                })
                continue

        return all_players

    def save_to_csv(self, players: List[Player], output_file: str):
        """Save players to CSV file"""
        if not players:
            logger.warning("No players to save")
            return

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Build team_id to team_state mapping
        team_state_map = {team['ncaa_id']: team.get('team_state', '') for team in self.teams_data}

        # Use entity-specific fieldnames
        fieldnames = ENTITY_CONFIGS[self.entity_type]['output_fields']
        entity_label = ENTITY_CONFIGS[self.entity_type]['entity_label']
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for player in players:
                # Post-process fields to remove label prefixes and accidental duplicates
                pdata = player.to_dict()
                pdata['name'] = FieldExtractors.clean_field_labels(pdata.get('name', ''))
                
                # For coaches, map position to title
                if self.entity_type == 'coach':
                    pdata['title'] = pdata.get('position', '')
                else:
                    # Only clean player-specific fields if we're saving players
                    pdata['hometown'] = FieldExtractors.clean_field_labels(pdata.get('hometown', ''))
                    pdata['high_school'] = FieldExtractors.clean_field_labels(pdata.get('high_school', ''))
                    pdata['previous_school'] = FieldExtractors.clean_field_labels(pdata.get('previous_school', ''))
                    pdata['academic_year'] = FieldExtractors.clean_field_labels(pdata.get('academic_year', ''))
                    
                    # Add state abbreviation to hometown if not already present (opt-in only)
                    team_id = pdata.get('team_id')
                    if team_id in TeamConfig.ADD_STATE_TO_HOMETOWN:
                        hometown = pdata.get('hometown', '')
                        if hometown and ',' not in hometown:
                            # Hometown doesn't have state - add team's state abbreviation
                            team_state = team_state_map.get(team_id)
                            if team_state:
                                pdata['hometown'] = f"{hometown}, {team_state}"
                
                writer.writerow(pdata)

        logger.info(f"Saved {len(players)} {entity_label} to {output_file}")

    def save_zero_player_teams_to_csv(self, output_file: str):
        """Save teams with zero scraped players to CSV file"""
        if not self.zero_player_teams:
            logger.info("No teams with zero players to save")
            return

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['team_id', 'team_name']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for team in self.zero_player_teams:
                writer.writerow(team)

        logger.info(f"Saved {len(self.zero_player_teams)} teams with zero players to {output_file}")

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
                # Use transformed season for four_digit_year format teams
                verification_season = season
                # Teams using four_digit_year format (2025-26 becomes 2025-2026)
                if (url_format == 'four_digit_year' or 
                    team['ncaa_id'] in [209, 339, 340, 77, 670, 1013, 11403, 11504] or
                    team['url'].startswith('https://hawaiiathletics.com')):
                    verification_season = f"{season[:4]}-{season[:2]}{season[-2:]}"
                return SeasonVerifier.verify_season_on_page(html, verification_season, entity_type=self.entity_type, team_id=team['ncaa_id'])
            
            return True  # Assume OK for non-Sidearm sites
        except Exception as e:
            logger.warning(f"Failed to verify season for {team['team']}: {e}")
            return True  # Default to True if verification fails

    def fetch_html(self, url: str, return_status: bool = False) -> Optional[Union[BeautifulSoup, tuple]]:
        """Fetch and parse HTML from URL
        
        Args:
            url: URL to fetch
            return_status: If True, return (html, status_code) tuple instead of just html
        
        Returns:
            BeautifulSoup object if return_status=False, or (BeautifulSoup, status_code) tuple if return_status=True
        """
        try:
            response = requests.get(url, timeout=30, verify=False)
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
        """Save teams that failed the year check to CSV file"""
        if not self.failed_year_check_teams:
            logger.info("No teams failed the year check")
            return

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['team_id', 'team_name', 'url']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for team in self.failed_year_check_teams:
                writer.writerow(team)

        logger.info(f"Saved {len(self.failed_year_check_teams)} teams that failed year check to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='NCAA Women\'s Basketball Roster Scraper - Refactored')
    parser.add_argument('-season', required=True, help='Season (e.g., "2023-24")')
    parser.add_argument('-teams', nargs='*', type=int, help='Specific team IDs to scrape')
    parser.add_argument('-team', type=int, help='Single team ID to scrape')
    parser.add_argument('-output', help='Output CSV file path')
    parser.add_argument('-url', help='Base URL for single team scraping')
    parser.add_argument('-entity', '--entity-type', 
                       choices=['player', 'coach', 'all'], 
                       default='player',
                       help='Type of entity to scrape: player, coach, or all (default: player)')
    parser.add_argument('--use-playwright', action='store_true', help='Use Playwright instead of shot-scraper')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    manager = RosterManager(entity_type=args.entity_type)

    # Handle single team with URL
    if args.url and args.team:
        teams = manager.get_teams([args.team])
        if teams:
            team_data = teams[0].copy()
            team_data['url'] = args.url
        else:
            team_data = {'ncaa_id': args.team, 'team': f'Team_{args.team}', 'url': args.url}
        
        players = manager.scrape_team_roster(team_data, args.season)
        
        # Check year verification for single team case
        year_check_failed = not manager._verify_team_season(team_data, args.season)
        
        if year_check_failed:
            manager.failed_year_check_teams.append({
                'team_id': team_data['ncaa_id'],
                'team_name': team_data.get('team', f'Team_{team_data["ncaa_id"]}'),
                'url': team_data['url']
            })
        
        # Only add to zero players if year check passed but no players found
        if len(players) == 0 and not year_check_failed:
            manager.zero_player_teams.append({
                'team_id': team_data['ncaa_id'],
                'team_name': team_data.get('team', f'Team_{team_data["ncaa_id"]}')
            })
        
        if args.output:
            manager.save_to_csv(players, args.output)
            if manager.zero_player_teams:
                zero_output_file = args.output.replace('.csv', '_zero_players.csv')
                manager.save_zero_player_teams_to_csv(zero_output_file)
            if manager.failed_year_check_teams:
                failed_year_output_file = args.output.replace('.csv', '_failed_year_check.csv')
                manager.save_failed_year_check_teams_to_csv(failed_year_output_file)
        else:
            for player in players:
                print(json.dumps(player.to_dict(), indent=2))
        return

    # Handle multiple teams
    team_ids = None
    if args.teams:
        team_ids = args.teams
    elif args.team:
        team_ids = [args.team]

    # Handle 'all' entity type - scrape both players and coaches
    if args.entity_type == 'all':
        logger.info("Scraping both players and coaches")
        
        # Scrape players
        logger.info("=== Scraping Players ===")
        player_manager = RosterManager(entity_type='player')
        players = player_manager.scrape_multiple_teams(args.season, team_ids)
        
        # Determine player output file
        if args.output:
            player_output = args.output.replace('.csv', '_players.csv')
        elif team_ids and len(team_ids) == 1:
            player_output = f"/Users/dwillis/code/wbb/ncaa/rosters_{args.season}_team_{team_ids[0]}.csv"
        else:
            player_output = f"/Users/dwillis/code/wbb/ncaa/rosters_{args.season}.csv"
        
        player_manager.save_to_csv(players, player_output)
        
        # Scrape coaches
        logger.info("=== Scraping Coaches ===")
        coach_manager = RosterManager(entity_type='coach')
        coaches = coach_manager.scrape_multiple_teams(args.season, team_ids)
        
        # Determine coach output file
        if args.output:
            coach_output = args.output.replace('.csv', '_coaches.csv')
        elif team_ids and len(team_ids) == 1:
            coach_output = f"/Users/dwillis/code/wbb/ncaa/coaches_{args.season}_team_{team_ids[0]}.csv"
        else:
            coach_output = f"/Users/dwillis/code/wbb/ncaa/coaches_{args.season}.csv"
        
        coach_manager.save_to_csv(coaches, coach_output)
        
        # Save zero player/coach teams if any
        if player_manager.zero_player_teams:
            zero_output = player_output.replace('.csv', '_zero_players.csv')
            player_manager.save_zero_player_teams_to_csv(zero_output)
        
        if coach_manager.zero_player_teams:
            zero_output = coach_output.replace('.csv', '_zero_coaches.csv')
            coach_manager.save_zero_player_teams_to_csv(zero_output)
        
        # Save failed year check teams if any
        if player_manager.failed_year_check_teams:
            failed_output = player_output.replace('.csv', '_failed_year_check.csv')
            player_manager.save_failed_year_check_teams_to_csv(failed_output)
            
    else:
        # Single entity type scraping
        players = manager.scrape_multiple_teams(args.season, team_ids)
        
        # Determine output file based on entity type
        entity_prefix = ENTITY_CONFIGS[args.entity_type]['csv_prefix']
        if args.output:
            output_file = args.output
        elif team_ids and len(team_ids) == 1:
            output_file = f"/Users/dwillis/code/wbb/ncaa/{entity_prefix}_{args.season}_team_{team_ids[0]}.csv"
        else:
            output_file = f"/Users/dwillis/code/wbb/ncaa/{entity_prefix}_{args.season}.csv"

        manager.save_to_csv(players, output_file)
        
        # Save teams with zero players
        if manager.zero_player_teams:
            zero_output_file = output_file.replace('.csv', '_zero_players.csv')
            manager.save_zero_player_teams_to_csv(zero_output_file)

        # Save teams that failed the year check
        if manager.failed_year_check_teams:
            failed_year_output_file = output_file.replace('.csv', '_failed_year_check.csv')
            manager.save_failed_year_check_teams_to_csv(failed_year_output_file)


if __name__ == "__main__":
    main()
