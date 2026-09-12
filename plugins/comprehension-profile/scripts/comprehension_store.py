"""Validate and persist Comprehension Profile learning observations."""

import argparse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time


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
LOCK_NAME = ".observations.lock"
OBSERVATIONS_NAME = "observations.jsonl"
LOCK_ATTEMPTS = 5
LOCK_DELAY_SECONDS = 0.02
REDACTIONS = (
    (
        re.compile(r"(authorization:\s*bearer\s+)\S+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"\b([A-Z0-9_]*(?:KEY|TOKEN|PASSWORD|SECRET))\s*=\s*\S+",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----", re.IGNORECASE),
        "[REDACTED PRIVATE KEY]",
    ),
)


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


def scrub_excerpt(text: str, max_length: int = MAX_EXCERPT_LENGTH) -> str:
    """Redact common credentials before limiting a persisted excerpt."""
    scrubbed = text
    for pattern, replacement in REDACTIONS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed[:max_length]


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
        present = (
            {signal for signal in signals if isinstance(signal, str)}
            if isinstance(signals, list)
            else set()
        )
        for signal in sorted(AUTOMATIC_SIGNALS - present):
            errors.append(f"automatic observation requires signal: {signal}")

    return errors


def _normalize_observation(record: object) -> object:
    if not isinstance(record, Mapping):
        return record
    normalized = dict(record)
    evidence = normalized.get("evidence")
    if isinstance(evidence, list):
        normalized_evidence: list[object] = []
        for item in evidence:
            if not isinstance(item, Mapping):
                normalized_evidence.append(item)
                continue
            normalized_item = dict(item)
            excerpt = normalized_item.get("excerpt")
            if isinstance(excerpt, str):
                normalized_item["excerpt"] = scrub_excerpt(excerpt)
            normalized_evidence.append(normalized_item)
        normalized["evidence"] = normalized_evidence
    return normalized


@contextmanager
def _observation_lock(store_root: Path) -> Iterator[None]:
    lock_path = store_root / LOCK_NAME
    lock_identity: tuple[int, int] | None = None
    lock_token = secrets.token_hex(16).encode("ascii")
    for attempt in range(LOCK_ATTEMPTS):
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if attempt == LOCK_ATTEMPTS - 1:
                raise OSError(
                    f"Could not acquire observation lock for store: {store_root}"
                ) from None
            time.sleep(LOCK_DELAY_SECONDS)
        else:
            lock_status = os.fstat(descriptor)
            lock_identity = (lock_status.st_dev, lock_status.st_ino)
            try:
                _write_all(descriptor, lock_token)
                os.fsync(descriptor)
            except BaseException:
                os.close(descriptor)
                _remove_lock_if_identity(lock_path, lock_identity)
                raise
            else:
                os.close(descriptor)
            break

    try:
        yield
    finally:
        if lock_identity is not None:
            _remove_owned_lock(lock_path, lock_identity, lock_token)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("Could not write observation lock token")
        offset += written


