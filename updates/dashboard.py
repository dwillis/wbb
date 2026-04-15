"""Generate a standalone HTML dashboard from transfers.json and coaching_changes.json."""

import json
import subprocess
from pathlib import Path

TRANSFERS_FILE = Path(__file__).parent / "transfers.json"
COACHING_FILE = Path(__file__).parent / "coaching_changes.json"
OUTPUT_FILE = Path(__file__).parent / "dashboard.html"


def get_git_log(n=20):
    try:
        result = subprocess.run(
            [
                "git", "log", "--oneline",
                "--pretty=format:%H|%h|%s|%an|%ad",
                "--date=format:%Y-%m-%d %H:%M",
                "-n", str(n),
                "--",
                "updates/transfers.json",
                "updates/coaching_changes.json",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "short": parts[1],
                    "message": parts[2],
                    "author": parts[3],
                    "date": parts[4],
                })
        return commits
    except Exception:
        return []


def main():
    transfers = json.loads(TRANSFERS_FILE.read_text())
    coaching = json.loads(COACHING_FILE.read_text())
    commits = get_git_log()

    transfers_json = json.dumps(transfers)
    coaching_json = json.dumps(coaching)
    commits_json = json.dumps(commits)

    generated = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%ad", "--date=format:%Y-%m-%d %H:%M UTC"],
        capture_output=True, text=True,
        cwd=Path(__file__).parent.parent,
    ).stdout.strip() or "unknown"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WBB Updates Dashboard</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #f0f2f5; color: #1a1a2e; }}
  header {{ background: #1a1a2e; color: #fff; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; }}
  header h1 {{ font-size: 1.4rem; font-weight: 700; }}
  header .generated {{ margin-left: auto; font-size: 0.75rem; opacity: 0.6; }}
  .layout {{ display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr; gap: 1rem; padding: 1rem; max-width: 1600px; margin: 0 auto; }}
  .commits-panel {{ grid-column: 1 / -1; background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); overflow: hidden; }}
  .panel {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); overflow: hidden; display: flex; flex-direction: column; min-height: 0; }}
  .panel-header {{ padding: .75rem 1rem; background: #1a1a2e; color: #fff; display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }}
  .panel-header h2 {{ font-size: 1rem; font-weight: 600; }}
  .badge {{ background: #e63946; color: #fff; border-radius: 999px; padding: 1px 8px; font-size: 0.72rem; font-weight: 700; }}
  .controls {{ display: flex; gap: .5rem; margin-left: auto; flex-wrap: wrap; }}
  .controls input, .controls select {{ border: 1px solid #ccd; border-radius: 5px; padding: .3rem .6rem; font-size: .82rem; background: #1e2a3a; color: #fff; }}
  .controls input::placeholder {{ color: #aaa; }}
  .controls select option {{ background: #1e2a3a; }}
  .table-wrap {{ overflow-y: auto; flex: 1; max-height: 420px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
  th {{ position: sticky; top: 0; background: #e8eaf0; padding: .5rem .75rem; text-align: left; font-weight: 600; white-space: nowrap; z-index: 1; }}
  td {{ padding: .45rem .75rem; border-bottom: 1px solid #eee; vertical-align: top; }}
  tr:hover td {{ background: #f7f8fc; }}
  .status-pill {{ display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .72rem; font-weight: 700; }}
  .status-in {{ background: #d4edda; color: #155724; }}
  .status-out {{ background: #f8d7da; color: #721c24; }}
  .status-open {{ background: #fff3cd; color: #856404; }}
  .status-filled {{ background: #d4edda; color: #155724; }}
  .role-hired {{ background: #d1ecf1; color: #0c5460; }}
  .role-departed {{ background: #f8d7da; color: #721c24; }}
  .commit-list {{ padding: .75rem 1rem; display: flex; flex-direction: column; gap: .5rem; max-height: 220px; overflow-y: auto; }}
  .commit {{ display: flex; align-items: baseline; gap: .75rem; font-size: .82rem; border-bottom: 1px solid #f0f0f0; padding-bottom: .4rem; }}
  .commit:last-child {{ border-bottom: none; }}
  .commit .date {{ color: #888; white-space: nowrap; min-width: 130px; }}
  .commit .sha {{ font-family: monospace; color: #457b9d; font-size: .75rem; min-width: 56px; }}
  .commit .msg {{ flex: 1; }}
  .commit .author {{ color: #888; font-size: .75rem; white-space: nowrap; }}
  .no-commits {{ padding: 1rem; color: #888; font-size: .85rem; }}
  .empty-row td {{ text-align: center; color: #999; padding: 2rem; }}
  a {{ color: #457b9d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  @media (max-width: 900px) {{
    .layout {{ grid-template-columns: 1fr; }}
    .commits-panel {{ grid-column: 1; }}
  }}
</style>
</head>
<body>
<header>
  <h1>WBB Updates Dashboard</h1>
  <span class="generated">Generated: {generated}</span>
</header>

<div class="layout">

  <!-- Recent Changes -->
  <div class="commits-panel panel">
    <div class="panel-header"><h2>Recent Data Changes</h2></div>
    <div id="commit-list" class="commit-list"></div>
  </div>

  <!-- Transfers -->
  <div class="panel">
    <div class="panel-header">
      <h2>Transfers</h2>
      <span class="badge" id="transfer-count">0</span>
      <div class="controls">
        <input type="search" id="transfer-search" placeholder="Search name, team…" style="width:160px">
        <select id="transfer-status">
          <option value="">All statuses</option>
          <option value="In">In</option>
          <option value="Out">Out</option>
        </select>
        <select id="transfer-year">
          <option value="">All years</option>
          <option value="FR">FR</option>
          <option value="RS FR">RS FR</option>
          <option value="SO">SO</option>
          <option value="RS SO">RS SO</option>
          <option value="JR">JR</option>
          <option value="RS JR">RS JR</option>
          <option value="SR">SR</option>
          <option value="RS SR">RS SR</option>
          <option value="GR">GR</option>
        </select>
        <select id="transfer-position">
          <option value="">All positions</option>
        </select>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Team</th>
            <th>Status</th>
            <th>Pos</th>
            <th>Yr</th>
            <th>Ht</th>
            <th>Entered Portal</th>
          </tr>
        </thead>
        <tbody id="transfer-tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Coaching Changes -->
  <div class="panel">
    <div class="panel-header">
      <h2>Coaching Changes</h2>
      <span class="badge" id="coaching-count">0</span>
      <div class="controls">
        <input type="search" id="coaching-search" placeholder="Search school, coach…" style="width:160px">
        <select id="coaching-role">
          <option value="">Hired &amp; departed</option>
          <option value="hired">Hired only</option>
          <option value="departed">Departed only</option>
        </select>
        <select id="coaching-conf">
          <option value="">All conferences</option>
        </select>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>School</th>
            <th>Conference</th>
            <th>Role</th>
            <th>Coach</th>
            <th>Date</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody id="coaching-tbody"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
const TRANSFERS = {transfers_json};
const COACHING = {coaching_json};
const COMMITS = {commits_json};

// --- Commits ---
const commitList = document.getElementById('commit-list');
if (COMMITS.length === 0) {{
  commitList.innerHTML = '<div class="no-commits">No git history found for these files.</div>';
}} else {{
  COMMITS.forEach(c => {{
    const div = document.createElement('div');
    div.className = 'commit';
    div.innerHTML = `
      <span class="date">${{c.date}}</span>
      <span class="sha">${{c.short}}</span>
      <span class="msg">${{escHtml(c.message)}}</span>
      <span class="author">${{escHtml(c.author)}}</span>
    `;
    commitList.appendChild(div);
  }});
}}

// --- Helpers ---
function escHtml(s) {{
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function statusPill(status, type) {{
  if (type === 'transfer') {{
    const cls = status === 'In' ? 'status-in' : 'status-out';
    return `<span class="status-pill ${{cls}}">${{escHtml(status)}}</span>`;
  }}
  const cls = status === 'Jobs Open' ? 'status-open' : 'status-filled';
  return `<span class="status-pill ${{cls}}">${{escHtml(status)}}</span>`;
}}

// --- Transfer positions filter ---
const positions = [...new Set(TRANSFERS.map(t => t.position).filter(Boolean))].sort();
const posSelect = document.getElementById('transfer-position');
positions.forEach(p => {{
  const o = document.createElement('option');
  o.value = p; o.textContent = p;
  posSelect.appendChild(o);
}});

// --- Coaching conference filter ---
const confs = [...new Set(COACHING.map(c => c.conference).filter(Boolean))].sort();
const confSelect = document.getElementById('coaching-conf');
confs.forEach(c => {{
  const o = document.createElement('option');
  o.value = c; o.textContent = c;
  confSelect.appendChild(o);
}});

// --- Render transfers ---
function renderTransfers() {{
  const search = document.getElementById('transfer-search').value.toLowerCase();
  const status = document.getElementById('transfer-status').value;
  const year = document.getElementById('transfer-year').value;
  const position = document.getElementById('transfer-position').value;

  const filtered = TRANSFERS.filter(t => {{
    if (status && t.status !== status) return false;
    if (year && (t.year ?? '').toUpperCase() !== year.toUpperCase()) return false;
    if (position && t.position !== position) return false;
    if (search) {{
      const hay = `${{t.name}} ${{t.team}} ${{t.hometown ?? ''}} ${{t.transfer_history ?? ''}}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }}
    return true;
  }});

  document.getElementById('transfer-count').textContent = filtered.length;
  const tbody = document.getElementById('transfer-tbody');
  if (filtered.length === 0) {{
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No results</td></tr>';
    return;
  }}
  tbody.innerHTML = filtered.map(t => `
    <tr>
      <td>${{escHtml(t.name)}}</td>
      <td>${{escHtml(t.team)}}</td>
      <td>${{statusPill(t.status, 'transfer')}}</td>
      <td>${{escHtml(t.position ?? '')}}</td>
      <td>${{escHtml(t.year ?? '')}}</td>
      <td>${{escHtml(t.height ?? '')}}</td>
      <td>${{escHtml(t.entered_portal ?? '')}}</td>
    </tr>
  `).join('');
}}

// --- Render coaching ---
function renderCoaching() {{
  const search = document.getElementById('coaching-search').value.toLowerCase();
  const role = document.getElementById('coaching-role').value;
  const conf = document.getElementById('coaching-conf').value;

  const filtered = COACHING.filter(c => {{
    if (role && c.role !== role) return false;
    if (conf && c.conference !== conf) return false;
    if (search) {{
      const hay = `${{c.school}} ${{c.coach ?? ''}} ${{c.conference ?? ''}} ${{c.text ?? ''}}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }}
    return true;
  }});

  document.getElementById('coaching-count').textContent = filtered.length;
  const tbody = document.getElementById('coaching-tbody');
  if (filtered.length === 0) {{
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No results</td></tr>';
    return;
  }}
  tbody.innerHTML = filtered.map(c => {{
    const roleCls = c.role === 'hired' ? 'role-hired' : 'role-departed';
    const roleLabel = c.role === 'hired' ? 'Hired' : 'Departed';
    return `
    <tr>
      <td>${{escHtml(c.school)}}</td>
      <td>${{escHtml(c.conference ?? '')}}</td>
      <td><span class="status-pill ${{roleCls}}">${{roleLabel}}</span></td>
      <td>${{escHtml(c.coach ?? '')}}</td>
      <td>${{escHtml(c.date ?? '')}}</td>
      <td>${{c.url ? `<a href="${{escHtml(c.url)}}" target="_blank" rel="noopener">release</a>` : ''}}</td>
    </tr>
  `;}}).join('');
}}

// --- Wire up listeners ---
['transfer-search','transfer-status','transfer-year','transfer-position'].forEach(id =>
  document.getElementById(id).addEventListener('input', renderTransfers));
['coaching-search','coaching-role','coaching-conf'].forEach(id =>
  document.getElementById(id).addEventListener('input', renderCoaching));

renderTransfers();
renderCoaching();
</script>
</body>
</html>
"""

    OUTPUT_FILE.write_text(html)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
