# Genrepo Examples

Sample `genrepo.yaml` files showing common scenarios. Use these as starting points and adjust to your project.

How to try an example:

1) Copy the file into your repo (e.g., `cp examples/standalone_sqlmodel_sync.yaml genrepo.yaml`).
2) Edit `import_path` to match your models (or set `allow_missing_models: true`).
3) Run `genrepo generate` (or `uv run genrepo generate`).

Files:

- `standalone_sqlmodel_sync.yaml`: Standalone repositories using SQLModel (sync).
- `standalone_sqlalchemy_async.yaml`: Standalone repositories using SQLAlchemy (async).
- `combined_sqlmodel.yaml`: Combined mode (base + user repos) with SQLModel.
- `combined_sqlmodel_multi.yaml`: Combined mode with multiple models and per-model methods.
- `combined_sqlmodel_multi_async.yaml`: Combined + multiple models (SQLModel, async).
- `combined_sqlalchemy_multi.yaml`: Combined + multiple models (SQLAlchemy, sync).
- `stub_only.yaml`: Stub-only generation (signatures + TODO/pass; no ORM logic).
- `discover_all.yaml`: Discover models automatically from a package/directory.
- `base_only_sqlmodel_sync.yaml`: Generate only the base repository (SQLModel, sync).
