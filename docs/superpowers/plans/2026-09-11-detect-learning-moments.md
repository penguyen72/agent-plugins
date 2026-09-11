# Detect Learning Moments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a quiet session-end mechanism that records at most one candidate only when a completed Codex or Claude Code session contains an explicit confusion → clarification → user restatement → assistant confirmation sequence.

**Architecture:** A shared plugin hook sends `SessionEnd` JSON to a small Python command. Harness-specific adapters normalize only visible user and assistant text; a deterministic state machine selects the strongest complete sequence, creates a conservative version 1 observation, and appends it through the existing store API.

**Tech Stack:** Codex and Claude Code plugin hooks, JSONL transcript adapters, Python 3 standard library, `unittest`, synthetic transcript fixtures.

**Spec:** `docs/superpowers/specs/2026-09-11-comprehension-profile-design.md`

## Global Constraints

- Complete `docs/superpowers/plans/2026-09-11-capture-learning-pattern.md` first.
- Reuse observation schema version `1` and `comprehension_store.py`; do not fork the contract.
- Automatic observations require `explicit_confusion`, `user_restatement`, and `assistant_confirmation` signals.
- Store at most one strongest automatic observation per session.
- Read only visible `user` and `assistant` text; ignore system, developer, reasoning, tool, subagent, and repository content.
- Retain at most six excerpts of 280 characters and never persist a raw session ID.
- Normal no-match, unsupported transcript, missing path, duplicate ID, or lock contention must not disrupt session shutdown.
- Use no model call, API key, network request, service, database, or third-party dependency.
- Keep processing comfortably below Claude Code's default plugin `SessionEnd` budget by reading at most the last 2 MiB of a transcript.
- Do not read or write `profile.md`.

---

## Purpose

Collect high-signal learning observations without requiring the user to remember the manual skill. Precision is more important than recall: a session that merely contains questions or gratitude must produce no candidate.

## Existing Repository Context

The prerequisite plan creates the cross-platform plugin, version 1 contract, user-store functions, test module loader, catalog entries, and manual capture skill. Current official Codex and Claude Code hook contracts both expose `SessionEnd` input with `session_id` and `transcript_path`, but transcript records differ and Codex explicitly treats its format as unstable.

## Architecture, Inputs, and Outputs

Input is one hook-event JSON object on standard input. `transcript_adapters.py` returns a stable list of `NormalizedMessage(role, text, ordinal)`. `detect_learning_moments.py` recognizes complete sequences, derives a deliberately modest observation, and calls `append_observation`.

Output is `True` internally only when a new candidate is appended. The hook process exits `0` for appended, duplicate, no-match, malformed, unsupported, missing, or contended cases and emits no normal stdout. This component never invokes a skill and never changes the profile.

## Data Contracts

This plan consumes the exact observation API from Plan 1 and adds:

```python
class NormalizedMessage(NamedTuple):
    role: str
    text: str
    ordinal: int

class LearningSequence(NamedTuple):
    confusion_index: int
    restatement_index: int
    confirmation_index: int
    clarification_indices: tuple[int, ...]
    explanation_indices: tuple[int, ...]
    score: int

def detect_harness(event: Mapping[str, object], env: Mapping[str, str]) -> str | None: ...
def parse_codex_record(record: object, ordinal: int) -> NormalizedMessage | None: ...
def parse_claude_record(record: object, ordinal: int) -> NormalizedMessage | None: ...
def normalize_transcript(path: Path, harness: str) -> list[NormalizedMessage]: ...
def find_learning_sequences(messages: Sequence[NormalizedMessage]) -> list[LearningSequence]: ...
def select_learning_sequence(messages: Sequence[NormalizedMessage]) -> LearningSequence | None: ...
def build_automatic_observation(
    messages: Sequence[NormalizedMessage],
    sequence: LearningSequence,
    harness: str,
    session_id: str,
    captured_at: str | None = None,
) -> dict[str, object]: ...
def process_session_end(
    event: Mapping[str, object],
    env: Mapping[str, str] | None = None,
) -> bool: ...
```

## Files Created or Modified

