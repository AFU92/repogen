from __future__ import annotations

from pathlib import Path
import os
import yaml

from genrepo.config import load_config
from genrepo.generator import generate_from_config


def _golden(path: str) -> Path:
    return Path(__file__).parent / "golden" / path


def _write_cfg(tmp: Path, data: dict) -> tuple[Path, Path]:
    out_dir = tmp / "out" / "repositories"
    cfg = {
        "output_dir": out_dir.as_posix(),
        **data,
    }
    cfg_path = tmp / "cfg.yaml"
    cfg_path.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg_path, out_dir


def _normalize(code: str) -> str:
    """Normalize without destroying Python structure.

    - Trim trailing whitespace on each line
    - Drop leading/trailing blank lines
    - Preserve indentation and in-line spacing
    """
    raw_lines = code.splitlines()
    lines = [ln.rstrip() for ln in raw_lines]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def assert_snapshot(got: str, golden_filename: str) -> None:
    golden_path = _golden(golden_filename)
    got_norm = _normalize(got)
    if os.getenv("REGEN_GOLDEN") == "1":
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(got_norm + "\n", encoding="utf-8")
        return
    if not golden_path.exists():
        raise AssertionError(
            f"Snapshot {golden_filename} is missing. Set REGEN_GOLDEN=1 to create it."
        )
    want_norm = _normalize(golden_path.read_text(encoding="utf-8"))
    assert got_norm == want_norm


def test_snapshot_base_sqlmodel_sync(tmp_path: Path) -> None:
    cfg_path, out_dir = _write_cfg(
        tmp_path,
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "generation": {"mode": "base"},
            "commit_strategy": "commit",
        },
    )
    cfg = load_config(cfg_path)
    repo_root = Path(__file__).resolve().parents[1]
    generate_from_config(cfg, project_root=repo_root, force=True)
    got = (out_dir / "base_repository.py").read_text(encoding="utf-8")
    assert_snapshot(got, "base_repository_sqlmodel_sync.py")


def test_snapshot_standalone_sqlmodel_sync_all(tmp_path: Path) -> None:
    cfg_path, out_dir = _write_cfg(
        tmp_path,
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "generation": {"mode": "standalone"},
            "commit_strategy": "commit",
            "allow_missing_models": True,
            "models": [
                {
                    "name": "User",
                    "import_path": "app.models.user:User",
                    "id_field": "id",
                    "id_type": "int",
                    "methods": ["all"],
                }
            ],
        },
    )
    cfg = load_config(cfg_path)
    repo_root = Path(__file__).resolve().parents[1]
    generate_from_config(cfg, project_root=repo_root, force=True)
    got = (out_dir / "user_repository.py").read_text(encoding="utf-8")
    assert_snapshot(got, "user_repository_sqlmodel_sync.py")
