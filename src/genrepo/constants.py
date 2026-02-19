"""Central constants for Genrepo messages and options."""

# CRUD base methods and sentinels
CRUD_METHODS: tuple[str, ...] = (
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
)
METHOD_PRESETS: tuple[str, ...] = ("all", "none")

# Packaged sample YAML location
SAMPLE_PACKAGE: str = "genrepo.assets"
SAMPLE_YAML_FILENAME: str = "genrepo.sample.yaml"

# CLI messages
MSG_HEALTH_OK: str = "genrepo: ok"
MSG_HEALTH_ERR: str = "genrepo: error - {err}"
MSG_CONFIG_CREATED: str = "Created {path}"
MSG_CONFIG_EXISTS: str = "Config already exists: {path} (use --force to overwrite)"
MSG_NO_FILES: str = "No files generated."
MSG_NO_FILES_HINT: str = "(maybe they already exist and --force is not set)"
PANEL_GENERATED: str = "Generated {n} file(s)"
LABEL_BASE: str = "base"
LABEL_REPOS: str = "repos"

# Supported ORM identifiers
ORM_SQLMODEL: str = "sqlmodel"
ORM_SQLALCHEMY: str = "sqlalchemy"

# Template filenames (avoid string literals scattered in code)
TPL_BASE_SQLMODEL_SYNC: str = "base_repository_sqlmodel_sync.j2"
TPL_BASE_SQLMODEL_ASYNC: str = "base_repository_sqlmodel_async.j2"
TPL_BASE_SQLALCHEMY_SYNC: str = "base_repository_sqlalchemy_sync.j2"
TPL_BASE_SQLALCHEMY_ASYNC: str = "base_repository_sqlalchemy_async.j2"

TPL_STANDALONE_SQLMODEL: str = "repository_sqlmodel.j2"
TPL_STANDALONE_SQLALCHEMY: str = "repository_sqlalchemy.j2"

TPL_USER_STUB: str = "model_repository_user_stub.j2"

# Stub-only templates (no ORM imports)
TPL_BASE_STUB: str = "repository_base_stub.j2"
TPL_STANDALONE_STUB: str = "repository_standalone_stub.j2"

# Config/validation errors (always in English)
ERR_MODEL_NAME: str = "model name must start with a letter"
ERR_IMPORT_PATH_CLASS: str = "import_path must include both module and class"
ERR_INVALID_METHOD: str = "invalid method: {method}"
ERR_DUPLICATE_MODELS: str = "duplicate model names in configuration"
ERR_CONFIG_NOT_FOUND: str = "config not found: {path}"
ERR_MODELS_MISSING: str = "invalid configuration: missing 'models'. Use 'models: all' for discovery or provide an explicit list under 'models:'."
ERR_MODELS_NONE: str = "no models configured. Use 'models: all' for discovery or define an explicit list under 'models:'."
ERR_MODELS_INVALID_VALUE: str = (
    "invalid value for 'models'. Use 'all' or an explicit list of models."
)
ERR_MODELS_EMPTY: str = "empty 'models' list. Use 'models: all' for discovery or provide one or more models."
ERR_INVALID_CONFIGURATION: str = "invalid configuration: {err}"
ERR_MODEL_NOT_IMPORTABLE: str = (
    "could not import model: {import_path}. Create the model or adjust 'import_path'."
)
ERR_UNSUPPORTED_ORM: str = "unsupported orm: {orm}. Supported: sqlmodel, sqlalchemy"
