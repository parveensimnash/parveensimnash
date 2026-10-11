#!/usr/bin/env python3
"""Render assets/stats.svg and assets/streak.svg from the account's real commit history.

Counts commits on the default branch of every owned repo (private included) that GitHub
attributes to the account, so it works even while the profile is marked private and
includes private repos, which the shared github-readme-stats cards cannot do.

Usage: GITHUB_TOKEN=<pat with repo scope> python3 scripts/stats_cards.py parveensimnash
"""
import json, os, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

USER = sys.argv[1] if len(sys.argv) > 1 else "parveensimnash"
TOKEN = os.environ["GITHUB_TOKEN"]
IST = timezone(timedelta(hours=5, minutes=30))
HERE = os.path.dirname(__file__)
ASSETS = os.path.join(HERE, "..", "assets")
FONT = "Segoe UI, Ubuntu, sans-serif"
BG, BORDER, TITLE, TEXT, ICON, RING = "#141321", "#e4e2e2", "#fe428e", "#a9fef7", "#f8d847", "#fe428e"


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if "errors" in out:
        raise SystemExit(out["errors"])
    return out["data"]


# ---------- account-level numbers ----------
acct = gql("""
query($login:String!) { user(login:$login) { id createdAt
  pullRequests { totalCount } issues { totalCount }
  repositories(first:100, ownerAffiliations:OWNER, isFork:false) {
    nodes { name stargazerCount defaultBranchRef { name } } } } }""", {"login": USER})["user"]
UID = acct["id"]
stars = sum(r["stargazerCount"] for r in acct["repositories"]["nodes"])
prs, issues = acct["pullRequests"]["totalCount"], acct["issues"]["totalCount"]
repos = [r["name"] for r in acct["repositories"]["nodes"] if r["defaultBranchRef"]]

# ---------- every commit date attributed to the account ----------
HIST = """
query($owner:String!, $name:String!, $id:ID!, $after:String) {
  repository(owner:$owner, name:$name) { defaultBranchRef { target { ... on Commit {
    history(first:100, after:$after, author:{id:$id}) {
      pageInfo { hasNextPage endCursor } nodes { committedDate } } } } } } }"""
days = {}
total_commits = 0
contributed_repos = 0
for name in repos:
    after, n = None, 0
    while True:
        h = gql(HIST, {"owner": USER, "name": name, "id": UID, "after": after})
        h = h["repository"]["defaultBranchRef"]["target"]["history"]
        for c in h["nodes"]:
            d = datetime.fromisoformat(c["committedDate"].replace("Z", "+00:00")).astimezone(IST).date()
            days[d] = days.get(d, 0) + 1
            n += 1
        if not h["pageInfo"]["hasNextPage"]:
            break
        after = h["pageInfo"]["endCursor"]
    total_commits += n
    contributed_repos += 1 if n else 0

today = datetime.now(IST).date()
year_ago = today - timedelta(days=365)
commits_last_year = sum(c for d, c in days.items() if d >= year_ago)

# streaks
active = sorted(days)
longest, cur_run, lstart, lend, run_start = 0, 0, None, None, None
prev = None
for d in active:
    if prev and (d - prev).days == 1:
        cur_run += 1
    else:
        cur_run, run_start = 1, d
    if cur_run > longest:
        longest, lstart, lend = cur_run, run_start, d
    prev = d
# current streak: counts back from today (or yesterday, today may not be over)
cur, d = 0, today
if d not in days:
    d -= timedelta(days=1)
cs_end = d
while d in days:
    cur += 1
    d -= timedelta(days=1)
cs_start = d + timedelta(days=1)
first_day = active[0] if active else today

fmt = lambda x: x.strftime("%b %-d, %Y")
fmt_short = lambda x: x.strftime("%b %-d")

os.makedirs(ASSETS, exist_ok=True)

# ---------- stats card ----------
rows = [("Total Stars Earned:", stars), ("Total Commits (last year):", commits_last_year),
        ("Total Commits (all time):", total_commits), ("Total PRs:", prs),
        ("Total Issues:", issues), ("Contributed to (repos):", contributed_repos)]
