import json

from Engine.goldtrading.database import Database
from Engine.goldtrading.versioning import load_version_manifest, register_version


def test_register_version_persists_manifest(tmp_path):
    version_dir = tmp_path / "Version"
    version_dir.mkdir()
    manifest = {
        "version": "9.9.9-test",
        "build_date": "2026-09-22",
        "database_version": 2,
        "release_state": "test",
    }
    (version_dir / "version.json").write_text(json.dumps(manifest), encoding="utf-8")
    db = Database(tmp_path / "Data" / "test.db")

    saved = register_version(db, tmp_path)

    rows = db.fetchall("SELECT version, build_date, payload FROM Versions")
    assert len(rows) == 1
    assert rows[0]["version"] == "9.9.9-test"
    assert rows[0]["build_date"] == "2026-09-22"
    payload = json.loads(rows[0]["payload"])
    assert payload["database_version"] == 2
    assert "registered_at" in payload
    assert saved["version"] == "9.9.9-test"


def test_load_version_manifest_rejects_missing_version(tmp_path):
    version_dir = tmp_path / "Version"
    version_dir.mkdir()
    (version_dir / "version.json").write_text("{}", encoding="utf-8")
    try:
        load_version_manifest(tmp_path)
    except ValueError as exc:
        assert "missing version" in str(exc)
    else:
        raise AssertionError("missing version should be rejected")
