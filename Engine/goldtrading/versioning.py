from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .database import Database


def load_version_manifest(project_root: Path) -> dict:
    path = project_root / "Version" / "version.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Version/version.json must contain a JSON object")
    version = str(data.get("version", "")).strip()
    if not version:
        raise ValueError("Version/version.json is missing version")
    return data


def register_version(db: Database, project_root: Path) -> dict:
    manifest = load_version_manifest(project_root)
    payload = dict(manifest)
    payload["registered_at"] = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO Versions(version,build_date,payload) VALUES(?,?,?)",
        (
            str(manifest["version"]),
            str(manifest.get("build_date", "")),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )
    return payload
