"""Repo hygiene: skills are well-formed and only reference real CLI commands."""

import re
from pathlib import Path

from growwbot.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())


def _commands():
    sub = next(a for a in build_parser()._actions if a.dest == "cmd")
    return set(sub.choices)


def test_every_skill_has_frontmatter():
    assert len(SKILLS) >= 18
    for d in SKILLS:
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"---\nname: (\S+)\ndescription: >-\n(.+?)\n---\n", text, re.S)
        assert m, d.name
        assert m.group(1) == d.name
        assert 50 < len(" ".join(m.group(2).split())) < 1024


def test_skills_only_use_real_commands():
    cmds = _commands()
    for d in SKILLS:
        for used in re.findall(r"python -m growwbot ([a-z-]+)", (d / "SKILL.md").read_text(encoding="utf-8")):
            assert used in cmds, f"{d.name} uses unknown command {used}"


def test_docs_only_use_real_commands():
    cmds = _commands()
    for f in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
        for used in re.findall(r"python -m growwbot ([a-z-]+)", f.read_text(encoding="utf-8")):
            assert used in cmds, f"{f.name} uses unknown command {used}"


def test_secrets_are_ignored():
    ignored = (ROOT / ".gitignore").read_text()
    for name in (".env", "config.toml", "state/"):
        assert name in ignored.splitlines()
    assert "GROWW_ENABLE_LIVE=\n" in (ROOT / ".env.example").read_text()
    assert 'mode = "paper"' in (ROOT / "config.example.toml").read_text()
