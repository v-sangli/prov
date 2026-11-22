from prov_skills.cli import install, main


def test_install(tmp_path):
    assert main(["install", str(tmp_path)]) == 0
    for skill in ("plot", "journal"):
        assert (tmp_path / ".claude" / "skills" / skill / "SKILL.md").is_file()
    assert install(tmp_path) == []                                           # idempotent, never overwrites
