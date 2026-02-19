from __future__ import annotations

from pathlib import Path
import tempfile

import yaml

from genrepo.config import load_config
from genrepo.generator import generate_from_config


def _write_cfg(tmp: Path, cfg: dict) -> tuple[Path, Path]:
    out_dir = tmp / "repositories"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = tmp / "genrepo.yaml"
    cfg2 = dict(cfg)
    cfg2["output_dir"] = out_dir.as_posix()

    cfg_path.write_text(yaml.safe_dump(cfg2, sort_keys=False), encoding="utf-8")
    return cfg_path, out_dir


def _write_golden(name: str, content: str) -> None:
    golden_dir = Path(__file__).resolve().parents[1] / "tests" / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    path = golden_dir / name
    # Normalize final newline
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # 1) base sqlmodel sync (default commit_strategy)
        cfg_path, out_dir = _write_cfg(
            tmp / "base_sqlmodel_sync",
            {
                "orm": "sqlmodel",
                "async_mode": False,
                "generation": {"mode": "base"},
            },
        )
        cfg = load_config(cfg_path)
        generate_from_config(cfg, project_root=repo_root, force=True)
        _write_golden(
            "base_repository_sqlmodel_sync.py",
            (out_dir / "base_repository.py").read_text(encoding="utf-8"),
        )

        # 2) standalone sqlmodel sync all (allow_missing_models)
        cfg_path, out_dir = _write_cfg(
            tmp / "standalone_sqlmodel_sync_all",
            {
                "orm": "sqlmodel",
                "async_mode": False,
                "generation": {"mode": "standalone"},
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
        generate_from_config(cfg, project_root=repo_root, force=True)
        _write_golden(
            "user_repository_sqlmodel_sync.py",
            (out_dir / "user_repository.py").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    main()
