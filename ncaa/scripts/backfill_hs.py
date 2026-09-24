"""Backfill missing high_school values in a season roster CSV.

Two independent passes (run with --mode payload, --mode prevschool, or --mode both):

  payload    For teams whose Sidearm OAS roster page embeds high_school in the
             static __NUXT_DATA__ payload but renders no high_school in the DOM
             (group "fixable_payload" in hs_diagnosis/final_groups.csv), fetch
             the roster page, decode the payload (snake_case first_name/high_school
             and camelCase firstName/highSchool person entities), and fill empty
             high_school cells by exact normalized-name match.

  prevschool Some sites combine hometown / high school / previous school into one
             column, and values that are clearly high school names end up in
             previous_school. For rows where high_school is empty and
             previous_school looks like a high school (contains HS / High School /
             Academy / Prep), route the value:
               - plain value            -> high_school (previous_school cleared)
               - "HS (Previous College)" -> high_school=HS, previous_school=paren part
               - "HS / College" or
                 "College / HS"         -> high_school=HS part, previous_school=rest

Reads and rewrites ncaa/rosters/rosters_<season>.csv in place (CRLF preserved).
A timestamped backup and an append-only audit CSV are written to
ncaa/scripts/hs_diagnosis/. Use --dry-run to preview without writing.
"""

import argparse
import csv
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
ROSTERS = REPO / "ncaa" / "rosters"
DIAG = REPO / "ncaa" / "scripts" / "hs_diagnosis"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) wbb-hs-backfill"}

HS_HINT = re.compile(r"\b(HS|High School|Academy|Prep)\b")
PAREN_SUFFIX = re.compile(r"^(.*?)\s*\((.*)\)\s*$", re.S)


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def load_season_csv(season: str):
    path = ROSTERS / f"rosters_{season}.csv"
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    return path, fields, rows


def roster_url_from_player(player_url: str) -> str:
    """Derive the (default) roster page URL from a player URL."""
    m = re.match(r"^(https?://[^/]+(?:/[^/]+)*/roster)", player_url or "")
    return m.group(1) if m else ""


def decode_nuxt_hs(html: str):
    """Extract {normalized name: high_school} from __NUXT_DATA__ person entities."""
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    def rv(v):
        if isinstance(v, (int, float)):
            i = int(v)
            return data[i] if 0 <= i < len(data) else None
        return v

    found = {}
    ambiguous = set()
    for flavor, fk, hk in (
        ("snake", "first_name", "high_school"),
        ("camel", "firstName", "highSchool"),
    ):
        ln_key = "last_name" if flavor == "snake" else "lastName"
        for d in data:
            if not (isinstance(d, dict) and fk in d and hk in d):
                continue
            ln = rv(d.get(ln_key))
            if not (isinstance(ln, str) and ln.strip()):
                continue
            hs = rv(d.get(hk))
            hs = hs.strip() if isinstance(hs, str) else ""
            if not hs:
                continue
            key = norm(f"{rv(d.get(fk))} {ln}")
            if not key:
                continue
            if key in found and found[key] != hs:
                ambiguous.add(key)
            else:
                found[key] = hs
    for k in ambiguous:
        found.pop(k, None)
    return found


def team_roster_urls(rows, team_id: str):
    """One roster URL per team, derived from that team's player URLs."""
    urls = []
    for r in rows:
        if r["team_id"] == team_id and r.get("url"):
            u = roster_url_from_player(r["url"])
            if u and u not in urls:
                urls.append(u)
    return urls


def payload_fixable_teams():
    """Team IDs classified fixable_payload in hs_diagnosis/final_groups.csv."""
    path = DIAG / "final_groups.csv"
    if not path.exists():
        sys.exit(f"missing {path} — run group_hs_diagnosis.py first")
    with open(path, newline="") as f:
        return {
            r["team_id"]: r["team"]
            for r in csv.DictReader(f)
            if r["group"] == "fixable_payload"
        }


