"""Regression tests for the Git branch shown next to dashboard version."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from git_info import repository_branch


class GitBranchDisplayTests(unittest.TestCase):
    def test_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/feature/remote-hardware-diagnostics\n")
            self.assertEqual(repository_branch(Path(temp)), "feature/remote-hardware-diagnostics")

    def test_main(self):
        with tempfile.TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n")
            self.assertEqual(repository_branch(Path(temp)), "main")

    def test_detached(self):
        with tempfile.TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("a" * 40 + "\n")
            self.assertEqual(repository_branch(Path(temp)), "detached @aaaaaaa")

    def test_missing_git(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(repository_branch(Path(temp)), "Git unbekannt")


if __name__ == "__main__":
    unittest.main()
