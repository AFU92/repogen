from __future__ import annotations

from pathlib import Path

import pytest

from genrepo.config import load_config
from genrepo.generator import generate_from_config


@pytest.mark.parametrize(
    "config_text, expected_classes, out_subdir",
    [
        (
            "\n".join(
                [
                    "orm: sqlmodel",
                    "output_dir: OUT/repositories",
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
            [("user_repository.py", "class UserRepository")],
            "standalone_case",
        ),
        (
            "\n".join(
                [
                    "orm: sqlmodel",
                    "output_dir: OUT/repositories",
                    "generation:",
                    "  mode: combined",
                    "  stub_only: true",
                    "allow_missing_models: true",
                    "models:",
                    "  - name: Alpha",
                    "    import_path: examples.ex_stub_only.models.alpha:Alpha",
                    "    id_field: id",
                    "    id_type: int",
                    "  - name: Beta",
                    "    import_path: examples.ex_stub_only.models.beta:Beta",
                    "    id_field: id",
                    "    id_type: int",
                ]
            ),
            [
                ("base_repository.py", "class BaseRepository"),
                ("alpha_repository.py", "class AlphaRepository"),
                ("beta_repository.py", "class BetaRepository"),
            ],
            "combined_stub_only_case",
        ),
    ],
)
def test_generate_examples_into_tmp(
    config_text: str,
    expected_classes: list[tuple[str, str]],
    out_subdir: str,
    tmp_path: Path,
) -> None:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    cfg_path = tmp_path / "cfg.yaml"
    # Replace OUT with tmp base (without trailing /repositories) to avoid duplication
    out_base = tmp_path / out_subdir
    cfg_path.write_text(
        config_text.replace("OUT", out_base.as_posix()), encoding="utf-8"
    )
    out_dir = out_base / "repositories"
    cfg = load_config(cfg_path)
    written = generate_from_config(cfg, project_root=REPO_ROOT, force=True)

    for fname, must_contain in expected_classes:
        fpath = out_dir / fname
        assert fpath in written or fpath.exists(), f"expected file not written: {fpath}"
        content = fpath.read_text(encoding="utf-8")
        assert must_contain in content, (
            f"missing expected snippet in {fpath}: {must_contain}"
        )
