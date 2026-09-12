import unittest
from pathlib import Path


def load_skill(path: Path) -> tuple[dict[str, str], str]:
    content = path.read_text(encoding="utf-8")
    _, frontmatter_text, body = content.split("---", 2)
    frontmatter = {}
    for line in frontmatter_text.strip().splitlines():
        key, value = line.split(":", 1)
        frontmatter[key] = value.strip()
    return frontmatter, body


class CreateCommitSkillContractTests(unittest.TestCase):
    def test_create_commit_skill_contains_required_commit_workflow(self):
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "plugins/git-craft/skills/create-commit/SKILL.md"
        )

        frontmatter, body = load_skill(skill_path)

        self.assertEqual(frontmatter["name"], "create-commit")
        self.assertIn("commit", frontmatter["description"].lower())
        self.assertIn("git status --short", body)
        self.assertIn("git diff --cached", body)
        self.assertIn("explicit paths", body)
        self.assertIn("approval", body.lower())
        self.assertIn("BREAKING CHANGE:", body)
        self.assertIn("72", body)
        self.assertIn("Choose the narrowest accurate type.", body)
        self.assertIn("Do not use emojis or vague filler", body)
        self.assertIn("commit footer or pull request body rather than the title", body)
        self.assertNotIn("git add .", body)
        self.assertIn(
            "Never amend, reset, rebase, force or force-push, discard work, rewrite history, "
            "or bypass hooks—even if separately requested.",
            body,
        )
        self.assertIn("every path already in the index", body)
        self.assertIn("re-check the cached diff and file set immediately before commit", body)
        self.assertNotIn("unless separately requested", body)


class CreatePullRequestSkillContractTests(unittest.TestCase):
    def test_create_pr_skill_contains_required_pull_request_workflow(self):
        skill_path = (
            Path(__file__).resolve().parents[1]
            / "plugins/git-craft/skills/create-pr/SKILL.md"
        )

        frontmatter, body = load_skill(skill_path)

        self.assertEqual(frontmatter["name"], "create-pr")
        self.assertIn("pull request", frontmatter["description"].lower())
        self.assertIn("gh auth status", body)
        self.assertIn("## Summary", body)
        self.assertIn("## Testing", body)
        self.assertIn("## Related issues", body)
        self.assertIn("gh pr create", body)
        self.assertIn("approval", body.lower())
        self.assertIn("72", body)
        self.assertIn("Choose the narrowest accurate type.", body)
        self.assertIn("Do not use emojis or vague filler", body)
        self.assertIn("commit footer or pull request body rather than the title", body)
        self.assertIn("Never force-push", body)
        self.assertIn("Do not invent tests or results", body)
        self.assertIn("Obtain explicit user approval before every push", body)
        self.assertIn(
            "Never amend, reset, rebase, force-push, discard work, or bypass hooks.",
            body,
        )
        self.assertIn("Never rewrite history, even if separately requested.", body)


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
            "confusion",
            "clarification questions",
            "successful explanation",
            "why it worked",
            "candidate_rule",
            "evidence",
        ):
            self.assertIn(phrase, self.body.lower())

    def test_skill_previews_and_requires_approval_before_append(self):
        self.assertIn("exact observation", self.body.lower())
        self.assertIn("explicit approval", self.body.lower())
        self.assertIn("append-observation", self.body)

    def test_skill_canonicalizes_preview_and_reuses_the_approved_path(self):
        self.assertIn("scrub_excerpt", self.body)
        self.assertIn("validate_observation", self.body)
        self.assertIn("canonical observation", self.body.lower())
        self.assertIn("same resolved store path", self.body.lower())
        self.assertIn("python3", self.body)
        self.assertIn("--store-root", self.body)

    def test_skill_never_reads_or_writes_profile(self):
        self.assertIn("must not read or modify `profile.md`", self.body.lower())
        self.assertNotIn("write-profile", self.body)

    def test_skill_uses_shared_contract(self):
        self.assertIn("references/data-contracts.md", self.body)
        self.assertIn("one observation", self.body.lower())
