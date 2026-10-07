"""Deterministic guards adapted from a human-supervised research workflow.

Checks record structure and declared relationships, not the truth of web claims.
The scoring weights describe prioritization; they are not conversion predictions.
"""

import math
from collections import Counter
from datetime import date
from urllib.parse import urlsplit


SCORE_LIMITS = {
    "process_fit": 35,
    "purchase_potential": 20,
    "reachability": 15,
    "trade_capability": 15,
    "development_ease": 15,
}
TERMINAL = {"researched", "no_reliable_contact", "low_fit"}
STATUSES = TERMINAL | {"pending", "in_progress"}
CONFIDENCE = {"low", "medium", "high"}


def grade_for(total):
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        raise ValueError("total must be a number")
    if not math.isfinite(total) or not 0 <= total <= 100:
        raise ValueError("total must be finite and within 0..100")
    return "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 45 else "D"


def text(value):
    return isinstance(value, str) and bool(value.strip())


def valid_url(value):
    if not text(value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"https", "http"} and bool(parsed.hostname)
    except ValueError:
        return False


def valid_date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def evaluate_batch(records):
    if not isinstance(records, list):
        raise ValueError("input must be a list of company records")
    errors, pending, contact_review = [], [], []
    ids, entities, ratings = set(), set(), Counter()
    if not records:
        errors.append("batch must contain at least one record")

    for index, record in enumerate(records):
        label = f"record[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label}: expected object")
            continue
        cid = record.get("company_id")
        if not text(cid):
            errors.append(f"{label}: missing company_id")
        else:
            label = cid
            if cid in ids:
                errors.append(f"{label}: duplicate company_id")
            ids.add(cid)

        for key in ("company_name", "country", "entity_key"):
            if not text(record.get(key)):
                errors.append(f"{label}: missing {key}")
        if text(record.get("entity_key")) and text(record.get("country")):
            entity = (record["country"].strip().casefold(), record["entity_key"].strip().casefold())
            if entity in entities:
                errors.append(f"{label}: duplicate country/entity_key")
            entities.add(entity)

        status = record.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(f"{label}: invalid status")
        elif status not in TERMINAL and text(cid):
            pending.append(cid)

        scores = record.get("scores")
        score_ok = isinstance(scores, dict) and set(scores) == set(SCORE_LIMITS)
        if score_ok:
            for key, upper in SCORE_LIMITS.items():
                value = scores[key]
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or not 0 <= value <= upper):
                    score_ok = False
        if not score_ok:
            errors.append(f"{label}: invalid score components")
        else:
            expected = grade_for(sum(scores.values()))
            if record.get("grade") != expected:
                errors.append(f"{label}: grade must be {expected}")
            else:
                ratings[expected] += 1
        if not text(record.get("score_rationale")):
            errors.append(f"{label}: missing score_rationale")

        evidence = record.get("evidence")
        evidence_ids = set()
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label}: at least one evidence record is required")
        else:
            for item in evidence:
                if not isinstance(item, dict):
                    errors.append(f"{label}: invalid evidence object")
                    continue
                eid = item.get("evidence_id")
                if not text(eid) or eid in evidence_ids:
                    errors.append(f"{label}: missing or duplicate evidence_id")
                else:
                    evidence_ids.add(eid)
                if not valid_url(item.get("url")) or not valid_date(item.get("checked_on")):
                    errors.append(f"{label}: evidence needs source URL and ISO date")
                if not text(item.get("claim")):
                    errors.append(f"{label}: evidence needs claim")
                if item.get("confidence") not in ("low", "medium", "high"):
                    errors.append(f"{label}: invalid evidence confidence")

        contacts = record.get("contacts")
        contact_keys = set()
        if not isinstance(contacts, list):
            errors.append(f"{label}: contacts must be a list (empty is allowed)")
            continue
        for contact in contacts:
            if not isinstance(contact, dict):
                errors.append(f"{label}: invalid contact object")
                continue
            source_id = contact.get("source_id")
            if not isinstance(source_id, str) or source_id not in evidence_ids:
                errors.append(f"{label}: contact references missing evidence")
            scope = contact.get("scope")
            if scope not in ("company", "person", "unresolved"):
                errors.append(f"{label}: invalid contact scope")
            if scope == "company" and contact.get("person_name"):
                errors.append(f"{label}: company route must not be assigned to a person")
            if scope == "person" and (
                not text(contact.get("person_name"))
                or contact.get("attribution") != "explicit_in_source"
            ):
                errors.append(f"{label}: person route requires explicit source attribution")
            email = contact.get("email")
            if not text(email) or email.count("@") != 1 or any(c.isspace() for c in email):
                errors.append(f"{label}: invalid demo email")
            else:
                key = email.strip().casefold()
                if key in contact_keys:
                    errors.append(f"{label}: duplicate contact route")
                contact_keys.add(key)
            # Public visibility and source confidence cannot establish deliverability.
            if contact.get("delivery_status") not in ("not_contacted", "bounced", "confirmed"):
                errors.append(f"{label}: invalid delivery status")
            if contact.get("delivery_status") == "confirmed" and not text(contact.get("confirmation_evidence")):
                errors.append(f"{label}: confirmed delivery requires separate evidence")
            if contact.get("delivery_status") != "confirmed" or scope == "unresolved":
                contact_review.append({"company_id": cid, "email": email, "scope": scope})

    return {
        "mode": "offline_synthetic_demo",
        "passed": not errors,
        "record_count": len(records),
        "grades": dict(sorted(ratings.items())),
        "all_research_terminal": bool(records) and not errors and not pending,
        "pending_research_ids": pending,
        "contact_routes_needing_review": contact_review,
        "errors": errors,
        "limits": "Structural checks only; no web verification, country acceptance, or sending.",
    }
