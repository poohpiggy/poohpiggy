"""Point the profile badge at the repository with the most Release downloads."""

import json
import os
import re
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://api.github.com"
MARKED_BADGE = re.compile(
    r"(  <!-- most-downloads:start -->\n).*?(\n  <!-- most-downloads:end -->)",
    re.DOTALL,
)


def github_pages(path, **params):
    page = 1
    while True:
        query = urlencode({**params, "per_page": 100, "page": page})
        request = Request(f"{API}{path}?{query}", headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-most-downloads",
        })
        if token := os.environ.get("GH_TOKEN"):
            request.add_unredirected_header("Authorization", f"Bearer {token}")
        with urlopen(request, timeout=20) as response:
            items = json.load(response)
        if not isinstance(items, list):
            raise ValueError(f"Expected a list from {path}")
        yield from items
        if len(items) < 100:
            return
        page += 1


def most_downloaded(owner):
    totals = {}
    for repo in github_pages(f"/users/{quote(owner, safe='')}/repos", type="owner"):
        name = repo["full_name"]
        repo_path = "/repos/" + quote(name, safe="/")
        total = 0
        for release in github_pages(repo_path + "/releases"):
            if not release["draft"]:
                assets = github_pages(f'{repo_path}/releases/{release["id"]}/assets')
                total += sum(asset["download_count"] for asset in assets)
        totals[name] = total
        print(f"{name}: {total}")
    if not totals or max(totals.values()) == 0:
        return None
    return min(totals, key=lambda name: (-totals[name], name.casefold(), name))


def update_badge(readme, repo):
    if len(MARKED_BADGE.findall(readme)) != 1:
        raise ValueError("Expected one Most Downloads block in README.md")
    target = f"https://github.com/{quote(repo, safe='/')}/releases"
    params = urlencode({
        "style": "for-the-badge",
        "logo": "github",
        "label": "Most Downloads",
        "labelColor": "282038",
        "color": "65479e",
    })
    badge = f"https://img.shields.io/github/downloads/{quote(repo, safe='/')}/total?{params}"
    alt = "Most downloads: " + repo.split("/", 1)[1]
    html = (
        f'  <a href="{escape(target)}">\n'
        f'    <img src="{escape(badge)}" alt="{escape(alt)}" height="28" />\n'
        f'  </a>'
    )
    return MARKED_BADGE.sub(lambda match: match[1] + html + match[2], readme)


def main():
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "poohpiggy")
    winner = most_downloaded(owner)
    if winner is None:
        print("No downloads found, leaving the badge as it is.")
        return

    path = Path("README.md")
    before = path.read_text(encoding="utf-8")
    after = update_badge(before, winner)
    if after != before:
        path.write_text(after, encoding="utf-8", newline="\n")
    print(f"Most downloaded repository: {winner}")


if __name__ == "__main__":
    main()
