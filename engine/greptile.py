"""Scout stage (PRD 6.1). Two sources behind SCOUT; ship whichever works first.

SCOUT=app   read the Greptile bot's review + issue comments off the PR.
SCOUT=api   index the repo through the Greptile API and ask two questions.
SCOUT=none  empty report; the ticker says "No scouting report" (PRD 11).

Output is always {"source": ..., "items": [{"path", "line", "body"}]}.
"""

import os
import time

import requests

from engine import github

GREPTILE_API = "https://api.greptile.com/v2"
BOT_MATCH = "greptile"

QUESTIONS = [
    "How is authorization enforced on routes in this repo, and which routes skip it?",
    "Is there an idempotency or double-execution guard pattern for money movement in this repo?",
]


def scout(source, owner, repo, number, branch, emit):
    if source == "none":
        return {"source": "none", "items": []}
    if source == "app":
        return scout_from_comments(owner, repo, number)
    if source == "api":
        return scout_from_api(owner, repo, branch, emit)
    raise ValueError(f"unknown SCOUT source: {source!r}")


def scout_from_comments(owner, repo, number):
    """SCOUT=app: every Greptile comment becomes an attack hypothesis seed."""
    items = []
    for c in github.get_comments(owner, repo, number):
        if BOT_MATCH in (c.get("author") or "").lower():
            items.append({"path": c.get("path"), "line": c.get("line"), "body": c["body"]})
    return {"source": "greptile-app", "items": items}


def _headers():
    h = {"Authorization": f"Bearer {os.environ.get('GREPTILE_API_KEY', '')}"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["X-GitHub-Token"] = token
    return h


def scout_from_api(owner, repo, branch, emit, poll_s=3, budget_s=120):
    """SCOUT=api. Emits index_status on every poll (PRD 6.1).

    TODO 1:00 pm: confirm the endpoint shapes against the Greptile docs before
    relying on this path. Section 10's cut order drops SCOUT=api first.
    """
    body = {"remote": "github", "repository": f"{owner}/{repo}", "branch": branch}
    r = requests.post(f"{GREPTILE_API}/repositories", json=body, headers=_headers(), timeout=30)
    r.raise_for_status()
    repo_id = r.json().get("repositoryId") or r.json().get("id")

    deadline = time.monotonic() + budget_s
    status = "queued"
    while time.monotonic() < deadline:
        s = requests.get(f"{GREPTILE_API}/repositories/{repo_id}", headers=_headers(), timeout=30)
        s.raise_for_status()
        info = s.json()
        status = info.get("status", "unknown")
        emit(
            "index_status",
            source="greptile-api",
            status=status,
            lines=info.get("numLines", 0),
            files=info.get("numFiles", 0),
        )
        if status in ("COMPLETED", "ready", "completed"):
            break
        time.sleep(poll_s)

    items = []
    for q in QUESTIONS:
        q_body = {
            "messages": [{"id": "q", "role": "user", "content": q}],
            "repositories": [{"remote": "github", "repository": f"{owner}/{repo}", "branch": branch}],
        }
        a = requests.post(f"{GREPTILE_API}/query", json=q_body, headers=_headers(), timeout=120)
        a.raise_for_status()
        data = a.json()
        for src in data.get("sources", []) or [{}]:
            items.append(
                {
                    "path": src.get("filepath"),
                    "line": src.get("linestart"),
                    "body": data.get("message", "")[:2000],
                }
            )
    return {"source": "greptile-api", "items": items}
