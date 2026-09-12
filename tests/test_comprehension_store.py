import contextlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tests.comprehension_helpers import PLUGIN_ROOT, load_plugin_module


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

    def test_automatic_observation_rejects_non_string_signals_without_crashing(self):
        record = valid_observation()
        record["source"] = "automatic"
        record["signals"] = ["explicit_confusion", [], {"signal": "invalid"}]
        errors = store.validate_observation(record)
        self.assertIn("signals must contain only strings", errors)
        self.assertIn(
            "automatic observation requires signal: user_restatement", errors
        )


class ObservationPersistenceTests(unittest.TestCase):
    def test_append_creates_one_compact_valid_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            self.assertTrue(store.append_observation(valid_observation(), root))
            lines = (root / "observations.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), valid_observation())
            self.assertNotIn(": ", lines[0])

    def test_duplicate_id_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(store.append_observation(valid_observation(), root))
            self.assertFalse(store.append_observation(valid_observation(), root))
            self.assertEqual(
                len((root / "observations.jsonl").read_text().splitlines()), 1
            )

    def test_duplicate_id_is_a_no_op_when_it_is_not_the_last_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = valid_observation()
            second = valid_observation()
            second["id"] = "c" * 64
            self.assertTrue(store.append_observation(first, root))
            self.assertTrue(store.append_observation(second, root))
            self.assertFalse(store.append_observation(first, root))
            self.assertEqual(
                len((root / "observations.jsonl").read_text().splitlines()), 2
            )

    def test_invalid_observation_does_not_create_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            record = valid_observation()
            record["topic"] = ""
            with self.assertRaisesRegex(ValueError, "topic"):
                store.append_observation(record, root)
            self.assertFalse(root.exists())

    def test_load_reports_bad_line_and_keeps_valid_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            valid = json.dumps(valid_observation(), separators=(",", ":"))
            (root / "observations.jsonl").write_text(
                f"not-json\n{valid}\n", encoding="utf-8"
            )
            records, errors = store.load_observations(root)
            self.assertEqual(records, [valid_observation()])
            self.assertIn("line 1", errors[0])

    def test_load_reports_invalid_record_and_keeps_valid_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            invalid = valid_observation()
            invalid["topic"] = ""
            content = "\n".join(
                json.dumps(item, separators=(",", ":"))
                for item in (invalid, valid_observation())
            )
            (root / "observations.jsonl").write_text(
                content + "\n", encoding="utf-8"
            )
            records, errors = store.load_observations(root)
            self.assertEqual(records, [valid_observation()])
            self.assertIn("line 1", errors[0])
            self.assertIn("topic", errors[0])

    def test_load_reports_non_string_automatic_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            record = valid_observation()
            record["source"] = "automatic"
            record["signals"] = ["explicit_confusion", []]
            (root / "observations.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            records, errors = store.load_observations(root)
            self.assertEqual(records, [])
            self.assertIn("signals must contain only strings", errors[0])

    def test_scrub_excerpt_redacts_before_truncating(self):
        text = "Authorization: Bearer secret-token " + ("x" * 400)
        scrubbed = store.scrub_excerpt(text)
        self.assertNotIn("secret-token", scrubbed)
        self.assertLessEqual(len(scrubbed), 280)

    def test_scrub_excerpt_redacts_credential_assignment(self):
        self.assertNotIn("abc123", store.scrub_excerpt("API_KEY=abc123"))

    def test_scrub_excerpt_redacts_private_key_header(self):
        self.assertNotIn(
            "BEGIN RSA PRIVATE KEY",
            store.scrub_excerpt("-----BEGIN RSA PRIVATE KEY-----"),
        )

    def test_append_scrubs_evidence_without_truncating_core_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = valid_observation()
            record["evidence"] = [
                {"role": "user", "excerpt": "API_TOKEN=secret-value"}
            ]
            self.assertTrue(store.append_observation(record, root))
            records, errors = store.load_observations(root)
            self.assertEqual(errors, [])
            self.assertNotIn("secret-value", records[0]["evidence"][0]["excerpt"])

            oversized = valid_observation()
            oversized["confusion"] = "x" * 501
            with self.assertRaisesRegex(ValueError, "confusion"):
                store.append_observation(oversized, root)

    def test_append_rejects_dangling_symlink_without_creating_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            profile_path = root / "profile.md"
            observations_path = root / "observations.jsonl"
            observations_path.symlink_to(profile_path.name)
            with self.assertRaisesRegex(OSError, "regular file"):
                store.append_observation(valid_observation(), root)
            self.assertTrue(observations_path.is_symlink())
            self.assertFalse(profile_path.exists())

    def test_load_rejects_symlink_instead_of_reading_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            target = Path(directory) / "outside.jsonl"
            target.write_text(
                json.dumps(valid_observation()) + "\n", encoding="utf-8"
            )
            (root / "observations.jsonl").symlink_to(target)
            records, errors = store.load_observations(root)
            self.assertEqual(records, [])
            self.assertIn("regular file", errors[0])

    @unittest.skipUnless(os.name == "posix", "POSIX permission modes required")
    def test_new_store_and_observation_file_are_user_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            previous_umask = os.umask(0)
            try:
                store.append_observation(valid_observation(), root)
            finally:
                os.umask(previous_umask)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(
                stat.S_IMODE((root / "observations.jsonl").stat().st_mode), 0o600
            )

    def test_lock_contention_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".observations.lock").write_text("held")
            with self.assertRaisesRegex(OSError, "lock"):
                store.append_observation(valid_observation(), root)
            self.assertFalse((root / "observations.jsonl").exists())

    def test_lock_owner_does_not_remove_replacement_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / ".observations.lock"
            with store._observation_lock(root):
                lock_path.unlink()
                lock_path.write_text("replacement", encoding="utf-8")
            self.assertEqual(lock_path.read_text(encoding="utf-8"), "replacement")

    def test_missing_owned_lock_does_not_mask_successful_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / ".observations.lock"
            with store._observation_lock(root):
                lock_path.unlink()
            self.assertFalse(lock_path.exists())

    def test_lock_acquisition_failure_removes_owned_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(
                store.os, "fsync", side_effect=OSError("forced fsync failure")
            ):
                with self.assertRaisesRegex(OSError, "forced fsync failure"):
                    with store._observation_lock(root):
                        self.fail("lock acquisition should not complete")
            self.assertFalse((root / ".observations.lock").exists())

    def test_partial_lock_token_writes_are_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_write = store.os.write

            def write_one_byte(descriptor, payload):
                return original_write(descriptor, payload[:1])

            with mock.patch.object(store.os, "write", side_effect=write_one_byte):
                with store._observation_lock(root):
                    self.assertTrue((root / ".observations.lock").is_file())
            self.assertFalse((root / ".observations.lock").exists())

    def test_append_rejects_history_replacement_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store.append_observation(valid_observation(), root)
            second = valid_observation()
            second["id"] = "c" * 64
            observations_path = root / "observations.jsonl"
            replacement_path = root / "replacement.jsonl"
            original_loads = store.json.loads
            replaced = False

            def replace_after_validation(payload):
                nonlocal replaced
                record = original_loads(payload)
                if not replaced:
                    replacement_path.write_text("", encoding="utf-8")
                    os.replace(replacement_path, observations_path)
                    replaced = True
                return record

            with mock.patch.object(
                store.json, "loads", side_effect=replace_after_validation
            ):
                with self.assertRaisesRegex(OSError, "changed"):
                    store.append_observation(second, root)

    def test_raw_session_identifier_is_absent_from_persisted_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_session_id = "session/秘密/secret-123"
            record = valid_observation()
            record["session_key"] = store.hash_session_key("codex", raw_session_id)
            record["id"] = store.make_observation_id(
                record["session_key"],
                record["confusion"],
                record["successful_explanation"],
                record["candidate_rule"],
            )
            store.append_observation(record, root)
            persisted = (root / "observations.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(raw_session_id, persisted)
            self.assertNotIn("secret-123", persisted)

    def test_cli_append_reads_json_file_and_prints_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            source = Path(directory) / "observation.json"
            source.write_text(json.dumps(valid_observation()), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = store.main(
                    [
                        "append-observation",
                        "--input",
                        str(source),
                        "--store-root",
                        str(root),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue().strip(), "Observation appended.")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = store.main(
                    [
                        "append-observation",
                        "--input",
                        str(source),
                        "--store-root",
                        str(root),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue().strip(), "Observation already exists.")

    def test_python_interpreter_cli_command_appends_to_exact_store_root(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "approved-observation.json"
            root = Path(directory) / "resolved store"
            source.write_text(json.dumps(valid_observation()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/comprehension_store.py"),
                    "append-observation",
                    "--input",
                    str(source),
                    "--store-root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "Observation appended.")
            self.assertTrue((root / "observations.jsonl").is_file())
            self.assertFalse((root / "profile.md").exists())

    def test_cli_validate_reports_success_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "observation.json"
            source.write_text(json.dumps(valid_observation()), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = store.main(["validate-observation", "--input", str(source)])
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue().strip(), "Observation is valid.")

            source.write_text("not-json", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = store.main(["validate-observation", "--input", str(source)])
            self.assertEqual(code, 1)
            self.assertTrue(stderr.getvalue().strip())

    def test_cli_reports_non_string_automatic_signals_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "observation.json"
            record = valid_observation()
            record["source"] = "automatic"
            record["signals"] = ["explicit_confusion", {}]
            source.write_text(json.dumps(record), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = store.main(["validate-observation", "--input", str(source)])
            self.assertEqual(code, 1)
            self.assertIn("signals must contain only strings", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
