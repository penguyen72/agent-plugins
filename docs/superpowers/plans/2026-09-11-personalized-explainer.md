# Personalized Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a runtime explanation skill that reads only the tiny canonical profile and adapts technical explanations to the user's demonstrated comprehension patterns while preserving each model's natural voice.

**Architecture:** Keep runtime behavior entirely in one portable Markdown skill. The skill obtains the validated `profile.md` through the shared store's `read-profile` command, selects only relevant rules, and applies them beneath correctness and explicit user requirements; it never loads observations or writes personalization data.

**Tech Stack:** Markdown Agent Skills, existing Python standard-library profile reader, `unittest` static contract tests, Codex and Claude Code plugin packaging.

**Spec:** `docs/superpowers/specs/2026-09-11-comprehension-profile-design.md`

## Global Constraints

- Complete Capture Learning Pattern and Refine Comprehension Profile before this plan; Detect Learning Moments is recommended but not required for runtime use.
- Reuse `comprehension_store.py read-profile`; do not add a second parser or profile format.
- Runtime context is only the current request plus validated `profile.md`.
- Never read, search, summarize, count, or mention `observations.jsonl`.
- Never write the profile, observations, or any new runtime memory.
- Apply only rules relevant to the current technical explanation.
- Correctness, safety, explicit user instructions, and requested output format take precedence over profile preferences.
- Preserve Codex's or Claude's natural voice; align explanation structure, not tone, phrasing, or sentence rhythm.
- Do not mention the profile or personalization machinery unless the user asks.
- Missing, empty, invalid, unsupported, irrelevant, or unreadable profiles fall back to a normal explanation.
- No network request, API key, model call from a script, embedding, database, or historical-context load.

---

## Purpose

Make the small distilled profile useful at the moment of explanation. Codex is the primary evidence source, while Claude can consume the same local profile and present concepts using the same proven structures without being forced to sound like Codex.

## Existing Repository Context

The prerequisite plans establish the `comprehension-profile` cross-platform plugin, user store, observation producers, profile contract, atomic writer, and `read-profile` command. Existing skill tests use `load_skill()` in `tests/test_skill_contracts.py`; plugin packaging and catalogs already exist.

## Architecture, Inputs, and Outputs

Inputs are the user's current request and the output of `read-profile`. The skill activates on requests to explain, clarify, teach, unpack, compare, or build intuition for a technical concept. It does not activate merely because code is being edited or a factual value is requested.

Output is a normal AI response whose organization reflects applicable profile rules. No persistent output is created.

## Data Contracts

The skill consumes only the Plan 3 command:

```text
comprehension_store.py read-profile
```

Exit `0` plus non-empty stdout means a valid version 1 profile. Exit `0` plus empty stdout means no profile. Nonzero exit means invalid or unreadable profile. The skill does not parse or consume observation records and introduces no new persistent schema.

## Files Created or Modified

- Create `plugins/comprehension-profile/skills/personalized-explainer/SKILL.md`.
- Modify `tests/test_skill_contracts.py`.
- Modify `README.md`.
- Modify no Python production file unless a verified bug prevents the already-specified `read-profile` interface from working; any such bug must remain a narrow compatibility fix with a regression test.

## Dependencies on Other Components

- Requires Plan 1 plugin packaging and shared path convention.
- Requires Plan 3 profile validation and `read-profile` command.
- Benefits from observations produced by Plans 1 and 2 only indirectly through refinement.
- Is downstream-only: no other component depends on runtime output from this skill.

## Edge Cases

- Missing profile: explain normally without warning or initialization.
- Invalid or unsupported profile: explain normally and mention the issue only if the user asks about personalization.
- A profile rule conflicts with an explicit request such as “no analogy”: honor the explicit request.
- A rule is domain-inapplicable: ignore it rather than awkwardly forcing it.
- Several rules overlap: combine them naturally without repeating explanation sections.
- The user requests a terse answer: preserve the requested brevity even if a rule prefers examples.
- The user asks to see the profile: answer that separate request directly; do not expose observations.
- The user expresses understanding: finish the response normally; do not append evidence from the runtime skill.
- The question is nontechnical or asks only for a value: do not force the explainer workflow.

## Non-Goals

- Making Claude imitate Codex's voice or vice versa.
- Automatically invoking capture or refinement.
- Reading evidence to justify a runtime response.
- Assessing the user's intelligence, expertise, personality, or preferred verbosity beyond explicit profile rules.
- Rewriting correct domain terminology solely to satisfy a preference.
- Guaranteeing identical output across different models.

## Tests

