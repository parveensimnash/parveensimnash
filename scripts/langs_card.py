#!/usr/bin/env python3
"""Render assets/top-langs.svg from ALL owned repos (private included).

Usage:  GITHUB_TOKEN=<pat with repo scope> python3 scripts/langs_card.py parveensimnash
The shared github-readme-stats card only sees public repos; this one sees everything the token can.
"""
import json, os, sys, urllib.request
from xml.sax.saxutils import escape

USER = sys.argv[1] if len(sys.argv) > 1 else "parveensimnash"
TOKEN = os.environ["GITHUB_TOKEN"]
HIDE = {"HTML", "CSS"}          # markup languages hidden, like hide=html,css
MAX_LANGS = 6
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "top-langs.svg")

QUERY = """
query($login:String!, $after:String) {
  user(login:$login) {
    repositories(first:100, after:$after, ownerAffiliations:OWNER, isFork:false) {
      pageInfo { hasNextPage endCursor }
      nodes { languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
        edges { size node { name color } } } }
    }
  }
}"""

def gql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]["user"]["repositories"]

sizes, colors, after = {}, {}, None
while True:
    page = gql({"login": USER, "after": after})
    for repo in page["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in HIDE:
                continue
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#858585"
    if not page["pageInfo"]["hasNextPage"]:
        break
    after = page["pageInfo"]["endCursor"]

total = sum(sizes.values()) or 1
langs = sorted(sizes.items(), key=lambda kv: -kv[1])[:MAX_LANGS]

# --- radical theme (matches the other cards) ---
BG, BORDER, TITLE, TEXT = "#141321", "#e4e2e2", "#fe428e", "#a9fef7"
W, PAD = 300, 25
rows = (len(langs) + 1) // 2
H = 90 + rows * 25 + 10

bar, x = [], PAD
for name, size in langs:
    w = (W - 2 * PAD) * size / total
    bar.append(f'<rect x="{x:.1f}" y="60" width="{w:.1f}" height="8" fill="{colors[name]}"/>')
    x += w

items = []
for i, (name, size) in enumerate(langs):
    col, row = i % 2, i // 2
    cx = PAD + col * 130
    cy = 90 + row * 25
    pct = 100 * size / total
    items.append(
        f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{colors[name]}"/>'
        f'<text x="{cx+16}" y="{cy}" fill="{TEXT}" font-size="11" font-family="Segoe UI, Ubuntu, sans-serif">'
        f'{escape(name)} {pct:.2f}%</text>'
    )

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Most Used Languages">
<rect x="0.5" y="0.5" rx="4.5" width="{W-1}" height="{H-1}" fill="{BG}" stroke="{BORDER}"/>
<text x="{PAD}" y="35" fill="{TITLE}" font-size="18" font-weight="600" font-family="Segoe UI, Ubuntu, sans-serif">Most Used Languages</text>
<rect x="{PAD}" y="60" width="{W-2*PAD}" height="8" rx="4" fill="#2b2a3a"/>
{"".join(bar)}
{"".join(items)}
</svg>
'''
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(svg)
print(f"wrote {os.path.relpath(OUT)}: " + ", ".join(f"{n} {100*s/total:.1f}%" for n, s in langs))
