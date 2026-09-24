"""Diagnose why 269 teams are missing high_school values in 2026-27 rosters.

Reads ncaa/rosters/needs_hs.csv, cross-references ncaa/rosters/rosters_2026-27.csv
for player URLs, then for each team fetches:
  1. the roster page (derived from player-URL path)
  2. one sample player bio page for a player whose high_school is empty in the CSV

and records what platform the site uses and where HS data lives, so teams with
the same page format can be grouped and fixed together.

Results are cached per team in ncaa/scripts/hs_diagnosis/<team_id>.json; re-runs
skip teams already cached. Summary is written to ncaa/scripts/hs_diagnosis/summary.csv.
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parents[2]
ROSTERS = REPO / "ncaa" / "rosters"
OUT_DIR = Path(__file__).resolve().parent / "hs_diagnosis"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wbb-hs-diagnosis"}

FLAVORS = {
    "oas_table": "roster-players__group",
    "oas_card": "roster-card",
    "oas_list": "roster-list-item",
    "person_card": "s-person-card",
    "sidearm_classic": "sidearm-roster-player",
    "presto": "ViewArticle.dbml",
    "players_table": "players-table",
}

BIO_HS_MARKER = re.compile(r"High\s*School", re.I)


def load_inputs():
    need = {}
    with open(ROSTERS / "needs_hs.csv") as f:
        for r in csv.DictReader(f):
            need[r["ncaa_id"].strip()] = r["team"].strip()

    teams = {}
    with open(ROSTERS / "rosters_2026-27.csv") as f:
        for r in csv.DictReader(f):
            tid = r["team_id"]
            if tid not in need:
                continue
            t = teams.setdefault(
                tid,
                {
                    "name": r["team"],
                    "total": 0,
                    "no_hs": 0,
                    "miss_urls": [],
                    "has_urls": [],
                    "any_url": "",
                },
            )
            t["total"] += 1
            u = r.get("url") or ""
            if (r.get("high_school") or "").strip():
                if u and len(t["has_urls"]) < 2:
                    t["has_urls"].append(u)
            else:
                t["no_hs"] += 1
                if u and len(t["miss_urls"]) < 2:
                    t["miss_urls"].append(u)
            if u and not t["any_url"]:
                t["any_url"] = u
    return need, teams


def roster_url_from_player(player_url):
    """Derive a roster page URL from a player URL."""
    if not player_url:
        return ""
    # Carlow/Centenary style: /sports/wbkb/2026-27/bios/name_xxxx
    m = re.match(r"^(https?://[^/]+/.*)/bios/[^/]+$", player_url)
    if m:
        return m.group(1)
    m = re.match(r"^(https?://[^/]+(?:/[^/]+)*/roster)", player_url)
    if m:
        return m.group(1)
    return ""


def fetch(url, timeout=20):
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, f"__ERROR__ {type(e).__name__}"


def decode_nuxt(html):
    """Pull __NUXT_DATA__ and count persons with resolvable HS values."""
    out = {"present": False}
    m = re.search(
        r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S
    )
    if not m:
        return out
    out["present"] = True
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        out["parse_error"] = True
        return out
    out["entries"] = len(data)

    def rv(v):
        if isinstance(v, (int, float)):
            i = int(v)
            return data[i] if 0 <= i < len(data) else None
        return v

    for flavor, fk, hk in (
        ("snake", "first_name", "high_school"),
        ("camel", "firstName", "highSchool"),
    ):
        ln_key = "last_name" if flavor == "snake" else "lastName"
        persons = []
        for d in data:
            if isinstance(d, dict) and fk in d and hk in d:
                ln = rv(d.get(ln_key))
                if not (isinstance(ln, str) and ln.strip()):
                    continue
                hs = rv(d.get(hk))
                hs = hs.strip() if isinstance(hs, str) else ""
                if hs:
                    persons.append(
                        {"name": f"{rv(d.get(fk))} {ln}"[:60], "hs": hs[:80]}
                    )
        out[f"{flavor}_persons_with_hs"] = len(persons)
        out[f"{flavor}_sample"] = persons[:2]
    return out


def scan_roster(html):
    rec = {"size": len(html)}
    for flavor, marker in FLAVORS.items():
        rec[flavor] = html.count(marker)
    rec["sidearm_hs_class"] = html.count("sidearm-roster-player-highschool")
    rec["person_card_hs_dtid"] = html.count(
        "s-person-card-list__content-location-person-high-school"
    )
    rec["bio_fields_component"] = html.count("roster-bio-player-fields-component")
    rec["th_high_school"] = 0
    try:
        soup = BeautifulSoup(html, "html.parser")
        ths = [
            th.get_text(strip=True)
            for th in soup.find_all("th")
        ]
        rec["th_high_school"] = sum(
            1 for t in ths if t and "high school" in t.lower()
        )
        rec["th_sample"] = [t for t in ths if t][:12]
    except Exception:
        pass
    rec.update(decode_nuxt(html))
    return rec


def scan_bio(html):
    rec = {"size": len(html)}
    rec["bio_fields_component"] = html.count("roster-bio-player-fields-component")
    rec["field_label_class"] = html.count("sidearm-roster-player-field-label")
    # extract High School label/value pairs from new OAS bio markup
    pairs = re.findall(
        r"High\s*School\s*:?\s*</dt>\s*<dd[^>]*>([^<]{1,120})</dd>", html
    )
    if not pairs:
        # old markup: <span class="sidearm-roster-player-field-label">High School</span> ... value
        pairs = re.findall(
            r'sidearm-roster-player-field-label[^>]*>\s*High\s*School\s*</span>[^<]*<[^>]*>([^<]{1,120})<',
            html,
        )
    if not pairs:
        pairs = re.findall(
            r'data-test-id="s-person-details__bio-stats-person-high-school"[^>]*>([^<]{1,120})<',
            html,
        )
    rec["bio_hs_values"] = [p.strip() for p in pairs if p.strip()][:3]
    return rec


def diagnose_team(tid, info, session=None):
    player_urls = info["miss_urls"] or info["has_urls"] or [info["any_url"]]
    rurl = roster_url_from_player(player_urls[0])
    rec = {
        "team_id": tid,
        "team": info["name"],
        "total": info["total"],
        "no_hs": info["no_hs"],
        "roster_url": rurl,
    }
    if rurl:
        status, html = fetch(rurl)
        rec["roster_status"] = status
        if not html.startswith("__ERROR__"):
            rec["roster"] = scan_roster(html)
        else:
            rec["roster_error"] = html.replace("__ERROR__ ", "")
    # bio page of a missing-HS player
    if info["miss_urls"]:
        burl = info["miss_urls"][0]
        status, bhtml = fetch(burl)
        rec["bio_url"] = burl
        rec["bio_status"] = status
        rec["bio_player_missing_hs"] = True
        if not bhtml.startswith("__ERROR__"):
            rec["bio_missing"] = scan_bio(bhtml)
        else:
            rec["bio_error"] = bhtml.replace("__ERROR__ ", "")
    # bio page of a player that HAS hs (sanity check for extraction)
    if info["has_urls"]:
        burl = info["has_urls"][0]
        status, bhtml = fetch(burl)
        rec["bio_has_url"] = burl
        rec["bio_has_status"] = status
        if not bhtml.startswith("__ERROR__"):
            rec["bio_has_hs"] = scan_bio(bhtml)
    return rec


def main():
    need, teams = load_inputs()
    OUT_DIR.mkdir(exist_ok=True)
    remaining = [tid for tid in need if tid in teams and not (OUT_DIR / f"{tid}.json").exists()]
    print(f"{len(need)} teams in needs_hs.csv; {len(remaining)} to fetch", file=sys.stderr)
    for i, tid in enumerate(sorted(remaining, key=lambda t: need[t]), 1):
        try:
            rec = diagnose_team(tid, teams[tid])
        except Exception as e:
            rec = {"team_id": tid, "team": need[tid], "fatal": f"{type(e).__name__}: {e}"}
        with open(OUT_DIR / f"{tid}.json", "w") as f:
            json.dump(rec, f, indent=1)
        # brief progress to stderr every 10 teams
        if i % 10 == 0:
            print(f"  {i}/{len(remaining)} done", file=sys.stderr)
        time.sleep(0.2)

    # summary
    rows = []
    for tid in need:
        p = OUT_DIR / f"{tid}.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        ro = r.get("roster", {})
        rows.append(
            {
                "team_id": tid,
                "team": r.get("team"),
                "total": r.get("total"),
                "no_hs": r.get("no_hs"),
                "roster_status": r.get("roster_status"),
                "oas_table": ro.get("oas_table", 0),
                "oas_card": ro.get("oas_card", 0),
                "oas_list": ro.get("oas_list", 0),
                "person_card": ro.get("person_card", 0),
                "sidearm_classic": ro.get("sidearm_classic", 0),
                "players_table": ro.get("players_table", 0),
                "presto": ro.get("presto", 0),
                "nuxt": ro.get("present", False),
                "snake_hs": ro.get("snake_persons_with_hs", 0),
                "camel_hs": ro.get("camel_persons_with_hs", 0),
                "roster_hs_class": ro.get("sidearm_hs_class", 0),
                "person_card_hs_dtid": ro.get("person_card_hs_dtid", 0),
                "th_hs": ro.get("th_high_school", 0),
                "bio_missing_hs_found": "; ".join(r.get("bio_missing", {}).get("bio_hs_values", [])),
                "bio_missing_has_component": r.get("bio_missing", {}).get("bio_fields_component", 0),
                "bio_missing_has_fieldlabel": r.get("bio_missing", {}).get("field_label_class", 0),
                "roster_url": r.get("roster_url", ""),
            }
        )
    with open(OUT_DIR / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            w.writeheader()
            w.writerows(rows)
    print(f"summary: {OUT_DIR / 'summary.csv'}", file=sys.stderr)


if __name__ == "__main__":
    main()