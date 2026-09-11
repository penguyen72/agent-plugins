# Comprehension Profile Data Contracts

These versioned contracts are shared by every Comprehension Profile producer and
consumer. Version 1 rejects unknown fields so schema drift remains visible.

## Shared user store

Resolve the store root in this order:

1. The non-empty value of `COMPREHENSION_PROFILE_HOME`.
2. `~/.comprehension-profile/`.

The store contains:

```text
~/.comprehension-profile/
├── observations.jsonl
└── profile.md
```

`observations.jsonl` is UTF-8 and append-only. Each newline-terminated line is
one complete, compact JSON object. Writers use user-only directory and file
permissions where the operating system supports them. A duplicate observation
ID is a no-op; existing history is never rewritten to remove duplicates or
malformed lines.

`profile.md` may be absent until an approved refinement. Writing or replacing
`profile.md` is reserved exclusively for `refine-comprehension-profile`.
Capture and automatic detection must never create, modify, or replace it.

## Learning observation, schema version 1

The exact object shape is:

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

Field rules:

- `schema_version` is the integer `1`.
- `id` is a stable SHA-256-based identifier represented by exactly 64 lowercase
  hexadecimal characters. Writers use it to make duplicate appends no-ops.
- `captured_at` is an RFC 3339 UTC timestamp ending in `Z`.
- `source` is `manual` or `automatic`.
- `harness` is `codex`, `claude`, or `other`.
- `session_key` is a SHA-256 hash of the harness namespace and raw session
  identifier. The raw session identifier is never retained.
- `topic` is non-empty and contains at most 120 characters.
- `confusion`, `successful_explanation`, and `why_it_worked` are non-empty and
  contain at most 500 characters each.
- `candidate_rule` is non-empty and contains at most 300 characters.
- `clarification_questions` contains zero to five strings, each at most 280
  characters.
- `signals` contains unique values selected from `explicit_confusion`,
  `repeated_clarification`, `user_restatement`, `assistant_confirmation`, and
  `explicit_understanding`.
- An automatic observation must contain `explicit_confusion`,
  `user_restatement`, and `assistant_confirmation` in `signals`.
- `evidence` contains one to six objects. Each object has exactly `role` and
  `excerpt`; `role` is `user` or `assistant`, and `excerpt` is non-empty and at
  most 280 characters.
- No other top-level or evidence fields are allowed in version 1.
- Readers report and skip unsupported schema versions instead of guessing.

Interpretive fields describe comprehension structure, not surface writing style,
personality, knowledge level, or factual competence. Evidence is scrubbed for
obvious credentials before it is truncated and persisted. Core interpretive
fields are never silently truncated.

Do not persist raw session identifiers, full transcripts, tool calls, tool
results, hidden reasoning, repository content, or unrelated conversation
segments. Retain only the minimum role-labeled, user-visible evidence needed to
support the observation. Stored data remains local and is never transmitted by
the plugin.

## Comprehension profile, schema version 1

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

The Markdown body is authoritative. It contains exactly one
`# Comprehension Profile` heading followed only by bullet rules. It contains at
most 10 rules and at most 250 words, counting the heading and rules but not the
frontmatter. Each rule is a concise imperative preference another model can
apply without historical evidence. `observation_count` is the number of distinct
valid observations considered during the latest approved refinement, not the
number of rules.

Refinement always proposes and validates a complete replacement, then writes it
atomically only after explicit approval. It never appends a rule directly. If a
proposal exceeds either budget, refinement must consolidate, replace, or reject
information before presenting it. No other component may write the profile.
