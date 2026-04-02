# Changelog

## Unreleased

- Added optional loader path expansion for `config_path`, `loaden_include`, and
  `loaden_env`.
- `loaden` can now expand `~` and environment variables in loader-managed
  paths while preserving existing relative include and env-file semantics.
- Ordinary config values are unchanged and are not rewritten as paths.