- Create `plugins/comprehension-profile/hooks/hooks.json`.
- Create `plugins/comprehension-profile/scripts/transcript_adapters.py`.
- Create `plugins/comprehension-profile/scripts/detect_learning_moments.py`.
- Create `tests/fixtures/comprehension/codex_learning.jsonl`.
- Create `tests/fixtures/comprehension/claude_learning.jsonl`.
- Create `tests/fixtures/comprehension/noisy_no_match.jsonl` only if a shared fixture improves readability; otherwise construct negative cases inline.
- Create `tests/test_transcript_adapters.py`.
- Create `tests/test_detect_learning_moments.py`.
- Modify `tests/comprehension_helpers.py`.
- Modify `scripts/validate_repository.py`.
- Modify `tests/test_validate_repository.py`.
- Modify `tests/test_skill_contracts.py`.
- Modify `README.md`.

## Dependencies on Other Components

- Requires Capture Learning Pattern/shared foundation to be complete.
- Produces the second source of records consumed by Refine Comprehension Profile.
- Has no dependency on Refine Comprehension Profile or Personalized Explainer.

## Edge Cases

- Transcript files larger than 2 MiB are tail-read; a partial first line is discarded.
- Empty, deleted, non-regular, non-UTF-8, partially written, or mixed-version transcripts yield no observation.
- Multiple learning moments yield only the highest-scoring complete sequence.
- Bare “yes,” “got it,” “thanks,” or “makes sense” is not a user restatement.
- Assistant “exactly” does not count without an earlier explicit confusion and substantive user restatement.
- Quoted dialogue, requests to explain the detector, and hypothetical examples must not self-trigger.
- More than 12 visible messages between confusion and confirmation is treated as too weak or topic-drifted.
- A session-end event from a subagent, when identifiable, is ignored.
- Reprocessing the same transcript is a duplicate no-op through the stable observation ID.

## Non-Goals

- Semantic interpretation by another model.
- Detecting every subtle or implicit learning moment.
- Producing a canonical rule or updating `profile.md`.
- Persisting a queue, raw transcript, processing ledger, or detector log.
- Per-turn intervention or extending a conversation through a `Stop` hook.

## Tests

All transcripts are synthetic and checked in. Unit tests separately verify adapters, state-machine precision, observation construction, deduplication, hook integration, and repository packaging.

## Acceptance Criteria

- Both harness fixtures normalize to equivalent visible message sequences.
- A complete explicit sequence appends one schema-valid automatic observation.
- Negative and ambiguous sequences append nothing.
- Multiple candidates produce at most one strongest observation.
- Repeated processing remains one line.
- The hook is packaged for both platforms and exits successfully without profile access or network use.
- Existing manual capture and repository tests remain green.

---

### Task 1: Normalize Codex and Claude transcripts

**Files:**

- Create: `plugins/comprehension-profile/scripts/transcript_adapters.py`
- Create: `tests/fixtures/comprehension/codex_learning.jsonl`
- Create: `tests/fixtures/comprehension/claude_learning.jsonl`
- Create: `tests/test_transcript_adapters.py`
- Modify: `tests/comprehension_helpers.py`

**Interfaces:**

- Consumes: a transcript path, harness name `codex` or `claude`, and known user-visible message records.
- Produces: `NormalizedMessage`, `detect_harness`, `parse_codex_record`, `parse_claude_record`, and `normalize_transcript`.

- [ ] **Step 1: Make the test loader support sibling imports**

Update `load_plugin_module` to register the module and temporarily expose its parent directory before execution:

```python
import sys


def load_plugin_module(name: str, relative_path: str) -> ModuleType:
    path = PLUGIN_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load plugin module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module
```

- [ ] **Step 2: Create equivalent synthetic fixtures**

Use these visible messages in both fixtures:

```text
user: I don't understand dependency injection; who creates the service?
assistant: For example, the request handler asks a container, which constructs the service first and passes it in.
user: So the container builds the service before the handler runs, and injection just means the handler receives it?
assistant: Exactly. The construction happens outside the handler.
```

Encode Codex lines in the known rollout shape:

```json
{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"I don't understand dependency injection; who creates the service?"}]}}
{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"For example, the request handler asks a container, which constructs the service first and passes it in."}]}}
```

Encode Claude lines in its message shape:

```json
{"type":"user","message":{"role":"user","content":[{"type":"text","text":"I don't understand dependency injection; who creates the service?"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"For example, the request handler asks a container, which constructs the service first and passes it in."}]}}
```

