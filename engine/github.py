"""PR metadata, diff, clone, comments, post review (PRD 6.0, 6.1, 6.6)."""

import os
import re
import subprocess

import requests

API = "https://api.github.com"
PR_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")


def parse_pr_url(pr_url):
    m = PR_URL_RE.search(pr_url or "")
    if not m:
        raise ValueError(f"not a PR url: {pr_url!r}")
    owner, repo, number = m.group(1), m.group(2), int(m.group(3))
    return owner, repo, number


def _headers(accept="application/vnd.github+json"):
    h = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_pr(owner, repo, number):
    r = requests.get(f"{API}/repos/{owner}/{repo}/pulls/{number}", headers=_headers(), timeout=20)
    r.raise_for_status()
    pr = r.json()
    return {
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "files": pr.get("changed_files", 0),
        "additions": pr.get("additions", 0),
        "head_sha": pr["head"]["sha"],
        "head_ref": pr["head"]["ref"],
        "base_ref": pr["base"]["ref"],
        "clone_url": pr["head"]["repo"]["clone_url"],
    }


def get_diff(owner, repo, number):
    r = requests.get(
        f"{API}/repos/{owner}/{repo}/pulls/{number}",
        headers=_headers("application/vnd.github.diff"),
        timeout=20,
    )
    r.raise_for_status()
    return r.text


def get_comments(owner, repo, number):
    """Review comments + issue comments, for SCOUT=app (PRD 6.1)."""
    out = []
    for url in (
        f"{API}/repos/{owner}/{repo}/pulls/{number}/comments",
        f"{API}/repos/{owner}/{repo}/issues/{number}/comments",
    ):
        r = requests.get(url, headers=_headers(), params={"per_page": 100}, timeout=20)
        r.raise_for_status()
        for c in r.json():
            out.append(
                {
                    "author": c.get("user", {}).get("login", ""),
                    "path": c.get("path"),
                    "line": c.get("line") or c.get("original_line"),
                    "body": c.get("body", ""),
                }
            )
    return out


def clone_at(clone_url, head_sha, dest):
    """Shallow clone at the PR head into runs/<arena_id>/repo (PRD 6.0)."""
    if os.path.isdir(os.path.join(dest, ".git")):
        return dest
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    token = os.environ.get("GITHUB_TOKEN")
    url = clone_url
    if token and url.startswith("https://"):
        url = url.replace("https://", f"https://x-access-token:{token}@", 1)
    subprocess.run(["git", "init", "-q", dest], check=True)
    subprocess.run(["git", "-C", dest, "remote", "add", "origin", url], check=True)
    subprocess.run(
        ["git", "-C", dest, "fetch", "-q", "--depth", "1", "origin", head_sha], check=True
    )
    subprocess.run(["git", "-C", dest, "checkout", "-q", "FETCH_HEAD"], check=True)
    return dest


def diff_stat(workdir):
    r = subprocess.run(
        ["git", "-C", workdir, "diff", "--stat"], capture_output=True, text=True
    )
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def read_conventions(workdir):
    """The snippet Recon cites: app/auth.py plus one admin route (PRD 6.2)."""
    parts = []
    for rel in ("app/auth.py", "app/admin.py", "app/main.py"):
        path = os.path.join(workdir, rel)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                parts.append(f"# {rel}\n{fh.read()[:4000]}")
    return "\n\n".join(parts)


def post_review(owner, repo, number, body):
    """PRD 6.6, optional, only after M3."""
    raise NotImplementedError(
        "engine/github.py: push arena/pr-<n>-<arena_id> and POST one review "
        "comment with the hypothesis table (PRD 6.6). Only after M3."
    )
