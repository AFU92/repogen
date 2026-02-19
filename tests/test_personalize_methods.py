from __future__ import annotations

from pathlib import Path
import yaml

from genrepo.config import load_config
from genrepo.generator import generate_from_config


def _write_cfg(tmp: Path, data: dict, out_subdir: str) -> tuple[Path, Path]:
    out_base = tmp / out_subdir
    out_dir = out_base / "repositories"
    cfg = {"output_dir": out_dir.as_posix(), **data}
    cfg_path = tmp / f"{out_subdir}.yaml"
    cfg_path.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg_path, out_dir


def test_personalize_methods_combined_generates_todo_and_pass(tmp_path: Path) -> None:
    # Combined mode should create user repo with custom method stubs (TODO + pass)
    cfg_dict = {
        "orm": "sqlmodel",
        "async_mode": False,
        "generation": {"mode": "combined"},
        "allow_missing_models": True,
        "models": [
            {
                "name": "User",
                "import_path": "examples.ex3_single.models.user:User",
                "id_field": "id",
                "id_type": "int",
                "personalize_methods": ["calculate_something"],
            }
        ],
    }
    cfg_path, out_dir = _write_cfg(tmp_path, cfg_dict, "combined_personalize")
    cfg = load_config(cfg_path)
    repo_root = Path(__file__).resolve().parents[1]
    generate_from_config(cfg, project_root=repo_root, force=True)

    user_repo = out_dir / "user_repository.py"
    content = user_repo.read_text(encoding="utf-8")
    assert "def calculate_something(" in content
    assert "TODO: implement custom method 'calculate_something'." in content
    assert "pass" in content


def test_personalize_methods_stub_only_generates_todo_and_pass(tmp_path: Path) -> None:
    # Stub-only standalone should also create custom stub methods (TODO + pass)
    cfg_dict = {
        "orm": "sqlmodel",
        "async_mode": False,
        "generation": {"mode": "standalone", "stub_only": True},
        "allow_missing_models": True,
        "models": [
            {
                "name": "User",
                "import_path": "examples.ex3_single.models.user:User",
                "id_field": "id",
                "id_type": "int",
                "methods": ["none"],
                "personalize_methods": ["custom_thing"],
            }
        ],
    }
    cfg_path, out_dir = _write_cfg(tmp_path, cfg_dict, "stub_only_personalize")
    cfg = load_config(cfg_path)
    repo_root = Path(__file__).resolve().parents[1]
    generate_from_config(cfg, project_root=repo_root, force=True)

    user_repo = out_dir / "user_repository.py"
    content = user_repo.read_text(encoding="utf-8")
    assert "def custom_thing(" in content
    assert "TODO: implement custom method 'custom_thing'." in content
    assert "pass" in content
