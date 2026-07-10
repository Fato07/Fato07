#!/usr/bin/env python3
"""Refresh the profile control-plane SVGs from public GitHub data."""

from __future__ import annotations

import base64
import html
import json
import os
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
GRAPHQL = f"{API}/graphql"


def github_request(url: str, token: str, payload: dict | None = None) -> dict | list:
    data = json.dumps(payload).encode() if payload else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Fato07-profile-control-plane",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST" if payload else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_stats(username: str, token: str) -> dict[str, int | str]:
    user = github_request(f"{API}/users/{username}", token)

    repositories: list[dict] = []
    page = 1
    while True:
        batch = github_request(
            f"{API}/users/{username}/repos?type=owner&per_page=100&page={page}", token
        )
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    now = datetime.now(UTC)
    contribution_query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    contribution_data = github_request(
        GRAPHQL,
        token,
        {
            "query": contribution_query,
            "variables": {
                "login": username,
                "from": (now - timedelta(days=364)).isoformat(),
                "to": now.isoformat(),
            },
        },
    )
    if contribution_data.get("errors"):
        raise RuntimeError(contribution_data["errors"])

    return {
        "contributions": contribution_data["data"]["user"]["contributionsCollection"][
            "contributionCalendar"
        ]["totalContributions"],
        "followers": user["followers"],
        "public_repos": user["public_repos"],
        "stars": sum(repository["stargazers_count"] for repository in repositories),
        "active_since": datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).year,
        "updated": now.strftime("%b %d, %Y").replace(" 0", " "),
    }


def svg_text(x: int, y: int, value: object, css_class: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" class="{css_class}" text-anchor="{anchor}">'
        f"{html.escape(str(value))}</text>"
    )


