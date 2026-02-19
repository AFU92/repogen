"""Code generator for Genrepo.

Uses Jinja2 templates to generate repository files from a validated
configuration model. Supports modes: standalone (per-model repos), base-only
(only BaseRepository), and combined (BaseRepository + user repos created once).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import importlib

from .config import GenrepoConfig, ModelConfig
from .constants import ERR_MODEL_NOT_IMPORTABLE
from .constants import (
    TPL_BASE_SQLMODEL_SYNC,
    TPL_BASE_SQLMODEL_ASYNC,
    TPL_BASE_SQLALCHEMY_SYNC,
    TPL_BASE_SQLALCHEMY_ASYNC,
    TPL_STANDALONE_SQLMODEL,
    TPL_STANDALONE_SQLALCHEMY,
    TPL_BASE_STUB,
    TPL_STANDALONE_STUB,
    TPL_USER_STUB,
    ORM_SQLMODEL,
    ORM_SQLALCHEMY,
    ERR_UNSUPPORTED_ORM,
)
from .constants import CRUD_METHODS


class TemplateSelector:
    """Select templates based on ORM/async/stub-only settings."""

    @staticmethod
    def standalone_template(cfg: GenrepoConfig) -> str:
        if cfg.generation.stub_only:
            return TPL_STANDALONE_STUB
        if cfg.orm == ORM_SQLMODEL:
            return TPL_STANDALONE_SQLMODEL
        if cfg.orm == ORM_SQLALCHEMY:
            return TPL_STANDALONE_SQLALCHEMY
        raise ValueError(ERR_UNSUPPORTED_ORM.format(orm=cfg.orm))

    @staticmethod
    def base_template(cfg: GenrepoConfig) -> str:
        if cfg.generation.stub_only:
            return TPL_BASE_STUB
        if cfg.orm == ORM_SQLMODEL:
            return TPL_BASE_SQLMODEL_ASYNC if cfg.async_mode else TPL_BASE_SQLMODEL_SYNC
        if cfg.orm == ORM_SQLALCHEMY:
            return (
                TPL_BASE_SQLALCHEMY_ASYNC
                if cfg.async_mode
                else TPL_BASE_SQLALCHEMY_SYNC
            )
        raise ValueError(ERR_UNSUPPORTED_ORM.format(orm=cfg.orm))


class ModelResolver:
    """Resolve effective model list from config, including discovery/wildcard."""

    @staticmethod
    def resolve(cfg: GenrepoConfig, project_root: Path) -> list[ModelConfig]:
        models: list[ModelConfig] = list(cfg.models)
        explicit_by_name: dict[str, ModelConfig] = {}
        wildcard: ModelConfig | None = None
        for m in list(models):
            if m.name.lower() in {"all", "*"}:
                wildcard = m
                models.remove(m)
            else:
                explicit_by_name[m.name] = m
        discover = cfg.discover_all or (wildcard is not None)
        if discover:
            models_dir = cfg.models_dir or (project_root / "app/models")
            pkg = cfg.models_package or (
                wildcard.import_path
                if wildcard and ":" not in wildcard.import_path
                else "app.models"
            )
            base_dir = Path(models_dir)
            default_id_field = wildcard.id_field if wildcard else "id"
            default_id_type = wildcard.id_type if wildcard else "int"
            default_methods = wildcard.methods if wildcard else ["all"]
            default_personalize = (
                wildcard.personalize_methods
                if (wildcard and hasattr(wildcard, "personalize_methods"))
                else []
            )
            for py in sorted(base_dir.glob("*.py")):
                if py.name.startswith("__"):
                    continue
                stem = py.stem
                cls = to_pascal(stem)
                import_path = f"{pkg}.{stem}:{cls}"
                if cls in explicit_by_name:
                    continue
                models.append(
                    ModelConfig(
                        name=cls,
                        import_path=import_path,
                        id_field=default_id_field,
                        id_type=default_id_type,
                        methods=default_methods,
                        personalize_methods=default_personalize,
                    )
                )
        else:
            if not cfg.allow_missing_models:
                for m in models:
                    try:
                        mod_name, cls_name = m.import_path.split(":", 1)
                        mod = importlib.import_module(mod_name)
                        getattr(mod, cls_name)
                    except Exception as e:
                        raise ValueError(
                            ERR_MODEL_NOT_IMPORTABLE.format(import_path=m.import_path)
                        ) from e
        return models


def _classify_file(path: Path, content: str, overwrite: bool) -> "FilePlan":
    if not path.exists():
        return FilePlan(
            path=path,
            exists=False,
            would_write=True,
            overwrite=overwrite,
            reason="create",
        )
    if not overwrite:
        return FilePlan(
            path=path,
            exists=True,
            would_write=False,
            overwrite=False,
            reason="exists-no-overwrite",
        )
    try:
        current = path.read_text(encoding="utf-8")
    except Exception:
        return FilePlan(
            path=path, exists=True, would_write=True, overwrite=True, reason="overwrite"
        )
    if current == content:
        return FilePlan(
            path=path,
            exists=True,
            would_write=False,
            overwrite=True,
            reason="up-to-date",
        )
    return FilePlan(
        path=path, exists=True, would_write=True, overwrite=True, reason="overwrite"
    )


def default_templates_dir() -> Path:
    """Return the path to the internal packaged templates directory."""
    try:
        from importlib.resources import files

        pkg_root = files("genrepo.templates")
        # Coerce to filesystem path string for the Jinja FileSystemLoader
        return Path(str(pkg_root))
    except Exception:
        # Fallback to relative path (editable installs)
        return Path(__file__).parent / "templates"


def to_snake(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def to_pascal(snake: str) -> str:
    parts = [p for p in snake.replace("-", "_").split("_") if p]
    return "".join(p.capitalize() for p in parts)


@dataclass
class GeneratedFile:
    path: Path
    content: str


@dataclass
class FilePlan:
    path: Path
    exists: bool
    would_write: bool
    overwrite: bool
    reason: str | None = None


@dataclass
class PlanReport:
    files: list[FilePlan]

    @property
    def to_write(self) -> list[FilePlan]:
        return [f for f in self.files if f.would_write]

    @property
    def up_to_date(self) -> list[FilePlan]:
        return [
            f
            for f in self.files
            if (not f.would_write and f.exists and f.reason == "up-to-date")
        ]


def _render_repo(
    env: Environment,
    model: ModelConfig,
    *,
    template_name: str,
    commit_strategy: str,
    is_async: bool,
) -> GeneratedFile:
    mod, cls_name = model.import_path.split(":", 1)
    file_name = f"{to_snake(model.name)}_repository.py"
    tpl = env.get_template(template_name)
    # Ensure stable order for methods based on CRUD_METHODS constant
    ordered_methods = [m for m in CRUD_METHODS if m in set(model.methods)]
    content = tpl.render(
        model_name=model.name,
        model_module=mod,
        model_class=cls_name,
        id_field=model.id_field,
        id_type=model.id_type,
        methods=ordered_methods,
        personalize_methods=list(getattr(model, "personalize_methods", [])),
        commit_strategy=commit_strategy,
        is_async=is_async,
    )
    return GeneratedFile(path=Path(file_name), content=content)


def generate_from_config(
    cfg: GenrepoConfig,
    *,
    project_root: Path,
    force: bool = False,
    templates_dir: Path | None = None,
    env: Environment | None = None,
) -> list[Path]:
    """Generate repository files and return the list of written paths.

    Supports modes: standalone, base, combined. In combined mode, the
    BaseRepository may be overwritten based on `overwrite_base`, and user
    repositories are created once and never overwritten.
    """

    def ensure_package(dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    def write(path: Path, content: str, *, overwrite: bool) -> bool:
        """Atomically write content to path.

        Skips if target exists and overwrite is False. Writes to a temporary
        file in the same directory and replaces the target to avoid partial
        writes on failures.
        """
        if path.exists() and not overwrite:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        return True

    # Resolve templates directory
    tpl_dir = Path(templates_dir) if templates_dir else default_templates_dir()
    env = env or Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["snake"] = to_snake
    env.filters["pascal"] = to_pascal

    written: list[Path] = []
    out_dir = (project_root / cfg.output_dir).resolve()
    ensure_package(out_dir)

    mode = cfg.generation.mode
    is_async = cfg.async_mode

    selector = TemplateSelector()

    # Mode: base or combined -> ensure base repository file
    if mode in ("base", "combined"):
        base_module = cfg.generation.base_filename.rsplit(".", 1)[0]
        base_path = out_dir / cfg.generation.base_filename
        tpl = env.get_template(selector.base_template(cfg))
        base_content = tpl.render(
            base_class_name=cfg.generation.base_class_name,
            commit_strategy=cfg.commit_strategy,
        )
        if write(base_path, base_content, overwrite=cfg.generation.overwrite_base):
            written.append(base_path)

    if mode == "base":
        return written

    # Prepare models list (support discovery)
    models: list[ModelConfig] = ModelResolver.resolve(cfg, project_root)

    if mode == "standalone":
        tpl_name = selector.standalone_template(cfg)
        for model in models:
            gen = _render_repo(
                env,
                model,
                template_name=tpl_name,
                commit_strategy=cfg.commit_strategy,
                is_async=is_async,
            )
            target = out_dir / gen.path
            if write(target, gen.content, overwrite=force):
                written.append(target)
        return written

    # Mode: combined -> generate base + user repository stubs (no _generated layer)
    base_module = cfg.generation.base_filename.rsplit(".", 1)[0]
    for model in models:
        file_name = f"{to_snake(model.name)}_repository.py"
        stub_tpl = env.get_template(TPL_USER_STUB)
        stub_content = stub_tpl.render(
            model_name=model.name,
            model_module=model.import_path.split(":", 1)[0],
            model_class=model.import_path.split(":", 1)[1],
            base_module=base_module,
            base_class_name=cfg.generation.base_class_name,
            id_field=model.id_field,
            id_type=model.id_type,
            personalize_methods=list(model.personalize_methods),
            orm=cfg.orm,
            is_async=is_async,
        )
        stub_path = out_dir / file_name
        if write(stub_path, stub_content, overwrite=False):
            written.append(stub_path)

    return written


def plan_from_config(
    cfg: GenrepoConfig,
    *,
    project_root: Path,
    force: bool = False,
    templates_dir: Path | None = None,
    env: Environment | None = None,
) -> PlanReport:
    """Compute a plan of file operations without writing anything.

    Mirrors the logic of generate_from_config to decide which files would be
    written, considering overwrite rules and content equality.
    """

    # Build Jinja environment just like in generate
    tpl_dir = Path(templates_dir) if templates_dir else default_templates_dir()
    env = env or Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    out_dir = (project_root / cfg.output_dir).resolve()

    plans: list[FilePlan] = []
    mode = cfg.generation.mode
    is_async = cfg.async_mode

    selector = TemplateSelector()

    # Base file plan (base/combined)
    if mode in ("base", "combined"):
        base_path = out_dir / cfg.generation.base_filename
        tpl = env.get_template(selector.base_template(cfg))
        base_content = tpl.render(
            base_class_name=cfg.generation.base_class_name,
            commit_strategy=cfg.commit_strategy,
        )
        plans.append(
            _classify_file(
                base_path, base_content, overwrite=cfg.generation.overwrite_base
            )
        )
        if mode == "base":
            return PlanReport(files=plans)

    # Prepare models list (support discovery), copy of generate logic
    models: list[ModelConfig] = ModelResolver.resolve(cfg, project_root)

    # Standalone mode: files can be overwritten via --force
    if mode == "standalone":
        tpl_name = selector.standalone_template(cfg)
        for model in models:
            gen = _render_repo(
                env,
                model,
                template_name=tpl_name,
                commit_strategy=cfg.commit_strategy,
                is_async=is_async,
            )
            target = (project_root / cfg.output_dir).resolve() / gen.path
            plans.append(_classify_file(target, gen.content, overwrite=force))
        return PlanReport(files=plans)

    # Combined mode: base + user stubs created once (no overwrite)
    base_module = cfg.generation.base_filename.rsplit(".", 1)[0]
    stub_tpl = env.get_template(TPL_USER_STUB)
    for model in models:
        file_name = f"{to_snake(model.name)}_repository.py"
        stub_content = stub_tpl.render(
            model_name=model.name,
            model_module=model.import_path.split(":", 1)[0],
            model_class=model.import_path.split(":", 1)[1],
            base_module=base_module,
            base_class_name=cfg.generation.base_class_name,
            id_field=model.id_field,
            id_type=model.id_type,
            personalize_methods=list(model.personalize_methods),
            orm=cfg.orm,
            is_async=is_async,
        )
        stub_path = (project_root / cfg.output_dir).resolve() / file_name
        plans.append(_classify_file(stub_path, stub_content, overwrite=False))

    return PlanReport(files=plans)
