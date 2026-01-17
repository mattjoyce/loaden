"""Configuration loading with minimal error handling."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = ["deep_merge", "load_config"]


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


def load_config(
    config_path: str = "config.yaml",
    required_keys: list[str] | None = None,
    _include_stack: list[str] | None = None,
) -> dict[str, Any]:
    """
    Load configuration from YAML file with include support.

    Supports recursive includes via "loaden_include" key:
        loaden_include: base.yaml
        loaden_include: [base.yaml, other.yaml]

    Included files are merged in order, with later files overriding earlier ones.
    The main config file always takes final precedence.

    Environment variables can be set via an "env" section - shell environment
    takes precedence over config values.

    Args:
        config_path: Path to config file
        required_keys: List of dot-separated keys that must exist (e.g., ["db.host", "api.key"])
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
                    _include_stack=_include_stack.copy(),
                )
                base_config = deep_merge(base_config, included)

            config = deep_merge(base_config, config)
    finally:
        if resolved_path in _include_stack:
            _include_stack.remove(resolved_path)

    is_root_call = len(_include_stack) == 0

    if is_root_call:
        if "env" in config:
            for key, value in config["env"].items():
                if key not in os.environ:
                    os.environ[key] = str(value)

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
