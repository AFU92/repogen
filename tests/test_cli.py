from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from genrepo.cli.app import app


runner = CliRunner()


def test_cli_healthcheck_ok() -> None:
    r = runner.invoke(app, ["healthcheck"])  # basic
    assert r.exit_code == 0
    assert "genrepo: ok" in r.stdout

    r = runner.invoke(app, ["healthcheck", "--verbose"])  # verbose
    assert r.exit_code == 0
    assert "python:" in r.stdout


def test_cli_init_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / "genrepo.yaml"
    # init-config writes sample config
    r = runner.invoke(app, ["init-config", "--path", str(cfg_path)])
    assert r.exit_code == 0
    assert cfg_path.exists()
    content = cfg_path.read_text(encoding="utf-8")
    assert "generation:" in content and "models:" in content

    # second run should be no-op if file exists (without --force)
    r2 = runner.invoke(app, ["init-config", "--path", str(cfg_path)])
    assert r2.exit_code == 0


def test_cli_generate_standalone(tmp_path: Path) -> None:
    # Minimal standalone config pointing to example model (importable via conftest)
    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
                "    methods: [get, list]",
            ]
        ),
        encoding="utf-8",
    )

    r = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r.exit_code == 0
    # One file written under out_dir
    user_repo = out_dir / "user_repository.py"
    assert user_repo.exists()
    assert "class UserRepository" in user_repo.read_text(encoding="utf-8")


def test_cli_init_templates(tmp_path: Path) -> None:
    dest = tmp_path / "tpls"
    r = runner.invoke(app, ["init-templates", "--dest", str(dest)])
    assert r.exit_code == 0
    # At least one known template should be present
    assert (dest / "repository_sqlmodel.j2").exists()


def _write_minimal_cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
                "    methods: [get]",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def test_cli_dry_run_and_check(tmp_path: Path) -> None:
    cfg = _write_minimal_cfg(tmp_path)
    # Dry run should not write files
    r = runner.invoke(app, ["generate", "--config", str(cfg), "--dry-run"])
    assert r.exit_code == 0
    user_repo = tmp_path / "out" / "repositories" / "user_repository.py"
    assert not user_repo.exists()

    # Check should fail (files would be created)
    r2 = runner.invoke(app, ["generate", "--config", str(cfg), "--check"])
    assert r2.exit_code == 1

    # After generation, check should pass
    r3 = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r3.exit_code == 0
    r4 = runner.invoke(app, ["generate", "--config", str(cfg), "--check"])
    assert r4.exit_code == 0


def test_cli_dry_run_json_strict_stdout(tmp_path: Path) -> None:
    import json

    cfg = _write_minimal_cfg(tmp_path)
    r = runner.invoke(
        app,
        ["generate", "--config", str(cfg), "--dry-run", "--format", "json"],
        catch_exceptions=False,
    )
    assert r.exit_code == 0
    # stdout must be strict JSON and parseable
    json.loads(r.stdout)
    # Additional scenarios below exercise overwrite and combined behaviors


def test_standalone_force_overwrite_behavior(tmp_path: Path) -> None:
    # Prepare minimal standalone config
    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
                "    methods: [get]",
            ]
        ),
        encoding="utf-8",
    )

    # First generation writes the file
    r1 = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r1.exit_code == 0
    user_repo = out_dir / "user_repository.py"
    assert user_repo.exists()

    # Mutate the file to simulate user changes
    mutated = user_repo.read_text(encoding="utf-8") + "\n# MUTATED\n"
    user_repo.write_text(mutated, encoding="utf-8")

    # Run without --force: file should remain mutated
    r2 = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r2.exit_code == 0
    assert "# MUTATED" in user_repo.read_text(encoding="utf-8")

    # Run with --force: file should be regenerated (mutation removed)
    r3 = runner.invoke(app, ["generate", "--config", str(cfg), "--force"])
    assert r3.exit_code == 0
    assert "# MUTATED" not in user_repo.read_text(encoding="utf-8")


def test_combined_create_once_and_overwrite_base(tmp_path: Path) -> None:
    # Combined config with overwrite_base=True to check base is overwritten, but user repo is not
    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: combined",
                "  overwrite_base: true",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
            ]
        ),
        encoding="utf-8",
    )

    r1 = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r1.exit_code == 0
    base_repo = out_dir / "base_repository.py"
    user_repo = out_dir / "user_repository.py"
    assert base_repo.exists() and user_repo.exists()

    # Mutate both files
    base_repo.write_text(
        base_repo.read_text(encoding="utf-8") + "\n# BASE_MUTATED\n", encoding="utf-8"
    )
    user_repo.write_text(
        user_repo.read_text(encoding="utf-8") + "\n# USER_MUTATED\n", encoding="utf-8"
    )

    # Second run: base should be overwritten (mutation removed), user should remain (create-once)
    r2 = runner.invoke(app, ["generate", "--config", str(cfg)])
    assert r2.exit_code == 0
    assert "# BASE_MUTATED" not in base_repo.read_text(encoding="utf-8")
    assert "# USER_MUTATED" in user_repo.read_text(encoding="utf-8")


