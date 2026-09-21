from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_tool(path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_validate_config_runs_when_cwd_is_outside_repo(tmp_path: Path):
    result = _run_tool(ROOT / "Tools" / "validate_config.py", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "V1 safety configuration validated" in result.stdout


def test_smoke_test_runs_when_cwd_is_outside_repo(tmp_path: Path):
    result = _run_tool(ROOT / "Tools" / "run_smoke_test.py", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SMOKE TEST OK" in result.stdout
