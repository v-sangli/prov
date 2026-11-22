import sys
from pathlib import Path

import pytest

from conftest import git
from prov.cli import main
from prov.artifacts.publish import load, publish
from prov.runs.schema import RunRecord
from prov.storage.store import resolve

SCRIPT = '''"""Write error per episode from an eval result."""
import json
import tempfile
from pathlib import Path
import prov

TITLE = "{title}"
rec = prov.load("res:evals/1")
rows = [json.loads(line) for line in open(prov.path(rec))]
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "errors.txt"
    out.write_text(TITLE + "\\n" + "".join("%d %s\\n" % (r["ep"], r["err"]) for r in rows))
    prov.publish(out, "result")
'''


@pytest.fixture
def analysis_repo(repo, registry, monkeypatch, tmp_path, ctx):
    (repo / "prov.toml").write_text('project = "demo"\n')
    (repo / "analysis").mkdir()
    (repo / "analysis" / "errors.py").write_text(SCRIPT.format(title="errors v1"))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "analysis")
    monkeypatch.chdir(repo)
    res = tmp_path / "evals.jsonl"
    res.write_text("".join(f'{{"ep": {i}, "err": {e}}}\n' for i, e in enumerate([12.0, 9.5, 11.2, 8.1])))
    publish(ctx, res, "result", alias="res:evals/1")
    return repo


def _runs(registry: Path) -> list[RunRecord]:
    return sorted((RunRecord.from_yaml(p) for p in (registry / "records" / "runs").glob("*.yaml")),
                  key=lambda r: r.started)


def _output_bytes(ctx, res_id: str) -> bytes:
    return resolve(ctx, load(ctx, res_id).uri).read_bytes()


def test_rerun_reproduces_file_byte_for_byte(analysis_repo, registry, tmp_path, ctx):
    main(["run", "--kind", "analysis", "--tag", "topic=errors", "--",
          sys.executable, str(analysis_repo / "analysis" / "errors.py")])
    [first] = _runs(registry)

    assert main(["rerun", first.id]) == 0
    second = _runs(registry)[-1]
    assert second.id != first.id and second.tags == {"rerun_of": first.id, "topic": "errors"}
    assert second.code[0].base == first.code[0].snapshot and not second.code[0].dirty
    assert _output_bytes(ctx, second.outputs[0]) == _output_bytes(ctx, first.outputs[0])
    assert git(analysis_repo, "worktree", "list").count("\n") == 0          # worktree cleaned up


def test_rerun_uses_snapshot_not_current_code(analysis_repo, registry, tmp_path, ctx):
    script = analysis_repo / "analysis" / "errors.py"
    script.write_text(SCRIPT.format(title="uncommitted edit"))           # dirty run
    main(["run", "--kind", "analysis", "--", sys.executable, str(script)])
    [first] = _runs(registry)
    assert first.code[0].dirty

    script.write_text(SCRIPT.format(title="later edit"))                 # code moves on
    assert main(["rerun", first.id]) == 0
    second = _runs(registry)[-1]
    assert _output_bytes(ctx, second.outputs[0]) == _output_bytes(ctx, first.outputs[0])
    assert "later edit" in script.read_text()                            # working tree untouched


def test_rerun_unknown(registry, capsys):
    assert main(["rerun", "run_00000000000000000000000000"]) == 2
    assert "no record" in capsys.readouterr().err
