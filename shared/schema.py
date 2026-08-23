"""The contract. Frozen at M0 (1:15 pm) -- see PRD.md section 15.2.

Both halves depend on this module and nothing else in common:
  * the engine's test asserts every event it emits validates here
  * the arena's UI reads only the fields named here

Changing anything below after 1:15 requires both people at one screen.
"""

# Fields present on every event (PRD 6.7).
COMMON_FIELDS = ("type", "ts", "arena_id", "round", "seq")

# type -> required payload fields, straight from the table in PRD 6.7.
EVENT_SCHEMA = {
    "arena_created": ("pr", "repo"),
    "index_status": ("source", "status", "lines", "files"),
    "scout_report": ("source", "items"),
    "attacker_intro": ("hypothesis", "damage"),
    "exploit_written": ("hypothesis_id", "path"),
    "sandbox_up": ("hypothesis_id", "sandbox_id", "boot_ms"),
    "test_output": ("hypothesis_id", "line"),
    "hit": ("hypothesis_id", "damage", "hp_after"),
    "miss": ("hypothesis_id", "reason"),
    "round_over": ("launched", "landed", "missed", "hp"),
    "fix_start": (),
    "fix_diff": ("files",),
    "fix_result": (
        "suite_passed",
        "suite_failed",
        "exploits_blocked",
        "exploits_still_landed",
    ),
    "fix_rejected": ("failing_tests",),
    "blocked": ("hypothesis_id", "hp_after"),
    "still_landed": ("hypothesis_id",),
    "final": (
        "launched",
        "landed_r1",
        "landed_r2",
        "suite_passed",
        "files_changed",
        "result",
    ),
    "error": ("stage", "message"),
}

# PRD 6.2. Recon returns a severity; the engine turns it into damage.
DAMAGE_BY_SEVERITY = {"critical": 40, "high": 30, "medium": 20}
MAX_TOTAL_DAMAGE = 100
STARTING_HP = 100

ATTACKERS = ("bug_hunter", "security", "ledger")

HYPOTHESIS_FIELDS = (
    "id",
    "attacker",
    "title",
    "claim",
    "file",
    "line",
    "exploit_plan",
    "severity",
)


class SchemaError(ValueError):
    """Raised when an event does not match EVENT_SCHEMA."""


def validate(event):
    """Raise SchemaError unless `event` is a well-formed event.

    Returns the event so it can be used inline: emit(validate(e)).
    """
    if not isinstance(event, dict):
        raise SchemaError(f"event must be a dict, got {type(event).__name__}")

    etype = event.get("type")
    if etype not in EVENT_SCHEMA:
        raise SchemaError(f"unknown event type: {etype!r}")

    missing = [f for f in COMMON_FIELDS if f not in event]
    if missing:
        raise SchemaError(f"{etype}: missing common fields {missing}")

    if not isinstance(event["seq"], int):
        raise SchemaError(f"{etype}: seq must be an int, got {event['seq']!r}")
    if event["round"] not in (1, 2):
        raise SchemaError(f"{etype}: round must be 1 or 2, got {event['round']!r}")

    missing = [f for f in EVENT_SCHEMA[etype] if f not in event]
    if missing:
        raise SchemaError(f"{etype}: missing payload fields {missing}")

    return event


def is_valid(event):
    try:
        validate(event)
        return True
    except SchemaError:
        return False


def validate_hypothesis(h):
    """Recon output check (PRD 6.2)."""
    missing = [f for f in HYPOTHESIS_FIELDS if f not in h]
    if missing:
        raise SchemaError(f"hypothesis missing fields {missing}")
    if h["attacker"] not in ATTACKERS:
        raise SchemaError(f"unknown attacker: {h['attacker']!r}")
    if h["severity"] not in DAMAGE_BY_SEVERITY:
        raise SchemaError(f"unknown severity: {h['severity']!r}")
    return h


def damage_for(hypotheses):
    """Damage per hypothesis, scaled down so the total never exceeds 100 (PRD 6.2)."""
    raw = [DAMAGE_BY_SEVERITY[h["severity"]] for h in hypotheses]
    total = sum(raw)
    if total <= MAX_TOTAL_DAMAGE:
        return raw
    scale = MAX_TOTAL_DAMAGE / total
    scaled = [max(1, int(d * scale)) for d in raw]
    # give the rounding remainder to the biggest hit so the total lands on 100
    drift = MAX_TOTAL_DAMAGE - sum(scaled)
    if drift and scaled:
        scaled[raw.index(max(raw))] += drift
    return scaled
