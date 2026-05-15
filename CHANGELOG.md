# Changelog

## 0.1.2 - 2026-05-16

No breaking changes; public API and observable behavior preserved.

- Malformed `.env` lines (missing `=` or empty key) now emit a `warnings.warn`
  instead of being skipped silently.
- YAML env-file parse errors now include the offending file path in the
  message (still raised as `yaml.YAMLError`).
- Library `FileNotFoundError` for a missing config no longer carries the
  CLI-specific `--config` hint; the `loaden` CLI prints that hint itself.
- Documented in the README: `${VAR}` substitution always yields strings,
  `${VAR:-default}` does not fall back on empty values (diverges from shell),
  and `load_config` writes to `os.environ` (not thread-safe).
- Internal refactor: extracted `_load_with_includes`, removed the
  `is_root_call` self-inspection, deduplicated nested-key lookup and
  loader-path resolution. No signature changes.

## 2026-04-03
- Version bumped to 0.1.1.

## 0.1.1 - 2026-04-03

- Added optional loader path expansion for `config_path`, `loaden_include`, and
  `loaden_env`.
- `loaden` can now expand `~` and environment variables in loader-managed
  paths while preserving existing relative include and env-file semantics.
- Ordinary config values are unchanged and are not rewritten as paths.