Complete both files with the restatement and confirmation. Add one reasoning/tool record to each fixture and ensure its distinctive text is absent after normalization.

- [ ] **Step 3: Add failing adapter tests**

Create `tests/test_transcript_adapters.py`:

```python
import tempfile
import unittest
from pathlib import Path

from tests.comprehension_helpers import PLUGIN_ROOT, load_plugin_module


adapters = load_plugin_module("transcript_adapters", "scripts/transcript_adapters.py")
FIXTURES = Path(__file__).parent / "fixtures/comprehension"


class TranscriptAdapterTests(unittest.TestCase):
    def test_codex_and_claude_normalize_to_same_visible_messages(self):
        codex = adapters.normalize_transcript(FIXTURES / "codex_learning.jsonl", "codex")
        claude = adapters.normalize_transcript(FIXTURES / "claude_learning.jsonl", "claude")
        self.assertEqual([(m.role, m.text) for m in codex], [(m.role, m.text) for m in claude])
        self.assertEqual([m.role for m in codex], ["user", "assistant", "user", "assistant"])

    def test_hidden_and_tool_content_is_ignored(self):
        messages = adapters.normalize_transcript(FIXTURES / "codex_learning.jsonl", "codex")
        self.assertNotIn("SECRET_TOOL_TEXT", " ".join(m.text for m in messages))

    def test_unknown_records_and_malformed_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.jsonl"
            path.write_text('not-json\n{"type":"unknown","text":"ignored"}\n')
            self.assertEqual(adapters.normalize_transcript(path, "codex"), [])

    def test_harness_detection_prefers_codex_marker(self):
        event = {"transcript_path": "/tmp/thread.jsonl"}
        env = {"PLUGIN_ROOT": "/plugin", "CLAUDE_PLUGIN_ROOT": "/plugin"}
        self.assertEqual(adapters.detect_harness(event, env), "codex")

    def test_harness_detection_uses_claude_marker(self):
        self.assertEqual(
            adapters.detect_harness({}, {"CLAUDE_PLUGIN_ROOT": "/plugin"}),
            "claude",
        )
```

Add:

```python
def test_non_regular_and_unknown_harness_return_empty(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        self.assertEqual(adapters.normalize_transcript(path, "codex"), [])
        self.assertEqual(adapters.normalize_transcript(FIXTURES / "codex_learning.jsonl", "other"), [])

def test_tail_read_discards_partial_first_line(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "large.jsonl"
        prefix = b"x" * adapters.MAX_TRANSCRIPT_BYTES
        valid = b'\n{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"visible"}]}}\n'
        path.write_bytes(prefix + valid)
        messages = adapters.normalize_transcript(path, "codex")
        self.assertEqual([(m.role, m.text) for m in messages], [("user", "visible")])
```

- [ ] **Step 4: Run adapter tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_transcript_adapters -v
```

Expected: `ERROR` because `transcript_adapters.py` is missing.

- [ ] **Step 5: Implement the adapters**

Create:

```python
from collections.abc import Mapping
import json
import os
from pathlib import Path
from typing import NamedTuple


MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024


class NormalizedMessage(NamedTuple):
    role: str
    text: str
    ordinal: int
```

For Codex, accept only top-level `type == "response_item"`, payload `type == "message"`, role `user|assistant`, and content item types `input_text|output_text`. For Claude, accept only top-level `type == "user"|"assistant"`, nested matching message role, and plain string content or content objects with `type == "text"`. Join multiple visible text items with newlines. Reject every other record instead of recursively searching it.

Read the last 2 MiB in binary, discard the first line when tail-seeking starts mid-file, decode each remaining line independently as UTF-8, and skip invalid lines. Preserve chronological ordinals from the retained lines.

- [ ] **Step 6: Run and commit adapter tests**

```bash
rtk python3 -m unittest tests.test_transcript_adapters -v
rtk git add plugins/comprehension-profile/scripts/transcript_adapters.py tests/comprehension_helpers.py tests/fixtures/comprehension/codex_learning.jsonl tests/fixtures/comprehension/claude_learning.jsonl tests/test_transcript_adapters.py
rtk git commit -m "feat(comprehension): normalize session transcripts"
```

Expected: adapter tests pass before the commit.

### Task 2: Implement the high-confidence state machine

**Files:**

- Create: `plugins/comprehension-profile/scripts/detect_learning_moments.py`
- Create: `tests/test_detect_learning_moments.py`

**Interfaces:**

- Consumes: `Sequence[NormalizedMessage]`.
- Produces: `LearningSequence`, `find_learning_sequences`, `select_learning_sequence`, and `build_automatic_observation`.

- [ ] **Step 1: Add failing positive and negative detector tests**

Create these helpers, then add the tests:

```python
def normalized(*items: tuple[str, str]):
    return [
        adapters.NormalizedMessage(role, text, ordinal)
        for ordinal, (role, text) in enumerate(items)
    ]


