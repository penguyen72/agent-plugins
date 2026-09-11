import re
import unittest
from pathlib import Path

from tests.comprehension_helpers import load_plugin_module


store = load_plugin_module(
    "comprehension_store",
    "scripts/comprehension_store.py",
)


def valid_observation() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "a" * 64,
        "captured_at": "2026-09-11T00:00:00Z",
        "source": "manual",
        "harness": "codex",
        "session_key": "b" * 64,
        "topic": "dependency injection",
        "confusion": "The abstraction hid object creation.",
        "clarification_questions": ["Who constructs the dependency?"],
        "successful_explanation": "A request path showed construction before use.",
        "why_it_worked": "Execution order made ownership concrete.",
        "candidate_rule": "Show lifecycle before naming abstractions.",
        "signals": ["explicit_confusion", "assistant_confirmation"],
        "evidence": [
            {"role": "user", "excerpt": "So the container creates it first?"},
            {"role": "assistant", "excerpt": "Exactly."},
        ],
    }


class ObservationSchemaTests(unittest.TestCase):
    def test_valid_manual_observation_has_no_errors(self):
        self.assertEqual(store.validate_observation(valid_observation()), [])

    def test_unknown_field_is_rejected(self):
        record = valid_observation()
        record["style"] = "friendly"
        self.assertIn("unknown field: style", store.validate_observation(record))

    def test_automatic_observation_requires_three_signals(self):
        record = valid_observation()
        record["source"] = "automatic"
        self.assertIn(
            "automatic observation requires signal: user_restatement",
            store.validate_observation(record),
        )

    def test_session_hash_is_stable_and_hides_raw_identifier(self):
        value = store.hash_session_key("codex", "session/secret-123")
        self.assertRegex(value, re.compile(r"^[0-9a-f]{64}$"))
        self.assertNotIn("secret-123", value)
        self.assertEqual(value, store.hash_session_key("codex", "session/secret-123"))

    def test_observation_id_normalizes_whitespace(self):
        key = "b" * 64
        first = store.make_observation_id(key, "one  two", "three")
        second = store.make_observation_id(key, "one two", "three")
        self.assertEqual(first, second)
        self.assertRegex(first, re.compile(r"^[0-9a-f]{64}$"))

    def test_store_root_prefers_nonempty_override(self):
        self.assertEqual(
            store.resolve_store_root(
                {"COMPREHENSION_PROFILE_HOME": "/tmp/profile-test"},
                Path("/unused"),
            ),
            Path("/tmp/profile-test"),
        )

    def test_store_root_uses_home_for_blank_override(self):
        self.assertEqual(
            store.resolve_store_root(
                {"COMPREHENSION_PROFILE_HOME": "  "},
                Path("/fake-home"),
            ),
            Path("/fake-home/.comprehension-profile"),
        )

    def test_valid_automatic_observation_has_no_errors(self):
        record = valid_observation()
        record["source"] = "automatic"
        record["signals"] = [
            "explicit_confusion",
            "user_restatement",
            "assistant_confirmation",
        ]
        self.assertEqual(store.validate_observation(record), [])

    def test_invalid_field_values_are_rejected(self):
        cases = {
            "schema_version": (2, "schema_version must be 1"),
            "id": ("not-hex", "id must be 64 lowercase hexadecimal characters"),
            "captured_at": (
                "2026-09-11",
                "captured_at must be an RFC 3339 UTC timestamp ending in Z",
            ),
            "source": ("hook", "source must be manual or automatic"),
            "harness": ("chatgpt", "harness must be codex, claude, or other"),
            "session_key": (
                "raw-session-id",
                "session_key must be 64 lowercase hexadecimal characters",
            ),
            "topic": ("x" * 121, "topic must be at most 120 characters"),
            "confusion": ("", "confusion must be non-empty"),
            "clarification_questions": (
                ["x" * 281],
                "clarification question 1 must be at most 280 characters",
            ),
            "successful_explanation": (
                "x" * 501,
                "successful_explanation must be at most 500 characters",
            ),
            "why_it_worked": (
                "x" * 501,
                "why_it_worked must be at most 500 characters",
            ),
            "candidate_rule": (
                "x" * 301,
                "candidate_rule must be at most 300 characters",
            ),
            "signals": (["unknown"], "invalid signal: unknown"),
            "evidence": (
                [{"role": "tool", "excerpt": "hidden"}],
                "evidence item 1 role must be user or assistant",
            ),
        }
        for field, (value, expected) in cases.items():
            with self.subTest(field=field):
                record = valid_observation()
                record[field] = value
                self.assertIn(expected, store.validate_observation(record))

    def test_collection_and_shape_boundaries(self):
        mutations = [
            (
                "evidence",
                [{"role": "user", "excerpt": str(i)} for i in range(7)],
                "at most 6",
            ),
            (
                "signals",
                ["explicit_confusion", "explicit_confusion"],
                "signals must be unique",
            ),
            ("evidence", [], "at least 1"),
            (
                "evidence",
                [{"role": "user", "excerpt": "x", "extra": True}],
                "unknown evidence field",
            ),
        ]
        for field, value, expected in mutations:
            with self.subTest(field=field, expected=expected):
                record = valid_observation()
                record[field] = value
                self.assertIn(expected, "; ".join(store.validate_observation(record)))

    def test_clarification_question_count_is_limited(self):
        record = valid_observation()
        record["clarification_questions"] = [str(i) for i in range(6)]
        self.assertIn(
            "clarification_questions must contain at most 5 items",
            store.validate_observation(record),
        )

    def test_evidence_excerpt_must_be_nonempty_and_within_limit(self):
        for excerpt, expected in (
            ("", "evidence item 1 excerpt must be non-empty"),
            ("x" * 281, "evidence item 1 excerpt must be at most 280 characters"),
        ):
            with self.subTest(expected=expected):
                record = valid_observation()
                record["evidence"] = [{"role": "user", "excerpt": excerpt}]
                self.assertIn(expected, store.validate_observation(record))

    def test_non_object_and_missing_fields_are_rejected(self):
        self.assertIn("observation must be an object", store.validate_observation([]))
        record = valid_observation()
        del record["topic"]
        self.assertIn("topic is required", store.validate_observation(record))

    def test_wrong_json_types_are_reported_without_crashing(self):
        cases = {
            "schema_version": (True, "schema_version must be the integer 1"),
            "id": ([], "id must be 64 lowercase hexadecimal characters"),
            "source": ({}, "source must be manual or automatic"),
            "harness": ([], "harness must be codex, claude, or other"),
            "clarification_questions": (
                "question",
                "clarification_questions must be an array",
            ),
            "signals": ("explicit_confusion", "signals must be an array"),
            "evidence": (
                [{"role": [], "excerpt": "x"}],
                "evidence item 1 role must be user or assistant",
            ),
        }
        for field, (value, expected) in cases.items():
            with self.subTest(field=field):
                record = valid_observation()
                record[field] = value
                self.assertIn(expected, store.validate_observation(record))

    def test_invalid_calendar_timestamp_is_rejected(self):
        record = valid_observation()
        record["captured_at"] = "2026-13-40T25:61:61Z"
        self.assertIn(
            "captured_at must be an RFC 3339 UTC timestamp ending in Z",
            store.validate_observation(record),
        )


if __name__ == "__main__":
    unittest.main()
