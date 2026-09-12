---
name: capture-learning-pattern
description: Capture one approved learning observation when a technical explanation finally clicks, without updating the canonical comprehension profile.
---

# Capture Learning Pattern

Capture one observation from a demonstrated transition between technical
confusion and understanding. The observation is user-level persistent evidence,
so preview and approval are part of the write boundary.

## Before drafting

1. Locate this installed plugin's root from the loaded skill path and read
   `references/data-contracts.md` completely.
2. Inspect only the relevant visible conversation window. Do not read historical
   observations or unrelated conversation, transcripts, tools, hidden reasoning,
   or repository content.
3. Identify the initial confusion or incorrect mental model, any clarification questions,
   the successful explanation or mental model, observable evidence of understanding,
   and why it worked for this user.

Stop and write nothing unless the conversation contains all three of these: clear
confusion, a successful explanation or corrected mental model, and confirmed
understanding. Explain which evidence is absent without inventing it.

## Draft one observation

Build exactly one schema-version-1 observation using every field in the shared
contract:

- Set `source` to `manual`, identify `harness` as `codex`, `claude`, or `other`,
  and use the current UTC time for `captured_at`.
- Draft a concise `topic`, `confusion`, the observed `clarification_questions`,
  `successful_explanation`, `why_it_worked`, one `candidate_rule`, and only the
  `signals` supported by the visible exchange.
- Hash the harness namespace plus raw session identifier through
  `hash_session_key(harness, session_id)`. Never place the raw identifier in the
  observation or use it as a path.
- Derive `id` with
  `make_observation_id(session_key, confusion, successful_explanation, candidate_rule)`.
- Retain only minimal role-labeled `evidence` excerpts needed to show the
  transition. Remove unrelated or sensitive content. Never retain a full
  transcript, tool data, hidden reasoning, or repository content.
- Pass every evidence excerpt through `scrub_excerpt` before previewing it. Then
  run `validate_observation` against the complete in-memory draft. Stop without
  a write and report the validation errors if any remain. The validated,
  scrubbed result is the canonical observation.

The candidate rule stays inside the observation. Do not summarize historical
observations or promote it directly into a profile rule.

## Preview and approve

Resolve the store path once with `resolve_store_root`. Show the resolved path and
the canonical observation as a complete JSON object. Label it as the exact observation
to persist, then ask for explicit approval to append that exact preview.

Any correction invalidates prior approval. Apply the correction, recompute the
stable ID when its inputs changed, scrub and validate again, show a new exact
preview and store path, and obtain explicit approval again. Do not create the
store or any temporary input file before approval.

## Append the approved observation

After approval only:

1. Serialize the approved canonical observation, unchanged, to one securely
   created temporary UTF-8 JSON file.
2. Run the plugin-root script through the interpreter with the same resolved store path:
   `python3 "$PLUGIN_ROOT/scripts/comprehension_store.py" append-observation --input "$TEMP_PATH" --store-root "$RESOLVED_STORE_ROOT"`.
3. Remove only that temporary file, including after an append failure. Never
   remove or rewrite store content.
4. Report whether the observation was appended, already existed, or failed. For
   a failure, include the concise actionable error without observation content
   or credentials.

This skill **must not read or modify `profile.md`**. It must not create the
profile, even when no profile exists; only the future
`refine-comprehension-profile` component may write it.
