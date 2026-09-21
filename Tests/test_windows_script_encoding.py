from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_PS1 = [
    ROOT / "Tools" / "install.ps1",
    ROOT / "Tools" / "install_runtime.ps1",
    ROOT / "Tools" / "deploy_mt5.ps1",
    ROOT / "Tools" / "deploy_atas.ps1",
    ROOT / "Tools" / "start_system.ps1",
    ROOT / "Tools" / "stop_system.ps1",
]


def test_windows_runtime_scripts_are_ascii_safe_for_powershell_51():
    targets = RUNTIME_PS1 + sorted((ROOT / "Start").glob("*.bat"))
    assert targets
    for path in targets:
        data = path.read_bytes()
        try:
            data.decode("ascii")
        except UnicodeDecodeError as exc:
            raise AssertionError(
                f"{path.relative_to(ROOT)} contains non-ASCII source text. "
                "Windows PowerShell 5.1/cmd.exe can misdecode UTF-8 without BOM. "
                "Keep executable launcher source ASCII-only."
            ) from exc
