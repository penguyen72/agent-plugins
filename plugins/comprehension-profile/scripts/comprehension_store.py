"""Validate and persist Comprehension Profile learning observations."""

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path
import re


SCHEMA_VERSION = 1
MAX_EVIDENCE_ITEMS = 6
MAX_EXCERPT_LENGTH = 280
ALLOWED_FIELDS = {
    "schema_version",
    "id",
    "captured_at",
    "source",
    "harness",
    "session_key",
    "topic",
    "confusion",
    "clarification_questions",
    "successful_explanation",
    "why_it_worked",
    "candidate_rule",
    "signals",
    "evidence",
}
ALLOWED_SIGNALS = {
    "explicit_confusion",
    "repeated_clarification",
    "user_restatement",
    "assistant_confirmation",
    "explicit_understanding",
}
AUTOMATIC_SIGNALS = {
    "explicit_confusion",
    "user_restatement",
    "assistant_confirmation",
}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ALLOWED_SOURCES = {"manual", "automatic"}
ALLOWED_HARNESSES = {"codex", "claude", "other"}
EVIDENCE_FIELDS = {"role", "excerpt"}
ALLOWED_EVIDENCE_ROLES = {"user", "assistant"}


def resolve_store_root(env=None, home=None):
    values = os.environ if env is None else env
    override = values.get("COMPREHENSION_PROFILE_HOME", "").strip()
    return (
        Path(override).expanduser()
        if override
        else (home or Path.home()) / ".comprehension-profile"
    )


def hash_session_key(harness: str, session_id: str) -> str:
    return sha256(f"{harness}\0{session_id}".encode("utf-8")).hexdigest()


def make_observation_id(session_key: str, *parts: str) -> str:
    normalized = [" ".join(part.split()) for part in parts]
    material = "\0".join([session_key, *normalized])
    return sha256(material.encode("utf-8")).hexdigest()


def _required_string(
    record: Mapping[object, object],
    field: str,
    limit: int,
    errors: list[str],
) -> None:
    if field not in record:
        return
    value = record[field]
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be non-empty")
    elif len(value) > limit:
        errors.append(f"{field} must be at most {limit} characters")


def _validate_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _validate_clarification_questions(value: object, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("clarification_questions must be an array")
        return
    if len(value) > 5:
        errors.append("clarification_questions must contain at most 5 items")
    for index, question in enumerate(value, start=1):
        if not isinstance(question, str):
            errors.append(f"clarification question {index} must be a string")
        elif len(question) > MAX_EXCERPT_LENGTH:
            errors.append(
                f"clarification question {index} must be at most "
                f"{MAX_EXCERPT_LENGTH} characters"
            )


def _validate_signals(value: object, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("signals must be an array")
        return
    if len(value) != len(set(item for item in value if isinstance(item, str))):
        errors.append("signals must be unique")
    for signal in value:
        if not isinstance(signal, str):
            errors.append("signals must contain only strings")
        elif signal not in ALLOWED_SIGNALS:
            errors.append(f"invalid signal: {signal}")


def _validate_evidence(value: object, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("evidence must be an array")
        return
    if not value:
        errors.append("evidence must contain at least 1 item")
    if len(value) > MAX_EVIDENCE_ITEMS:
        errors.append(f"evidence must contain at most {MAX_EVIDENCE_ITEMS} items")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"evidence item {index} must be an object")
            continue
        unknown = set(item) - EVIDENCE_FIELDS
        for field in sorted(unknown, key=str):
            errors.append(f"unknown evidence field: {field}")
        for field in sorted(EVIDENCE_FIELDS - set(item)):
            errors.append(f"evidence item {index} {field} is required")

        role = item.get("role")
        if "role" in item and (
            not isinstance(role, str) or role not in ALLOWED_EVIDENCE_ROLES
        ):
            errors.append(f"evidence item {index} role must be user or assistant")

        excerpt = item.get("excerpt")
        if "excerpt" in item:
            if not isinstance(excerpt, str) or not excerpt.strip():
                errors.append(f"evidence item {index} excerpt must be non-empty")
            elif len(excerpt) > MAX_EXCERPT_LENGTH:
                errors.append(
                    f"evidence item {index} excerpt must be at most "
                    f"{MAX_EXCERPT_LENGTH} characters"
                )


def validate_observation(record: object) -> list[str]:
    """Return every validation error for a learning observation."""
    if not isinstance(record, Mapping):
        return ["observation must be an object"]

    errors = [
        f"unknown field: {field}"
        for field in sorted(set(record) - ALLOWED_FIELDS, key=str)
    ]
    missing = ALLOWED_FIELDS - set(record)
    errors.extend(f"{field} is required" for field in sorted(missing))

    if "schema_version" in record:
        version = record["schema_version"]
        if type(version) is not int:
            errors.append(f"schema_version must be the integer {SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")

    for field in ("id", "session_key"):
        value = record.get(field)
        if field in record and (
            not isinstance(value, str) or not HEX_64.fullmatch(value)
        ):
            errors.append(f"{field} must be 64 lowercase hexadecimal characters")

    if "captured_at" in record and not _validate_timestamp(record["captured_at"]):
        errors.append("captured_at must be an RFC 3339 UTC timestamp ending in Z")

    source = record.get("source")
    if "source" in record and (
        not isinstance(source, str) or source not in ALLOWED_SOURCES
    ):
        errors.append("source must be manual or automatic")

    harness = record.get("harness")
    if "harness" in record and (
        not isinstance(harness, str) or harness not in ALLOWED_HARNESSES
    ):
        errors.append("harness must be codex, claude, or other")

    _required_string(record, "topic", 120, errors)
    _required_string(record, "confusion", 500, errors)
    _required_string(record, "successful_explanation", 500, errors)
    _required_string(record, "why_it_worked", 500, errors)
    _required_string(record, "candidate_rule", 300, errors)

    if "clarification_questions" in record:
        _validate_clarification_questions(record["clarification_questions"], errors)
    if "signals" in record:
        _validate_signals(record["signals"], errors)
    if "evidence" in record:
        _validate_evidence(record["evidence"], errors)

    if source == "automatic":
        signals = record.get("signals")
        present = set(signals) if isinstance(signals, list) else set()
        for signal in sorted(AUTOMATIC_SIGNALS - present):
            errors.append(f"automatic observation requires signal: {signal}")

    return errors
