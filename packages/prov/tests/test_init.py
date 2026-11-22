from prov.core.context import init_project


def test_init_project(tmp_path):
    assert init_project(tmp_path, "cube-grasp") == ["prov.toml"]
    assert 'project = "cube-grasp"' in (tmp_path / "prov.toml").read_text()
    assert init_project(tmp_path, "cube-grasp") == []                         # idempotent, never overwrites
