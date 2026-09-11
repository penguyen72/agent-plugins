# Capture Learning Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the shared Comprehension Profile plugin, observation contract, user-level store, and explicit skill that captures one approved learning observation without touching the canonical profile.

**Architecture:** Add a self-contained cross-platform plugin whose standard-library Python store owns all observation validation and persistence. The manual skill inspects the current conversation, drafts one versioned observation, obtains approval, and delegates the append to that store; it never reads or writes `profile.md`.

**Tech Stack:** Markdown Agent Skills, JSON plugin manifests, JSONL, Python 3 standard library, `unittest`, Codex and Claude Code plugin packaging.

**Spec:** `docs/superpowers/specs/2026-09-11-comprehension-profile-design.md`

## Global Constraints

- First-release runnable support is Codex and Claude Code on the same local machine.
- Plugin name and directory are `comprehension-profile`; initial version is `0.1.0` in both manifests.
- All installed behavior and references stay inside `plugins/comprehension-profile/`.
- The store root is non-empty `COMPREHENSION_PROFILE_HOME`, otherwise `~/.comprehension-profile/`.
- `observations.jsonl` is UTF-8, append-only, and may grow; `profile.md` is the only runtime artifact.
- Observation schema version is integer `1`; unknown fields and unknown schema versions fail closed.
- Persist no raw session IDs, full transcripts, tool data, hidden reasoning, repository content, or unrelated excerpts.
- Evidence is limited to six `user` or `assistant` excerpts of at most 280 characters each.
- No third-party dependency, network request, API key, database, daemon, embedding, or model call.
- Any persistent manual write requires an exact preview and explicit user approval.
- This plan creates no automatic detector, profile refiner, or personalized explainer.

---

## Purpose

Give the user a high-quality, explicit way to record a conversation that finally clicked. This plan also establishes the shared observation interface that every later component must consume unchanged.

## Existing Repository Context

- The existing cross-platform example lives in `plugins/git-craft/` with `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`; the new plugin follows that layout.
- Root catalogs are `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`.
- `scripts/validate_repository.py` checks marketplace, manifest, containment, version, and skill-frontmatter invariants.
- `tests/test_validate_repository.py` builds temporary marketplace fixtures.
- `tests/test_skill_contracts.py` statically checks portable skill behavior.
- Tests run with `python3 -m unittest discover -s tests -v`; repository instructions require the `rtk` prefix for shell commands.

## Architecture, Inputs, and Outputs

The skill consumes the visible conversation window and optional user corrections. It outputs one approved version 1 observation through `comprehension_store.py`. The store resolves the user directory, validates and scrubs the record, hashes the session identifier, suppresses duplicate IDs, acquires a short-lived lock, and appends one compact newline-terminated JSON object.

The skill must not load historical observations to decide what clicked. It must not create or modify `profile.md`.

## Data Contracts

The authoritative contract is copied from the approved spec into `plugins/comprehension-profile/references/data-contracts.md`. The Python API established by this plan is:

```python
SCHEMA_VERSION: int = 1
MAX_EVIDENCE_ITEMS: int = 6
MAX_EXCERPT_LENGTH: int = 280

def resolve_store_root(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path: ...

def hash_session_key(harness: str, session_id: str) -> str: ...

def make_observation_id(session_key: str, *parts: str) -> str: ...

def scrub_excerpt(text: str, max_length: int = MAX_EXCERPT_LENGTH) -> str: ...

def validate_observation(record: object) -> list[str]: ...

def append_observation(record: dict[str, object], store_root: Path) -> bool: ...

def load_observations(
    store_root: Path,
) -> tuple[list[dict[str, object]], list[str]]: ...

def main(argv: Sequence[str] | None = None) -> int: ...
```

`append_observation` returns `True` when it writes and `False` for a duplicate ID. Validation and I/O failures raise `ValueError` or `OSError`; the CLI converts them to concise stderr and a nonzero exit. `load_observations` returns valid records and line-specific errors without modifying the file.

## Files Created or Modified