def fixture_messages():
    return normalized(
        ("user", "I don't understand dependency injection; who creates the service?"),
        ("assistant", "For example, the container constructs the service before use."),
        ("user", "So basically the container creates it before the handler runs, then passes it in?"),
        ("assistant", "Exactly. Construction happens outside the handler."),
    )


class LearningSequenceTests(unittest.TestCase):
    def test_complete_sequence_is_selected(self):
        messages = fixture_messages()
        sequence = detector.select_learning_sequence(messages)
        self.assertIsNotNone(sequence)
        self.assertEqual(sequence.confusion_index, 0)
        self.assertEqual(sequence.restatement_index, 2)
        self.assertEqual(sequence.confirmation_index, 3)

    def test_acknowledgment_without_restatement_is_rejected(self):
        messages = normalized(
            ("user", "I don't understand dependency injection."),
            ("assistant", "Here is a concrete example."),
            ("user", "Got it, thanks!"),
            ("assistant", "Exactly."),
        )
        self.assertIsNone(detector.select_learning_sequence(messages))

    def test_confirmation_without_explicit_confusion_is_rejected(self):
        messages = normalized(
            ("assistant", "A container constructs the service."),
            ("user", "So it is built before the handler runs?"),
            ("assistant", "Exactly."),
        )
        self.assertIsNone(detector.select_learning_sequence(messages))

    def test_automatic_observation_has_required_signals_and_hashed_session(self):
        messages = fixture_messages()
        sequence = detector.select_learning_sequence(messages)
        record = detector.build_automatic_observation(
            messages, sequence, "codex", "raw-session-42", "2026-09-11T00:00:00Z"
        )
        self.assertEqual(record["source"], "automatic")
        self.assertEqual(
            set(("explicit_confusion", "user_restatement", "assistant_confirmation"))
            <= set(record["signals"]),
            True,
        )
        self.assertNotIn("raw-session-42", json.dumps(record))
        self.assertEqual(store.validate_observation(record), [])
```

Add a table-driven rejection test and selection/limit tests:

```python
def test_ambiguous_sequences_are_rejected(self):
    cases = {
        "quoted": (("user", "> I don't understand\n> So basically because then"),),
        "hypothetical": (("user", "Suppose someone says: I don't understand this."),),
        "negative_confirmation": (
            ("user", "I don't understand this lifecycle."),
            ("assistant", "It starts before the request."),
            ("user", "So basically it starts before the request, then it is reused?"),
            ("assistant", "Not exactly; it is rebuilt."),
        ),
    }
    for name, items in cases.items():
        with self.subTest(name=name):
            self.assertIsNone(detector.select_learning_sequence(normalized(*items)))

def test_thirteen_message_gap_is_rejected(self):
    middle = tuple(("assistant" if i % 2 else "user", f"detail {i}") for i in range(13))
    messages = normalized(
        ("user", "I don't understand this lifecycle."),
        *middle,
        ("user", "So basically it starts before the request, then it is reused?"),
        ("assistant", "Exactly."),
    )
    self.assertIsNone(detector.select_learning_sequence(messages))

def test_strongest_sequence_wins_and_evidence_is_capped(self):
    messages = normalized(
        ("user", "I don't understand the first lifecycle."),
        ("assistant", "It starts before the request."),
        ("user", "So basically it starts before the request, then it is reused?"),
        ("assistant", "Exactly."),
        ("user", "I don't understand the second lifecycle."),
        ("assistant", "It creates one object per request."),
        ("user", "Who creates it?"),
        ("assistant", "The request scope creates it."),
        ("user", "When is it removed?"),
        ("assistant", "For example, cleanup runs after the response."),
        ("user", "So basically the scope creates it before handling, then removes it after the response?"),
        ("assistant", "Exactly."),
    )
    sequence = detector.select_learning_sequence(messages)
    record = detector.build_automatic_observation(messages, sequence, "codex", "session")
    self.assertGreater(sequence.confusion_index, 0)
    self.assertLessEqual(len(record["evidence"]), 6)
