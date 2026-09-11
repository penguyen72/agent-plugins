# Refine Comprehension Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the sole profile-writer skill, which distills accumulated observations into an approved human-readable profile of at most 10 rules and 250 words instead of appending rules indefinitely.

**Architecture:** Extend the shared Python store with strict profile parsing, read commands, and atomic replacement. Keep semantic grouping and contradiction resolution in a portable model-driven skill, but make the file helper enforce the exact profile contract so no model or harness can bypass the size and structure limits.

**Tech Stack:** Markdown Agent Skills, Markdown with scalar frontmatter, JSONL, Python 3 standard library, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-11-comprehension-profile-design.md`

## Global Constraints

- Complete the Capture Learning Pattern plan before this plan; run the Detect Learning Moments plan first when automatic observations are desired.
- Consume observation schema version `1` without modifying it.
- `profile.md` is the only canonical runtime profile and the refiner is its only writer.
- The Markdown body has exactly one `# Comprehension Profile` heading followed only by bullet rules.
- Enforce at most 10 rules and at most 250 words, counting the heading and rules but not frontmatter.
- Every rule is a concise imperative explanation preference, not a domain fact, personality claim, or prose-style imitation.
- Count support by distinct `session_key`, never raw observation count.
- Favor repeated cross-session evidence; allow a singleton only when manual, explicitly confirmed, narrow, and within available budget.
- Show a complete replacement and concise rationale; write only after explicit approval of that exact text.
- A failed validation or write leaves the prior profile byte-for-byte intact.
- Do not modify, annotate, delete, or compact `observations.jsonl`.
- No third-party dependency, network request, API key, model call from Python, database, or opaque scoring store.

---

## Purpose

Turn growing, noisy evidence into a deliberately tiny set of durable explanation rules. Refinement should often merge or reject information; “no profile change” is a valid successful result.

## Existing Repository Context

Plan 1 creates `comprehension_store.py`, the observation schema/reference, cross-platform plugin packaging, and manual producer. Plan 2 optionally adds automatic observations through the same JSONL contract. Existing tests use `unittest`, a plugin-module loader, static skill-contract checks, and temporary directories.

## Architecture, Inputs, and Outputs

Inputs are all valid distinct observations plus the current valid profile when present. The skill obtains data through read-only store CLI commands, performs evidence grouping and rule selection in model context, constructs one complete Markdown proposal, and validates it before showing it.

Output is either no change or one approved atomic replacement of `profile.md`. The skill reports added, consolidated, replaced, retained, and rejected patterns without creating a second canonical artifact.

## Data Contracts

This plan keeps all Plan 1 observation interfaces and adds:

```python
PROFILE_NAME: str = "profile.md"
MAX_PROFILE_RULES: int = 10
MAX_PROFILE_WORDS: int = 250

def profile_word_count(body: str) -> int: ...
def validate_profile_text(text: str) -> list[str]: ...
def load_profile(store_root: Path) -> tuple[str | None, list[str]]: ...
def write_profile(text: str, store_root: Path) -> None: ...
```

Add CLI subcommands:

```text
read-observations [--store-root PATH]
read-profile [--store-root PATH]
validate-profile --input PATH
write-profile --input PATH [--store-root PATH]
```

`read-observations` prints one JSON array only when every existing nonblank line is valid; otherwise it prints line errors to stderr, no partial array, and returns `1`. A missing observations file prints `[]` and returns `0`. `read-profile` prints a valid profile, prints nothing for a missing profile, and returns `1` for an invalid profile. `write-profile` validates before any store mutation and atomically replaces the target.

## Files Created or Modified

- Modify `plugins/comprehension-profile/scripts/comprehension_store.py`.
- Create `plugins/comprehension-profile/skills/refine-comprehension-profile/SKILL.md`.
- Modify `plugins/comprehension-profile/references/data-contracts.md` only to document the finalized CLI; do not change schema fields.
- Modify `tests/test_comprehension_store.py`.
- Modify `tests/test_skill_contracts.py`.
- Modify `README.md`.

## Dependencies on Other Components

- Requires shared storage and manual capture from Plan 1.
- Consumes automatic observations from Plan 2 when present but works with manual observations alone.
- Produces `profile.md`, which Plan 4 Personalized Explainer consumes.
- Must be implemented before Plan 4.

