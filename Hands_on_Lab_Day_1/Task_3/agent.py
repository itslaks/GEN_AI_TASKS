"""
agent.py — Self-Reflecting Code Review Agent orchestration.
"""

import json
import logging
import re
from typing import Any

from analyzer import analyze
from groq_client import chat
from prompts import (
    build_review_messages,
    build_reflect_messages,
    build_revise_messages,
    MALICIOUS_SIGNALS,
)

log = logging.getLogger(__name__)

# ── JSON extraction helper ────────────────────────────────────────────────────
def _extract_json(text: str) -> Any:
    """Extract JSON from LLM response — strips markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` fences
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _is_malicious(source: str) -> bool:
    """Heuristic check for obviously malicious patterns."""
    lower = source.lower()
    hits = sum(1 for sig in MALICIOUS_SIGNALS if sig.lower() in lower)
    return hits >= 4  # conservative threshold


def _normalize(source: str) -> str:
    """Normalize line endings, strip BOM."""
    return source.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


def _validate_schema(review: dict) -> dict:
    """Ensure the review dict matches our required schema; fill gaps."""
    review.setdefault("summary", "")
    review.setdefault("severity_breakdown", {"critical": 0, "high": 0, "medium": 0, "low": 0})
    review.setdefault("issues", [])
    review.setdefault("tests_to_add", [])
    review.setdefault("reflections_applied", [])

    # Re-compute severity breakdown from issues list
    sb = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in review["issues"]:
        sev = issue.get("severity", "low")
        if sev in sb:
            sb[sev] += 1
        # Ensure required subfields
        issue.setdefault("id", f"I{len(review['issues']):03d}")
        issue.setdefault("evidence", {"lines": [], "snippet": ""})
        issue.setdefault("suggested_patch", None)
    review["severity_breakdown"] = sb
    return review


# ── Main agent entry point ─────────────────────────────────────────────────────
def run_review(
    source: str,
    max_rounds: int = 2,
    verbose: bool = False,
) -> dict:
    """
    Run the self-reflecting code review agent.

    Returns final review dict matching the output JSON schema.
    """
    source = _normalize(source)

    def vlog(msg: str):
        if verbose:
            log.info(msg)

    # ── Step 1: AST analysis ──────────────────────────────────────────────────
    vlog("Running AST analysis…")
    findings = analyze(source)
    ast_dict = findings.to_dict()

    if findings.syntax_error:
        vlog(f"Syntax error detected: {findings.syntax_error}")

    # ── Step 2: Malicious code check ──────────────────────────────────────────
    if _is_malicious(source):
        log.warning("⚠ Potential malicious code detected. Review will flag this.")

    # ── Step 3: Round 1 — Initial review ─────────────────────────────────────
    vlog("Round 1: Generating initial review…")
    msgs = build_review_messages(source, ast_dict)
    raw = chat(msgs)
    try:
        review = _validate_schema(_extract_json(raw))
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"LLM returned non-JSON on initial review: {e}\nRaw: {raw[:500]}")

    vlog(f"Round 1 complete. Found {len(review['issues'])} issues.")

    # ── Step 4: Self-reflection + revision loop ────────────────────────────────
    for round_num in range(2, max_rounds + 1):
        vlog(f"Reflection step (before round {round_num})…")
        reflect_msgs = build_reflect_messages(source, review)
        reflect_raw = chat(reflect_msgs)

        try:
            reflections: list[str] = _extract_json(reflect_raw)
            if not isinstance(reflections, list):
                reflections = []
        except (json.JSONDecodeError, ValueError):
            vlog("Reflection returned non-JSON; skipping revision.")
            break

        if not reflections:
            vlog("Reflection found no material improvements. Stopping early.")
            break

        vlog(f"Applying {len(reflections)} reflection(s) in round {round_num}…")
        revise_msgs = build_revise_messages(source, ast_dict, review, reflections)
        revise_raw = chat(revise_msgs)

        try:
            revised = _validate_schema(_extract_json(revise_raw))
            # Preserve any previously applied reflections
            existing = review.get("reflections_applied", [])
            revised["reflections_applied"] = existing + revised.get("reflections_applied", [])
            review = revised
        except (json.JSONDecodeError, ValueError) as e:
            vlog(f"Revision JSON parse failed: {e}. Keeping previous review.")
            break

        vlog(f"Round {round_num} complete. Now {len(review['issues'])} issues.")

    return review