```

- [ ] **Step 2: Run detector tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_detect_learning_moments.LearningSequenceTests -v
```

Expected: `ERROR` because `detect_learning_moments.py` is missing.

- [ ] **Step 3: Implement explicit signal predicates**

Use anchored, case-insensitive patterns and structural checks:

```python
CONFUSION = re.compile(
    r"\b(i (?:do not|don't) understand|i(?:'m| am) confused|i(?:'m| am) lost|"
    r"not clicking|doesn't make sense to me)\b",
    re.IGNORECASE,
)
RESTATEMENT_START = re.compile(
    r"^\s*(so|basically|in other words|if i understand|that means)",
    re.IGNORECASE,
)
CAUSAL_CONNECTOR = re.compile(
    r"\b(because|then|before|after|therefore|which means|so that)\b",
    re.IGNORECASE,
)
CONFIRMATION = re.compile(
    r"^\s*(exactly|yes[,.!:—-]|that's right\b|correct[,.!:—-])",
    re.IGNORECASE,
)
NEGATED_CONFIRMATION = re.compile(
    r"^\s*(not exactly|no[,.!:—-]|almost[,.!:—-])",
    re.IGNORECASE,
)
```

A restatement must be a user message of 30–600 characters, match `RESTATEMENT_START`, and contain a causal connector. A confirmation must be the next assistant message after the restatement, match `CONFIRMATION`, and not match `NEGATED_CONFIRMATION`. Ignore matches inside fenced code, block quotes, or messages discussing phrases/signals/detectors.

- [ ] **Step 4: Implement sequence enumeration and scoring**

Search forward no more than 12 normalized messages from each confusion. Require at least one assistant explanation between confusion and restatement. Collect intervening user questions as clarification indices.

Score exactly:

```text
+4 explicit confusion
+2 each clarification question, capped at +4
+3 restatement
+2 causal connector
+4 assistant confirmation
+1 explicit understanding phrase after confirmation, when present
+2 explanation includes “for example”, “e.g.”, or a fenced code block
```

Sort complete sequences by descending score, then shortest span, then latest confirmation ordinal. Return only the first from `select_learning_sequence`.

- [ ] **Step 5: Build a conservative observation**

Use the confusion text for `confusion`, intervening user questions for `clarification_questions`, and the final assistant explanation before the restatement for `successful_explanation`. Choose one template:

```python
if explanation_has_example:
    why = "Understanding followed a concrete example that the user mapped back in their own words."
    rule = "Give one concrete example before the abstraction, then invite a restatement."
elif len(clarification_indices) >= 2:
    why = "Understanding followed stepwise answers to repeated clarification questions and a user restatement."
    rule = "Answer clarification questions step by step, then invite the user to restate the model."
else:
    why = "Understanding followed a causal explanation that the user restated and the assistant confirmed."
    rule = "Present the causal sequence, then invite the user to restate it."
```

Derive a non-empty topic by stripping the explicit confusion prefix and clipping the remaining first sentence to 120 characters. Derive `id` with `make_observation_id(session_key, str(confusion.ordinal), str(restatement.ordinal), candidate_rule)`. Pass all excerpts through `scrub_excerpt` and validate before returning.

- [ ] **Step 6: Run detector unit tests**

```bash
rtk python3 -m unittest tests.test_detect_learning_moments.LearningSequenceTests -v
```

Expected: all learning-sequence tests report `ok`.

- [ ] **Step 7: Commit the detector core**

```bash
rtk git add plugins/comprehension-profile/scripts/detect_learning_moments.py tests/test_detect_learning_moments.py
rtk git commit -m "feat(comprehension): detect high-confidence learning moments"
```

### Task 3: Connect detection to session-end persistence

**Files:**

- Modify: `plugins/comprehension-profile/scripts/detect_learning_moments.py`
- Modify: `tests/test_detect_learning_moments.py`
- Create: `plugins/comprehension-profile/hooks/hooks.json`