- Create `plugins/comprehension-profile/.codex-plugin/plugin.json`.
- Create `plugins/comprehension-profile/.claude-plugin/plugin.json`.
- Create `plugins/comprehension-profile/references/data-contracts.md`.
- Create `plugins/comprehension-profile/scripts/__init__.py`.
- Create `plugins/comprehension-profile/scripts/comprehension_store.py`.
- Create `plugins/comprehension-profile/skills/capture-learning-pattern/SKILL.md`.
- Create `tests/comprehension_helpers.py`.
- Create `tests/test_comprehension_store.py`.
- Modify `.agents/plugins/marketplace.json`.
- Modify `.claude-plugin/marketplace.json`.
- Modify `scripts/validate_repository.py` only if packaging exposes a validator gap; do not add capture-specific behavior there.
- Modify `tests/test_validate_repository.py`.
- Modify `tests/test_skill_contracts.py`.
- Modify `README.md`.

## Dependencies on Other Components

This is the foundation plan and has no dependency on the other three components. Detect Learning Moments must use its observation functions and schema. Refine Comprehension Profile later extends the store with profile validation/writes. Personalized Explainer later consumes only the profile contract.

## Edge Cases

- Empty or whitespace-only `COMPREHENSION_PROFILE_HOME` falls back to the default.
- A raw session ID containing Unicode or path separators is hashed and never used as a path.
- Duplicate IDs are no-ops even when the duplicate line is not the last line.
- A malformed existing JSONL line is reported by readers but does not authorize rewriting history.
- Obvious bearer tokens, API keys, private-key headers, and credential assignments are replaced before truncation.
- Lock contention times out quickly and leaves the file unchanged.
- Permission failure, invalid UTF-8 input, an empty conversation, or no demonstrated understanding produces no observation.
- Approval applies to the exact preview; any user correction creates a new preview and approval gate.

## Non-Goals

- Detecting learning moments automatically.
- Reading accumulated history while capturing the current moment.
- Updating or initializing `profile.md`.
- Inferring prose style, personality, knowledge level, or factual competence.
- Supporting cross-machine synchronization or hosted ChatGPT.

## Tests

Use synthetic records only. Schema tests cover every field and limit; persistence tests use `tempfile.TemporaryDirectory`; contract tests inspect the skill text. No test touches the real home directory.

## Acceptance Criteria

- The plugin is valid and listed in both marketplace catalogs at version `0.1.0`.
- One approved manual observation can be appended to an isolated store and loaded unchanged except for defined scrubbing/normalization.
- Invalid, duplicate, oversized, unapproved, or evidence-free observations do not create extra lines.
- Raw session IDs and representative secrets do not appear in persisted bytes.
- Capture includes confusion, clarification questions, successful explanation, why it worked, candidate rule, signals, and minimal evidence.
- Capture explicitly cannot read or write `profile.md`.
- All existing and new tests pass.

---

### Task 1: Lock the shared observation schema

**Files:**

- Create: `plugins/comprehension-profile/references/data-contracts.md`
- Create: `plugins/comprehension-profile/scripts/__init__.py`
- Create: `plugins/comprehension-profile/scripts/comprehension_store.py`
- Create: `tests/comprehension_helpers.py`
- Create: `tests/test_comprehension_store.py`

**Interfaces:**

- Consumes: the exact Learning Observation Contract in the approved spec.
- Produces: `resolve_store_root`, `hash_session_key`, `make_observation_id`, `scrub_excerpt`, and `validate_observation` with the signatures above.

- [ ] **Step 1: Add a plugin-module loader and failing schema tests**

Create `tests/comprehension_helpers.py`:

```python
import importlib.util
from pathlib import Path
from types import ModuleType


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins/comprehension-profile"


def load_plugin_module(name: str, relative_path: str) -> ModuleType:
    path = PLUGIN_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load plugin module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

Create `tests/test_comprehension_store.py` with a `valid_observation()` fixture and these initial tests:

```python
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
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

```bash
rtk python3 -m unittest tests.test_comprehension_store -v
```

Expected: `ERROR` because `plugins/comprehension-profile/scripts/comprehension_store.py` does not exist.

- [ ] **Step 3: Implement the schema constants and pure validators**

Create `comprehension_store.py` with the exact field set, enums, limits, UTC timestamp check, 64-character lowercase hex checks, nested evidence validation, and automatic-signal requirement. Begin with:

```python
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import re


SCHEMA_VERSION = 1
MAX_EVIDENCE_ITEMS = 6
MAX_EXCERPT_LENGTH = 280
ALLOWED_FIELDS = {
    "schema_version", "id", "captured_at", "source", "harness",
    "session_key", "topic", "confusion", "clarification_questions",
    "successful_explanation", "why_it_worked", "candidate_rule",
    "signals", "evidence",
}
ALLOWED_SIGNALS = {
    "explicit_confusion", "repeated_clarification", "user_restatement",
    "assistant_confirmation", "explicit_understanding",
}
AUTOMATIC_SIGNALS = {
    "explicit_confusion", "user_restatement", "assistant_confirmation",
}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def resolve_store_root(env=None, home=None):
    values = os.environ if env is None else env
    override = values.get("COMPREHENSION_PROFILE_HOME", "").strip()
    return Path(override).expanduser() if override else (home or Path.home()) / ".comprehension-profile"


def hash_session_key(harness: str, session_id: str) -> str:
    return sha256(f"{harness}\0{session_id}".encode("utf-8")).hexdigest()


def make_observation_id(session_key: str, *parts: str) -> str:
    normalized = [" ".join(part.split()) for part in parts]
    material = "\0".join([session_key, *normalized])
    return sha256(material.encode("utf-8")).hexdigest()
```

Use small helpers such as `_required_string(record, field, limit, errors)` and accumulate all readable errors rather than returning after the first one.

- [ ] **Step 4: Complete schema boundary tests**

Add table-driven subtests that mutate `valid_observation()` and assert errors for:

```python
cases = {
    "schema_version": 2,
    "id": "not-hex",
    "captured_at": "2026-09-11",
    "source": "hook",
    "harness": "chatgpt",
    "session_key": "raw-session-id",
    "topic": "x" * 121,
    "confusion": "",
    "clarification_questions": ["x" * 281],
    "successful_explanation": "x" * 501,
    "why_it_worked": "x" * 501,
    "candidate_rule": "x" * 301,
    "signals": ["unknown"],
    "evidence": [{"role": "tool", "excerpt": "hidden"}],
}
```

Add these concrete boundary assertions:

```python
def test_collection_and_shape_boundaries(self):
    mutations = [
        ("evidence", [{"role": "user", "excerpt": str(i)} for i in range(7)], "at most 6"),
        ("signals", ["explicit_confusion", "explicit_confusion"], "signals must be unique"),
        ("evidence", [], "at least 1"),
        ("evidence", [{"role": "user", "excerpt": "x", "extra": True}], "unknown evidence field"),
    ]
    for field, value, expected in mutations:
        with self.subTest(field=field, expected=expected):
            record = valid_observation()
            record[field] = value
            self.assertIn(expected, "; ".join(store.validate_observation(record)))

def test_non_object_and_missing_fields_are_rejected(self):
    self.assertIn("observation must be an object", store.validate_observation([]))
    record = valid_observation()
    del record["topic"]
    self.assertIn("topic is required", store.validate_observation(record))
```

- [ ] **Step 5: Run schema tests**

Run:

```bash
rtk python3 -m unittest tests.test_comprehension_store.ObservationSchemaTests -v
```

Expected: all schema tests report `ok`.

- [ ] **Step 6: Write the portable contract reference**

Create `references/data-contracts.md` with the exact JSON example, field rules, size limits, store resolution order, append-only rule, privacy exclusions, and profile contract from the spec. Clearly label profile writing as reserved for `refine-comprehension-profile`.

- [ ] **Step 7: Commit the schema boundary**

```bash
rtk git add plugins/comprehension-profile/references/data-contracts.md plugins/comprehension-profile/scripts/__init__.py plugins/comprehension-profile/scripts/comprehension_store.py tests/comprehension_helpers.py tests/test_comprehension_store.py
rtk git commit -m "feat(comprehension): define observation contract"
```

### Task 2: Add safe observation persistence and CLI

**Files:**

- Modify: `plugins/comprehension-profile/scripts/comprehension_store.py`
- Modify: `tests/test_comprehension_store.py`

**Interfaces:**

- Consumes: a fully materialized version 1 observation object.
- Produces: `scrub_excerpt`, `append_observation`, `load_observations`, and CLI subcommands `validate-observation` and `append-observation`.

- [ ] **Step 1: Add failing persistence tests**

Add tests using `TemporaryDirectory`:

```python
def test_append_creates_one_compact_valid_line(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "profile"
        self.assertTrue(store.append_observation(valid_observation(), root))
        lines = (root / "observations.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), valid_observation())

def test_duplicate_id_is_a_no_op(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        self.assertTrue(store.append_observation(valid_observation(), root))
        self.assertFalse(store.append_observation(valid_observation(), root))
        self.assertEqual(len((root / "observations.jsonl").read_text().splitlines()), 1)

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
        root = Path(directory)
        root.mkdir()
        valid = json.dumps(valid_observation(), separators=(",", ":"))
        (root / "observations.jsonl").write_text(f"not-json\n{valid}\n")
        records, errors = store.load_observations(root)
        self.assertEqual(records, [valid_observation()])
        self.assertIn("line 1", errors[0])
```

Add these exact persistence checks, importing `contextlib`, `io`, `json`, and `tempfile`:

```python
def test_scrub_excerpt_redacts_before_truncating(self):
    text = "Authorization: Bearer secret-token " + ("x" * 400)
    scrubbed = store.scrub_excerpt(text)
    self.assertNotIn("secret-token", scrubbed)
    self.assertLessEqual(len(scrubbed), 280)

def test_scrub_excerpt_redacts_credential_assignment(self):
    self.assertNotIn("abc123", store.scrub_excerpt("API_KEY=abc123"))

def test_lock_contention_leaves_file_unchanged(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".observations.lock").write_text("held")
        with self.assertRaisesRegex(OSError, "lock"):
            store.append_observation(valid_observation(), root)
        self.assertFalse((root / "observations.jsonl").exists())

def test_cli_append_reads_json_file_and_prints_appended(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "store"
        source = Path(directory) / "observation.json"
        source.write_text(json.dumps(valid_observation()), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = store.main(["append-observation", "--input", str(source), "--store-root", str(root)])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "Observation appended.")
```

- [ ] **Step 2: Run persistence tests and confirm failure**

Run:

```bash
rtk python3 -m unittest tests.test_comprehension_store -v
```

Expected: failures naming undefined `append_observation`, `load_observations`, or `scrub_excerpt`.

- [ ] **Step 3: Implement scrubbing, locking, append, and load**

Use these persistence constants and flow:

```python
LOCK_NAME = ".observations.lock"
OBSERVATIONS_NAME = "observations.jsonl"
LOCK_ATTEMPTS = 5
LOCK_DELAY_SECONDS = 0.02


def append_observation(record: dict[str, object], store_root: Path) -> bool:
    normalized = _normalize_observation(record)
    errors = validate_observation(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    store_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _observation_lock(store_root):
        existing, load_errors = load_observations(store_root)
        if load_errors:
            raise ValueError("; ".join(load_errors))
        if any(item["id"] == normalized["id"] for item in existing):
            return False
        payload = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        path = store_root / OBSERVATIONS_NAME
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_file_permissions(path)
        return True
```

Implement `_observation_lock` with `os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)`, five 20 ms retries, and removal in `finally`. Do not delete a lock that this process did not create. The contention error must name the store without printing observation content.

Normalize only defined fields. Scrub every evidence excerpt before validation with these case-insensitive substitutions, then truncate to 280 characters:

```python
REDACTIONS = (
    (re.compile(r"(authorization:\s*bearer\s+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\b([A-Z0-9_]*(?:KEY|TOKEN|PASSWORD|SECRET))\s*=\s*\S+", re.IGNORECASE), r"\1=[REDACTED]"),
    (re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----", re.IGNORECASE), "[REDACTED PRIVATE KEY]"),
)
```

Never silently truncate the core interpretive fields; oversized core fields remain errors.

- [ ] **Step 4: Implement the CLI**

Add `argparse` subcommands:

```text
validate-observation --input PATH
append-observation --input PATH [--store-root PATH]
```

Both read one UTF-8 JSON object. `validate-observation` prints `Observation is valid.` on success. `append-observation` prints `Observation appended.` or `Observation already exists.`. Errors go to stderr and return `1`; success returns `0`. `--store-root` exists for tests and diagnostics; normal callers rely on the shared resolution order.

- [ ] **Step 5: Run store tests**

```bash
rtk python3 -m unittest tests.test_comprehension_store -v
```

Expected: all tests report `ok`.

- [ ] **Step 6: Commit persistence**

```bash
rtk git add plugins/comprehension-profile/scripts/comprehension_store.py tests/test_comprehension_store.py
rtk git commit -m "feat(comprehension): persist learning observations"
```

