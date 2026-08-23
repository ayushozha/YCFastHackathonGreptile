"""Recon: diff + scout report + conventions -> 1..4 attack hypotheses (PRD 6.2).

Primary path is the one the PRD names: a single OpenAI Responses API call with
the JSON schema enforced, prompt in prompts/recon.txt.

`RECON=codex` is the labeled fallback for a machine with no OPENAI_API_KEY.
It runs the same prompt and the same schema through `codex exec
--output-schema`, read-only so it cannot touch the clone. Same model family,
same enforced shape, different transport -- and it keeps the run honest when
the key is missing rather than stubbing the stage (PRD rule 0.5).

Which path ran is reported in the `source` field so the ticker can say so.
"""

import json
import os

from shared.schema import ATTACKERS, validate_hypothesis

MODEL = os.environ.get("RECON_MODEL", "gpt-5")
MAX_HYPOTHESES = 4


def backend():
    """openai | codex. Explicit RECON wins; otherwise the key decides."""
    choice = os.environ.get("RECON", "").strip().lower()
    if choice in ("openai", "codex"):
        return choice
    return "openai" if os.environ.get("OPENAI_API_KEY") else "codex"

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


def hypotheses(diff, scout_report, conventions, workdir="."):
    """Returns (validated hypotheses, backend name)."""
    user_input = build_user_input(diff, scout_report, conventions)
    if backend() == "codex":
        return normalize(_via_codex(user_input, workdir)), "codex"
    return normalize(_via_openai(user_input)), "openai"


def _via_codex(user_input, workdir):
    """codex exec with --output-schema: same prompt, same enforced shape."""
    from engine import codex

    prompt = (
        _system_prompt()
        + "\n\nReturn ONLY the JSON object. Do not read or write any files;"
        " everything you need is below.\n\n"
        + user_input
    )
    out = codex.exec(
        prompt,
        workdir,
        kind="recon",
        timeout=240,
        extra_flags=codex.READONLY_FLAGS,
        output_schema=HYPOTHESIS_JSON_SCHEMA,
    )
    if out["exit_code"] != 0:
        raise RuntimeError(f"recon via codex failed (exit {out['exit_code']})")
    return _extract(out["last_message"]).get("hypotheses", [])


def _extract(text):
    """The last message should be the JSON object; be forgiving about fences."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"recon returned no JSON object: {text[:300]!r}")
        return json.loads(text[start : end + 1])


def _via_openai(user_input):
    from openai import OpenAI

    client = OpenAI()
    resp = client.responses.create(
        model=MODEL,
        instructions=_system_prompt(),
        input=user_input,
        text={
            "format": {
                "type": "json_schema",
                "name": "hypotheses",
                "schema": HYPOTHESIS_JSON_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(resp.output_text).get("hypotheses", [])


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
