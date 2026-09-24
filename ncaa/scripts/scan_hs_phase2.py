"""Phase-2 HS scan: for teams whose roster page has no __NUXT_DATA__ payload,
re-fetch the roster page and look for HS values in:

  1. classic Sidearm Vue component JSON  ("players":[...] with a
     "highschool" key inside vue-roster-template scripts)
  2. old Sidearm server-rendered markup   (non-empty
     sidearm-roster-player-highschool spans; data-label="High School" cells)
  3. responsive-table data-label cells    (data-label="Hometown / High School"
     and friends, with values)
  4. PrestoSports-style combined columns  (data-field="hometown:/:custom2")

Writes ncaa/scripts/hs_diagnosis/phase2.csv with per-team counts of HS values
present in the static roster HTML.
"""

import csv
import json
import re
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DIAG = HERE / "hs_diagnosis"
REPO = HERE.parents[2]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wbb-hs-diagnosis"}


def vue_json_players(html):
    """Extract players arrays from classic Sidearm Vue component scripts.

    Uses bracket matching rather than a regex lookahead: what follows the
    array varies by site (all_staff_image, coaches, staff, ...).
    """
    players = []
    pos = 0
    while True:
        i = html.find('"players":', pos)
        if i < 0:
            break
        start = i + len('"players":')
        if html[start] != "[":
            pos = start
            continue
        depth = 0
        end = -1
        for j in range(start, min(start + 2_000_000, len(html))):
            c = html[j]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end < 0:
            break
        try:
            arr = json.loads(html[start : end + 1])
            if isinstance(arr, list):
                players.extend(p for p in arr if isinstance(p, dict))
        except (json.JSONDecodeError, ValueError):
            pass
        pos = end + 1
    return players


def scan(html):
    rec = {}
    players = vue_json_players(html)
    rec["vue_json_players"] = len(players)
    rec["vue_json_hs"] = sum(1 for p in players if (p.get("highschool") or "").strip())

    # old sidearm list spans (roster markup is served once per view; dedupe)
    vals = [v.strip() for v in re.findall(r'class="sidearm-roster-player-highschool[^"]*"[^>]*>([^<]+)<', html)]
    distinct = sorted(set(vals))
    rec["sidearm_hs_values"] = len(distinct)
    rec["sidearm_hs_sample"] = distinct[:3]

    # responsive table cells with an HS-ish data-label
    rec["dl_hs_cells"] = 0
    rec["dl_hs_nonempty"] = 0
    for label_pat in (r'[Hh]igh [Ss]chool', r'[Ss]econdary [Ss]chool', r'[Ll]ast [Ss]chool', r'Hometown /[^\"]*School'):
        for m in re.finditer(r'data-label="([^"]*%s[^"]*)"[^>]*>([^<]*)<' % label_pat, html):
            rec["dl_hs_cells"] += 1
            if m.group(2).strip():
                rec["dl_hs_nonempty"] += 1

    # combined presto column
    rec["presto_combined"] = sum(
        1 for m in re.finditer(r'data-field="hometown:/:custom2"[^>]*>(.*?)</td>', html, re.S)
        if "/" in m.group(1)
    )
    return rec


def main():
    rows = []
    for p in sorted(DIAG.glob("*.json")):
        if p.stem == "summary":
            continue
        d = json.loads(p.read_text())
        if "fatal" in d or not d.get("roster"):
            continue
        if d["roster"].get("present"):
            continue  # has Nuxt payload; phase 1 already covers it
        rurl = d.get("roster_url")
        if not rurl:
            continue
        try:
            resp = requests.get(rurl, headers=UA, timeout=20)
            html = resp.text
        except requests.RequestException as e:
            rows.append({"team_id": d["team_id"], "team": d["team"], "error": type(e).__name__})
            continue
        rec = scan(html)
        rec.update(team_id=d["team_id"], team=d["team"], no_hs=d["no_hs"], total=d["total"])
        rows.append(rec)

    out = DIAG / "phase2.csv"
    fields = ["team_id", "team", "total", "no_hs", "vue_json_players", "vue_json_hs",
              "sidearm_hs_values", "dl_hs_cells", "dl_hs_nonempty", "presto_combined",
              "sidearm_hs_sample", "error"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()