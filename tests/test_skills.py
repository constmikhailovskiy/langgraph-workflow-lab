from __future__ import annotations

from unittest.mock import patch

import pytest

from lab.core import skills


def _write_skill(root, name: str, description: str = "A skill.", body: str = "Body text.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_load_skill_reads_directory_based_skill_and_strips_frontmatter(tmp_path) -> None:
    _write_skill(tmp_path, "my-skill", body="Do the thing.")
    with patch.object(skills, "SKILLS_DIR", tmp_path):
        assert skills.load_skill("my-skill") == "Do the thing."


def test_load_skill_raises_when_skill_missing(tmp_path) -> None:
    with patch.object(skills, "SKILLS_DIR", tmp_path):
        with pytest.raises(skills.SkillNotFound):
            skills.load_skill("does-not-exist")


def test_load_skill_ignores_a_stray_flat_markdown_file(tmp_path) -> None:
    """A bare ``<name>.md`` (the old layout) is not a valid Agent Skill anymore."""
    (tmp_path / "legacy-skill.md").write_text("---\nname: legacy-skill\n---\n\nBody.\n")
    with patch.object(skills, "SKILLS_DIR", tmp_path):
        with pytest.raises(skills.SkillNotFound):
            skills.load_skill("legacy-skill")


def test_available_skills_lists_directories_with_skill_md(tmp_path) -> None:
    _write_skill(tmp_path, "skill-a")
    _write_skill(tmp_path, "skill-b")
    (tmp_path / "not-a-skill").mkdir()  # no SKILL.md inside, must be ignored
    with patch.object(skills, "SKILLS_DIR", tmp_path):
        assert skills.available_skills() == ["skill-a", "skill-b"]


def test_with_skills_is_a_noop_without_names() -> None:
    assert skills.with_skills("base prompt", None) == "base prompt"
    assert skills.with_skills("base prompt", []) == "base prompt"


def test_with_skills_appends_skills_section(tmp_path) -> None:
    _write_skill(tmp_path, "my-skill", body="Do the thing.")
    with patch.object(skills, "SKILLS_DIR", tmp_path):
        result = skills.with_skills("base prompt", ["my-skill"])
    assert result == "base prompt\n\n# Skills\n\nDo the thing."


def test_import_skills_from_dir_copies_whole_skill_directory(tmp_path) -> None:
    """Bundled scripts/references/assets must travel with the skill, not just SKILL.md."""
    source = tmp_path / "source-repo"
    dest = tmp_path / "lab-skills"
    _write_skill(source, "bundled-skill", body="Use the script.")
    (source / "bundled-skill" / "scripts").mkdir()
    (source / "bundled-skill" / "scripts" / "run.py").write_text("print('hi')\n")

    with patch.object(skills, "SKILLS_DIR", dest):
        imported = skills.import_skills_from_dir(source)

    assert imported == ["bundled-skill"]
    assert (dest / "bundled-skill" / "SKILL.md").is_file()
    assert (dest / "bundled-skill" / "scripts" / "run.py").is_file()


def test_import_skills_from_dir_can_filter_by_name(tmp_path) -> None:
    source = tmp_path / "source-repo"
    dest = tmp_path / "lab-skills"
    _write_skill(source, "wanted-skill")
    _write_skill(source, "unwanted-skill")

    with patch.object(skills, "SKILLS_DIR", dest):
        imported = skills.import_skills_from_dir(source, names=["wanted-skill"])

    assert imported == ["wanted-skill"]
    assert not (dest / "unwanted-skill").exists()


def test_import_skills_from_dir_supports_a_single_skill_at_the_source_root(tmp_path) -> None:
    """A source dir whose SKILL.md sits at its own root (not nested) is one skill."""
    source = tmp_path / "single-skill-repo"
    dest = tmp_path / "lab-skills"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: single-skill-repo\ndescription: A skill.\n---\n\nBody.\n"
    )

    with patch.object(skills, "SKILLS_DIR", dest):
        imported = skills.import_skills_from_dir(source)

    assert imported == ["single-skill-repo"]
    assert (dest / "single-skill-repo" / "SKILL.md").is_file()
