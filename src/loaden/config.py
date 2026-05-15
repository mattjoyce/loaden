"""Configuration loading with minimal error handling."""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any

import yaml

__all__ = ["deep_merge", "get", "load_config"]

# Pattern for ${VAR} or ${VAR:-default}
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge overlay into base, with overlay taking precedence.

    Args:
        base: Base configuration dictionary
        overlay: Overlay configuration (overrides base)

    Returns:
        Merged configuration dictionary

    Examples:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> overlay = {"b": {"d": 3}, "e": 4}
        >>> deep_merge(base, overlay)
        {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
    """
    result = base.copy()

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get(config: dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Safely get a nested key using dot notation.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path (e.g., "database.host")
        default: Value to return if key not found

    Returns:
        Value at key path, or default if not found

    Examples:
        >>> config = {"database": {"host": "localhost", "port": 5432}}
        >>> get(config, "database.host")
        "localhost"
        >>> get(config, "database.missing", "default_value")
        "default_value"
    """
    parts = key_path.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _expand_env_vars(value: Any) -> Any:
    """
    Recursively expand ${VAR} and ${VAR:-default} in string values.

    Args:
        value: Value to expand (string, dict, list, or other)

    Returns:
        Value with environment variables expanded
    """
    if isinstance(value, str):

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default_val = match.group(2)  # None if no default specified
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            if default_val is not None:
                return default_val
            return match.group(0)  # Keep original if no value and no default

        return _ENV_VAR_PATTERN.sub(replace_var, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def _load_env_file(env_path: Path) -> None:
    """
    Load environment variables from a file.

    Supports two formats:
    - .env format: KEY=value (one per line, # comments, empty lines ignored)
    - YAML format: key: value dictionary

    Shell environment takes precedence - existing vars are not overwritten.

    Malformed .env lines (missing '=' or empty key after strip) are skipped
    with a warnings.warn rather than raising, to preserve historical behavior.

    Args:
        env_path: Path to env file

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If a .yaml/.yml env file's top-level is not a dict
        yaml.YAMLError: If a .yaml/.yml env file has parse errors (the message
            is tagged with the env file path)
    """
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    content = env_path.read_text(encoding="utf-8")

    if env_path.suffix in (".yaml", ".yml"):
        try:
            env_vars = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in env file {env_path}: {e}") from e
        if env_vars is None:
            return
        if not isinstance(env_vars, dict):
            raise ValueError(f"Env file must be a dictionary: {env_path}")
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[str(key)] = str(value)
        return

    # Parse as .env format
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            warnings.warn(
                f"Skipping malformed line in {env_path} (no '='): {line!r}",
                stacklevel=2,
            )
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            warnings.warn(
                f"Skipping malformed line in {env_path} (empty key): {line!r}",
                stacklevel=2,
            )
            continue
        # Remove surrounding quotes if present
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def _normalize_loader_path(path_value: str | Path, base_dir: Path | None = None) -> Path:
    """
    Expand user/env vars and normalize a loader-managed path.

    Args:
        path_value: Raw path value from API or config
        base_dir: Base directory for relative paths

    Returns:
        Normalized absolute path
    """
    path = Path(os.path.expandvars(str(path_value))).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path.resolve(strict=False)


def _resolve_loader_path(
    value: str | Path,
    base_dir: Path | None,
    expand: bool,
) -> Path:
    """Resolve a loader-managed path either via expansion or simple base-dir join."""
    if expand:
        return _normalize_loader_path(value, base_dir=base_dir)
    p = Path(value)
    return base_dir / p if base_dir is not None else p


def _load_with_includes(
    path: Path,
    expand_loader_paths: bool,
    include_stack: list[str],
) -> dict[str, Any]:
    """
    Read one YAML file, recursively merge its loaden_include chain, and apply
    any loaden_env files. Returns the merged tree without env-section
    processing, ${VAR} expansion, or required-key validation — those run
    once in load_config regardless of include depth.

    include_stack is treated as immutable here: each recursion passes a fresh
    list, so there is no try/finally bookkeeping.

    Args:
        path: Existing path to a YAML config file
        expand_loader_paths: Expand ~ and ${VAR} in loaden_include / loaden_env
        include_stack: Resolved paths of ancestors in the current load chain

    Returns:
        Merged config dict (loaden_include and loaden_env keys removed)

    Raises:
        FileNotFoundError: If an included file is missing
        ValueError: On circular include or non-dict YAML
        yaml.YAMLError: On invalid YAML
    """
    resolved_path = str(path.resolve())
    if resolved_path in include_stack:
        cycle = " -> ".join(include_stack + [resolved_path])
        raise ValueError(f"Circular include detected: {cycle}")
    next_stack = include_stack + [resolved_path]

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError(
            f"Invalid config file: {path}\n"
            f"Config must be a YAML dictionary, got {type(config).__name__}"
        )

    if "loaden_include" in config:
        includes = config.pop("loaden_include")
        if isinstance(includes, str):
            includes = [includes]

        base_config: dict[str, Any] = {}
        for include_path in includes:
            include_full = _resolve_loader_path(include_path, path.parent, expand_loader_paths)
            if not include_full.exists():
                raise FileNotFoundError(f"Config file not found: {include_full}")
            included = _load_with_includes(include_full, expand_loader_paths, next_stack)
            base_config = deep_merge(base_config, included)

        config = deep_merge(base_config, config)

    if "loaden_env" in config:
        env_files = config.pop("loaden_env")
        if isinstance(env_files, str):
            env_files = [env_files]

        for env_file in env_files:
            env_path = _resolve_loader_path(env_file, path.parent, expand_loader_paths)
            _load_env_file(env_path)

    return config


def load_config(
    config_path: str = "config.yaml",
    required_keys: list[str] | None = None,
    expand_vars: bool = True,
    expand_loader_paths: bool = False,
    _include_stack: list[str] | None = None,
) -> dict[str, Any]:
    """
    Load configuration from YAML file with include support.

    Supports recursive includes via "loaden_include" key:
        loaden_include: base.yaml
        loaden_include: [base.yaml, other.yaml]

    Supports loading env files via "loaden_env" key:
        loaden_env: .env
        loaden_env: [.env, secrets.env]

    Environment variables can be set via an "env" section - shell environment
    takes precedence over config values.

    Environment variable substitution expands ${VAR} and ${VAR:-default} in
    string values throughout the config. Substituted values are always strings:
    ``port: ${PORT:-5432}`` yields the string ``"5432"``, not an int. Cast at
    the call site if you need a non-string type.

    Included files are merged in order, with later files overriding earlier ones.
    The main config file always takes final precedence.

    Side effects: ``load_config`` writes to ``os.environ`` when the config
    contains a top-level ``env:`` section or a ``loaden_env:`` directive
    pointing at an env file. ``os.environ`` is not thread-safe for writes —
    concurrent calls to ``load_config`` can race.

    Args:
        config_path: Path to config file
        required_keys: List of dot-separated keys that must exist (e.g., ["db.host", "api.key"])
        expand_vars: Whether to expand ${VAR} in values (default: True)
        expand_loader_paths: Whether to expand ~ and environment variables in
            config_path, loaden_include, and loaden_env paths (default: False)
        _include_stack: Internal parameter — seeds the include-cycle stack.
            Kept for backward compatibility; new code should not pass this.

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If config is empty/invalid, circular include detected, or required keys missing
    """
    path = _resolve_loader_path(config_path, None, expand_loader_paths)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    config = _load_with_includes(
        path,
        expand_loader_paths,
        list(_include_stack) if _include_stack else [],
    )

    if "env" in config:
        for key, value in config["env"].items():
            if key not in os.environ:
                os.environ[key] = str(value)

    if expand_vars:
        config = _expand_env_vars(config)

    if required_keys:
        _validate_required_keys(config, required_keys, config_path)

    return config


_MISSING = object()


def _validate_required_keys(
    config: dict[str, Any],
    required_keys: list[str],
    config_path: str,
) -> None:
    """
    Validate that all required keys exist in config.

    A key whose value is ``None`` counts as present — only structurally missing
    keys (or a non-dict ancestor) are reported.

    Args:
        config: Configuration dictionary
        required_keys: List of dot-separated keys (e.g., ["db.host", "api.key"])
        config_path: Path to config file (for error messages)

    Raises:
        ValueError: If any required key is missing
    """
    missing = [k for k in required_keys if get(config, k, _MISSING) is _MISSING]
    if missing:
        raise ValueError(
            f"Invalid config: missing required keys in {config_path}: {', '.join(missing)}"
        )