def build_svg(profile: dict[str, str], stats: dict[str, int | str], portrait: str, theme: str) -> str:
    colors = {
        "dark": {
            "background": "#0d1117",
            "panel": "#161b22",
            "border": "#30363d",
            "text": "#f0f6fc",
            "muted": "#8b949e",
            "accent": "#58a6ff",
            "success": "#3fb950",
            "portrait": "#c9d1d9",
            "shadow": "#010409",
        },
        "light": {
            "background": "#ffffff",
            "panel": "#f6f8fa",
            "border": "#d0d7de",
            "text": "#1f2328",
            "muted": "#59636e",
            "accent": "#0969da",
            "success": "#1a7f37",
            "portrait": "#24292f",
            "shadow": "#afb8c1",
        },
    }[theme]

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="430" viewBox="0 0 1000 430" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(profile["handle"])} profile control plane</title>',
        '<desc id="desc">ASCII portrait of Fathin Dosunmu with live public GitHub statistics and current areas of work.</desc>',
        "<style>",
        "text { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }",
        ".eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 1.4px; }",
        ".handle { font-size: 29px; font-weight: 700; }",
        ".label { font-size: 11px; font-weight: 700; letter-spacing: 1px; }",
        ".value { font-size: 14px; font-weight: 500; }",
        ".stat { font-size: 26px; font-weight: 750; }",
        ".stat-label { font-size: 10px; font-weight: 700; letter-spacing: 0.9px; }",
        ".tiny { font-size: 10px; }",
        "@keyframes blink { 50% { opacity: 0; } }",
        ".cursor { animation: blink 1.1s steps(2, end) infinite; }",
        "</style>",
        '<defs><mask id="portrait-mask" maskUnits="userSpaceOnUse" x="60" y="62" width="263" height="280">',
        f'<image x="60" y="62" width="263" height="280" href="data:image/png;base64,{portrait}"/>',
        "</mask></defs>",
        f'<rect width="1000" height="430" rx="18" fill="{colors["background"]}"/>',
        f'<rect x="1" y="1" width="998" height="428" rx="17" fill="none" stroke="{colors["border"]}" stroke-width="2"/>',
        f'<rect x="20" y="20" width="960" height="390" rx="12" fill="{colors["panel"]}" stroke="{colors["border"]}"/>',
        f'<circle cx="42" cy="42" r="5" fill="#ff5f57"/><circle cx="60" cy="42" r="5" fill="#febc2e"/><circle cx="78" cy="42" r="5" fill="#28c840"/>',
        svg_text(98, 47, "FATHIN_OS // PROFILE CONTROL PLANE", "eyebrow",),
        f'<rect x="842" y="30" width="112" height="24" rx="12" fill="{colors["success"]}" opacity="0.14"/>',
        f'<circle cx="858" cy="42" r="4" fill="{colors["success"]}"/>',
        svg_text(870, 46, "PRODUCTION", "label"),
        f'<line x1="384" y1="68" x2="384" y2="388" stroke="{colors["border"]}"/>',
        f'<rect x="60" y="62" width="263" height="280" fill="{colors["portrait"]}" mask="url(#portrait-mask)"/>',
        svg_text(36, 360, "ASCII // FATHIN DOSUNMU", "label"),
        svg_text(36, 382, "IDENTITY · SYSTEMS · SECURITY", "eyebrow"),
        svg_text(36, 403, "source photo stays private", "tiny"),
        svg_text(420, 92, profile["handle"], "handle"),
        svg_text(420, 120, "builder@tallinn:~$ ./now", "eyebrow"),
        svg_text(420, 153, "ROLE", "label"),
        svg_text(500, 153, profile["role"], "value"),
        svg_text(420, 177, "BASE", "label"),
        svg_text(500, 177, profile["base"], "value"),
        svg_text(420, 201, "FOCUS", "label"),
        svg_text(500, 201, profile["focus"], "value"),
        svg_text(420, 225, "SHIPPING", "label"),
        svg_text(500, 225, profile["shipping"], "value"),
        f'<line x1="420" y1="246" x2="946" y2="246" stroke="{colors["border"]}"/>',
        svg_text(420, 268, "GITHUB TELEMETRY // LIVE", "eyebrow"),
        svg_text(420, 304, f'{stats["contributions"]:,}', "stat"),
        svg_text(420, 322, "CONTRIBUTIONS / 365D", "stat-label"),
        svg_text(600, 304, f'{stats["public_repos"]:,}', "stat"),
        svg_text(600, 322, "PUBLIC REPOSITORIES", "stat-label"),
        svg_text(780, 304, f'{stats["stars"]:,}', "stat"),
        svg_text(780, 322, "STARS EARNED", "stat-label"),
        svg_text(420, 361, f'{stats["followers"]:,}', "stat"),
        svg_text(420, 379, "FOLLOWERS", "stat-label"),
        svg_text(600, 361, stats["active_since"], "stat"),
        svg_text(600, 379, "ACTIVE SINCE", "stat-label"),
        svg_text(780, 361, stats["updated"], "value"),
        svg_text(780, 379, "LAST SYNC", "stat-label"),
        svg_text(420, 404, f'STATUS: {profile["status"]}', "eyebrow"),
        f'<rect class="cursor" x="574" y="392" width="8" height="14" fill="{colors["success"]}"/>',
        "<style>",
        f'.eyebrow, .stat-label {{ fill: {colors["accent"]}; }}',
        f'.handle, .value, .stat, .label {{ fill: {colors["text"]}; }}',
        f'.tiny {{ fill: {colors["muted"]}; }}',
        "</style>",
        "</svg>",
    ]
    return "".join(parts)


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN before running this script.")

    profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    portrait = base64.b64encode((ROOT / "assets" / "portrait.png").read_bytes()).decode("ascii")
    stats = fetch_stats(profile["username"], token)

    for theme in ("dark", "light"):
        output = ROOT / "assets" / f"profile-{theme}.svg"
        output.write_text(build_svg(profile, stats, portrait, theme), encoding="utf-8")
        print(f"Updated {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
