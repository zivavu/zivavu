"""Builds assets/streak-{dark,light}.svg: the contribution streak card.

Runs daily in .github/workflows/stats.yml. Locally:
    GH_TOKEN=$(gh auth token) python scripts/build.py
"""

import json
import os
import urllib.request
from pathlib import Path

USER = "zivavu"
OUT = Path(__file__).resolve().parent.parent / "assets"
TOKEN = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]

MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

THEMES = {
    "dark": {
        "fg": "#e6edf3",
        "muted": "#7d8590",
        "accent": "#3ddc97",
        "red": "#ff2d6f",
        "cyan": "#19d3f3",
        "blend": "screen",
    },
    "light": {
        "fg": "#1f2328",
        "muted": "#59636e",
        "accent": "#1a7f37",
        "red": "#ff2d6f",
        "cyan": "#00b8d9",
        "blend": "multiply",
    },
}


def graphql(query):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": USER},
    )
    with urllib.request.urlopen(request) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


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


def card(t, current, longest, total):
    label = f"font: 600 11px {MONO}; letter-spacing: 2.5px; fill: {t['muted']};"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 170" width="380" height="170" role="img" aria-label="{current} day contribution streak">
  <title>{current} day streak, longest {longest}, {total:,} contributions in the last 12 months</title>
  <style>
    .label {{ {label} }}
    .live {{ {label} fill: {t['accent']}; }}
    .num {{ font: 800 76px {MONO}; letter-spacing: -3px; }}
    .sub {{ font: 500 14px {MONO}; fill: {t['fg']}; }}
    .note {{ font: 400 12px {MONO}; fill: {t['muted']}; }}
    .dot {{ fill: {t['accent']}; animation: blink 1.6s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0.2; }} }}

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
  </defs>

  <text x="0" y="20" class="label">STREAK</text>
  <circle cx="312" cy="16" r="3.5" class="dot"/>
  <text x="380" y="20" class="live" text-anchor="end">LIVE</text>
  <use href="#num" class="cyan"/>
  <use href="#num" class="red"/>
  <use href="#num" class="base"/>
  <text x="2" y="140" class="sub">days in a row</text>
  <text x="2" y="164" class="note">longest {longest} · {total:,} contributions in 12 months</text>
</svg>
"""


def main():
    current, longest, total = contributions()
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        (OUT / f"streak-{theme}.svg").write_text(card(t, current, longest, total), encoding="utf-8")
    print(f"streak {current} (longest {longest}), {total} contributions")


if __name__ == "__main__":
    main()
