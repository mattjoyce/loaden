"""CLI for config file operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from loaden.config import deep_merge, load_config

__all__ = ["main"]


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a config file."""
    required_keys = args.required.split(",") if args.required else None

    try:
        config = load_config(args.config, required_keys=required_keys)
        if args.verbose:
            print(f"Valid: {args.config}")
            print(f"  Keys: {len(config)}")
            if required_keys:
                print(f"  Required keys present: {', '.join(required_keys)}")
        return 0
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    """Show resolved config (with includes merged)."""
    try:
        config = load_config(args.config)

        if args.key:
            value = _get_nested_key(config, args.key)
            if value is None:
                print(f"Key not found: {args.key}", file=sys.stderr)
                return 1
            if isinstance(value, dict):
                print(yaml.dump(value, default_flow_style=False, sort_keys=False))
            else:
                print(value)
        else:
            print(yaml.dump(config, default_flow_style=False, sort_keys=False))
        return 0
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_combine(args: argparse.Namespace) -> int:
    """Combine multiple config files into one."""
    try:
        result: dict[str, Any] = {}
        for config_path in args.configs:
            config = load_config(config_path)
            result = deep_merge(result, config)

        output = yaml.dump(result, default_flow_style=False, sort_keys=False)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Written to: {args.output}")
        else:
            print(output)
        return 0
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract a section from config to a new file."""
    try:
        config = load_config(args.config)
        value = _get_nested_key(config, args.key)

        if value is None:
            print(f"Key not found: {args.key}", file=sys.stderr)
            return 1

        if not isinstance(value, dict):
            msg = f"Key '{args.key}' is not a section (got {type(value).__name__})"
            print(msg, file=sys.stderr)
            return 1

        output = yaml.dump(value, default_flow_style=False, sort_keys=False)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Extracted '{args.key}' to: {args.output}")
        else:
            print(output)
        return 0
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _get_nested_key(config: dict[str, Any], key_path: str) -> Any | None:
    """Get a nested key using dot notation."""
    parts = key_path.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="loaden",
        description="Config file utilities with YAML include support",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate a config file")
    p_validate.add_argument("config", help="Path to config file")
    p_validate.add_argument(
        "-r", "--required", help="Comma-separated required keys (e.g., db.host,api.key)"
    )
    p_validate.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    p_validate.set_defaults(func=cmd_validate)

    # show
    p_show = subparsers.add_parser("show", help="Show resolved config (includes merged)")
    p_show.add_argument("config", help="Path to config file")
    p_show.add_argument("-k", "--key", help="Show only this key (dot notation)")
    p_show.set_defaults(func=cmd_show)

    # combine
    p_combine = subparsers.add_parser("combine", help="Combine multiple config files")
    p_combine.add_argument("configs", nargs="+", help="Config files to combine (in order)")
    p_combine.add_argument("-o", "--output", help="Output file (default: stdout)")
    p_combine.set_defaults(func=cmd_combine)

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract a section to a new file")
    p_extract.add_argument("config", help="Path to config file")
    p_extract.add_argument("key", help="Key to extract (dot notation)")
    p_extract.add_argument("-o", "--output", help="Output file (default: stdout)")
    p_extract.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
