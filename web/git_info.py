"""Read Git branch for the dashboard without requiring the git executable.

The value is informational only. No repository mutation or user-controlled
commands are performed. On a detached HEAD display a short commit ID.
"""
from pathlib import Path


def repository_branch(root: Path) -> str:
    git = Path(root) / ".git"
    try:
        if git.is_file():
            # Git worktree checkout stores the gitdir in a small text file.
            entry = git.read_text(encoding="utf-8").strip()
            if not entry.startswith("gitdir: "):
                return "Git unbekannt"
            location = Path(entry[8:])
            git = location if location.is_absolute() else git.parent / location
        head = (git / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref: refs/heads/"):
            branch = head[len("ref: refs/heads/"):]
            return branch if branch and "\n" not in branch else "Git unbekannt"
        if len(head) == 40 and all(c in "0123456789abcdefABCDEF" for c in head):
            return "detached @" + head[:7]
    except (OSError, UnicodeError):
        pass
    return "Git unbekannt"
