"""Recon: diff + scout report + conventions -> 1..4 attack hypotheses (PRD 6.2).

One OpenAI Responses API call, JSON enforced, prompt in prompts/recon.txt.
"""

import json
import os

from shared.schema import ATTACKERS, validate_hypothesis

MODEL = os.environ.get("RECON_MODEL", "gpt-5")
MAX_HYPOTHESES = 4

HYPOTHESIS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "hypotheses": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_HYPOTHESES,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "attacker": {"type": "string", "enum": list(ATTACKERS)},
                    "title": {"type": "string"},
                    "claim": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "exploit_plan": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium"]},
                },
                "required": [
                    "id", "attacker", "title", "claim", "file", "line",
                    "exploit_plan", "severity",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hypotheses"],
    "additionalProperties": False,
}


def _system_prompt():
    with open(os.path.join("prompts", "recon.txt"), "r", encoding="utf-8") as fh:
        return fh.read()


def build_user_input(diff, scout_report, conventions, max_diff_chars=40000):
    items = scout_report.get("items", [])
    lines = ["## PR diff", diff[:max_diff_chars], "", "## Scouting report"]
    if items:
        for it in items:
            lines.append(f"- {it.get('path')}:{it.get('line')} {it.get('body', '')[:800]}")
    else:
        lines.append("(empty -- no scouting report available)")
    lines += ["", "## Repo conventions", conventions[:8000]]
    return "\n".join(lines)


def hypotheses(diff, scout_report, conventions):
    """Returns a validated list of 1..4 hypotheses."""
    from openai import OpenAI

    client = OpenAI()
    resp = client.responses.create(
        model=MODEL,
        instructions=_system_prompt(),
        input=build_user_input(diff, scout_report, conventions),
        text={
            "format": {
                "type": "json_schema",
                "name": "hypotheses",
                "schema": HYPOTHESIS_JSON_SCHEMA,
                "strict": True,
            }
        },
    )
    data = json.loads(resp.output_text)
    return normalize(data.get("hypotheses", []))


def normalize(raw):
    out = []
    for i, h in enumerate(raw[:MAX_HYPOTHESES], start=1):
        h = dict(h)
        h.setdefault("id", f"h{i}")
        h["line"] = int(h.get("line") or 0)
        validate_hypothesis(h)
        out.append(h)
    if not out:
        raise ValueError("recon produced no hypotheses")
    return out


def slug(hypothesis):
    """tests/exploits/test_<slug>.py (PRD 6.3)."""
    base = "".join(
        c if c.isalnum() else "_" for c in (hypothesis.get("title") or hypothesis["id"]).lower()
    )
    return "_".join(p for p in base.split("_") if p)[:48] or hypothesis["id"]