## Edge Cases

- No observations: report that refinement has no evidence and write nothing.
- Only weak automatic singleton evidence: reject it and write nothing.
- Malformed observation line or unsupported version: surface the exact line error and stop without using partial evidence.
- Missing profile: propose a first profile normally.
- Invalid current profile: report it and stop; never silently replace corruption.
- Ten established rules plus a new pattern: consolidate, replace a weaker rule, or reject the new pattern.
- Contradictory patterns with equal distinct-session support: omit both from new rules and retain an established rule only if its prior evidence remains stronger.
- Multiple observations from one session: count as one supporting session per semantic group.
- An approved proposal changed after approval: revalidate, show the changed full text, and ask again.
- Atomic rename, permission, or temporary-file failure: retain prior profile and remove only the temporary sibling created by this attempt.

## Non-Goals

- Continuous or automatic refinement.
- Editing observations or maintaining accepted/rejected status inside JSONL.
- A hidden score, vector index, or machine-only user model.
- Guaranteeing that every observation becomes a rule.
- Personalizing voice, warmth, humor, verbosity, or sentence rhythm.
- Loading the profile automatically into unrelated tasks.

## Tests

Pure store tests enforce syntax, metadata, count limits, word limits, and atomicity. Skill-contract tests enforce the evidence policy, complete-replacement preview, approval gate, and exclusive-writer boundary. No test asks a real model to cluster observations.

## Acceptance Criteria

- Valid profiles round-trip through the helper.
- Invalid heading, body, frontmatter, rule count, word count, or schema cannot replace an existing profile.
- Read commands never emit partially valid history as if it were complete.
- The skill groups overlapping evidence, counts distinct sessions, resolves contradictions deterministically, and prefers repeated evidence.
- The exact replacement is shown and approved before the only profile write.
- Observations remain byte-for-byte unchanged.
- All existing producer, detector, and repository tests remain green.

---

### Task 1: Enforce the canonical profile format

**Files:**

- Modify: `plugins/comprehension-profile/scripts/comprehension_store.py`
- Modify: `tests/test_comprehension_store.py`

**Interfaces:**

- Consumes: UTF-8 Markdown text.
- Produces: `profile_word_count(body) -> int` and `validate_profile_text(text) -> list[str]`.

- [ ] **Step 1: Add a valid-profile fixture and failing validator tests**

Add:

```python
def valid_profile(*rules: str) -> str:
    selected = rules or (
        "Show causal execution order before introducing abstractions.",
        "Use one concrete example, then map it back to the general rule.",
    )
    bullets = "\n".join(f"- {rule}" for rule in selected)
    return (
        "---\n"
        "schema_version: 1\n"
        "updated_at: 2026-09-11T00:00:00Z\n"
        "observation_count: 12\n"
        "---\n\n"
        "# Comprehension Profile\n\n"
        f"{bullets}\n"
    )


class ProfileValidationTests(unittest.TestCase):
    def test_valid_profile_has_no_errors(self):
        self.assertEqual(store.validate_profile_text(valid_profile()), [])

    def test_profile_rejects_eleventh_rule(self):
        text = valid_profile(*(f"Explain concept number {index} concretely." for index in range(11)))
        self.assertIn("profile has 11 rules; maximum is 10", store.validate_profile_text(text))

    def test_profile_rejects_more_than_250_body_words(self):
        text = valid_profile(" ".join(["word"] * 249))
        self.assertIn("profile body exceeds 250 words", store.validate_profile_text(text))

    def test_profile_rejects_wrong_heading(self):
        text = valid_profile().replace("# Comprehension Profile", "# Preferences")
        self.assertIn("profile heading must be '# Comprehension Profile'", store.validate_profile_text(text))

    def test_profile_rejects_non_bullet_body_content(self):
        text = valid_profile() + "Extra paragraph.\n"
        self.assertIn("profile body may contain only the heading and bullet rules", store.validate_profile_text(text))
```

Add a table-driven format test:

```python
def test_invalid_profile_shapes_are_rejected(self):
    base = valid_profile()
    cases = {
        "missing delimiter": base.removeprefix("---\n"),
        "duplicate delimiter": base.replace("---\n\n# Comprehension", "---\n---\n\n# Comprehension"),
        "unknown metadata": base.replace("schema_version: 1", "schema_version: 1\nextra: value"),
        "schema version": base.replace("schema_version: 1", "schema_version: 2"),
        "timestamp": base.replace("2026-09-11T00:00:00Z", "yesterday"),
        "negative count": base.replace("observation_count: 12", "observation_count: -1"),
        "noninteger count": base.replace("observation_count: 12", "observation_count: many"),
        "zero rules": base[:base.index("- Show")],
        "nested bullet": base + "  - nested\n",
        "blank bullet": base + "- \n",
    }
    for expected, text in cases.items():
        with self.subTest(expected=expected):
            self.assertIn(expected, "; ".join(store.validate_profile_text(text)))
```

- [ ] **Step 2: Run profile tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_comprehension_store.ProfileValidationTests -v
```

Expected: failures because the profile functions are undefined.

- [ ] **Step 3: Implement strict parsing and counting**

Add constants and helpers:

```python
PROFILE_NAME = "profile.md"
MAX_PROFILE_RULES = 10
MAX_PROFILE_WORDS = 250
PROFILE_FIELDS = {"schema_version", "updated_at", "observation_count"}
WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def profile_word_count(body: str) -> int:
    return len(WORD.findall(body))
```

Parse frontmatter without a YAML dependency. Require exactly the three scalar fields, `schema_version: 1`, a valid UTC timestamp, and a nonnegative integer observation count. After frontmatter, ignore surrounding blank lines but require one exact heading, one or more top-level `- ` rules, and no other nonblank lines. Count heading plus bullets through `profile_word_count`.

- [ ] **Step 4: Run profile validation tests**

```bash
rtk python3 -m unittest tests.test_comprehension_store.ProfileValidationTests -v
```

Expected: all profile validation tests report `ok`.

- [ ] **Step 5: Commit the profile contract**

```bash
rtk git add plugins/comprehension-profile/scripts/comprehension_store.py tests/test_comprehension_store.py
rtk git commit -m "feat(comprehension): validate canonical profiles"
```

### Task 2: Add safe reads and atomic profile replacement

**Files:**

- Modify: `plugins/comprehension-profile/scripts/comprehension_store.py`
- Modify: `plugins/comprehension-profile/references/data-contracts.md`
- Modify: `tests/test_comprehension_store.py`

**Interfaces:**

- Consumes: store root and a valid complete profile proposal.
- Produces: `load_profile`, `write_profile`, and the four read/validate/write CLI subcommands.

- [ ] **Step 1: Add failing read and atomic-write tests**

Add:

```python
class ProfilePersistenceTests(unittest.TestCase):
    def test_missing_profile_loads_as_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(store.load_profile(Path(directory)), (None, []))

    def test_valid_profile_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store.write_profile(valid_profile(), root)
            self.assertEqual(store.load_profile(root), (valid_profile(), []))

    def test_invalid_proposal_preserves_existing_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = valid_profile("Start with a concrete example.")
            store.write_profile(original, root)
            with self.assertRaisesRegex(ValueError, "heading"):
                store.write_profile(original.replace("# Comprehension Profile", "# Wrong"), root)
            self.assertEqual((root / "profile.md").read_text(), original)

    def test_observations_remain_unchanged_during_profile_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store.append_observation(valid_observation(), root)
            before = (root / "observations.jsonl").read_bytes()
            store.write_profile(valid_profile(), root)
            self.assertEqual((root / "observations.jsonl").read_bytes(), before)