### Task 3: Package the cross-platform plugin skeleton

**Files:**

- Create: `plugins/comprehension-profile/.codex-plugin/plugin.json`
- Create: `plugins/comprehension-profile/.claude-plugin/plugin.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `tests/test_validate_repository.py`
- Modify: `README.md`

**Interfaces:**

- Consumes: repository marketplace conventions and the self-contained plugin directory.
- Produces: install selectors `comprehension-profile@penguyen72-plugins` for Codex and Claude Code.

- [ ] **Step 1: Add a failing checked-in packaging test**

Add to `tests/test_validate_repository.py`:

```python
def test_checked_in_comprehension_plugin_is_cross_platform_and_self_contained(self):
    root = Path(__file__).resolve().parents[1]
    plugin = root / "plugins/comprehension-profile"
    codex = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
    claude = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
    self.assertEqual(codex["name"], "comprehension-profile")
    self.assertEqual(claude["name"], "comprehension-profile")
    self.assertEqual(codex["version"], "0.1.0")
    self.assertEqual(codex["version"], claude["version"])
    self.assertTrue((plugin / "references/data-contracts.md").is_file())
    self.assertTrue((plugin / "scripts/comprehension_store.py").is_file())
```

- [ ] **Step 2: Run the packaging test and confirm failure**

```bash
rtk python3 -m unittest tests.test_validate_repository.ValidateRepositoryTests.test_checked_in_comprehension_plugin_is_cross_platform_and_self_contained -v
```

Expected: `ERROR` because one or both manifests are missing.

- [ ] **Step 3: Create manifests and catalog entries**

Use this content in both plugin manifests:

```json
{
  "name": "comprehension-profile",
  "version": "0.1.0",
  "description": "Learn and apply a small profile of demonstrated technical comprehension patterns."
}
```

Append this Codex catalog entry:

```json
{
  "name": "comprehension-profile",
  "source": {
    "source": "local",
    "path": "./plugins/comprehension-profile"
  }
}
```

Append the equivalent Claude entry with string source `./plugins/comprehension-profile` and category `Development`. Preserve the existing `git-craft` entries.

- [ ] **Step 4: Document installation and the shared store**

Update the README plugin table and add Codex/Claude installation examples for `comprehension-profile@penguyen72-plugins`. Document the default store, the override variable, local-only storage, the fact that manual capture never updates the profile, and the absence of automatic detection until the next plan is implemented. Add the second plugin to validator command examples without replacing `git-craft`.

- [ ] **Step 5: Run repository validation tests**

```bash
rtk python3 -m unittest tests.test_validate_repository -v
rtk python3 scripts/validate_repository.py .
```

Expected: all unit tests report `ok`, followed by `Repository validation passed.`.

- [ ] **Step 6: Commit packaging**

```bash
rtk git add .agents/plugins/marketplace.json .claude-plugin/marketplace.json plugins/comprehension-profile/.codex-plugin/plugin.json plugins/comprehension-profile/.claude-plugin/plugin.json tests/test_validate_repository.py README.md
rtk git commit -m "feat(comprehension): package capture plugin"
```

### Task 4: Add the explicit capture skill

**Files:**

- Create: `plugins/comprehension-profile/skills/capture-learning-pattern/SKILL.md`
- Modify: `tests/test_skill_contracts.py`
- Modify: `README.md`

**Interfaces:**

- Consumes: the current visible conversation and `references/data-contracts.md`.
- Produces: exactly one approved observation passed to `append-observation --input PATH`; never produces `profile.md`.

- [ ] **Step 1: Add failing skill contract tests**

Add a new test class:

```python
class CaptureLearningPatternSkillContractTests(unittest.TestCase):
    def setUp(self):
        self.path = (
            Path(__file__).resolve().parents[1]
            / "plugins/comprehension-profile/skills/capture-learning-pattern/SKILL.md"
        )
        self.frontmatter, self.body = load_skill(self.path)

    def test_frontmatter_targets_explicit_learning_moments(self):
        self.assertEqual(self.frontmatter["name"], "capture-learning-pattern")
        self.assertIn("click", self.frontmatter["description"].lower())

    def test_skill_extracts_complete_observation(self):
        for phrase in (
            "confusion", "clarification questions", "successful explanation",
            "why it worked", "candidate_rule", "evidence",
        ):
            self.assertIn(phrase, self.body.lower())

    def test_skill_previews_and_requires_approval_before_append(self):
        self.assertIn("exact observation", self.body.lower())
        self.assertIn("explicit approval", self.body.lower())
        self.assertIn("append-observation", self.body)

    def test_skill_never_reads_or_writes_profile(self):
        self.assertIn("must not read or modify `profile.md`", self.body.lower())
        self.assertNotIn("write-profile", self.body)

    def test_skill_uses_shared_contract(self):
        self.assertIn("references/data-contracts.md", self.body)
        self.assertIn("one observation", self.body.lower())