**Interfaces:**

- Consumes: session-end event JSON with `session_id`, `transcript_path`, and `hook_event_name`.
- Produces: `process_session_end(...) -> bool` and a hook-safe `main(...) -> int`.

- [ ] **Step 1: Add failing integration tests**

Use a temporary store and copied fixture:

```python
class SessionEndIntegrationTests(unittest.TestCase):
    def test_complete_codex_session_appends_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            event = {
                "session_id": "thread-123",
                "transcript_path": str(FIXTURES / "codex_learning.jsonl"),
                "hook_event_name": "SessionEnd",
            }
            env = {
                "PLUGIN_ROOT": str(PLUGIN_ROOT),
                "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
                "COMPREHENSION_PROFILE_HOME": str(root),
            }
            self.assertTrue(detector.process_session_end(event, env))
            self.assertFalse(detector.process_session_end(event, env))
            records, errors = store.load_observations(root)
            self.assertEqual(errors, [])
            self.assertEqual(len(records), 1)

    def test_missing_transcript_is_quiet_no_op(self):
        event = {
            "session_id": "thread-123",
            "transcript_path": "/missing/transcript.jsonl",
            "hook_event_name": "SessionEnd",
        }
        self.assertFalse(detector.process_session_end(event, {"PLUGIN_ROOT": "/plugin"}))

    def test_non_session_end_event_is_ignored(self):
        event = {"hook_event_name": "Stop", "session_id": "x", "transcript_path": "x"}
        self.assertFalse(detector.process_session_end(event, {"PLUGIN_ROOT": "/plugin"}))
```

Add these concrete cases, importing `io` and `unittest.mock`:

```python
def test_complete_claude_session_appends(self):
    with tempfile.TemporaryDirectory() as directory:
        event = {"session_id": "c-1", "transcript_path": str(FIXTURES / "claude_learning.jsonl"), "hook_event_name": "SessionEnd"}
        env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "COMPREHENSION_PROFILE_HOME": directory}
        self.assertTrue(detector.process_session_end(event, env))

def test_missing_session_id_and_lock_contention_are_no_ops(self):
    event = {"transcript_path": str(FIXTURES / "codex_learning.jsonl"), "hook_event_name": "SessionEnd"}
    self.assertFalse(detector.process_session_end(event, {"PLUGIN_ROOT": str(PLUGIN_ROOT)}))
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, ".observations.lock").write_text("held")
        event["session_id"] = "x"
        env = {"PLUGIN_ROOT": str(PLUGIN_ROOT), "COMPREHENSION_PROFILE_HOME": directory}
        self.assertFalse(detector.process_session_end(event, env))

def test_main_treats_malformed_input_as_quiet_success(self):
    with mock.patch("sys.stdin", io.StringIO("not-json")):
        self.assertEqual(detector.main([]), 0)
```