```

Add atomic-failure and CLI tests, importing `contextlib`, `io`, and `unittest.mock`:

```python
def test_replace_failure_preserves_original_and_removes_temporary_file(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original = valid_profile("Start concretely.")
        store.write_profile(original, root)
        with mock.patch.object(store.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                store.write_profile(valid_profile("Show causal order."), root)
        self.assertEqual((root / "profile.md").read_text(), original)
        self.assertEqual(list(root.glob(".profile.*.tmp")), [])

def test_read_observations_cli_never_emits_partial_data(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "observations.jsonl").write_text("not-json\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = store.main(["read-observations", "--store-root", str(root)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("line 1", stderr.getvalue())

def test_profile_cli_missing_read_and_valid_write(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "store"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(store.main(["read-profile", "--store-root", str(root)]), 0)
        self.assertEqual(stdout.getvalue(), "")
        source = Path(directory) / "profile-input.md"
        source.write_text(valid_profile())
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = store.main(["write-profile", "--input", str(source), "--store-root", str(root)])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "Profile updated.")

def test_validate_profile_cli_rejects_invalid_heading(self):
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "bad.md"
        source.write_text(valid_profile().replace("# Comprehension Profile", "# Wrong"))
        self.assertEqual(store.main(["validate-profile", "--input", str(source)]), 1)
```

- [ ] **Step 2: Run persistence tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_comprehension_store.ProfilePersistenceTests -v
```

Expected: failures naming undefined `load_profile` and `write_profile`.

- [ ] **Step 3: Implement profile load and atomic replacement**

Use a temporary sibling and `os.replace`:

```python
def write_profile(text: str, store_root: Path) -> None:
    errors = validate_profile_text(text)
    if errors:
        raise ValueError("; ".join(errors))
    store_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = store_root / PROFILE_NAME
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=store_root,
            prefix=".profile.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_file_permissions(temporary_path)
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
```

`load_profile` reads only `profile.md`, validates it, and returns `(text, [])`, `(None, [])`, or `(None, errors)`.

- [ ] **Step 4: Add the read and write CLI commands**

Implement exact behavior:

- `read-observations`: JSON array on stdout only if there are no errors.
- `read-profile`: full valid Markdown on stdout; missing profile is success with empty stdout.
- `validate-profile`: `Profile is valid.` on success.
- `write-profile`: `Profile updated.` only after observed atomic replacement.

All errors are concise stderr with exit `1`. CLI reads never initialize the store.

- [ ] **Step 5: Update the contract reference**

Document command names and exit behavior. Preserve every approved schema field and limit verbatim.

- [ ] **Step 6: Run store tests and commit**

```bash
rtk python3 -m unittest tests.test_comprehension_store -v
rtk git add plugins/comprehension-profile/scripts/comprehension_store.py plugins/comprehension-profile/references/data-contracts.md tests/test_comprehension_store.py
rtk git commit -m "feat(comprehension): replace profiles atomically"
```

Expected: all store tests report `ok` before commit.

### Task 3: Define evidence distillation and approval behavior

**Files:**

- Create: `plugins/comprehension-profile/skills/refine-comprehension-profile/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**

- Consumes: `read-observations`, `read-profile`, and the approved evidence policy.
- Produces: zero writes or one exact approved complete profile through `write-profile`.

- [ ] **Step 1: Add failing refiner contract tests**

Add:

```python
class RefineComprehensionProfileSkillContractTests(unittest.TestCase):
    def setUp(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "plugins/comprehension-profile/skills/refine-comprehension-profile/SKILL.md"
        )
        self.frontmatter, self.body = load_skill(path)

    def test_frontmatter_names_distillation_skill(self):
        self.assertEqual(self.frontmatter["name"], "refine-comprehension-profile")
        self.assertIn("distill", self.frontmatter["description"].lower())

    def test_skill_enforces_evidence_policy(self):
        for phrase in (
            "distinct `session_key`", "manual observations", "automatic observations",
            "merge overlapping", "resolve contradictions", "weak evidence",
        ):
            self.assertIn(phrase.lower(), self.body.lower())

    def test_skill_enforces_both_budgets(self):
        self.assertIn("10 rules", self.body)
        self.assertIn("250 words", self.body)
        self.assertIn("consolidate, replace, or reject", self.body.lower())

    def test_skill_previews_complete_replacement_and_requires_approval(self):
        self.assertIn("complete replacement", self.body.lower())
        self.assertIn("explicit approval", self.body.lower())
        self.assertIn("write-profile", self.body)

    def test_skill_is_only_profile_writer_and_never_changes_observations(self):
        self.assertIn("only profile writer", self.body.lower())
        self.assertIn("must not modify `observations.jsonl`", self.body.lower())
```

Add these literal contract checks:

```python
def test_skill_defines_safe_no_change_and_conflict_ties(self):
    self.assertIn("no valid observations", self.body.lower())
    self.assertIn("write nothing", self.body.lower())
    self.assertIn("if still tied", self.body.lower())
    self.assertIn("add neither", self.body.lower())
    self.assertIn("preserve an existing rule", self.body.lower())

def test_skill_invalidates_approval_after_any_edit(self):
    self.assertIn("any edit", self.body.lower())
    self.assertIn("approval again", self.body.lower())
```

- [ ] **Step 2: Run contract tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_skill_contracts.RefineComprehensionProfileSkillContractTests -v
```

Expected: `ERROR` because the skill file is missing.

- [ ] **Step 3: Write the refiner skill**

Use frontmatter:

```yaml
---
name: refine-comprehension-profile
description: Distill accumulated learning observations into a tiny approved comprehension profile by merging repeated evidence and resolving contradictions.
---
```

The workflow must specify:

1. Read `references/data-contracts.md` completely.
2. Run `read-observations`; stop on any reported malformed line or unsupported schema.
3. Run `read-profile`; treat empty output as no existing profile and stop on invalid output.
4. Group semantically overlapping candidate rules without erasing meaningful context.
5. Compute support using unique `session_key` values per group. Record manual count, automatic count, and newest timestamp only as tie-break evidence.
6. Require two distinct sessions for a broad rule. Permit one-session evidence only if `source == manual`, the evidence includes assistant confirmation, the rule remains narrow, and space exists.
7. Merge overlapping rules; remove redundant or weak rules.
8. For contradictions, prefer more distinct sessions, then more manual observations, then newer evidence. If still tied, add neither new rule; preserve an existing rule only when its supporting evidence is independently stronger.
9. Preserve an established rule when new evidence does not materially improve or contradict it.
10. Build one full profile with exact metadata, no more than 10 bullets, and no more than 250 body words.
11. When over budget, consolidate, replace, or reject—never append past the limit.
12. Show the complete replacement and a concise rationale organized as retained, added, consolidated/replaced, and rejected.
13. Run `validate-profile` on the exact proposal.
14. Ask for explicit approval. Any edit requires validation and approval again.
15. Run `write-profile` once, then report the observed result.
16. State that it is the **only profile writer** and **must not modify `observations.jsonl`**.

- [ ] **Step 4: Run skill contract tests**

```bash
rtk python3 -m unittest tests.test_skill_contracts.RefineComprehensionProfileSkillContractTests -v
```

Expected: all refiner contract tests report `ok`.

- [ ] **Step 5: Commit the refiner skill**

```bash
rtk git add plugins/comprehension-profile/skills/refine-comprehension-profile/SKILL.md tests/test_skill_contracts.py
rtk git commit -m "feat(comprehension): distill comprehension profiles"
```

### Task 4: Document and verify the complete distillation component

**Files:**

- Modify: `README.md`
- Modify only on failure: files owned by this plan.

**Interfaces:**

- Consumes: an installed plugin and isolated test store.
- Produces: clear usage, privacy, budget, and approval documentation plus full-suite evidence.

- [ ] **Step 1: Document refinement usage and limits**

Add Codex and Claude examples:

```text
$comprehension-profile:refine-comprehension-profile
/comprehension-profile:refine-comprehension-profile
```

State that refinement is manual, reads accumulated local observations, shows a complete proposal, requires approval, and is the only profile writer. Document the 10-rule and 250-word limits and that new evidence may be rejected.

- [ ] **Step 2: Add an isolated CLI acceptance test**

In `tests/test_comprehension_store.py`, call `main` with temporary JSON/profile input paths and a temporary store to prove this sequence:

```text
append-observation -> read-observations -> validate-profile -> write-profile -> read-profile
```

Assert each exit code is `0`, the read profile exactly equals the proposal, and observations bytes are unchanged after the profile write.

- [ ] **Step 3: Run all Python and repository validation**

```bash
rtk python3 -m unittest discover -s tests -v
rtk python3 scripts/validate_repository.py .
```

Expected: all tests pass and repository validation succeeds.

- [ ] **Step 4: Run platform validators when available**

```bash
rtk python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/comprehension-profile
rtk claude plugin validate ./plugins/comprehension-profile --strict
```

Expected: both pass. If unavailable, report the exact missing CLI rather than claiming success.

- [ ] **Step 5: Commit docs and acceptance coverage**

```bash
rtk git add README.md tests/test_comprehension_store.py
rtk git commit -m "docs(comprehension): explain profile refinement"
```