Static contract tests verify activation language, the profile-only read path, priority rules, structural-not-stylistic behavior, quiet fallback, and total absence of observation/write commands. Existing store tests already verify that `read-profile` returns only a valid profile.

## Acceptance Criteria

- The skill is discoverable for technical explanation requests in both Codex and Claude Code.
- With a valid profile, it reads and applies only relevant rules.
- Without a usable profile, it provides a normal explanation without blocking.
- It never loads observations or mutates user data.
- It explicitly preserves model voice and prioritizes correctness and user instructions.
- README documents the full capture → detect → refine → explain flow and the structural-not-stylistic goal.
- All existing and new tests and both platform validators pass.

---

### Task 1: Specify the runtime explanation contract

**Files:**

- Create: `plugins/comprehension-profile/skills/personalized-explainer/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**

- Consumes: current technical explanation request and validated stdout from `read-profile`.
- Produces: one explanation response and no persistent mutation.

- [ ] **Step 1: Add failing skill contract tests**

Add:

```python
class PersonalizedExplainerSkillContractTests(unittest.TestCase):
    def setUp(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "plugins/comprehension-profile/skills/personalized-explainer/SKILL.md"
        )
        self.frontmatter, self.body = load_skill(path)

    def test_frontmatter_targets_technical_explanations(self):
        self.assertEqual(self.frontmatter["name"], "personalized-explainer")
        description = self.frontmatter["description"].lower()
        self.assertIn("technical", description)
        self.assertIn("explain", description)

    def test_skill_reads_only_the_canonical_profile(self):
        self.assertIn("read-profile", self.body)
        self.assertIn("`profile.md`", self.body)
        self.assertNotIn("observations.jsonl", self.body)
        self.assertNotIn("read-observations", self.body)

    def test_skill_has_no_persistent_write_path(self):
        self.assertNotIn("append-observation", self.body)
        self.assertNotIn("write-profile", self.body)
        self.assertIn("must not write", self.body.lower())

    def test_skill_prioritizes_truth_and_user_requirements(self):
        for phrase in (
            "factual correctness", "safety", "explicit user instructions",
            "requested output format",
        ):
            self.assertIn(phrase, self.body.lower())

    def test_skill_preserves_model_voice(self):
        self.assertIn("natural voice", self.body.lower())
        self.assertIn("explanation structure", self.body.lower())
        self.assertIn("not stylistic imitation", self.body.lower())

    def test_skill_falls_back_quietly(self):
        for phrase in ("missing", "invalid", "unsupported", "irrelevant"):
            self.assertIn(phrase, self.body.lower())
        self.assertIn("explain normally", self.body.lower())
```

Add:

```python
def test_skill_uses_only_relevant_rules_and_keeps_personalization_quiet(self):
    self.assertIn("select", self.body.lower())
    self.assertIn("relevant rules", self.body.lower())
    self.assertIn("unless the user asks", self.body.lower())
    self.assertIn("must not invoke another skill", self.body.lower())
```

- [ ] **Step 2: Run the contract tests and confirm failure**

```bash
rtk python3 -m unittest tests.test_skill_contracts.PersonalizedExplainerSkillContractTests -v
```

Expected: `ERROR` because `SKILL.md` is missing.

- [ ] **Step 3: Write precise activation frontmatter**

Create:

```yaml
---
name: personalized-explainer
description: Explain, clarify, teach, compare, or build intuition for technical concepts using the user's small comprehension profile while preserving the model's natural voice.
---
```

The description should trigger for explanation work but not claim every coding, editing, or lookup request.

- [ ] **Step 4: Write the profile-only runtime workflow**

The body must direct the agent to:

1. Resolve the installed plugin root as the directory two levels above this `SKILL.md`; do not assume the current working directory is the plugin.
2. Assign the resolved path to task-specific variable `COMPREHENSION_PLUGIN_ROOT`, run `python3 "$COMPREHENSION_PLUGIN_ROOT/scripts/comprehension_store.py" read-profile`, and treat its output according to the established exit contract.
3. On missing, invalid, unsupported, or unreadable profile, explain normally without blocking, initializing data, or mentioning the failure unless asked.
4. Parse only the bullet rules from the already validated profile.
5. Select the subset relevant to this request; ignore irrelevant or conflicting rules.
6. Apply preferences to explanation structure: ordering, concrete examples, causal framing, analogy choice, abstraction timing, mappings, and checks for understanding.
7. Use this priority order: safety and factual correctness; explicit user instructions and requested format; applicable profile rules; the model's normal defaults.
8. Produce the explanation in the current model's natural voice. State that the goal is **explanation structure, not stylistic imitation**.
9. Do not reveal or mention the profile unless the user asks.
10. **Must not write** any profile, observation, note, or memory and **must not invoke another skill** as a side effect of explaining.

Do not instruct the skill to open `references/data-contracts.md`; that would add irrelevant observation-schema context at runtime.

- [ ] **Step 5: Run all skill contract tests**

```bash
rtk python3 -m unittest tests.test_skill_contracts -v
```

Expected: every skill contract test reports `ok`.

- [ ] **Step 6: Commit the runtime skill**

```bash
rtk git add plugins/comprehension-profile/skills/personalized-explainer/SKILL.md tests/test_skill_contracts.py
rtk git commit -m "feat(comprehension): personalize technical explanations"
```

### Task 2: Document the complete user workflow

**Files:**

- Modify: `README.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**