- [ ] **Step 2: Run integration tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_detect_learning_moments.SessionEndIntegrationTests -v
```

Expected: failures naming undefined `process_session_end` or `main`.

- [ ] **Step 3: Implement the hook-safe entrypoint**

`process_session_end` must validate event type and scalar inputs, choose an adapter, normalize messages, select one sequence, construct one observation, resolve the store with the injected environment, and append. Catch expected `OSError`, `ValueError`, Unicode, JSON, missing-file, and lock errors and return `False`.

`main` reads one JSON object from stdin. It returns `0` without output for every normal or expected failure path. Do not return a hook decision object; `SessionEnd` has no decision control.

- [ ] **Step 4: Add the shared hook configuration**

Create exactly:

```json
{
  "description": "Capture high-confidence technical learning moments at session end.",
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/detect_learning_moments.py\"",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

Do not add `Stop`, `SessionStart`, MCP, prompt, agent, or asynchronous hooks.

- [ ] **Step 5: Run integration tests**

```bash
rtk python3 -m unittest tests.test_detect_learning_moments -v
```

Expected: all detector tests report `ok`.

- [ ] **Step 6: Commit hook integration**

```bash
rtk git add plugins/comprehension-profile/hooks/hooks.json plugins/comprehension-profile/scripts/detect_learning_moments.py tests/test_detect_learning_moments.py
rtk git commit -m "feat(comprehension): capture session-end candidates"
```

### Task 4: Validate hook packaging and component isolation

**Files:**

- Modify: `scripts/validate_repository.py`
- Modify: `tests/test_validate_repository.py`
- Modify: `tests/test_skill_contracts.py`
- Modify: `README.md`

**Interfaces:**

- Consumes: an optional plugin-local `hooks/hooks.json`.
- Produces: repository errors for escaping/missing hook commands and documentation for opt-in/disable behavior.

- [ ] **Step 1: Add failing repository-hook tests**

Extend the temporary fixture helper to optionally create a hook file. Add:

```python
def test_rejects_hook_script_missing_from_plugin(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        build_repo(root)
        hook = root / "plugins/git-craft/hooks/hooks.json"
        write_json(hook, {
            "hooks": {"SessionEnd": [{"hooks": [{
                "type": "command",
                "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/missing.py\""
            }]}]}
        })
        self.assertIn(
            "Hook command script is missing: plugins/git-craft/scripts/missing.py",
            validate_repository(root),
        )

def test_checked_in_comprehension_hook_uses_only_session_end(self):
    root = Path(__file__).resolve().parents[1]
    path = root / "plugins/comprehension-profile/hooks/hooks.json"
    payload = json.loads(path.read_text())
    self.assertEqual(set(payload["hooks"]), {"SessionEnd"})
```

Add:

```python
def test_rejects_invalid_hook_json(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        build_repo(root)
        path = root / "plugins/git-craft/hooks/hooks.json"
        path.parent.mkdir(parents=True)
        path.write_text("not-json")
        self.assertIn("Invalid JSON", "\n".join(validate_repository(root)))

def test_rejects_hook_command_path_traversal(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        build_repo(root)
        write_json(root / "plugins/git-craft/hooks/hooks.json", {
            "hooks": {"SessionEnd": [{"hooks": [{
                "type": "command",
                "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/../outside.py\""
            }]}]}
        })
        self.assertIn("Hook command path escapes plugin", validate_repository(root))
```

- [ ] **Step 2: Run validator tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_validate_repository -v
```

Expected: at least the missing-script or escaping-path test fails.

- [ ] **Step 3: Add optional hook validation**

In `validate_repository`, when `hooks/hooks.json` exists inside a plugin:

1. Load it as an object.
2. Require `hooks` to be an object of event arrays.
3. Inspect command handlers for the literal `${CLAUDE_PLUGIN_ROOT}/` prefix and parse the remaining relative path.
4. Reject absolute paths or `..` components.
5. Resolve the relative path through `plugin_path` and require the script to exist.

Do not require every plugin to have hooks and do not hard-code `SessionEnd` globally; the checked-in component test owns that product-specific invariant.

- [ ] **Step 4: Add detector isolation contract checks**

Read the detector and hook text in `tests/test_skill_contracts.py` and assert:

```python
self.assertNotIn("profile.md", detector_text)
self.assertNotIn("observations.jsonl", hook_text)
self.assertNotIn("Stop\"", hook_text)
self.assertNotIn("http", hook_text.lower())
self.assertIn("append_observation", detector_text)
```

The hook should call the detector, not manipulate storage directly.

- [ ] **Step 5: Document automatic detection and disable behavior**

Update README with:

- Automatic detection is enabled only after the installed hook is reviewed/trusted.
- It retains short excerpts locally and may deliberately miss ambiguous moments.
- Codex and Claude on the same machine share the configured store.
- Users can disable the plugin hook through their harness's hook/plugin controls while retaining manual skill files; do not invent one cross-harness command if the CLIs differ.
- The detector never updates the canonical profile.

- [ ] **Step 6: Run all verification**

```bash
rtk python3 -m unittest discover -s tests -v
rtk python3 scripts/validate_repository.py .
rtk python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/comprehension-profile
rtk claude plugin validate ./plugins/comprehension-profile --strict
```

Expected: Python tests and repository validation pass; both platform validators pass when installed. Record an unavailable CLI honestly.

- [ ] **Step 7: Commit validation and documentation**

```bash
rtk git add scripts/validate_repository.py tests/test_validate_repository.py tests/test_skill_contracts.py README.md
rtk git commit -m "test(comprehension): validate session-end detection"
```