def test_generate_dry_run_invalid_format_fails(tmp_path: Path) -> None:
    cfg = _write_minimal_cfg(tmp_path)
    r = runner.invoke(
        app, ["generate", "--config", str(cfg), "--dry-run", "--format", "yaml"]
    )  # invalid
    assert r.exit_code != 0
    assert "must be 'text' or 'json'" in r.stdout or r.stderr


def test_generate_uses_local_templates_dir_override(tmp_path: Path) -> None:
    # Create a local templates dir overriding repository_sqlmodel.j2 by copying the real template
    tdir = tmp_path / "tpl"
    tdir.mkdir(parents=True, exist_ok=True)
    local_tpl = tdir / "repository_sqlmodel.j2"
    repo_root = Path(__file__).resolve().parents[1]
    src_tpl = repo_root / "src" / "genrepo" / "templates" / "repository_sqlmodel.j2"
    original = src_tpl.read_text(encoding="utf-8")
    local_tpl.write_text("# LOCAL_TPL\n" + original, encoding="utf-8")

    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
                "    methods: [get]",
            ]
        ),
        encoding="utf-8",
    )

    r = runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(cfg),
            "--templates-dir",
            str(tdir),
            "--force",
        ],
    )
    assert r.exit_code == 0
    content = (out_dir / "user_repository.py").read_text(encoding="utf-8")
    assert "# LOCAL_TPL" in content


def test_cli_stub_only_flag_generates_stub_templates(tmp_path: Path) -> None:
    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "allow_missing_models: true",
                "models:",
                "  - name: User",
                "    import_path: examples.ex3_single.models.user:User",
                "    id_field: id",
                "    id_type: int",
                "    methods: [get]",
            ]
        ),
        encoding="utf-8",
    )

    r = runner.invoke(app, ["generate", "--config", str(cfg), "--stub-only", "--force"])
    assert r.exit_code == 0
    content = (out_dir / "user_repository.py").read_text(encoding="utf-8")
    # Invariants: sin ORM e indica stubs (texto estable o patrones comunes)
    assert "from sqlmodel" not in content and "from sqlalchemy" not in content
    assert "UserRepository" in content
    assert any(k in content for k in ["NotImplementedError", "pass", "...", "TODO"])


def test_discovery_models_all_with_models_dir(tmp_path: Path) -> None:
    # Create ephemeral package mypkg/models with foo.py and bar.py
    models_dir = tmp_path / "mypkg" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "__init__.py").write_text("", encoding="utf-8")
    (models_dir / "foo.py").write_text("class Foo:\n    pass\n", encoding="utf-8")
    (models_dir / "bar.py").write_text("class Bar:\n    pass\n", encoding="utf-8")

    cfg = tmp_path / "genrepo.yaml"
    out_dir = tmp_path / "out" / "repositories"
    cfg.write_text(
        "\n".join(
            [
                "orm: sqlmodel",
                f"output_dir: {out_dir.as_posix()}",
                "generation:",
                "  mode: standalone",
                "models: all",
                f"models_dir: {models_dir.as_posix()}",
                "models_package: mypkg.models",
            ]
        ),
        encoding="utf-8",
    )

    r = runner.invoke(app, ["generate", "--config", str(cfg), "--force"])
    assert r.exit_code == 0
    # Expect repositories for Foo and Bar
    assert (out_dir / "foo_repository.py").exists()
    assert (out_dir / "bar_repository.py").exists()


def test_cli_error_missing_config_and_invalid_yaml(tmp_path: Path) -> None:
    # Missing config file
    missing = tmp_path / "nope.yaml"
    r1 = runner.invoke(app, ["generate", "--config", str(missing)])
    assert r1.exit_code != 0
    assert "nope.yaml" in (r1.stdout + r1.stderr)
    assert "not found" in (r1.stdout + r1.stderr).lower()
    # Invalid YAML
    bad = tmp_path / "bad.yaml"
    bad.write_text(": : :\n", encoding="utf-8")
    r2 = runner.invoke(app, ["generate", "--config", str(bad)])
    assert r2.exit_code != 0
    assert "bad.yaml" in (r2.stdout + r2.stderr)
    assert (
        "error" in (r2.stdout + r2.stderr).lower()
        or "parse" in (r2.stdout + r2.stderr).lower()
    )
