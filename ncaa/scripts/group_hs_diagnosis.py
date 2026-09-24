"""Aggregate ncaa/scripts/hs_diagnosis/<team_id>.json records into fix groups.

Produces ncaa/scripts/hs_diagnosis/groups.csv with one row per team:
  - fixable_payload  : roster __NUXT_DATA__ contains high_school values the
                       scrape missed (biggest fixable group)
  - genuine_gap      : scrape already captured every HS the site publishes
                       (missing rows are absent from the site itself)
  - bio_page_fixable : a sampled missing-HS player's bio page shows the HS
                       value, but the roster/bio extractor never reads the
                       new OAS bio markup
  - combined_column  : HS names are stored in the site's combined
                       "Hometown/Previous School" column and land in
                       previous_school (heuristic split needed)
  - unmapped_header  : roster table has an HS-style column the header map
                       doesn't know (e.g. "Secondary School")
  - site_publishes_none: no HS data found anywhere on the site
"""

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAG = HERE / "hs_diagnosis"
REPO = HERE.parents[1]  # HERE is ncaa/scripts/
ROSTERS = REPO / "ncaa" / "rosters"

HSISH = re.compile(r"high\s*school|secondary\s*school|last\s*school|prep\s*school", re.I)
HS_VALUE_HINT = re.compile(r"\b(HS|High School|Academy|Prep)\b|\bHS\b")
MAPPED_HEADERS = {
    "high school", "highschool", "last school", "high school/previous school",
    "hometown/high school", "hometown / high school", "hometown/last school",
    "hometown/high school/last school", "hometown / previous school / high school",
    "hometown/high school/previous school", "hometown/high school (former school)",
    "hometown/ high school", "hometown/high school/previous college",
    "hometown / high school / previous college", "hometown / high school / last college",
    "hometown / previous school", "hometown/previous school", "hometoown/high school",
}


def load():
    need = {}
    with open(ROSTERS / "needs_hs.csv") as f:
        for r in csv.DictReader(f):
            need[r["ncaa_id"].strip()] = r["team"].strip()

    csv26 = {}
    with open(ROSTERS / "rosters_2026-27.csv") as f:
        for r in csv.DictReader(f):
            tid = r["team_id"]
            t = csv26.setdefault(tid, {"n": 0, "hs": 0, "rows": []})
            t["n"] += 1
            if (r.get("high_school") or "").strip():
                t["hs"] += 1
            else:
                t["rows"].append(r)

    csv25 = {}
    try:
        with open(ROSTERS / "rosters_2025-26.csv") as f:
            for r in csv.DictReader(f):
                tid = r["team_id"]
                t = csv25.setdefault(tid, {"n": 0, "hs": 0})
                t["n"] += 1
                if (r.get("high_school") or "").strip():
                    t["hs"] += 1
    except FileNotFoundError:
        pass
    return need, csv26, csv25


def main():
    need, csv26, csv25 = load()
    rows = []
    for tid, name in need.items():
        p = DIAG / f"{tid}.json"
        rec = {"team_id": tid, "team": name}
        if not p.exists():
            rec["group"] = "not_scanned"
            rows.append(rec)
            continue
        d = json.loads(p.read_text())
        if "fatal" in d:
            rec["group"] = "scan_error"
            rec["note"] = d["fatal"][:80]
            rows.append(rec)
            continue
        ro = d.get("roster") or {}
        total, no_hs = d.get("total", 0), d.get("no_hs", 0)
        csv_hs = csv26.get(tid, {}).get("hs", 0)
        payload_hs = (ro.get("snake_persons_with_hs") or 0) + (ro.get("camel_persons_with_hs") or 0)
        bio_missing_hs = (d.get("bio_missing") or {}).get("bio_hs_values") or []
        bio_has_hs = (d.get("bio_has_hs") or {}).get("bio_hs_values") or []
        ths = [t for t in (ro.get("th_sample") or []) if HSISH.search(t or "")]
        unmapped = [t for t in ths if (t or "").strip().lower() not in MAPPED_HEADERS]
        # prev-school values in CSV that look like HS names
        hs_in_prev = sum(
            1 for r in csv26.get(tid, {}).get("rows", [])
            if HS_VALUE_HINT.search(r.get("previous_school") or "")
        ) if tid in csv26 else 0

        prev25 = csv25.get(tid)
        rec.update(
            total=total,
            no_hs=no_hs,
            csv_hs_26=csv_hs,
            hs_25=prev25["hs"] if prev25 else "",
            payload_hs=payload_hs,
            roster_flavor=(
                "oas_table" if ro.get("oas_table") else
                "oas_card" if ro.get("oas_card") else
                "oas_list" if ro.get("oas_list") else
                "person_card" if ro.get("person_card") else
                "sidearm_classic" if ro.get("sidearm_classic") else
                "presto" if ro.get("presto") else
                "other"
            ),
            nuxt=ro.get("present", False),
        )

        if payload_hs > csv_hs:
            rec["group"] = "fixable_payload"
            rec["fix_count"] = payload_hs - csv_hs
            rec["note"] = f"payload has {payload_hs} HS values, CSV captured {csv_hs}"
        elif bio_missing_hs:
            rec["group"] = "bio_page_fixable"
            rec["note"] = "missing player's bio page shows: " + "; ".join(bio_missing_hs[:2])
        elif unmapped:
            rec["group"] = "unmapped_header"
            rec["note"] = "unmapped HS-style column: " + "; ".join(unmapped[:3])
        elif hs_in_prev and payload_hs == 0 and not bio_missing_hs:
            rec["group"] = "combined_column"
            rec["note"] = f"{hs_in_prev} missing rows have HS-looking values in previous_school"
        elif payload_hs == csv_hs and payload_hs > 0:
            rec["group"] = "genuine_gap"
            rec["note"] = f"site publishes HS for only {payload_hs}/{total}"
        elif bio_has_hs and no_hs:
            # bios can carry HS for some players; the missing ones sampled as empty
            rec["group"] = "genuine_gap"
            rec["note"] = "site publishes HS on bios for some players; sampled missing player had none"
        else:
            rec["group"] = "site_publishes_none"
            rec["note"] = "no HS found in roster payload, table headers, or sampled bio"
        rows.append(rec)

    field_order = ["team_id", "team", "group", "fix_count", "total", "no_hs",
                   "csv_hs_26", "hs_25", "payload_hs", "roster_flavor", "nuxt", "note"]
    out = DIAG / "groups.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=field_order)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in field_order})

    from collections import Counter
    c = Counter(r["group"] for r in rows)
    print(f"wrote {out}")
    print()
    for g, n in c.most_common():
        tot_fix = sum(r.get("fix_count", 0) or 0 for r in rows if r["group"] == g)
        print(f"  {g:20s} {n:3d} teams" + (f"  ({tot_fix} recoverable HS values)" if tot_fix else ""))


if __name__ == "__main__":
    main()