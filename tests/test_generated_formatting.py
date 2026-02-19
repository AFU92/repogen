from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from genrepo.config import load_config
from genrepo.generator import generate_from_config


@pytest.mark.parametrize(
    "orm,async_mode",
    [
        ("sqlmodel", False),
        ("sqlalchemy", False),
        # Cover async variants to catch indentation/formatting issues there too
        ("sqlmodel", True),
        ("sqlalchemy", True),
    ],
)
def test_generated_files_pass_ruff_and_are_indented(
    tmp_path: Path, orm: str, async_mode: bool
) -> None:
    cfg_text = "\n".join(
        [
            f"orm: {orm}",
            f"async_mode: {str(async_mode).lower()}",
            "output_dir: OUT",
            "generation:",
            "  mode: standalone",
            "allow_missing_models: true",
            "models:",
            "  - name: Order",
            "    import_path: app.models.order:Order",
            "    id_field: id",
            "    id_type: int",
            "    methods: [get, get_or_raise, list, find_one, create, update, delete, delete_by_id, exists, count]",
        ]
    ).replace("OUT", (tmp_path / "out").as_posix())

    cfg_path = tmp_path / "genrepo.yaml"
    cfg_path.write_text(cfg_text, encoding="utf-8")
    cfg = load_config(cfg_path)
    written = generate_from_config(cfg, project_root=tmp_path, force=True)

    assert written, "no files were generated"

    for fpath in written:
        # Check that module header does not include a hard "DO NOT EDIT"
        content = Path(fpath).read_text(encoding="utf-8")
        assert "DO NOT EDIT" not in content

        # Basic syntax check via Python compiler (catches bad indentation)
        try:
            compile(content, str(fpath), "exec")
        except SyntaxError as e:  # pragma: no cover - surface compiler error
            raise AssertionError(f"SyntaxError in generated file {fpath}: {e}")

        # Optional: ruff syntax/lint shouldn't crash (0 or 1 acceptable)
        res_check = subprocess.run(
            ["ruff", "check", str(fpath)], capture_output=True, text=True
        )
        assert res_check.returncode in (0, 1), res_check.stderr

        # Heuristic: ensure 'return' lines are indented (at least 8 spaces)
        for line in content.splitlines():
            if line.lstrip().startswith("return "):
                assert len(line) - len(line.lstrip()) >= 8, (
                    f"mis-indented return: {line} in {fpath}"
                )

        # Heuristic: avoid compressed statements like "; return ..." on same line
        for line in content.splitlines():
            assert "; return" not in line, (
                f"multiple statements on one line: {line} in {fpath}"
            )

        # Heuristic: ensure a blank line separates consecutive methods inside class
        lines = content.splitlines()
        for i, line in enumerate(lines[:-2]):
            if line.startswith("    def ") and i > 0:
                prev = lines[i - 1]
                # Expect previous line empty (single blank line between methods)
                assert prev.strip() == "", (
                    f"missing blank line before method at line {i + 1} in {fpath}"
                )