def _remove_lock_if_identity(
    lock_path: Path,
    expected_identity: tuple[int, int],
) -> None:
    try:
        path_status = os.lstat(lock_path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(path_status.st_mode):
        return
    if (path_status.st_dev, path_status.st_ino) != expected_identity:
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _remove_owned_lock(
    lock_path: Path,
    expected_identity: tuple[int, int],
    expected_token: bytes,
) -> None:
    try:
        path_status = os.lstat(lock_path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(path_status.st_mode):
        return
    if (path_status.st_dev, path_status.st_ino) != expected_identity:
        return

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags)
    except OSError:
        return
    try:
        opened_status = os.fstat(descriptor)
        if (opened_status.st_dev, opened_status.st_ino) != expected_identity:
            return
        if os.read(descriptor, len(expected_token) + 1) != expected_token:
            return
    finally:
        os.close(descriptor)
    _remove_lock_if_identity(lock_path, expected_identity)


def _file_identity(status: os.stat_result) -> tuple[int, int]:
    return status.st_dev, status.st_ino


def _regular_file_status(path: Path) -> os.stat_result | None:
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(status.st_mode):
        raise OSError(f"Observation store path must be a regular file: {path}")
    return status


def _verify_opened_regular_file(
    path: Path,
    descriptor: int,
    initial_status: os.stat_result | None,
) -> tuple[int, int]:
    opened_status = os.fstat(descriptor)
    if not stat.S_ISREG(opened_status.st_mode):
        raise OSError(f"Observation store path must be a regular file: {path}")
    current_status = _regular_file_status(path)
    if current_status is None:
        raise OSError(f"Observation store path changed while opening: {path}")
    opened_identity = _file_identity(opened_status)
    if _file_identity(current_status) != opened_identity:
        raise OSError(f"Observation store path changed while opening: {path}")
    if initial_status is not None and _file_identity(initial_status) != opened_identity:
        raise OSError(f"Observation store path changed while opening: {path}")
    return opened_identity


def _read_observation_lines(path: Path) -> list[str] | None:
    initial_status = _regular_file_status(path)
    if initial_status is None:
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        _verify_opened_regular_file(path, descriptor, initial_status)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            return handle.read().splitlines()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@contextmanager
def _open_observations_for_append(path: Path) -> Iterator[object]:
    initial_status = _regular_file_status(path)
    flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    if initial_status is None:
        flags |= os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        _verify_opened_regular_file(path, descriptor, initial_status)
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a+", encoding="utf-8", newline="") as handle:
            descriptor = -1
            yield handle
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _parse_observation_lines(
    lines: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"line {line_number}: invalid JSON: {error.msg}")
            continue
        record_errors = validate_observation(record)
        if record_errors:
            errors.append(f"line {line_number}: {'; '.join(record_errors)}")
            continue
        records.append(dict(record))
    return records, errors


def load_observations(
    store_root: Path,
) -> tuple[list[dict[str, object]], list[str]]:
    """Load valid observations and report line-specific errors without mutation."""
    path = store_root / OBSERVATIONS_NAME
    try:
        lines = _read_observation_lines(path)
    except (OSError, UnicodeError) as error:
        return [], [f"Cannot read {path}: {error}"]
    if lines is None:
        return [], []
    return _parse_observation_lines(lines)


def append_observation(record: dict[str, object], store_root: Path) -> bool:
    """Append one valid observation, returning false for a duplicate ID."""
    normalized = _normalize_observation(record)
    errors = validate_observation(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(normalized, dict):
        raise ValueError("observation must be an object")

    store_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = store_root / OBSERVATIONS_NAME
    with _observation_lock(store_root):
        payload = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        with _open_observations_for_append(path) as handle:
            handle.seek(0)
            try:
                lines = handle.read().splitlines()
            except UnicodeError as error:
                raise ValueError(f"Cannot read {path}: {error}") from error
            existing, load_errors = _parse_observation_lines(lines)
            if load_errors:
                raise ValueError("; ".join(load_errors))
            _verify_opened_regular_file(
                path, handle.fileno(), os.fstat(handle.fileno())
            )
            if any(item["id"] == normalized["id"] for item in existing):
                return False
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            _verify_opened_regular_file(
                path, handle.fileno(), os.fstat(handle.fileno())
            )
        return True


def _read_json_object(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    """Validate or append a learning observation from a UTF-8 JSON file."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-observation")
    validate_parser.add_argument("--input", required=True, type=Path)

    append_parser = subparsers.add_parser("append-observation")
    append_parser.add_argument("--input", required=True, type=Path)
    append_parser.add_argument("--store-root", type=Path)

    arguments = parser.parse_args(argv)
    try:
        record = _normalize_observation(_read_json_object(arguments.input))
        errors = validate_observation(record)
        if errors:
            raise ValueError("; ".join(errors))
        if arguments.command == "validate-observation":
            print("Observation is valid.")
            return 0
        if not isinstance(record, dict):
            raise ValueError("observation must be an object")
        store_root = arguments.store_root or resolve_store_root()
        appended = append_observation(record, store_root)
        print("Observation appended." if appended else "Observation already exists.")
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
