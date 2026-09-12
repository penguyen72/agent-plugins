# Comprehension Profile Design

## Purpose

Add a small, cross-harness system that learns how a user understands technical concepts and applies those preferences to later explanations. Codex is the primary source of learning evidence in the first release. Codex and Claude Code both consume the same canonical profile so Claude follows the same demonstrated explanation structure without imitating Codex's tone or phrasing.

The system optimizes for signal over volume. Historical observations may grow, but the runtime profile remains human-readable and intentionally tiny: no more than 10 rules and no more than 250 words.

## Scope and First-Release Support

The first release provides runnable integration for Codex and Claude Code. Its file formats are harness-neutral so another local agent can adopt them later, but direct ChatGPT or other hosted-harness integration is not part of this release.

The profile captures explanation structure, including sequencing, abstraction level, analogy type, concrete examples, causal framing, and checks for understanding. It does not capture surface voice, sentence rhythm, favorite phrases, or a model's general writing style.

All persistent data is user-scoped rather than project-scoped. This allows evidence learned in one technical domain or repository to improve explanations elsewhere and lets Codex and Claude installations on the same local machine read the same profile. Cross-machine and cloud synchronization are not included.

## Repository Context

This repository is a dual-platform Codex and Claude Code plugin marketplace. Existing plugins are self-contained beneath `plugins/`, use Markdown skills, have separate platform manifests, and are listed in both root marketplace catalogs. Repository validation and contract tests use Python's standard library and `unittest`.

The new feature should follow those conventions as one self-contained `comprehension-profile` plugin. The plugin must not depend on files elsewhere in the repository after installation.

Current platform hook contracts make a shared adapter boundary practical:

