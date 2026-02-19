from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from genrepo.config import load_config
from genrepo.generator import generate_from_config


DEFAULT_MODELS = [
    {
        "name": "User",
        "import_path": "examples.ex3_single.models.user:User",
        "id_field": "id",
        "id_type": "int",
        "methods": ["all"],
    }
]


def _write_cfg_dict(tmp: Path, config_dict: dict, out_subdir: str) -> tuple[Path, Path]:
    """Write a YAML config from a Python dict and return (cfg_path, out_dir)."""
    cfg_path = tmp / f"{out_subdir}_cfg.yaml"
    out_base = tmp / out_subdir
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    out_base.mkdir(parents=True, exist_ok=True)
    out_dir = out_base / "repositories"
    # Inject output dir into the config
    cfg = dict(config_dict)
    cfg["output_dir"] = out_dir.as_posix()
    cfg_path.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg_path, out_dir


# Common snippet sets to avoid repetition in expectations
CLASS_BASE_REPO = "class BaseRepository"
CLASS_USER_REPO = "class UserRepository"

CRUD_SYNC = [
    "def get(",
    "def get_or_raise(",
    "def list(",
    "def find_one(",
    "def create(",
    "def update(",
    "def delete(",
    "def delete_by_id(",
    "def exists(",
    "def count(",
]
CRUD_ASYNC = [s.replace("def ", "async def ") for s in CRUD_SYNC]

IMPORT_SQLMODEL_SYNC = "from sqlmodel import Session"
IMPORT_SQLMODEL_ASYNC = (
    "from sqlmodel.ext.asyncio.session import AsyncSession as Session"
)
IMPORT_SQLA_SYNC = "from sqlalchemy.orm import Session"
IMPORT_SQLA_ASYNC = "from sqlalchemy.ext.asyncio import AsyncSession as Session"


CASES: list[tuple[str, dict, list[str], list[str]]] = [
    (
        "base_sqlmodel_sync",
        {"orm": "sqlmodel", "async_mode": False, "generation": {"mode": "base"}},
        ["base_repository.py"],
        ["class BaseRepository", "def get(self, session: Session"],
    ),
    (
        "base_sqlmodel_async",
        {"orm": "sqlmodel", "async_mode": True, "generation": {"mode": "base"}},
        ["base_repository.py"],
        ["class BaseRepository", "async def get(self, session: AsyncSession"],
    ),
    (
        "base_sqlalchemy_sync",
        {"orm": "sqlalchemy", "async_mode": False, "generation": {"mode": "base"}},
        ["base_repository.py"],
        ["class BaseRepository", "from sqlalchemy.orm import Session"],
    ),
    (
        "base_sqlalchemy_async",
        {"orm": "sqlalchemy", "async_mode": True, "generation": {"mode": "base"}},
        ["base_repository.py"],
        ["class BaseRepository", "from sqlalchemy.ext.asyncio import AsyncSession"],
    ),
    (
        "standalone_sqlmodel",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "generation": {"mode": "standalone"},
            "allow_missing_models": True,
            "models": DEFAULT_MODELS,
        },
        ["user_repository.py"],
        [CLASS_USER_REPO] + CRUD_SYNC + [IMPORT_SQLMODEL_SYNC],
    ),
    (
        "standalone_sqlalchemy",
        {
            "orm": "sqlalchemy",
            "async_mode": False,
            "generation": {"mode": "standalone"},
            "allow_missing_models": True,
            "models": [
                {
                    "name": "User",
                    "import_path": "examples.ex5_three_explicit.models.user:User",
                    "id_field": "id",
                    "id_type": "int",
                    "methods": ["all"],
                }
            ],
        },
        ["user_repository.py"],
        [CLASS_USER_REPO] + CRUD_SYNC + [IMPORT_SQLA_SYNC],
    ),
    (
        "standalone_sqlmodel_async",
        {
            "orm": "sqlmodel",
            "async_mode": True,
            "generation": {"mode": "standalone"},
            "allow_missing_models": True,
            "models": DEFAULT_MODELS,
        },
        ["user_repository.py"],
        [CLASS_USER_REPO] + CRUD_ASYNC + [IMPORT_SQLMODEL_ASYNC],
    ),
    (
        "standalone_sqlalchemy_async",
        {
            "orm": "sqlalchemy",
            "async_mode": True,
            "generation": {"mode": "standalone"},
            "allow_missing_models": True,
            "models": [
                {
                    "name": "User",
                    "import_path": "examples.ex5_three_explicit.models.user:User",
                    "id_field": "id",
                    "id_type": "int",
                    "methods": ["all"],
                }
            ],
        },
        ["user_repository.py"],
        [CLASS_USER_REPO] + CRUD_ASYNC + [IMPORT_SQLA_ASYNC],
    ),
    (
        "combined_user_stub",
        {
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
                    "personalize_methods": ["custom_thing"],
                }
            ],
        },
        ["base_repository.py", "user_repository.py"],
        [
            "class BaseRepository",
            "class UserRepository(BaseRepository[User])",
            "def custom_thing(",
        ],
    ),
    (
        "stub_only_base",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "generation": {"mode": "base", "stub_only": True},
        },
        ["base_repository.py"],
        ["class BaseRepository", "TODO: implement get by primary key."],
    ),
    (
        "stub_only_standalone",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "generation": {"mode": "standalone", "stub_only": True},
            "allow_missing_models": True,
            "models": DEFAULT_MODELS,
        },
        ["user_repository.py"],
        ["class UserRepository", "TODO: implement get by primary key."],
    ),
    # commit_strategy matrix (sqlmodel base sync/async)
    (
        "base_sqlmodel_sync_commit",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "commit_strategy": "commit",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["session.commit()", "def create(", "def update(", "def delete("],
    ),
    (
        "base_sqlmodel_sync_flush",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "commit_strategy": "flush",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["session.flush()", "def create(", "def update(", "def delete("],
    ),
    (
        "base_sqlmodel_sync_none",
        {
            "orm": "sqlmodel",
            "async_mode": False,
            "commit_strategy": "none",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["def create(", "def update(", "def delete("],
    ),
    (
        "base_sqlmodel_async_commit",
        {
            "orm": "sqlmodel",
            "async_mode": True,
            "commit_strategy": "commit",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["await session.commit()", "async def create(", "async def delete("],
    ),
    (
        "base_sqlmodel_async_flush",
        {
            "orm": "sqlmodel",
            "async_mode": True,
            "commit_strategy": "flush",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["await session.flush()", "async def create(", "async def delete("],
    ),
    (
        "base_sqlmodel_async_none",
        {
            "orm": "sqlmodel",
            "async_mode": True,
            "commit_strategy": "none",
            "generation": {"mode": "base"},
        },
        ["base_repository.py"],
        ["async def create(", "async def update(", "async def delete("],
    ),
]


@pytest.mark.parametrize(
    "name,config_patch,expected_files,expected_snippets",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_templates_cover_all_variants(
    name: str,
    config_patch: dict,
    expected_files: list[str],
    expected_snippets: list[str],
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg_path, out_dir = _write_cfg_dict(tmp_path / name, config_patch, name)
    cfg = load_config(cfg_path)
    written = generate_from_config(cfg, project_root=repo_root, force=True)

    for fname in expected_files:
        fpath = out_dir / fname
        assert fpath in written or fpath.exists(), (
            f"expected file not written: {fpath} (case={name})"
        )

    agg_content = "\n".join(
        (out_dir / f).read_text(encoding="utf-8") for f in expected_files
    )
    for s in expected_snippets:
        assert s in agg_content, (
            f"missing snippet in aggregated output: {s} (case={name})"
        )
