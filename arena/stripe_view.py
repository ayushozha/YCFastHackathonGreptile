"""Refunds on the fixture's seeded payment intent, test mode only (PRD 9).

The UI shows this as a cut-in card after a landed B1 hit (two refunds on one
payment) and again after the fix (one). Reads the intent id out of
runs/<id>/repo/seed.json -- the arena reads nothing else from the workdir.
"""

import json
import os

from arena.paths import seed_path


def payment_intent_id(arena_id):
    path = seed_path(arena_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        seed = json.load(fh)
    return seed.get("stripe_payment_intent") or seed.get("payment_intent")


def refunds(arena_id):
    """{"available": bool, "payment_intent": id, "refunds": [...]}"""
    intent = payment_intent_id(arena_id)
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not intent or not key:
        return {
            "available": False,
            "reason": "no seed.json" if not intent else "STRIPE_SECRET_KEY unset",
            "payment_intent": intent,
            "refunds": [],
        }
    import stripe

    stripe.api_key = key
    listing = stripe.Refund.list(payment_intent=intent, limit=10)
    return {
        "available": True,
        "payment_intent": intent,
        "refunds": [
            {
                "id": r["id"],
                "amount": r["amount"],
                "currency": r.get("currency"),
                "status": r.get("status"),
                "created": r.get("created"),
            }
            for r in listing.get("data", [])
        ],
    }
