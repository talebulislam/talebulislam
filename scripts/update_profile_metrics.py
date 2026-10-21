#!/usr/bin/env python3
"""Generate self-hosted GitHub profile metric SVGs using the GitHub GraphQL API.

The workflow runs this script on a schedule so the profile does not depend on
third-party README-stat card hosts. It deliberately reports only public profile
contributions and public repositories.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USERNAME = os.environ.get("GITHUB_USERNAME", "talebulislam")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

QUERY = r"""
query ProfileMetrics($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    url
    followers { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, first: 100,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        isFork
        isArchived
        pushedAt
        primaryLanguage { name color }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def number(value: int) -> str:
    return f"{value:,}"


def safe_color(value: str | None, fallback: str = "#22d3ee") -> str:
    if value and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return fallback


def get_profile_data() -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required. Run this from the provided GitHub Actions workflow.")

    now = datetime.now(timezone.utc)
    start = (now.date() - timedelta(days=364)).isoformat() + "T00:00:00Z"
    end = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    payload = {
        "query": QUERY,
        "variables": {"login": USERNAME, "from": start, "to": end},
    }
    req = Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-profile-metrics-workflow",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"GitHub GraphQL returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach GitHub GraphQL API: {exc.reason}") from exc

    if result.get("errors"):
        messages = "; ".join(err.get("message", "GraphQL error") for err in result["errors"])
        raise RuntimeError(f"GitHub GraphQL error: {messages}")
    profile = (result.get("data") or {}).get("user")
    if not profile:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found or is not accessible.")

    collection = profile["contributionsCollection"]["contributionCalendar"]
    repos = profile["repositories"]
    nodes = repos.get("nodes", [])
    languages = Counter()
    language_colors: dict[str, str] = {}
    for repo in nodes:
        lang = repo.get("primaryLanguage")
        if lang and lang.get("name"):
            languages[lang["name"]] += 1
            language_colors[lang["name"]] = safe_color(lang.get("color"))

    return {
        "login": profile["login"],
        "name": profile.get("name") or profile["login"],
        "url": profile["url"],
        "followers": profile["followers"]["totalCount"],
        "public_repos": repos["totalCount"],
        "stars": sum(repo.get("stargazerCount", 0) for repo in nodes),
        "forks": sum(repo.get("forkCount", 0) for repo in nodes),
        "contributions": collection["totalContributions"],
        "weeks": collection["weeks"],
        "languages": languages,
        "language_colors": language_colors,
        "last_sync": now.strftime("%Y-%m-%d %H:%M UTC"),
        "window_start": start[:10],
        "window_end": now.strftime("%Y-%m-%d"),
    }


def dashboard_svg(data: dict | None) -> str:
    W, H = 1200, 500
    if data is None:
        data = {
            "login": USERNAME, "followers": None, "public_repos": None,
            "stars": None, "contributions": None, "languages": Counter(),
            "language_colors": {}, "last_sync": "AWAITING FIRST WORKFLOW RUN",
            "window_start": "", "window_end": "",
        }

    def metric(value):
        return "—" if value is None else number(int(value))

    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">GitHub metrics dashboard for {esc(data['login'])}</title>
<desc id="desc">Public repository count, followers, stars, yearly GitHub contributions and primary repository languages.</desc>
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#080d1c"/><stop offset="0.55" stop-color="#10162d"/><stop offset="1" stop-color="#15102d"/></linearGradient>
 <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset="0.55" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
 <linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#161e38"/><stop offset="1" stop-color="#0c1226"/></linearGradient>
 <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="#405078" stroke-opacity=".22" stroke-width="1"/></pattern>
 <filter id="glow"><feGaussianBlur stdDeviation="8" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="1200" height="500" rx="24" fill="url(#bg)"/>
<rect width="1200" height="500" rx="24" fill="url(#grid)"/>
<circle cx="1110" cy="25" r="150" fill="#7c3aed" opacity=".12"/>
<circle cx="1100" cy="30" r="100" fill="none" stroke="#8b5cf6" stroke-opacity=".26"/>
<path d="M30 4 H360" stroke="url(#accent)" stroke-width="4" stroke-linecap="round" filter="url(#glow)"/>
<text x="38" y="43" fill="#67e8f9" font-family="Segoe UI,Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="3">DEVELOPER INTELLIGENCE / 01</text>
<text x="38" y="79" fill="#f8fafc" font-family="Segoe UI,Arial,sans-serif" font-size="30" font-weight="800" letter-spacing=".5">GITHUB COMMAND CENTER</text>
<text x="40" y="103" fill="#9baac7" font-family="Segoe UI,Arial,sans-serif" font-size="14">PUBLIC PROFILE SIGNALS · @{esc(data['login'])}</text>
<rect x="865" y="39" width="295" height="38" rx="19" fill="#0b1f2b" stroke="#22d3ee" stroke-opacity=".6"/>
<circle cx="887" cy="58" r="5" fill="{'#f59e0b' if data['public_repos'] is None else '#34d399'}"/>
<text x="902" y="63" fill="#d1fae5" font-family="Segoe UI,Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="1">{esc('SYNC PENDING' if data['public_repos'] is None else 'METRICS SYNCED')}</text>
<text x="38" y="141" fill="#7284a8" font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="2">PROFILE SNAPSHOT</text>
''']
    cards = [
        (38, "PUBLIC REPOSITORIES", data["public_repos"], "#22d3ee", "01"),
        (326, "FOLLOWERS", data["followers"], "#a78bfa", "02"),
        (614, "PUBLIC STARS", data["stars"], "#f472b6", "03"),
        (902, "CONTRIBUTIONS · 365D", data["contributions"], "#34d399", "04"),
    ]
    for x, label, val, color, index in cards:
        svg.append(f'''<rect x="{x}" y="158" width="260" height="106" rx="15" fill="url(#card)" stroke="{color}" stroke-opacity=".48"/>
<rect x="{x}" y="158" width="260" height="3" rx="1.5" fill="{color}"/>
<text x="{x+18}" y="184" fill="#93a4c5" font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="1.1">{esc(label)}</text>
<text x="{x+18}" y="229" fill="#f8fafc" font-family="Segoe UI,Arial,sans-serif" font-size="31" font-weight="800">{esc(metric(val))}</text>
<text x="{x+230}" y="244" text-anchor="end" fill="{color}" font-family="Consolas,monospace" font-size="11">{index} / 04</text>
''')

    # Language bars are repository-count based, not estimates of lines of code.
    svg.append('''<rect x="38" y="287" width="690" height="176" rx="16" fill="#0b1124" stroke="#354466" stroke-opacity=".8"/>
<text x="58" y="315" fill="#e2e8f0" font-family="Segoe UI,Arial,sans-serif" font-size="14" font-weight="700" letter-spacing="1">PRIMARY LANGUAGE FOOTPRINT</text>
<text x="58" y="335" fill="#7e91b4" font-family="Segoe UI,Arial,sans-serif" font-size="11">Public repositories · grouped by primary language</text>
''')
    languages = data["languages"]
    top = languages.most_common(5) if languages else []
    max_count = top[0][1] if top else 1
    if top:
        for idx, (lang, count) in enumerate(top):
            y = 360 + idx * 19
            color = safe_color(data["language_colors"].get(lang))
            width = max(5, round(390 * count / max_count))
            svg.append(f'''<text x="58" y="{y+8}" fill="#cbd5e1" font-family="Segoe UI,Arial,sans-serif" font-size="11">{esc(lang)}</text>
<rect x="190" y="{y-3}" width="410" height="10" rx="5" fill="#1b2945"/>
<rect x="190" y="{y-3}" width="{width}" height="10" rx="5" fill="{color}"/>
<text x="616" y="{y+7}" text-anchor="end" fill="#94a3b8" font-family="Consolas,monospace" font-size="11">{count} repos</text>
''')
    else:
        svg.append('''<text x="58" y="382" fill="#9baac7" font-family="Segoe UI,Arial,sans-serif" font-size="13">Language data will appear after the first successful sync.</text>
<text x="58" y="405" fill="#64748b" font-family="Consolas,monospace" font-size="11">WORKFLOW → ACTIONS → REFRESH GITHUB PROFILE METRICS</text>
''')

    svg.append(f'''<rect x="750" y="287" width="410" height="176" rx="16" fill="#0b1124" stroke="#354466" stroke-opacity=".8"/>
<text x="772" y="315" fill="#e2e8f0" font-family="Segoe UI,Arial,sans-serif" font-size="14" font-weight="700" letter-spacing="1">SYNC TELEMETRY</text>
<circle cx="779" cy="345" r="3" fill="#22d3ee"/><text x="792" y="349" fill="#9fb0ce" font-family="Segoe UI,Arial,sans-serif" font-size="12">DATA SOURCE</text><text x="1138" y="349" text-anchor="end" fill="#e2e8f0" font-family="Consolas,monospace" font-size="11">GitHub GraphQL</text>
<circle cx="779" cy="374" r="3" fill="#a78bfa"/><text x="792" y="378" fill="#9fb0ce" font-family="Segoe UI,Arial,sans-serif" font-size="12">CONTRIBUTION WINDOW</text><text x="1138" y="378" text-anchor="end" fill="#e2e8f0" font-family="Consolas,monospace" font-size="11">365 days</text>
<circle cx="779" cy="403" r="3" fill="#34d399"/><text x="792" y="407" fill="#9fb0ce" font-family="Segoe UI,Arial,sans-serif" font-size="12">REFRESH CADENCE</text><text x="1138" y="407" text-anchor="end" fill="#e2e8f0" font-family="Consolas,monospace" font-size="11">Every 6 hours</text>
<path d="M772 428 H1138" stroke="#354466" stroke-width="1"/>
<text x="772" y="447" fill="#7284a8" font-family="Consolas,monospace" font-size="10">LAST SYNC  ·  {esc(data['last_sync'])}</text>
<text x="38" y="485" fill="#657694" font-family="Consolas,monospace" font-size="10">TALIBUL ISLAM  /  BUILD • SHIP • SCALE</text>
<text x="1160" y="485" text-anchor="end" fill="#657694" font-family="Consolas,monospace" font-size="10">AUTO-GENERATED PROFILE METRICS</text>
</svg>''')
    return "\n".join(svg)


def heatmap_svg(data: dict | None) -> str:
    W, H = 1200, 218
    if data is None:
        weeks = []
        total = None
        status = "AWAITING FIRST WORKFLOW RUN"
    else:
        weeks = data["weeks"]
        total = data["contributions"]
        status = f"{data['window_start']} → {data['window_end']}"

    out = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution heatmap for {esc(USERNAME)}</title>
<desc id="desc">Daily public GitHub contributions over the last 365 days, generated with GitHub Actions.</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#080d1c"/><stop offset="1" stop-color="#13132b"/></linearGradient><pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="#354466" stroke-opacity=".18"/></pattern></defs>
<rect width="1200" height="218" rx="20" fill="url(#bg)"/><rect width="1200" height="218" rx="20" fill="url(#grid)"/>
<text x="30" y="35" fill="#67e8f9" font-family="Segoe UI,Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="2">CONTRIBUTION MATRIX / 365 DAYS</text>
<text x="30" y="61" fill="#f8fafc" font-family="Segoe UI,Arial,sans-serif" font-size="18" font-weight="800">{esc('—' if total is None else number(total))} <tspan fill="#9baac7" font-size="12" font-weight="400">total contributions</tspan></text>
<text x="1166" y="39" text-anchor="end" fill="#8192b2" font-family="Consolas,monospace" font-size="10">{esc(status)}</text>
''']
    x0, y0, cell, gap = 80, 83, 13, 4
    # GitHub's API returns one list of seven days per week, ordered Sunday through Saturday.
    weekdays = [("Mon", 1), ("Wed", 3), ("Fri", 5)]
    for label, day_index in weekdays:
        out.append(f'<text x="27" y="{y0 + day_index * (cell+gap) + 10}" fill="#7184a7" font-family="Segoe UI,Arial,sans-serif" font-size="10">{label}</text>')

    month_marks = []
    previous_month = None
    if weeks:
        for wi, week in enumerate(weeks):
            days = week.get("contributionDays", [])
            for day in days:
                date = datetime.strptime(day["date"], "%Y-%m-%d").date()
                if date.month != previous_month:
                    month_marks.append((wi, date.strftime("%b")))
                    previous_month = date.month
                # API dates in a week are Sunday (0) through Saturday (6).
                y_index = (date.weekday() + 1) % 7
                count = int(day.get("contributionCount", 0))
                if count == 0:
                    color = "#17213a"
                elif count == 1:
                    color = "#164e63"
                elif count <= 3:
                    color = "#0e7490"
                elif count <= 6:
                    color = "#0d9488"
                else:
                    color = "#5eead4"
                x = x0 + wi * (cell + gap)
                y = y0 + y_index * (cell + gap)
                title = f"{day['date']}: {count} contributions"
                out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}" stroke="#94a3b8" stroke-opacity=".10"><title>{esc(title)}</title></rect>')
    else:
        # Preview-only neutral squares. The first successful workflow run replaces them.
        for wi in range(53):
            for di in range(7):
                x, y = x0 + wi * (cell + gap), y0 + di * (cell + gap)
                out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="#17213a" stroke="#94a3b8" stroke-opacity=".06"/>')
        month_marks = [(0, "SYNC"), (9, "PENDING"), (23, "DATA"), (38, "READY")]

    for wi, label in month_marks:
        if x0 + wi * (cell + gap) < 1160:
            out.append(f'<text x="{x0 + wi * (cell + gap)}" y="77" fill="#7184a7" font-family="Segoe UI,Arial,sans-serif" font-size="10">{esc(label)}</text>')
    out.append('<text x="1004" y="135" fill="#7184a7" font-family="Segoe UI,Arial,sans-serif" font-size="10">LESS</text>')
    for i, color in enumerate(["#17213a", "#164e63", "#0e7490", "#0d9488", "#5eead4"]):
        out.append(f'<rect x="{1004 + i * 18}" y="144" width="13" height="13" rx="3" fill="{color}"/>')
    out.append('<text x="1100" y="155" fill="#7184a7" font-family="Segoe UI,Arial,sans-serif" font-size="10">MORE</text>')
    out.append('</svg>')
    return "\n".join(out)


def write_assets(data: dict | None) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "github-dashboard.svg").write_text(dashboard_svg(data), encoding="utf-8")
    (ASSETS / "contribution-heatmap.svg").write_text(heatmap_svg(data), encoding="utf-8")


def main() -> int:
    try:
        data = get_profile_data()
        write_assets(data)
        print(f"Updated profile assets for @{data['login']} at {data['last_sync']}.")
        return 0
    except Exception as exc:  # Keep failures visible in the Actions log.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
