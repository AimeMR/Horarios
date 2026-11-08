from pathlib import Path

from horaris_solver.check_bridge import default_challenge_root, run_official_check
from horaris_solver.solver.pipeline import solve_and_export

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_pipeline_writes_csv(tmp_path: Path) -> None:
    out = tmp_path / "proposta.csv"
    result = solve_and_export(paquet=FIXTURE, out_csv=out, max_time_s=60)
    assert result.ok, result.summary
    assert out.exists()
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header == "id_sessio,dia,h_ini,aula"


def test_pipeline_mini_passes_official_check(tmp_path: Path) -> None:
    root = default_challenge_root()
    if not root.is_dir():
        import pytest

        pytest.skip("repte-horaris-escola not present (symlink or copy the challenge pack)")
    out = tmp_path / "proposta.csv"
    result = solve_and_export(paquet=FIXTURE, out_csv=out, max_time_s=60)
    assert result.ok, result.summary
    code, output = run_official_check(
        out,
        challenge_root=root,
        paquet=FIXTURE,
    )
    assert code == 0, output
    assert "VALIDA" in output
