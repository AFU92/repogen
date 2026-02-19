"""Configuration models and loader for Genrepo.

Defines Pydantic models for parsing and validating the `genrepo.yaml` file
and exposes a `load_config` helper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Iterable, cast

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator
from .constants import (
    CRUD_METHODS,
    ERR_MODEL_NAME,
    ERR_IMPORT_PATH_CLASS,
    ERR_INVALID_METHOD,
    ERR_DUPLICATE_MODELS,
    ERR_CONFIG_NOT_FOUND,
    ERR_MODELS_MISSING,
    ERR_MODELS_NONE,
    ERR_MODELS_INVALID_VALUE,
    ERR_MODELS_EMPTY,
    ERR_INVALID_CONFIGURATION,
)


CrudMethod = Literal[
    "get",
    "get_or_raise",
    "list",
    "find_one",
    "create",
    "update",
    "delete",
    "delete_by_id",
    "exists",
    "count",
    "all",
    "none",
]
OrmType = Literal["sqlmodel", "sqlalchemy"]
GenerationMode = Literal["standalone", "base", "combined"]
CommitStrategy = Literal["commit", "flush", "none"]


# Default CRUD methods for a model (typed for mypy)
DEFAULT_METHODS: tuple[CrudMethod, ...] = (
    "get",
    "list",
    "create",
    "update",
    "delete",
)


class ModelConfig(BaseModel):
    name: str = Field(..., description="PascalCase model name, e.g., User")
    import_path: str = Field(..., description="Import as 'module.path:ClassName'")
    id_field: str = Field(..., description="Primary key field name, e.g., id")
    id_type: str = Field(..., description="Primary key type, e.g., int, str, UUID")
    # Provide a typed default for methods (helps mypy with Literal types)
    methods: list[CrudMethod] = Field(default_factory=lambda: list(DEFAULT_METHODS))
    personalize_methods: list[str] = Field(
        default_factory=list,
        description="Custom repo-only methods to stub (combined mode)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:  # noqa: D401
        """Ensure non-empty PascalCase-ish name."""
        if not v or not v[0].isalpha():
            raise ValueError(ERR_MODEL_NAME)
        return v

    @field_validator("import_path")
    @classmethod
    def validate_import_path(cls, v: str) -> str:  # noqa: D401
        """Ensure the value follows 'module:Class'."""
        # Allow package-only import_path when used as global defaults (name 'All' or '*')
        if ":" not in v:
            # accept when used in a wildcard/default entry
            return v
        mod, cls_name = v.split(":", 1)
        if not mod or not cls_name:
            raise ValueError(ERR_IMPORT_PATH_CLASS)
        return v

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, v: list[CrudMethod]) -> list[CrudMethod]:  # noqa: D401
        """Normalize special sentinels and ensure uniqueness within allowed set."""
        # Cast constants to the Literal union for type-checking
        allowed: list[CrudMethod] = list(cast(Iterable[CrudMethod], CRUD_METHODS))
        if not v:
            return []
        if "none" in v:
            return []
        result: list[CrudMethod] = []
        seen: set[str] = set()
        if "all" in v:
            result.extend(allowed)
            seen.update(allowed)
        for m in v:
            if m in ("all", "none"):
                continue
            if m not in allowed:
                raise ValueError(ERR_INVALID_METHOD.format(method=m))
            if m in seen:
                continue
            result.append(m)
            seen.add(m)
        # Enforce method dependencies used in templates:
        # - get_or_raise and delete_by_id call self.get; ensure 'get' exists.
        if (
            "get_or_raise" in result or "delete_by_id" in result
        ) and "get" not in result:
            result.insert(0, "get")
        return result

    @field_validator("personalize_methods")
    @classmethod
    def validate_personalize_methods(cls, v: list[str]) -> list[str]:  # noqa: D401
        """Ensure unique custom method names (free-form)."""
        out: list[str] = []
        seen: set[str] = set()
        for m in v:
            if m in seen:
                continue
            out.append(m)
            seen.add(m)
        return out


class GenrepoConfig(BaseModel):
    orm: OrmType = Field("sqlmodel")
    async_mode: bool = Field(False, description="Use AsyncSession and async/await")
    output_dir: Path
    models: list[ModelConfig]
    # Model discovery options
    models_dir: Path | None = Field(
        None, description="Directory to discover models when using models=all"
    )
    models_package: str | None = Field(
        None, description="Package path for discovered models (e.g., app.models)"
    )
    discover_all: bool = Field(
        False, description="If true, discover all models in models_dir/models_package"
    )
    commit_strategy: CommitStrategy = Field(
        "none", description="Transaction strategy for write ops (default: none)"
    )
    allow_missing_models: bool = Field(
        False,
        description=(
            "If true, do not fail when an explicit model's import_path cannot be imported."
        ),
    )

    class Generation(BaseModel):
        mode: GenerationMode = Field("standalone")
        base_filename: str = Field("base_repository.py")
        base_class_name: str = Field("BaseRepository")
        overwrite_base: bool = Field(False)
        stub_only: bool = Field(
            False,
            description="Generate stub-only repositories without ORM-specific logic",
        )

    generation: Generation = Field(default_factory=Generation)

    @field_validator("models")
    @classmethod
    def validate_models(cls, v: list[ModelConfig]) -> list[ModelConfig]:  # noqa: D401
        """Ensure unique model names."""
        names = [m.name for m in v]
        if len(names) != len(set(names)):
            raise ValueError(ERR_DUPLICATE_MODELS)
        return v


def load_config(path: Path) -> GenrepoConfig:
    """Load and validate a Genrepo configuration from YAML."""
    if not path.exists():
        raise FileNotFoundError(ERR_CONFIG_NOT_FOUND.format(path=path))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # Determine generation mode early to allow base-only configs without 'models'
    gen = data.get("generation") or {}
    gen_mode = (gen.get("mode") or "standalone").strip().lower()

    # Validate/normalize models field with friendlier messages (except base-only)
    models_field = data.get("models")
    if models_field is None and gen_mode != "base":
        raise ValueError(ERR_MODELS_MISSING)
    if models_field is None and gen_mode == "base":
        # Provide a harmless placeholder so Pydantic validation passes; generator ignores models in base mode
        data["models"] = [
            {
                "name": "All",
                "import_path": "app.models",
                "id_field": "id",
                "id_type": "int",
                "methods": ["none"],
            }
        ]
    # Allow sentinels for discovery or explicit none
    discover_all = False
    if isinstance(models_field, str):
        mval = models_field.strip().lower()
        if mval == "all":
            data = {**data, "models": []}
            discover_all = True
        elif mval == "none":
            raise ValueError(ERR_MODELS_NONE)
        else:
            raise ValueError(ERR_MODELS_INVALID_VALUE)
    elif isinstance(models_field, list) and len(models_field) == 0:
        raise ValueError(ERR_MODELS_EMPTY)
    try:
        cfg = GenrepoConfig.model_validate(data)
    except ValidationError as e:  # pragma: no cover - pass-through representation
        raise ValueError(ERR_INVALID_CONFIGURATION.format(err=e)) from e
    if discover_all:
        cfg.discover_all = True
        # defaults if not provided
        if cfg.models_dir is None and cfg.models_package is None:
            cfg.models_dir = Path("app/models")
            cfg.models_package = "app.models"
    return cfg
