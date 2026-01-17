"""Configuration loading with minimal error handling."""

from __future__ import annotations

import os
import re
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

    Args:
        env_path: Path to env file

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    content = env_path.read_text(encoding="utf-8")

    # Try YAML first (if it looks like YAML)
    if env_path.suffix in (".yaml", ".yml"):
        env_vars = yaml.safe_load(content)
        if env_vars is None:
            return
        if not isinstance(env_vars, dict):
            raise ValueError(f"Env file must be a dictionary: {env_path}")
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[str(key)] = str(value)
        return

    # Parse as .env format
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Remove surrounding quotes if present
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(
    config_path: str = "config.yaml",
    required_keys: list[str] | None = None,
    expand_vars: bool = True,
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
    string values throughout the config.

    Included files are merged in order, with later files overriding earlier ones.
    The main config file always takes final precedence.

    Args:
        config_path: Path to config file
        required_keys: List of dot-separated keys that must exist (e.g., ["db.host", "api.key"])
        expand_vars: Whether to expand ${VAR} in values (default: True)
        _include_stack: Internal parameter to detect circular includes

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If config is empty/invalid, circular include detected, or required keys missing
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please create a config.yaml file or specify path with --config"
        )

    if _include_stack is None:
        _include_stack = []

    resolved_path = str(path.resolve())
    if resolved_path in _include_stack:
        cycle = " -> ".join(_include_stack + [resolved_path])
        raise ValueError(f"Circular include detected: {cycle}")

    _include_stack.append(resolved_path)

    try:
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError(
                f"Invalid config file: {config_path}\n"
                f"Config must be a YAML dictionary, got {type(config).__name__}"
            )

        if "loaden_include" in config:
            includes = config.pop("loaden_include")
            if isinstance(includes, str):
                includes = [includes]

            base_config: dict[str, Any] = {}
            for include_path in includes:
                include_full = path.parent / include_path
                included = load_config(
                    str(include_full),
                    required_keys=None,
                    expand_vars=False,  # Expand only at root level
                    _include_stack=_include_stack.copy(),
                )
                base_config = deep_merge(base_config, included)

            config = deep_merge(base_config, config)

        # Process loaden_env - load env files before expanding vars
        if "loaden_env" in config:
            env_files = config.pop("loaden_env")
            if isinstance(env_files, str):
                env_files = [env_files]

            for env_file in env_files:
                env_path = path.parent / env_file
                _load_env_file(env_path)

    finally:
        if resolved_path in _include_stack:
            _include_stack.remove(resolved_path)

    is_root_call = len(_include_stack) == 0

    if is_root_call:
        # Set env vars from config's env section
        if "env" in config:
            for key, value in config["env"].items():
                if key not in os.environ:
                    os.environ[key] = str(value)

        # Expand ${VAR} in all string values
        if expand_vars:
            config = _expand_env_vars(config)

        if required_keys:
            _validate_required_keys(config, required_keys, config_path)

    return config


def _validate_required_keys(
    config: dict[str, Any],
    required_keys: list[str],
    config_path: str,
) -> None:
    """
    Validate that all required keys exist in config.

    Args:
        config: Configuration dictionary
        required_keys: List of dot-separated keys (e.g., ["db.host", "api.key"])
        config_path: Path to config file (for error messages)

    Raises:
        ValueError: If any required key is missing
    """
    missing = []
    for key_path in required_keys:
        parts = key_path.split(".")
        current = config
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                missing.append(key_path)
                break
            current = current[part]

    if missing:
        raise ValueError(
            f"Invalid config: missing required keys in {config_path}: {', '.join(missing)}"
        )