- [Codex hooks](https://learn.chatgpt.com/codex/hooks) support plugin-bundled `SessionEnd` command hooks and supply `session_id` and `transcript_path`. Codex limits `SessionEnd` hooks to three seconds and explicitly states that transcript format is not a stable interface.
- [Claude Code hooks](https://code.claude.com/docs/en/hooks) support plugin-bundled hooks and also supply `session_id` and `transcript_path` to `SessionEnd` hooks.

Therefore the session-end path must be local, dependency-free, conservative, and fast. Transcript parsing is isolated behind harness-specific adapters.

## Approaches Considered

### 1. File-first plugin with deterministic detection

Package portable skills, a small Python utility layer, and session-end hook adapters in one plugin. Store append-only observations and one Markdown profile in a shared user directory. Automatic detection uses a conservative state machine rather than another model call.

This is the selected approach. It has no service, API key, network traffic, database, or background worker. It fits both plugin systems and keeps behavior auditable. Its trade-off is intentional recall loss: subtle learning moments may be missed and left for manual capture.

### 2. Model-backed session-end detection

Call an external model or nested harness process at session end to interpret the transcript. This could recognize subtler moments but introduces cost, credentials, privacy concerns, nondeterminism, and lifecycle problems. It also does not fit Codex's short session-end budget reliably.

This is rejected for the first release.

### 3. Local daemon with a database and processing queue

Have hooks enqueue sessions for a long-running service that performs analysis, stores structured history, and serves the profile to multiple clients. This offers reliable asynchronous processing and future extensibility, but installation, synchronization, upgrades, and failure recovery become a product of their own.

This is rejected as unnecessary infrastructure.

## Overall Architecture

```text
Codex or Claude conversation
           |
           +------------------------------+
           |                              |
           v                              v
  SessionEnd hook                 Capture Learning Pattern
           |                         explicit skill
           v                              |
  transcript adapter                     |
           |                              |
           v                              v
  Detect Learning Moments ------> observations.jsonl
                                          |
                                          v
                            Refine Comprehension Profile
                                   explicit skill
                                          |
                                approved replacement
                                          v
                                     profile.md
                                          |
                                          v
                               Personalized Explainer
                                    runtime skill
                                          |
                                          v
                                   AI explanation
```

Automatic detection and manual capture share one observation contract and never modify the canonical profile. Refinement is the only component allowed to create or replace `profile.md`. The explainer reads only `profile.md`; it never loads observations.

## Plugin Layout

```text
plugins/comprehension-profile/
├── .codex-plugin/
│   └── plugin.json
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   └── hooks.json
├── references/
│   └── data-contracts.md
├── scripts/
│   ├── comprehension_store.py
│   ├── detect_learning_moments.py
│   └── transcript_adapters.py
└── skills/
    ├── capture-learning-pattern/
    │   └── SKILL.md
    ├── refine-comprehension-profile/
    │   └── SKILL.md
    └── personalized-explainer/
        └── SKILL.md
```

`hooks/hooks.json` is shared by both platforms and invokes the detector for `SessionEnd`. The command uses the plugin-root compatibility environment exposed by both harnesses. The detector identifies the harness from environment markers and falls back to safe adapter probing when the marker is absent.

## Shared User Store

The store root resolves in this order:

1. Non-empty `COMPREHENSION_PROFILE_HOME`.
2. `~/.comprehension-profile/`.

The first release uses two persistent files:

```text
~/.comprehension-profile/
├── observations.jsonl
└── profile.md
```

`observations.jsonl` may grow over time and is never loaded by the runtime explainer. `profile.md` may be absent until the user first approves a refinement.

Writers create the directory and files with user-only permissions where the operating system supports them. Observation writes use a short-lived lock file, compact single-record serialization, and deterministic IDs. Profile writes use a temporary sibling file followed by atomic replacement.

## Learning Observation Contract

`observations.jsonl` is UTF-8 and append-only. Each line is one complete JSON object:

```json
{
  "schema_version": 1,
  "id": "64 lowercase hexadecimal characters",
  "captured_at": "2026-09-11T00:00:00Z",
  "source": "manual",
  "harness": "codex",
  "session_key": "64 lowercase hexadecimal characters",
  "topic": "dependency injection",
  "confusion": "The abstraction hid when objects were created.",
  "clarification_questions": [
    "Who constructs the dependency?"
  ],
  "successful_explanation": "A concrete request path showing construction before use.",
  "why_it_worked": "It replaced an abstract container metaphor with causal execution order.",
  "candidate_rule": "Show lifecycle and ownership in execution order before naming abstractions.",
  "signals": [
    "explicit_confusion",
    "user_restatement",
    "assistant_confirmation"
  ],
  "evidence": [
    {"role": "user", "excerpt": "So the container creates it before..."},
    {"role": "assistant", "excerpt": "Exactly..."}
  ]
}
```

### Observation field rules

- `schema_version` is the integer `1`.
- `id` is a SHA-256-based stable identifier for the learning moment. Writers use it to turn duplicate appends into no-ops.
- `captured_at` is an RFC 3339 UTC timestamp ending in `Z`.
- `source` is `manual` or `automatic`.
- `harness` is `codex`, `claude`, or `other`.
- `session_key` is a SHA-256 hash of the harness namespace and raw session identifier. The raw identifier is not retained.
- `topic` is non-empty and at most 120 characters.
- `confusion`, `successful_explanation`, and `why_it_worked` are non-empty and at most 500 characters each.
- `candidate_rule` is non-empty and at most 300 characters.
- `clarification_questions` contains zero to five strings, each at most 280 characters.
- `signals` contains unique values from `explicit_confusion`, `repeated_clarification`, `user_restatement`, `assistant_confirmation`, and `explicit_understanding`.
- `evidence` contains one to six role-labeled excerpts. Roles are `user` or `assistant`; each excerpt is non-empty and at most 280 characters.
- Automatic observations require `explicit_confusion`, `user_restatement`, and `assistant_confirmation`.
- Unknown fields are rejected in version 1 so accidental schema drift is visible.
- Readers report and skip unsupported schema versions rather than guessing.

Interpretive fields describe comprehension, not writing style. Evidence is scrubbed for obvious credentials and truncated before persistence. Full transcripts, tool calls, tool results, hidden reasoning, repository content, and unrelated conversation segments are never copied into the store.

## Comprehension Profile Contract

`profile.md` is UTF-8 Markdown with scalar frontmatter:

```markdown
---
schema_version: 1
updated_at: 2026-09-11T00:00:00Z
observation_count: 12
---

# Comprehension Profile

- Show causal execution order before introducing abstractions.
- Use one concrete example, then map each part back to the general rule.
```

The Markdown body is authoritative and contains one `# Comprehension Profile` heading followed only by bullet rules. It may contain at most 10 rules and at most 250 words, counting the heading and rules but not frontmatter. Each rule is a concise imperative preference that another model can apply without reading historical evidence. `observation_count` records the number of distinct valid observations considered during the latest approved refinement, not the number of rules.

Refinement always proposes and validates a complete replacement. It never appends a rule directly. If a new preference would exceed either budget, refinement must consolidate, replace, or reject information before presenting the proposal.

## Component Design

### Capture Learning Pattern

This explicit/manual skill handles moments the user recognizes as meaningful. It inspects only the relevant conversation window and identifies:

- The initial confusion or incorrect mental model.
- The user's clarification questions.
- The explanation, example, analogy, ordering, or restatement that made the concept understandable.
- Observable evidence that understanding occurred.
- Why the successful explanation worked for this user.
- One concise, potentially generalizable candidate rule.

The skill validates and previews one complete observation. It asks for approval before appending because the observation becomes persistent user-level data. It may initialize the observations store after approval, but it must not create, read for mutation, or modify `profile.md`.

If the conversation does not contain a clear transition to understanding, the skill explains that evidence is insufficient and writes nothing. The user may correct the proposed wording before approval.

### Detect Learning Moments

The detector is a dependency-free Python command invoked by a plugin `SessionEnd` hook. It receives the hook event as JSON on standard input. `transcript_adapters.py` exposes a stable internal stream of user-visible messages with `role`, `text`, and chronological position; adapter details do not leak into detection logic.

The detector applies this state machine:

1. Find an explicit user confusion signal.
2. Find a later clarification question or explanatory turn.
3. Find a later user restatement that reconstructs the concept rather than merely acknowledging it.
4. Find a later assistant confirmation of that restatement.
5. Score competing sequences and select only the strongest complete sequence.
6. Append at most one automatic observation for the session.

The detector rejects quoted examples, hypothetical dialogue, meta-discussion about confusion signals, bare acknowledgments such as "thanks" or "got it," assistant confirmation without a preceding user restatement, sequences separated by a topic change, subagent messages, tool chatter, and an already-recorded stable ID.

Automatic summaries are conservative and template-based. They describe observable explanation structure, such as a transition after a concrete example or causal restatement, without claiming a deeper preference the transcript cannot prove. A low-confidence or malformed session produces no candidate. Missing subtle moments is acceptable; generating noise is not.

The hook performs no network calls and launches no nested model process. It remains silent on normal no-match outcomes.

### Refine Comprehension Profile

This explicit skill reads all valid observations and the current profile, when present. It performs distillation rather than accumulation:

1. Group observations that support the same underlying explanation preference.
2. Count support across distinct `session_key` values so repeats in one conversation do not masquerade as independent evidence.
3. Give manual observations more evidentiary weight than automatic observations while still requiring cross-session support for broad rules.
4. Merge overlapping rules and remove redundant or weak rules.
5. Resolve contradictions by keeping the better-supported rule, narrowing rules to different contexts, or omitting both when evidence is inconclusive.
6. Preserve established rules unless new evidence materially improves or contradicts them.
7. Produce a complete proposed profile within both size limits.
8. Show the replacement profile and a concise change rationale.
9. Write it atomically only after explicit approval.

A singleton may justify a narrow rule only when it is a manually captured, explicitly confirmed learning moment and there is available budget. Near the size limit, repeated cross-session evidence takes priority over single-session preferences. Refusal to add a weak rule is a successful outcome.

### Personalized Explainer

This runtime skill applies when the user asks for a technical concept to be explained. It reads only `profile.md`, validates the frontmatter and size limits, selects the rules relevant to the requested explanation, and follows them without mentioning the profile unless the user asks.

The profile influences presentation but never overrides factual correctness, safety constraints, requested output format, or explicit user instructions. Rules that do not apply to the current domain are ignored. The model retains its natural voice; the intended consistency between Codex and Claude is structural, not stylistic.

If the profile is missing, empty, malformed, unsupported, or irrelevant, the skill explains normally. It never opens `observations.jsonl` as a fallback.

## Failure Handling and Safety

- Installing and trusting the plugin hook is the opt-in boundary for automatic detection. Documentation includes a way to disable the hook while retaining explicit skills.
- The session-end detector must not block or prolong session shutdown. Missing transcript paths, unsupported transcript records, lock contention, low-confidence matches, and duplicate observations leave data unchanged and exit successfully.
- Explicit skills surface malformed records, unsupported schemas, invalid profiles, and permission errors with an actionable message. They do not repair or overwrite data without approval.
- A partially written observation must never be treated as valid. The append helper validates the compact record before acquiring the lock and writes one complete newline-terminated record.
- A failed profile validation or atomic rename leaves the previous profile intact.
- Store paths are resolved once and shown before the first approved persistent write. The plugin never transmits stored data.
- Secret scrubbing is defense in depth, not a guarantee. The primary privacy control is retaining only short user-visible excerpts from the relevant learning sequence.

## Testing Strategy

Use Python standard-library `unittest` and checked-in synthetic data only. No automated test invokes a real model, reads a real user transcript, uses a network, or changes a real user profile.

### Store and schema tests

- Accept a valid version 1 manual and automatic observation.
- Reject missing, unknown, oversized, duplicated, or invalid fields.
- Hash raw session IDs and verify raw IDs are absent from persisted text.
- Truncate evidence and scrub representative credential forms.
- Treat duplicate IDs as no-ops.
- Exercise lock contention and ensure existing data remains valid.
- Validate profile frontmatter, heading, bullet-only body, 10-rule limit, and 250-word limit.
- Prove invalid proposed profiles cannot replace an existing valid profile.

### Detector and adapter tests

- Parse synthetic Codex and Claude transcript fixtures into the same normalized message stream.
- Detect explicit confusion followed by clarification, user restatement, and assistant confirmation.
- Select only the strongest sequence and append at most one candidate per session.
- Reject acknowledgment-only, confirmation-only, quoted, hypothetical, topic-shifted, tool, subagent, malformed, and low-confidence sequences.
- Verify no-match and unsupported-transcript paths exit cleanly without writes.

### Skill contract tests

- Capture must inspect confusion, clarification, successful explanation, why it worked, and request approval before append.
- Capture and detection must explicitly prohibit profile writes.
- Refinement must merge, deduplicate, resolve contradictions, count distinct sessions, enforce both budgets, preview a complete replacement, and request approval.
- The explainer must read only `profile.md`, preserve the underlying model's voice, and fall back safely.
- Skills must use the shared data-contract reference rather than redefining incompatible formats.

### Repository integration tests

- Both marketplace catalogs list `comprehension-profile` consistently.
- Codex and Claude manifests agree on plugin name and version.
- The hook path resolves inside the plugin and declares `SessionEnd` only.
- Every referenced script, skill, and contract file is packaged inside the plugin.
- The checked-in repository passes its Python validator and both platform plugin validators where available.

## Non-Goals

- Direct ChatGPT or hosted-harness integration in version 1.
- Cross-machine, cloud, or account-based profile synchronization.
- Imitating Codex, Claude, or ChatGPT tone and prose style.
- Saving complete transcripts or building searchable conversation memory.
- Automatically promoting every observation into the profile.
- Embeddings, vector search, clustering infrastructure, a database, a daemon, or a hosted service.
- Model calls, API keys, or network access from hooks.
- Domain-specific tutoring curricula, knowledge assessment, or factual user modeling.
- A UI for browsing or editing observations.
- Perfect recall of every learning moment.

## Acceptance Criteria

The design is successfully implemented when:

- Codex and Claude Code can install the same self-contained plugin and point to the same user-level store.
- Manual capture writes an approved, schema-valid observation and cannot modify the canonical profile.
- Session-end detection writes no more than one observation only for a complete high-confidence confusion-to-understanding sequence and never modifies the profile.
- Refinement uses accumulated evidence to propose a complete human-readable profile, enforces 10 rules and 250 words, and writes only after approval.
- The personalized explainer reads only the canonical profile and adapts explanation structure without imitating another model's voice.
- Missing, invalid, noisy, duplicate, or contradictory evidence fails safely without corrupting observations or the profile.
- All synthetic unit, contract, and repository validation tests pass without a network or real transcript data.

## Recommended Implementation Order

1. **Capture Learning Pattern and shared storage contract.** Establish the plugin skeleton, schemas, store helper, and first producer.
2. **Detect Learning Moments.** Add transcript adapters and the second producer against the established observation contract.
3. **Refine Comprehension Profile.** Add the sole profile writer after both observation sources exist.
4. **Personalized Explainer.** Add the runtime consumer after the canonical profile contract and writer are stable.

Each component receives its own implementation plan. Later plans depend on the shared contracts and utilities established by the earlier plans and must not redefine them.