- Consumes: all four implemented components.
- Produces: accurate installation, usage, privacy, disable, and lifecycle documentation.

- [ ] **Step 1: Add a failing README contract test**

Add:

```python
class ComprehensionProfileReadmeContractTests(unittest.TestCase):
    def test_readme_documents_complete_flow_and_limits(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "capture-learning-pattern",
            "SessionEnd",
            "refine-comprehension-profile",
            "personalized-explainer",
            "10 rules",
            "250 words",
            "~/.comprehension-profile",
            "COMPREHENSION_PROFILE_HOME",
        ):
            self.assertIn(phrase, text)
        self.assertIn("structure", text.lower())
        self.assertIn("natural voice", text.lower())
```

- [ ] **Step 2: Run the README contract test and confirm failure**

```bash
rtk python3 -m unittest tests.test_skill_contracts.ComprehensionProfileReadmeContractTests -v
```

Expected: failure for `personalized-explainer` or final workflow language not yet present.

- [ ] **Step 3: Add a concise Comprehension Profile section to README**

Document this lifecycle in order:

```text
conversation
  -> manual capture and/or trusted SessionEnd detector
  -> observations.jsonl
  -> explicitly invoked refinement with approved replacement
  -> profile.md (10 rules / 250 words)
  -> personalized explainer in Codex or Claude Code
```

Include invocation examples:

```text
$comprehension-profile:personalized-explainer explain dependency injection
/comprehension-profile:personalized-explainer explain dependency injection
```

Explain that skill discovery may activate it for technical explanation requests, that the two harnesses must use the same local store path, that only short excerpts are stored, and that explanation structure is shared while each model keeps its natural voice. Preserve the hook trust/disable guidance from Plan 2.

- [ ] **Step 4: Run README and skill tests**

```bash
rtk python3 -m unittest tests.test_skill_contracts -v
```

Expected: all contract tests report `ok`.

- [ ] **Step 5: Commit user documentation**

```bash
rtk git add README.md tests/test_skill_contracts.py
rtk git commit -m "docs(comprehension): explain personalized workflow"
```

### Task 3: Verify runtime isolation and cross-platform packaging

**Files:**

- Modify only if verification exposes a scoped defect in files owned by this plan.

**Interfaces:**

- Consumes: final `comprehension-profile` plugin.
- Produces: test evidence that the runtime skill is profile-only and both platforms package it.

- [ ] **Step 1: Prove the runtime skill has no observation dependency**

```bash
rtk rg -n "observations\.jsonl|read-observations|append-observation|write-profile|capture-learning-pattern|refine-comprehension-profile" plugins/comprehension-profile/skills/personalized-explainer/SKILL.md
```

Expected: no matches. If the required “must not invoke capture or refinement” wording uses those literal names, adjust the static assertion to permit only that prohibition and prove no command invocation exists.

- [ ] **Step 2: Run the full local suite**

```bash
rtk python3 -m unittest discover -s tests -v
rtk python3 scripts/validate_repository.py .
```

Expected: all tests pass and repository validation prints `Repository validation passed.`.

- [ ] **Step 3: Run platform validators**

```bash
rtk python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/comprehension-profile
rtk claude plugin validate ./plugins/comprehension-profile --strict
```

Expected: both platform validators pass when installed. Record unavailable tooling honestly.

- [ ] **Step 4: Review the final file boundary**

```bash
rtk git status --short
rtk rg --files plugins/comprehension-profile
```

Expected: the plugin contains only the two manifests, one hook file, one reference, focused scripts, and three skills specified by the design. No profile or observation data is checked into the repository.

- [ ] **Step 5: Commit scoped corrections only if required**

If verification required a correction, stage exact paths and commit:

```bash
rtk git commit -m "fix(comprehension): preserve runtime isolation"
```

If no correction was needed, do not create an empty commit.