W, H = 495, 60 + len(rows) * 25 + 20
lines = []
for i, (label, val) in enumerate(rows):
    y = 72 + i * 25
    lines.append(f'<text x="25" y="{y}" fill="{TEXT}" font-size="14" font-weight="600" font-family="{FONT}">{label}</text>'
                 f'<text x="300" y="{y}" fill="{TEXT}" font-size="14" font-weight="700" font-family="{FONT}" text-anchor="end">{val}</text>')
# simple rank ring: percentage of days active in the last year
active_pct = min(100, round(100 * sum(1 for d in days if d >= year_ago) / 365))
circ = 2 * 3.14159 * 40
stats_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{USER}'s GitHub Stats">
<rect x="0.5" y="0.5" rx="4.5" width="{W-1}" height="{H-1}" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="35" fill="{TITLE}" font-size="18" font-weight="600" font-family="{FONT}">{USER}'s GitHub Stats</text>
{"".join(lines)}
<g transform="translate(420, {H/2 + 10})">
  <circle r="40" fill="none" stroke="{RING}" stroke-opacity="0.2" stroke-width="6"/>
  <circle r="40" fill="none" stroke="{RING}" stroke-width="6" stroke-linecap="round"
          stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ*(1-active_pct/100):.1f}" transform="rotate(-90)"/>
  <text y="6" fill="{TEXT}" font-size="20" font-weight="700" font-family="{FONT}" text-anchor="middle">{active_pct}%</text>
  <text y="60" fill="{TEXT}" font-size="10" font-family="{FONT}" text-anchor="middle">days active · last year</text>
</g>
</svg>
'''
with open(os.path.join(ASSETS, "stats.svg"), "w") as f:
    f.write(stats_svg)

# ---------- streak card ----------
SW, SH = 495, 195
streak_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}" viewBox="0 0 {SW} {SH}" role="img" aria-label="GitHub streak">
<rect x="0.5" y="0.5" rx="4.5" width="{SW-1}" height="{SH-1}" fill="{BG}" stroke="{BORDER}"/>
<line x1="165" y1="28" x2="165" y2="170" stroke="{BORDER}" stroke-opacity="0.5"/>
<line x1="330" y1="28" x2="330" y2="170" stroke="{BORDER}" stroke-opacity="0.5"/>
<g text-anchor="middle" font-family="{FONT}">
  <text x="82" y="80" fill="{TITLE}" font-size="28" font-weight="700">{total_commits}</text>
  <text x="82" y="110" fill="{TITLE}" font-size="14" font-weight="600">Total Contributions</text>
  <text x="82" y="135" fill="{TEXT}" font-size="12">{fmt(first_day)} - Present</text>

  <circle cx="247" cy="78" r="40" fill="none" stroke="{RING}" stroke-width="5"/>
  <text x="247" y="88" fill="{ICON}" font-size="28" font-weight="700">{cur}</text>
  <text x="247" y="140" fill="{ICON}" font-size="14" font-weight="600">Current Streak</text>
  <text x="247" y="160" fill="{TEXT}" font-size="12">{(fmt_short(cs_start) + " - " + fmt_short(cs_end)) if cur else "No commits today"}</text>
  <text x="247" y="48" fill="{RING}" font-size="22">🔥</text>

  <text x="412" y="80" fill="{TITLE}" font-size="28" font-weight="700">{longest}</text>
  <text x="412" y="110" fill="{TITLE}" font-size="14" font-weight="600">Longest Streak</text>
  <text x="412" y="135" fill="{TEXT}" font-size="12">{(fmt_short(lstart) + " - " + fmt(lend)) if longest else "-"}</text>
</g>
</svg>
'''
with open(os.path.join(ASSETS, "streak.svg"), "w") as f:
    f.write(streak_svg)

print(f"stars={stars} commits_all={total_commits} commits_last_year={commits_last_year} prs={prs} issues={issues} "
      f"repos_with_commits={contributed_repos} active_days_pct={active_pct}% current_streak={cur} longest={longest} ({lstart}→{lend}) first={first_day}")
