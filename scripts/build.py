"""Builds assets/stats-{dark,light}.svg: contribution streak and top languages.

Runs daily in .github/workflows/stats.yml. Locally:
    GH_TOKEN=$(gh auth token) python scripts/build.py
"""

import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

USER = "zivavu"
TOP_LANGUAGES = 6
IGNORED_LANGUAGES = {"PLpgSQL"}  # Supabase migrations, they drown out everything else
OUT = Path(__file__).resolve().parent.parent / "assets"
TOKEN = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]

MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

THEMES = {
    "dark": {
        "fg": "#e6edf3",
        "muted": "#7d8590",
        "line": "#30363d",
        "red": "#ff2d6f",
        "cyan": "#19d3f3",
        "blend": "screen",
    },
    "light": {
        "fg": "#1f2328",
        "muted": "#59636e",
        "line": "#d1d9e0",
        "red": "#ff2d6f",
        "cyan": "#00b8d9",
        "blend": "multiply",
    },
}


# github/linguist colors for the languages likely to show up
LANGUAGE_COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Svelte": "#ff3e00",
    "Python": "#3572a5",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "GLSL": "#5686a5",
    "C++": "#f34b7d",
    "Vue": "#41b883",
    "Astro": "#ff5a03",
}


def api(path, body=None):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER,
        },
    )
    with urllib.request.urlopen(request) as response:
        data = json.load(response)
    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


def graphql(query):
    return api("/graphql", {"query": query})["data"]["user"]


CALENDAR = "contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }"


def contributions():
    """Returns (current streak, longest streak, contributions in the last 12 months)."""
    recent = graphql(
        f'{{ user(login: "{USER}") {{ contributionsCollection {{ contributionYears {CALENDAR} }} }} }}'
    )["contributionsCollection"]

    # contributionsCollection spans one year at most, so older years get one alias each
    years = " ".join(
        f'y{year}: contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{ {CALENDAR} }}'
        for year in recent["contributionYears"]
    )
    calendars = [recent] + list(graphql(f'{{ user(login: "{USER}") {{ {years} }} }}').values())

    days = {}
    for collection in calendars:
        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[day["date"]] = max(days.get(day["date"], 0), day["contributionCount"])

    today = recent["contributionCalendar"]["weeks"][-1]["contributionDays"][-1]["date"]
    counts = [days[d] for d in sorted(days) if d <= today]

    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)

    if counts and counts[-1] == 0:
        counts.pop()  # today isn't over yet, so it doesn't break the streak
    current = 0
    for count in reversed(counts):
        if not count:
            break
        current += 1

    return current, longest, recent["contributionCalendar"]["totalContributions"]


def languages():
    """Returns [(language, share of all bytes)] for the top languages across own repos."""
    totals = Counter()
    for repo in api(f"/users/{USER}/repos?per_page=100&type=owner"):
        if repo["fork"] or repo["name"] == USER:
            continue
        totals.update(api(f"/repos/{repo['full_name']}/languages"))
    for name in IGNORED_LANGUAGES:
        totals.pop(name, None)
    total = sum(totals.values())
    return [(name, size / total) for name, size in totals.most_common(TOP_LANGUAGES)]


def card(t, current, longest, total, langs):
    label = f"font: 600 11px {MONO}; letter-spacing: 2.5px; fill: {t['muted']};"

    bar_x, bar_w = 430, 370
    segments, x = [], bar_x
    for name, share in langs:
        w = max(share * bar_w, 3)
        segments.append(
            f'<rect x="{x:.1f}" y="40" width="{w:.1f}" height="10" fill="{LANGUAGE_COLORS.get(name, t["muted"])}"/>'
        )
        x += w + 2

    legend = []
    for i, (name, share) in enumerate(langs):
        lx = bar_x + (i % 2) * 190
        ly = 84 + (i // 2) * 30
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{LANGUAGE_COLORS.get(name, t["muted"])}"/>'
            f'<text x="{lx + 18}" y="{ly}" class="lang">{name}</text>'
            f'<text x="{lx + 180}" y="{ly}" class="pct" text-anchor="end">{share * 100:.1f}%</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 176" width="800" height="176" role="img" aria-label="{current} day contribution streak and top languages">
  <title>{current} day streak, longest {longest}, {total:,} contributions in the last 12 months</title>
  <style>
    .label {{ {label} }}
    .num {{ font: 800 76px {MONO}; letter-spacing: -3px; }}
    .sub {{ font: 500 14px {MONO}; fill: {t['fg']}; }}
    .note {{ font: 400 12px {MONO}; fill: {t['muted']}; }}
    .lang {{ font: 500 13px {MONO}; fill: {t['fg']}; }}
    .pct {{ font: 400 12px {MONO}; fill: {t['muted']}; }}

    /* RGB-split copies of the number that sit slightly apart and jump around every 7s */
    .cyan {{ fill: {t['cyan']}; mix-blend-mode: {t['blend']}; transform: translate(-2px, 0); animation: cyan 7s steps(1) infinite; }}
    .red {{ fill: {t['red']}; mix-blend-mode: {t['blend']}; transform: translate(2px, 0); animation: red 7s steps(1) infinite; }}
    .base {{ fill: {t['fg']}; animation: base 7s steps(1) infinite; }}
    @keyframes cyan {{
      0%, 100% {{ transform: translate(-2px, 0); }}
      90% {{ transform: translate(-8px, 1px); }}
      92% {{ transform: translate(5px, -1px); }}
      94% {{ transform: translate(-4px, 2px); }}
      96% {{ transform: translate(-2px, 0); }}
    }}
    @keyframes red {{
      0%, 100% {{ transform: translate(2px, 0); }}
      90% {{ transform: translate(9px, -1px); }}
      92% {{ transform: translate(-6px, 1px); }}
      94% {{ transform: translate(3px, -2px); }}
      96% {{ transform: translate(2px, 0); }}
    }}
    @keyframes base {{
      0%, 100% {{ opacity: 1; }}
      90% {{ opacity: 0.55; }}
      93% {{ opacity: 0.85; }}
      96% {{ opacity: 1; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  <defs>
    <text id="num" x="0" y="112" class="num">{current}</text>
    <clipPath id="bar"><rect x="{bar_x}" y="40" width="{bar_w}" height="10" rx="5"/></clipPath>
  </defs>

  <text x="0" y="20" class="label">STREAK</text>
  <use href="#num" class="cyan"/>
  <use href="#num" class="red"/>
  <use href="#num" class="base"/>
  <text x="2" y="140" class="sub">days in a row</text>
  <text x="2" y="164" class="note">longest {longest} · {total:,} contributions in 12 months</text>

  <line x1="405" y1="6" x2="405" y2="170" stroke="{t['line']}"/>

  <text x="{bar_x}" y="20" class="label">LANGUAGES</text>
  <rect x="{bar_x}" y="40" width="{bar_w}" height="10" rx="5" fill="{t['line']}"/>
  <g clip-path="url(#bar)">{"".join(segments)}</g>
  {"".join(legend)}
</svg>
"""


def main():
    current, longest, total = contributions()
    langs = languages()
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        svg = card(t, current, longest, total, langs)
        (OUT / f"stats-{theme}.svg").write_text(svg, encoding="utf-8", newline="\n")  # same bytes on Windows and CI
    print(f"streak {current} (longest {longest}), {total} contributions, languages {langs}")


if __name__ == "__main__":
    main()
