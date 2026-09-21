"""JavaScript templates for dynamic roster pages.

Moved verbatim from ncaa/rosters/rosters.py L423-1391 (JSTemplates).
Do not reformat: these are live-site JS strings."""

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
            
            const nameMatch = fullText.match(/Jersey Number \\d+([\\s\\S]+?)Position/);
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
            
            // Get academic year (some Sidearm layouts put this in custom1/custom2)
            const yearElem = player.querySelector('.sidearm-roster-player-academic-year, .sidearm-roster-player-academic-year-long');
            let year = yearElem ? yearElem.textContent.trim() : '';
            if (!year) {
                // fallback: Sidearm sometimes stores the year in custom1/custom2 spans
                const custom1 = player.querySelector('.sidearm-roster-player-custom1, .sidearm-roster-list-item-custom1');
                const custom2 = player.querySelector('.sidearm-roster-player-custom2, .sidearm-roster-list-item-custom2');
                if (custom1 && custom1.textContent && custom1.textContent.trim()) {
                    year = custom1.textContent.trim();
                } else if (custom2 && custom2.textContent && custom2.textContent.trim()) {
                    // Only use custom2 as a fallback if custom1 isn't present
                    year = custom2.textContent.trim();
                }
            }
            
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
            
            // Get academic year (fall back to custom1/custom2 if necessary)
            const yearElem = item.querySelector('.sidearm-roster-list-item-year, .sidearm-roster-list-item-academic-year, .sidearm-roster-player-academic-year');
            let year = yearElem ? yearElem.textContent.trim() : '';
            if (!year) {
                const custom1 = item.querySelector('.sidearm-roster-list-item-custom1, .sidearm-roster-player-custom1');
                const custom2 = item.querySelector('.sidearm-roster-list-item-custom2, .sidearm-roster-player-custom2');
                if (custom1 && custom1.textContent && custom1.textContent.trim()) {
                    year = custom1.textContent.trim();
                } else if (custom2 && custom2.textContent && custom2.textContent.trim()) {
                    year = custom2.textContent.trim();
                }
            }
            
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