def apply_payload(rows, audit):
    teams = payload_fixable_teams()
    n_fixed = 0
    for tid, name in sorted(teams.items(), key=lambda kv: kv[1]):
        team_rows = [r for r in rows if r["team_id"] == tid]
        empty = [r for r in team_rows if not (r.get("high_school") or "").strip()]
        if not empty:
            print(f"  {name} (ID {tid}): nothing to do", file=sys.stderr)
            continue
        hs_map = None
        url_used = ""
        for u in team_roster_urls(rows, tid):
            try:
                resp = requests.get(u, headers=UA, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  {name}: fetch failed {u}: {e}", file=sys.stderr)
                continue
            hs_map = decode_nuxt_hs(resp.text)
            url_used = u
            if hs_map:
                break
        if not hs_map:
            print(f"  {name} (ID {tid}): no payload HS found", file=sys.stderr)
            continue
        fixed = unmatched = ambiguous = 0
        for r in empty:
            hs = hs_map.get(norm(r["name"]))
            if not hs:
                unmatched += 1
                continue
            r["high_school"] = hs
            n_fixed += 1
            fixed += 1
            audit.append({
                "mode": "payload", "team_id": tid, "team": name, "name": r["name"],
                "high_school_old": "", "high_school_new": hs,
                "previous_school_old": r.get("previous_school", ""),
                "previous_school_new": r.get("previous_school", ""),
                "rule": "nuxt-payload", "source": url_used,
            })
        print(f"  {name} (ID {tid}): filled {fixed}, unmatched {unmatched} "
              f"of {len(empty)} empty ({len(hs_map)} payload values)", file=sys.stderr)
    return n_fixed


def route_previous_school(prev: str):
    """Return (high_school, previous_school, rule) or None if not clearly a HS."""
    prev = (prev or "").strip()
    if not prev or not HS_HINT.search(prev):
        return None
    m = PAREN_SUFFIX.match(prev)
    if m and HS_HINT.search(m.group(1)):
        core = m.group(1).strip()
        paren = m.group(2).strip()
        return core, paren, "paren-split"
    if "/" in prev:
        parts = [p.strip() for p in re.split(r"\s*/\s*", prev) if p.strip()]
        hs_idx = [i for i, p in enumerate(parts) if HS_HINT.search(p)]
        if len(hs_idx) == 1:
            i = hs_idx[0]
            rest = parts[:i] + parts[i + 1:]
            return parts[i], " / ".join(rest), "slash-split"
        return None
    return prev, "", "move"


def apply_prevschool(rows, audit):
    n_fixed = 0
    per_team = {}
    for r in rows:
        if (r.get("high_school") or "").strip():
            continue
        prev = (r.get("previous_school") or "").strip()
        if not prev:
            continue
        routed = route_previous_school(prev)
        if not routed:
            continue
        hs, new_prev, rule = routed
        r["high_school"] = hs
        r["previous_school"] = new_prev
        n_fixed += 1
        t = per_team.setdefault((r["team_id"], r["team"]), [0, ""])
        t[0] += 1
        t[1] = rule
        audit.append({
            "mode": "prevschool", "team_id": r["team_id"], "team": r["team"],
            "name": r["name"], "high_school_old": "", "high_school_new": hs,
            "previous_school_old": prev, "previous_school_new": new_prev,
            "rule": rule, "source": "previous_school",
        })
    for (tid, name), (n, _) in sorted(per_team.items(), key=lambda kv: -kv[1][0]):
        print(f"  {name} (ID {tid}): routed {n}", file=sys.stderr)
    return n_fixed


def write_season_csv(path, fields, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_audit(audit):
    out = DIAG / "backfill_audit.csv"
    fields = ["mode", "team_id", "team", "name", "high_school_old", "high_school_new",
              "previous_school_old", "previous_school_new", "rule", "source"]
    exists = out.exists()
    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerows(audit)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", default="2026-27", help='season, e.g. "2026-27"')
    ap.add_argument("--mode", choices=["payload", "prevschool", "both"], default="both")
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    args = ap.parse_args()

    path, fields, rows = load_season_csv(args.season)
    before = sum(1 for r in rows if not (r.get("high_school") or "").strip())
    print(f"{path.name}: {len(rows)} rows, {before} missing high_school", file=sys.stderr)

    audit = []
    if args.mode in ("payload", "both"):
        print(f"\n== payload pass ==", file=sys.stderr)
        n = apply_payload(rows, audit)
        print(f"payload pass: filled {n} rows", file=sys.stderr)
    if args.mode in ("prevschool", "both"):
        print(f"\n== previous_school pass ==", file=sys.stderr)
        n = apply_prevschool(rows, audit)
        print(f"previous_school pass: routed {n} rows", file=sys.stderr)

    after = sum(1 for r in rows if not (r.get("high_school") or "").strip())
    print(f"\nmissing high_school: {before} -> {after} (filled {before - after})",
          file=sys.stderr)

    if args.dry_run:
        print("dry run — CSV not written; audit not written", file=sys.stderr)
        return
    if before == after:
        print("no changes — CSV not written", file=sys.stderr)
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DIAG / f"backup_rosters_{args.season}_{stamp}.csv"
    shutil.copy2(path, backup)
    write_season_csv(path, fields, rows)
    write_audit(audit)
    print(f"wrote {path.name} (backup: {backup})", file=sys.stderr)
    print(f"audit: {DIAG / 'backfill_audit.csv'} ({len(audit)} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()