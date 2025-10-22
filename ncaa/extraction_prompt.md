# Prompt: Extract Career History and Education from Coach Biographies

Given coach biography text, extract structured data for career positions, education and playing career history.

## Output Format

For each coach, create only a valid JSON object with three arrays:

### 1. positions array
Each position object should contain:

{
  "college": "name of school",
  "title": "job title",
  "start_year": starting_year,
  "end_year": ending_year_or_null
}

### 2. education array
Each education object should contain:
{
  "college": "name of college",
  "degree": "Bachelors|Masters|Doctorate",
  "year": graduation_year
}

### 3. playing_career array
Each playing_career object should contain:

{
  "team": "name of college or professional team",
  "level: "college or professional",
  "start_year": starting year,
  "end_year": ending_year
}

## Extraction Rules

### For Positions:
- List positions in reverse chronological order (current position first)
- Current positions should have `end_year: null`
- Include all coaching positions, administrative roles, and relevant internships
- Extract years from phrases like:
  - "announced on Apr. 25, 2024" → start_year: 2024
  - "from 2014-18" → start_year: 2014, end_year: 2018
  - "previous nine seasons" (requires context calculation)
  - "enters her second season in 2025-26" → start_year: 2024

### For Education:
- Map degree types:
  - "bachelor's degree", "Bachelor of Arts", "B.A." → "Bachelors"
  - "master's degree", "Master's", "M.S.", "MBA" → "Masters"
  - "Ph.D.", "doctorate" → "Doctorate"
- Extract graduation year from phrases like:
  - "graduated from Kentucky in 1994"
  - "2025 graduate of East Tennessee State"
  - "completed her time at CSU" (may require inferring from context)

### For Playing Career:
- Only add an object if the coach played basketball
- List playing career in reverse chronological order (most recent team first)
- Extract years from phrases like:
  - "from 2014-18" → start_year: 2014, end_year: 2018
  - "previous nine seasons" (requires context calculation)
  - "enters her second season in 2025-26" → start_year: 2024
- If no playing history, return an empty array

## Examples

### Example 1: Stacy McIntyre

**Input text excerpt:**
"McIntyre was announced as the ninth head coach of Air Force Women's Basketball on Apr. 25, 2024, assuming the role after spending the previous nine seasons as an assistant under Chris Gobrecht and most recent five as associate head coach... In addition to one season with her at Yale, McIntyre was part of Gobrecht's staff at the University of Southern California for seven seasons. McIntyre has previous ties to the Mountain West, spending three years as an assistant coach at the University of Nevada... McIntyre graduated from Kentucky in 1994 with a Bachelor of Arts in Education."

**Output:**
{
  "positions": [
    {
      "college": "Air Force",
      "title": "Head Women's Basketball Coach",
      "start_year": 2024,
      "end_year": null
    },
    {
      "college": "Air Force",
      "title": "Associate Head Coach",
      "start_year": 2019,
      "end_year": 2024
    },
    {
      "college": "Air Force",
      "title": "Assistant Coach",
      "start_year": 2015,
      "end_year": 2019
    },
    {
      "college": "Yale",
      "title": "Assistant Coach",
      "start_year": 2014,
      "end_year": 2015
    },
    {
      "college": "USC",
      "title": "Assistant Coach",
      "start_year": 2007,
      "end_year": 2014
    },
    {
      "college": "Nevada",
      "title": "Assistant Coach",
      "start_year": 2004,
      "end_year": 2007
    }
  ],
  "education": [
    {
      "college": "Kentucky",
      "degree": "Bachelors",
      "year": 1994
    }
  ]
}

### Example 2: Adam Wardenburg

**Input text excerpt:**
"Air Force women's basketball and first-year head coach Stacy McIntyre announced the addition of Adam Wardenburg as the Falcons' newest Associate Head Coach, the program announced on June 5, 2024... Wardenburg arrives at the Academy after a second stint at Utah Valley, where he held the same title. In Wardenburg's 2023-24 at UVU... Wardenburg previously served as an assistant coach and offensive/recruiting coordinator for UVU from 2014-18... served as head coach for both men's and women's programs at Southern Virginia, heading up the Knights' men's program from 2019-2023 and serving one year at the helm of the women's team in 2018-19... serving as an assistant with the College of Southern Idaho's women's team in 2013-14... Wardenburg also served two seasons at Utah State on staff as Director of Operations (2011-13)... Wardenburg earned a bachelor's degree from alma mater Utah State in 2013 and received a Master's of Business Administration from Western Governors University in 2016."

**Output:**
{
  "positions": [
    {
      "college": "Air Force",
      "title": "Associate Head Coach",
      "start_year": 2024,
      "end_year": null
    },
    {
      "college": "Utah Valley",
      "title": "Associate Head Coach",
      "start_year": 2023,
      "end_year": 2024
    },
    {
      "college": "Southern Virginia",
      "title": "Head Men's Basketball Coach",
      "start_year": 2019,
      "end_year": 2023
    },
    {
      "college": "Southern Virginia",
      "title": "Head Women's Basketball Coach",
      "start_year": 2018,
      "end_year": 2019
    },
    {
      "college": "Utah Valley",
      "title": "Assistant Coach/Offensive Coordinator/Recruiting Coordinator",
      "start_year": 2014,
      "end_year": 2018
    },
    {
      "college": "College of Southern Idaho",
      "title": "Assistant Coach",
      "start_year": 2013,
      "end_year": 2014
    },
    {
      "college": "Utah State",
      "title": "Director of Operations",
      "start_year": 2011,
      "end_year": 2013
    }
  ],
  "education": [
    {
      "college": "Utah State",
      "degree": "Bachelors",
      "year": 2013
    },
    {
      "college": "Western Governors University",
      "degree": "Masters",
      "year": 2016
    }
  ]
}

### Example 3: Lauren Brocke (Shorter Career)

**Input text excerpt:**
"Lauren Brocke was announced to the Air Force women's basketball staff on June 21, 2023, following a two-year stint as assistant coach at Colorado College under head coach Katherine Menendez... Brocke was a four-year letter winner at Colorado State, playing for the Rams from 2018-2021, earning a Mountain West All-Academic selection in 2019 and serving on the Student-Athlete Advisory Committee. Brocke completed her time at CSU with a bachelor's degree in human resource management."

**Output:**
{
  "positions": [
    {
      "college": "Air Force",
      "title": "Assistant Coach, Recruiting Coordinator",
      "start_year": 2023,
      "end_year": null
    },
    {
      "college": "Colorado College",
      "title": "Assistant Coach",
      "start_year": 2021,
      "end_year": 2023
    }
  ],
  "education": [
    {
      "college": "Colorado State",
      "degree": "Bachelors",
      "year": 2021
    }
  ],
  "playing_career": [
    {
      "team": "Colorado State",
      "level: "college",
      "start_year": 2018,
      "end_year": 2021
    }
  ]
}

## Special Cases

- **Multiple positions at same institution**: Create separate entries for each distinct role
- **Concurrent roles**: List the primary title; you may combine related titles with slashes
- **Missing years**: Use null if year cannot be determined from context
- **Internships/Student positions**: Include if mentioned as part of career progression
- **Playing career**: Do NOT include undergraduate playing positions
- **Year ranges with context clues**: Calculate based on phrases like "previous nine seasons" or "enters her second season"

## Task

Apply this extraction process to the provided coach biography text and return structured JSON containing both `positions` and `education` arrays.