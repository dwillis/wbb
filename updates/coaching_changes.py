import json
import re

import requests
from bs4 import BeautifulSoup

API_URL = "https://wbbblog.com/wp-json/wp/v2/posts/62914"
OUTPUT_FILE = "coaching_changes.json"

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

HIRED_RE = re.compile(r"\b(hired|named)\b", re.IGNORECASE)


def infer_role(text):
    """Return 'hired' if text describes a hire, otherwise 'departed'."""
    return "hired" if HIRED_RE.search(text) else "departed"


DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)


def parse_date(text):
    match = DATE_PATTERN.search(text)
    if match:
        month_str = match.group(1).rstrip(".").lower()
        day = int(match.group(2))
        year = int(match.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def parse_school_conference(h3):
    text = h3.get_text()
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", text.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text.strip(), ""


def get_press_release_url(li):
    for a in li.find_all("a", href=True):
        href = a["href"]
        if "wbbblog.com" not in href:
            return href
    return None


def main():
    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    html_content = data["content"]["rendered"]
    soup = BeautifulSoup(html_content, "html.parser")

    entries = []
    current_status = None
    current_school = None
    current_conference = None

    for element in soup.find_all(["h2", "h3", "ul"]):
        if element.name == "h2":
            heading = element.get_text().strip().upper()
            if "JOBS OPEN" in heading:
                current_status = "Jobs Open"
            elif "JOBS FILLED" in heading:
                current_status = "Jobs Filled"
            else:
                current_status = None
            current_school = None
            current_conference = None

        elif element.name == "h3" and current_status:
            current_school, current_conference = parse_school_conference(element)

        elif element.name == "ul" and current_status and current_school:
            for li in element.find_all("li", recursive=False):
                strong = li.find("strong")
                coach = strong.get_text().strip() if strong else None
                raw = re.sub(r"\s+", " ", li.get_text(separator=" ")).strip()
                text = re.sub(r"\s+([).,;])", r"\1", raw)
                entries.append(
                    {
                        "status": current_status,
                        "school": current_school,
                        "conference": current_conference,
                        "coach": coach,
                        "role": infer_role(text),
                        "text": text,
                        "date": parse_date(text),
                        "url": get_press_release_url(li),
                    }
                )

    with open(OUTPUT_FILE, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"Wrote {len(entries)} entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
