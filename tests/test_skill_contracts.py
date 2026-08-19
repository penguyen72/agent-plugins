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
        self.assertNotIn("git add .", body)
        self.assertIn("Never amend, reset, force, discard work, or bypass hooks", body)
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
        self.assertIn("Never force-push", body)
        self.assertIn("Do not invent tests or results", body)
        self.assertIn("Obtain explicit user approval before every push", body)
        self.assertIn(
            "Never amend, reset, rebase, force-push, discard work, or bypass hooks.",
            body,
        )
        self.assertIn("Never rewrite history, even if separately requested.", body)
