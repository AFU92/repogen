"""Genrepo CLI application.

Defines the Typer application with a root callback and commands:
- healthcheck: environment sanity check
- init-config: write sample genrepo.yaml
- generate: read genrepo.yaml and generate repositories
- init-templates: copy packaged templates for local overrides

Typed functions and module-level objects align with the repo's strong typing.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from typing import Any, Annotated

from pathlib import Path
from importlib.resources import files as ir_files

from genrepo.config import load_config
from genrepo.generator import generate_from_config, plan_from_config
from genrepo.constants import (
    MSG_HEALTH_OK,
    MSG_HEALTH_ERR,
    MSG_CONFIG_CREATED,
    MSG_CONFIG_EXISTS,
    PANEL_GENERATED,
    LABEL_BASE,
    LABEL_REPOS,
    SAMPLE_PACKAGE,
    SAMPLE_YAML_FILENAME,
    MSG_NO_FILES,
    MSG_NO_FILES_HINT,
)

app: typer.Typer = typer.Typer(no_args_is_help=True)
console: Console = Console()
console_err: Console = Console(stderr=True)


@app.callback()
def main_callback() -> None:
    """Genrepo CLI.

    Root command callback used to define the main application. It does not
    print by default; it only establishes the CLI root and its description.
    """
    pass


@app.command("healthcheck")
def healthcheck(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show environment details")
    ] = False,
) -> None:
    """Report CLI readiness with optional environment details."""
    try:
        import sys
        from jinja2 import __version__ as jinja_ver
        from pydantic import __version__ as pydantic_ver
        from typer import __version__ as typer_ver

        if verbose:
            console.print(f"python: {sys.version.split()[0]}")
            console.print(
                f"jinja2: {jinja_ver} | pydantic: {pydantic_ver} | typer: {typer_ver}"
            )
        console.print(f"[green]{MSG_HEALTH_OK}[/green]")
    except Exception as e:
        console.print(f"[red]{MSG_HEALTH_ERR.format(err=e)}[/red]")
        raise typer.Exit(code=1)


def _write_sample_yaml(
    path: Path, *, force: bool, quiet_if_exists: bool = False
) -> None:
    if path.exists() and not force:
        if not quiet_if_exists:
            console.print(f"[yellow]{MSG_CONFIG_EXISTS.format(path=path)}[/yellow]")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sample = (ir_files(SAMPLE_PACKAGE) / SAMPLE_YAML_FILENAME).read_text(
            encoding="utf-8"
        )
    except Exception:
        sample = "orm: sqlmodel\nasync_mode: false\ncommit_strategy: none\n\noutput_dir: app/repositories\n\ngeneration:\n  mode: combined\n  base_filename: base_repository.py\n  base_class_name: BaseRepository\n\nmodels:\n  - name: All\n    import_path: app.models\n    id_field: id\n    id_type: int\n    methods: [none]\n    personalize_methods: [calculate_something]\n"
    path.write_text(sample, encoding="utf-8")
    console.print(
        Panel.fit(f"[bold green]{MSG_CONFIG_CREATED.format(path=path)}[/bold green]")
    )


@app.command("init-config")
def init_config(
    path: Annotated[
        Path, typer.Option("--path", "-p", help="Where to write the config file.")
    ] = Path("genrepo.yaml"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing files.")
    ] = False,
) -> None:
    """Create a starter genrepo.yaml (combined mode)."""
    # Print a friendly message if the file already exists (no-op without --force)
    _write_sample_yaml(path, force=force, quiet_if_exists=False)


@app.command("generate")
def generate(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to genrepo.yaml")
    ] = Path("genrepo.yaml"),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan generation without writing files.")
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="Exit with non-zero if changes would be made."),
    ] = False,
    format: Annotated[
        str, typer.Option("--format", help="Output format for plan (text|json)")
    ] = "text",
    stub_only: Annotated[
        bool,
        typer.Option(
            "--stub-only",
            help="Generate stub-only repositories ignoring ORM/async details.",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing generated files.")
    ] = False,
    templates_dir: Annotated[
        Path | None,
        typer.Option(
            "--templates-dir", help="Override templates directory (e.g. ./templates)."
        ),
    ] = None,
) -> None:
    """Generate repositories from genrepo.yaml."""
    try:
        config_path = config.resolve()
        cfg = load_config(config_path)
        if stub_only:
            cfg.generation.stub_only = True
        if dry_run or check:
            pr = plan_from_config(
                cfg,
                project_root=config_path.parent,
                force=force,
                templates_dir=templates_dir,
            )
            if format not in {"text", "json"}:
                raise typer.BadParameter("--format must be 'text' or 'json'")
            if format == "json":

                def _to_dict(fp: object) -> object:
                    if hasattr(fp, "__dict__"):
                        d: dict[str, Any] = {}
                        for k, v in fp.__dict__.items():
                            if isinstance(v, Path):
                                d[k] = str(v)
                            elif isinstance(v, list):
                                d[k] = [_to_dict(x) for x in v]
                            else:
                                d[k] = v
                        return d
                    return fp

                console.print_json(data=_to_dict(pr))
            else:
                # text summary
                total = len(pr.files)
                would = len(pr.to_write)
                up_to = len(pr.up_to_date)
                console.print(
                    Panel.fit(
                        f"Plan: {would} to write, {up_to} up-to-date, {total} total"
                    )
                )
                for f in pr.files:
                    status = "WRITE" if f.would_write else f.reason or "skip"
                    console.print(f" - {status:>10} | {f.path}")
            if check:
                raise typer.Exit(code=1 if pr.to_write else 0)
            return
        # Execute generation
        written = generate_from_config(
            cfg,
            project_root=config_path.parent,
            force=force,
            templates_dir=templates_dir,
        )
    except typer.Exit:
        # Propagate explicit exit codes (e.g., --check outcome)
        raise
    except Exception as e:
        # Include config path for clearer error context (helps tests and UX)
        console_err.print(f"[red]Error while reading {config_path}:[/red] {e}")
        raise typer.Exit(code=1)

    if not written:
        console.print(f"[yellow]{MSG_NO_FILES}[/yellow] {MSG_NO_FILES_HINT}")
        raise typer.Exit(code=0)

    # Summary: classify repos created from explicit vs wildcard
    base_name = cfg.generation.base_filename
    repo_files = [p for p in written if p.name != base_name]

    def snake_to_pascal(s: str) -> str:
        return "".join(part.capitalize() for part in s.split("_"))

    explicit_names = {
        m.name for m in getattr(cfg, "models", []) if m.name.lower() not in {"all", "*"}
    }
    explicit_count = 0
    wildcard_count = 0
    for p in repo_files:
        stem = p.stem  # e.g., user_repository
        model_snake = (
            stem[: -len("_repository")] if stem.endswith("_repository") else stem
        )
        model_name = snake_to_pascal(model_snake)
        if model_name in explicit_names:
            explicit_count += 1
        else:
            wildcard_count += 1

    console.print(
        Panel.fit(f"[bold green]{PANEL_GENERATED.format(n=len(written))}[/bold green]")
    )
    if base_path := next((p for p in written if p.name == base_name), None):
        console.print(f" [cyan]{LABEL_BASE}[/cyan]: {base_path}")
    if repo_files:
        console.print(
            f" [cyan]{LABEL_REPOS}[/cyan]: {len(repo_files)} (explicit: {explicit_count}, wildcard: {wildcard_count})"
        )
        for p in repo_files:
            console.print(f"  - {p}")


# Removed legacy "generate" (config) and "init" commands in favor of init-config.


@app.command("init-templates")
def init_templates(
    dest: Annotated[
        Path,
        typer.Option(
            "--dest", help="Destination directory to copy packaged templates to."
        ),
    ] = Path("templates/genrepo"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing files if present.")
    ] = False,
) -> None:
    """Copy packaged templates to a local directory for customization."""
    try:
        from importlib.resources import files as ir_files

        src_root = ir_files("genrepo.templates")
    except Exception as e:
        console.print(f"[red]Cannot locate packaged templates: {e}[/red]")
        raise typer.Exit(code=1)

    copied = 0

    def should_skip(name: str) -> bool:
        return name in {"__init__.py", "__pycache__"}

    try:
        dest.mkdir(parents=True, exist_ok=True)
        for entry in src_root.iterdir():
            name = entry.name
            if should_skip(name):
                continue
            target = dest / name
            # Files only at this level
            if entry.is_file():
                if target.exists() and not force:
                    continue
                data = entry.read_bytes()
                target.write_bytes(data)
                copied += 1
    except Exception as e:
        console.print(f"[red]Error copying templates: {e}[/red]")
        raise typer.Exit(code=1)

    if copied == 0 and not force:
        console.print("[yellow]No templates copied (already present?).[/yellow]")
    else:
        console.print(
            Panel.fit(f"[bold green]Copied {copied} template(s) to {dest}[/bold green]")
        )


def main() -> None:
    """Entrypoint for console script."""
    app()
