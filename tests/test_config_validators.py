from __future__ import annotations

from pathlib import Path

import pytest

from genrepo.config import GenrepoConfig, ModelConfig, load_config
from genrepo.constants import (
    CRUD_METHODS,
    ERR_DUPLICATE_MODELS,
    ERR_MODELS_EMPTY,
    ERR_MODELS_INVALID_VALUE,
    ERR_MODELS_MISSING,
    ERR_MODELS_NONE,
)


def test_model_methods_normalization_all_and_none() -> None:
    # 'all' expands to full CRUD set (order not guaranteed)
    m_all = ModelConfig(
        name="User",
        import_path="app.models.user:User",
        id_field="id",
        id_type="int",
        methods=["all"],
    )
    assert set(m_all.methods) == set(CRUD_METHODS)

    # 'none' yields empty list
    m_none = ModelConfig(
        name="User",
        import_path="app.models.user:User",
        id_field="id",
        id_type="int",
        methods=["none"],
    )
    assert m_none.methods == []


def test_model_methods_deduplicate_and_validate() -> None:
    # Deduplicate valid methods
    m = ModelConfig(
        name="User",
        import_path="app.models.user:User",
        id_field="id",
        id_type="int",
        methods=["get", "get", "list"],
    )
    assert m.methods == ["get", "list"]

    # Invalid method raises (use model_validate to avoid static type warnings)
    with pytest.raises(ValueError) as e:
        ModelConfig.model_validate(
            {
                "name": "User",
                "import_path": "app.models.user:User",
                "id_field": "id",
                "id_type": "int",
                "methods": ["bogus"],
            }
        )
    # Pydantic's Literal validation will fire; ensure the bad token appears
    assert "bogus" in str(e.value)


def test_genrepo_config_duplicate_model_names() -> None:
    with pytest.raises(ValueError) as e:
        GenrepoConfig.model_validate(
            {
                "orm": "sqlmodel",
                "async_mode": False,
                "output_dir": "app/repositories",
                "models": [
                    {
                        "name": "User",
                        "import_path": "app.models.user:User",
                        "id_field": "id",
                        "id_type": "int",
                    },
                    {
                        "name": "User",
                        "import_path": "app.models.user:User",
                        "id_field": "id",
                        "id_type": "int",
                    },
                ],
            }
        )
    assert ERR_DUPLICATE_MODELS in str(e.value)


def test_load_config_models_field_validation(tmp_path: Path) -> None:
    # Missing 'models'
    p = tmp_path / "cfg_missing.yaml"
    p.write_text("orm: sqlmodel\noutput_dir: out\n", encoding="utf-8")
    with pytest.raises(ValueError) as e1:
        load_config(p)
    assert ERR_MODELS_MISSING in str(e1.value)

    # models: [] is invalid
    p = tmp_path / "cfg_empty.yaml"
    p.write_text("orm: sqlmodel\noutput_dir: out\nmodels: []\n", encoding="utf-8")
    with pytest.raises(ValueError) as e2:
        load_config(p)
    assert ERR_MODELS_EMPTY in str(e2.value)

    # models: all is accepted and sets discover_all
    p = tmp_path / "cfg_all.yaml"
    p.write_text("orm: sqlmodel\noutput_dir: out\nmodels: all\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.discover_all is True
    # Defaults set for discovery
    assert cfg.models_dir is not None and cfg.models_package is not None

    # models: none is rejected with a clear error
    p = tmp_path / "cfg_none.yaml"
    p.write_text("orm: sqlmodel\noutput_dir: out\nmodels: none\n", encoding="utf-8")
    with pytest.raises(ValueError) as e3:
        load_config(p)
    assert ERR_MODELS_NONE in str(e3.value)

    # models: invalid string value → explicit error
    p = tmp_path / "cfg_invalid.yaml"
    p.write_text("orm: sqlmodel\noutput_dir: out\nmodels: maybe\n", encoding="utf-8")
    with pytest.raises(ValueError) as e4:
        load_config(p)
    assert ERR_MODELS_INVALID_VALUE in str(e4.value)
