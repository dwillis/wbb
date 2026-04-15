import json
import re

import requests
from bs4 import BeautifulSoup

API_URL = "https://wbbblog.com/wp-json/wp/v2/posts/59451"
OUTPUT_FILE = "transfers.json"

PORTAL_DATE_RE = re.compile(r"entered portal\s+(\d+)/(\d+)/(\d+)", re.IGNORECASE)

# Matches: height  year  position (stops at comma, (, {, → or end)
HEIGHT_YEAR_POS_RE = re.compile(
    r"(\d-\d{1,2})\s+"
    r"((?:RS\s+)?(?:FR|SO|JR|SR|GR))\s+"
    r"([^,{(→]+?)(?=\s*,|\s*\(|\s*[{→]|$)",
    re.IGNORECASE,
)


def parse_portal_date(brace_text):
    m = PORTAL_DATE_RE.search(brace_text)
    if not m:
        return None
    month, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{2000 + yr:04d}-{month:02d}-{day:02d}"


def parse_transfer_history(brace_text):
    m = re.search(r"transfer history\s*:\s*(.+)", brace_text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def find_strong(group):
    """Return the first <strong> element found in a list of elements."""
    for el in group:
        if not hasattr(el, "name"):
            continue
        if el.name == "strong":
            return el
        if el.name in ("em", "span"):
            s = el.find("strong")
            if s:
                return s
    return None


def has_bullet_player(group):
    s = find_strong(group)
    return s is not None and ("\u2022" in s.get_text() or "\u2022" in s.get_text())


def group_has_player_bullet(group):
    s = find_strong(group)
    if s:
        t = s.get_text()
        if "\u2022" in t or "•" in t:
            return True
    return False


def get_group_text(group):
    parts = []
    for el in group:
        if hasattr(el, "get_text"):
            parts.append(el.get_text())
        else:
            parts.append(str(el))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def get_status(group):
    """Return 'In', 'Out', or None if this group is a status-section header."""
    for el in group:
        if hasattr(el, "name") and el.name == "span":
            style = el.get("style", "")
            if "underline" in style:
                text = el.get_text(strip=True).upper()
                if text == "IN":
                    return "In"
                if text == "OUT":
                    return "Out"
    return None


def split_by_br(tag):
    """Yield lists of children separated by <br> elements."""
    current = []
    for child in tag.children:
        if hasattr(child, "name") and child.name == "br":
            yield current
            current = []
        else:
            current.append(child)
    if current:
        yield current


def parse_player(team, status, group):
    strong = find_strong(group)
    if not strong:
        return None

    strong_text = strong.get_text(strip=True).lstrip("\u2022").lstrip("•").strip()
    # Name ends at first comma if the whole description is crammed in <strong>
    name = strong_text.split(",")[0].strip()
    if not name:
        return None

    full_text = get_group_text(group)
    full_text = re.sub(r"^[\u2022•\s]+", "", full_text).strip()

    # Brace content
    brace_match = re.search(r"\{([^}]+)\}", full_text)
    brace_content = brace_match.group(1) if brace_match else ""

    entered_portal = parse_portal_date(brace_content)
    transfer_history = parse_transfer_history(brace_content)

    # Text before the brace block
    pre_brace = full_text.split("{")[0].strip() if "{" in full_text else full_text
    # Strip name from front
    if pre_brace.startswith(name):
        remainder = pre_brace[len(name):].lstrip(",").strip()
    else:
        remainder = pre_brace
    # Strip destination arrow
    remainder = re.sub(r"\s*→.*$", "", remainder).strip()

    height = year = position = hometown = None
    m = HEIGHT_YEAR_POS_RE.match(remainder)
    if m:
        height = m.group(1)
        year = re.sub(r"\s+", " ", m.group(2)).strip()
        position = m.group(3).strip()

        after = remainder[m.end():].lstrip(",").strip()
        # Remove trailing qualifiers like (grad xfer)
        after = re.sub(r"\s*\([^)]+\)\s*$", "", after).strip()
        # Remove "/ PreviousSchool" suffix (IN entries)
        after = re.sub(r"\s*/[^{]+$", "", after).strip()
        hometown = after if after else None

    return {
        "team": team,
        "status": status,
        "name": name,
        "height": height,
        "year": year,
        "position": position,
        "hometown": hometown,
        "entered_portal": entered_portal,
        "transfer_history": transfer_history,
    }


def main():
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    soup = BeautifulSoup(data["content"]["rendered"], "html.parser")

    entries = []
    current_team = None

    for el in soup.find_all(["h2", "p"]):
        if el.name == "h2":
            team_text = re.sub(r"\s+", " ", el.get_text()).strip()
            # Skip pagination labels
            if not re.search(r"\bback\b|\bpage\b", team_text, re.IGNORECASE):
                current_team = team_text

        elif el.name == "p" and current_team:
            current_status = None
            for group in split_by_br(el):
                status = get_status(group)
                if status:
                    current_status = status
                    continue
                if current_status and group_has_player_bullet(group):
                    record = parse_player(current_team, current_status, group)
                    if record:
                        entries.append(record)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"Wrote {len(entries)} entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
