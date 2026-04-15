"""
Print a git commit message summarising what was added/removed in
transfers.json and coaching_changes.json compared to HEAD.
"""

import json
import subprocess
import sys
from pathlib import Path

UPDATES_DIR = Path(__file__).parent
REPO_ROOT = UPDATES_DIR.parent


def load_head(rel_path: str) -> list:
    """Return the JSON list from HEAD for a repo-relative path, or [] if new."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def diff_transfers(old: list, new: list) -> tuple[list, list]:
    def key(r):
        return (r.get("team", ""), r.get("name", ""), r.get("status", ""))

    old_keys = {key(r) for r in old}
    new_keys = {key(r) for r in new}

    added = [r for r in new if key(r) not in old_keys]
    removed = [r for r in old if key(r) not in new_keys]
    return added, removed


def diff_coaching(old: list, new: list) -> tuple[list, list]:
    def key(r):
        return (r.get("school", ""), r.get("coach", ""), r.get("role", ""))

    old_keys = {key(r) for r in old}
    new_keys = {key(r) for r in new}

    added = [r for r in new if key(r) not in old_keys]
    removed = [r for r in old if key(r) not in new_keys]
    return added, removed


def main():
    old_transfers = load_head("updates/transfers.json")
    new_transfers = json.loads((UPDATES_DIR / "transfers.json").read_text())

    old_coaching = load_head("updates/coaching_changes.json")
    new_coaching = json.loads((UPDATES_DIR / "coaching_changes.json").read_text())

    t_added, t_removed = diff_transfers(old_transfers, new_transfers)
    c_added, c_removed = diff_coaching(old_coaching, new_coaching)

    if not any([t_added, t_removed, c_added, c_removed]):
        print("chore: refresh data, no new entries [skip ci]")
        return

    parts = []

    if t_added:
        names = ", ".join(
            f"{r['name']} ({r['team']}, {r['status']})" for r in t_added[:5]
        )
        suffix = f" + {len(t_added) - 5} more" if len(t_added) > 5 else ""
        parts.append(f"transfers added: {names}{suffix}")

    if t_removed:
        parts.append(f"{len(t_removed)} transfer(s) removed")

    if c_added:
        names = ", ".join(
            f"{r['coach']} ({r['school']}, {r.get('role', '')})" for r in c_added[:5]
        )
        suffix = f" + {len(c_added) - 5} more" if len(c_added) > 5 else ""
        parts.append(f"coaching added: {names}{suffix}")

    if c_removed:
        parts.append(f"{len(c_removed)} coaching entry/entries removed")

    summary = "; ".join(parts)
    # Keep commit message under ~72 chars on first line with a body if needed
    headline = f"data: {summary[:200]} [skip ci]"
    print(headline)


if __name__ == "__main__":
    main()