```

- [ ] **Step 2: Run the contract test and verify failure**

```bash
rtk python3 -m unittest tests.test_skill_contracts.CaptureLearningPatternSkillContractTests -v
```

Expected: `ERROR` because `SKILL.md` is missing.

- [ ] **Step 3: Write the capture workflow**

Create frontmatter with:

```yaml
---
name: capture-learning-pattern
description: Capture one approved learning observation when a technical explanation finally clicks, without updating the canonical comprehension profile.
---
```

The body must instruct the agent to:

1. Read `references/data-contracts.md` completely.
2. Inspect only the relevant visible conversation window.
3. Stop with no write when confusion, a successful mental model, or confirmed understanding is absent.
4. Draft every required field; hash the harness plus raw session identifier through `hash_session_key`; derive the stable ID through `make_observation_id(session_key, confusion, successful_explanation, candidate_rule)`.
5. Retain only minimal role-labeled evidence and remove unrelated or sensitive content.
6. Show the exact observation and resolved store path.
7. Ask for explicit approval; corrections invalidate the prior approval.
8. Serialize the approved object to a temporary UTF-8 JSON file, call `comprehension_store.py append-observation --input`, and remove only that temporary file.
9. Report appended, duplicate, or actionable failure status.
10. State verbatim that it **must not read or modify `profile.md`**.

Do not tell the skill to summarize historical observations or produce a profile rule directly outside the candidate observation.

- [ ] **Step 4: Document capture usage**

Add `$comprehension-profile:capture-learning-pattern` and `/comprehension-profile:capture-learning-pattern` examples to the README. Explain that capture creates evidence only; the future refiner is the only profile writer.

- [ ] **Step 5: Run skill and repository tests**

```bash
rtk python3 -m unittest tests.test_skill_contracts -v
rtk python3 -m unittest discover -s tests -v
rtk python3 scripts/validate_repository.py .
```

Expected: every test reports `ok`; repository validation passes.

- [ ] **Step 6: Commit the capture skill**

```bash
rtk git add plugins/comprehension-profile/skills/capture-learning-pattern/SKILL.md tests/test_skill_contracts.py README.md
rtk git commit -m "feat(comprehension): capture learning patterns"
```

### Task 5: Validate both plugin packages without implementing later components

**Files:**

- Modify only if validation exposes a packaging defect in files owned by this plan.

**Interfaces:**

- Consumes: completed capture plugin skeleton.
- Produces: evidence that the first component is independently installable and does not claim later behavior.

- [ ] **Step 1: Run the complete local suite**

```bash
rtk python3 -m unittest discover -s tests -v
rtk python3 scripts/validate_repository.py .
```

Expected: all tests pass and the validator prints `Repository validation passed.`.

- [ ] **Step 2: Run platform validators when installed**

```bash
rtk python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/comprehension-profile
rtk claude plugin validate ./plugins/comprehension-profile --strict
```

Expected: both validators pass. If a CLI is unavailable, record that exact limitation in the handoff; do not fabricate a pass.

- [ ] **Step 3: Verify scope and clean state**

```bash
rtk rg -n "profile\.md|detect-learning|SessionEnd|personalized-explainer" plugins/comprehension-profile/skills/capture-learning-pattern plugins/comprehension-profile/scripts README.md
rtk git status --short
```

Expected: `profile.md` appears only in the capture prohibition or shared contract, automatic/runtime components are not claimed as implemented, and only intended files are changed.

- [ ] **Step 4: Commit validation-only corrections if needed**

If Step 1 or 2 required a scoped correction, stage its explicit paths and commit:

```bash
rtk git commit -m "fix(comprehension): correct capture packaging"
```

If no correction was needed, do not create an empty commit.
