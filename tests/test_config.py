"""Unit tests for loaden.config module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loaden.config import deep_merge, get, load_config


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_basic_merge(self) -> None:
        """Merge two flat dictionaries."""
        base = {"a": 1, "b": 2}
        overlay = {"c": 3}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_overlay_overrides_base(self) -> None:
        """Overlay values take precedence over base values."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 99}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": 99}

    def test_nested_dict_merge(self) -> None:
        """Nested dictionaries are merged recursively."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        overlay = {"b": {"d": 99, "e": 4}}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": {"c": 2, "d": 99, "e": 4}}

    def test_deeply_nested_merge(self) -> None:
        """Merge works at arbitrary nesting depth."""
        base = {"level1": {"level2": {"level3": {"a": 1, "b": 2}}}}
        overlay = {"level1": {"level2": {"level3": {"b": 99, "c": 3}}}}
        result = deep_merge(base, overlay)
        assert result == {"level1": {"level2": {"level3": {"a": 1, "b": 99, "c": 3}}}}

    def test_empty_base(self) -> None:
        """Merge with empty base returns overlay."""
        base: dict = {}
        overlay = {"a": 1, "b": {"c": 2}}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": {"c": 2}}

    def test_empty_overlay(self) -> None:
        """Merge with empty overlay returns base."""
        base = {"a": 1, "b": {"c": 2}}
        overlay: dict = {}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": {"c": 2}}

    def test_both_empty(self) -> None:
        """Merge of two empty dicts returns empty dict."""
        result = deep_merge({}, {})
        assert result == {}

    def test_overlay_replaces_non_dict_with_dict(self) -> None:
        """Overlay dict replaces base non-dict value."""
        base = {"a": 1}
        overlay = {"a": {"nested": "value"}}
        result = deep_merge(base, overlay)
        assert result == {"a": {"nested": "value"}}

    def test_overlay_replaces_dict_with_non_dict(self) -> None:
        """Overlay non-dict replaces base dict."""
        base = {"a": {"nested": "value"}}
        overlay = {"a": "flat"}
        result = deep_merge(base, overlay)
        assert result == {"a": "flat"}

    def test_base_not_mutated(self) -> None:
        """Original base dict is not modified."""
        base = {"a": 1, "b": {"c": 2}}
        overlay = {"b": {"d": 3}}
        deep_merge(base, overlay)
        assert base == {"a": 1, "b": {"c": 2}}

    def test_overlay_not_mutated(self) -> None:
        """Original overlay dict is not modified."""
        base = {"a": 1}
        overlay = {"b": {"c": 2}}
        deep_merge(base, overlay)
        assert overlay == {"b": {"c": 2}}

    def test_list_values_replaced_not_merged(self) -> None:
        """List values are replaced, not concatenated."""
        base = {"items": [1, 2, 3]}
        overlay = {"items": [4, 5]}
        result = deep_merge(base, overlay)
        assert result == {"items": [4, 5]}

    def test_none_values(self) -> None:
        """None values in overlay override base."""
        base = {"a": 1, "b": 2}
        overlay = {"b": None}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": None}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_basic_load(self, tmp_path: Path) -> None:
        """Load a simple YAML config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\nnumber: 42\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config == {"key": "value", "number": 42}

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(str(tmp_path / "nonexistent.yaml"))

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty YAML file returns empty dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")

        config = load_config(str(config_file))
        assert config == {}

    def test_invalid_yaml_not_dict(self, tmp_path: Path) -> None:
        """Raise ValueError if YAML is not a dictionary."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Config must be a YAML dictionary"):
            load_config(str(config_file))

    def test_nested_config(self, tmp_path: Path) -> None:
        """Load config with nested structures."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database:
  host: localhost
  port: 5432
  credentials:
    user: admin
    password: secret
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file))
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert config["database"]["credentials"]["user"] == "admin"


class TestLoadConfigIncludes:
    """Tests for include functionality."""

    def test_single_include(self, tmp_path: Path) -> None:
        """Include a single file."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text("base_key: base_value\n", encoding="utf-8")

        main_file = tmp_path / "config.yaml"
        main_file.write_text("loaden_include: base.yaml\nmain_key: main_value\n", encoding="utf-8")

        config = load_config(str(main_file))
        assert config == {"base_key": "base_value", "main_key": "main_value"}

    def test_multiple_includes(self, tmp_path: Path) -> None:
        """Include multiple files in order."""
        first = tmp_path / "first.yaml"
        first.write_text("a: 1\nb: first\n", encoding="utf-8")

        second = tmp_path / "second.yaml"
        second.write_text("b: second\nc: 3\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text(
            "loaden_include:\n  - first.yaml\n  - second.yaml\nd: 4\n", encoding="utf-8"
        )

        config = load_config(str(main))
        assert config == {"a": 1, "b": "second", "c": 3, "d": 4}

    def test_main_config_overrides_includes(self, tmp_path: Path) -> None:
        """Main config values override included values."""
        base = tmp_path / "base.yaml"
        base.write_text("key: from_base\nother: base\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text("loaden_include: base.yaml\nkey: from_main\n", encoding="utf-8")

        config = load_config(str(main))
        assert config == {"key": "from_main", "other": "base"}

    def test_nested_includes(self, tmp_path: Path) -> None:
        """Includes can include other files."""
        level2 = tmp_path / "level2.yaml"
        level2.write_text("deep: value\n", encoding="utf-8")

        level1 = tmp_path / "level1.yaml"
        level1.write_text("loaden_include: level2.yaml\nmid: level\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text("loaden_include: level1.yaml\ntop: level\n", encoding="utf-8")

        config = load_config(str(main))
        assert config == {"deep": "value", "mid": "level", "top": "level"}

    def test_include_from_subdirectory(self, tmp_path: Path) -> None:
        """Include paths are relative to the including file."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        nested = subdir / "nested.yaml"
        nested.write_text("nested_key: nested_value\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text(
            "loaden_include: subdir/nested.yaml\nmain_key: main_value\n", encoding="utf-8"
        )

        config = load_config(str(main))
        assert config == {"nested_key": "nested_value", "main_key": "main_value"}

    def test_circular_include_direct(self, tmp_path: Path) -> None:
        """Detect direct circular include (file includes itself)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_include: config.yaml\nkey: value\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Circular include detected"):
            load_config(str(config_file))

    def test_circular_include_indirect(self, tmp_path: Path) -> None:
        """Detect indirect circular include (A -> B -> A)."""
        file_a = tmp_path / "a.yaml"
        file_b = tmp_path / "b.yaml"

        file_a.write_text("loaden_include: b.yaml\na: 1\n", encoding="utf-8")
        file_b.write_text("loaden_include: a.yaml\nb: 2\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Circular include detected"):
            load_config(str(file_a))

    def test_circular_include_chain(self, tmp_path: Path) -> None:
        """Detect circular include in longer chain (A -> B -> C -> A)."""
        file_a = tmp_path / "a.yaml"
        file_b = tmp_path / "b.yaml"
        file_c = tmp_path / "c.yaml"

        file_a.write_text("loaden_include: b.yaml\na: 1\n", encoding="utf-8")
        file_b.write_text("loaden_include: c.yaml\nb: 2\n", encoding="utf-8")
        file_c.write_text("loaden_include: a.yaml\nc: 3\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Circular include detected"):
            load_config(str(file_a))

    def test_diamond_dependency_allowed(self, tmp_path: Path) -> None:
        """Diamond dependencies (A -> B, A -> C, B -> D, C -> D) are allowed."""
        shared = tmp_path / "shared.yaml"
        shared.write_text("shared: value\n", encoding="utf-8")

        left = tmp_path / "left.yaml"
        left.write_text("loaden_include: shared.yaml\nleft: value\n", encoding="utf-8")

        right = tmp_path / "right.yaml"
        right.write_text("loaden_include: shared.yaml\nright: value\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text(
            "loaden_include:\n  - left.yaml\n  - right.yaml\nmain: value\n", encoding="utf-8"
        )

        config = load_config(str(main))
        assert config == {"shared": "value", "left": "value", "right": "value", "main": "value"}

    def test_include_key_removed_from_result(self, tmp_path: Path) -> None:
        """The 'loaden_include' key is not present in the final config."""
        base = tmp_path / "base.yaml"
        base.write_text("base: value\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text("loaden_include: base.yaml\nmain: value\n", encoding="utf-8")

        config = load_config(str(main))
        assert "loaden_include" not in config


class TestLoadConfigEnv:
    """Tests for environment variable handling."""

    def test_env_vars_set_from_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables are set from env section."""
        monkeypatch.delenv("TEST_VAR_FROM_CONFIG", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
env:
  TEST_VAR_FROM_CONFIG: config_value
key: value
""",
            encoding="utf-8",
        )

        load_config(str(config_file))
        assert os.environ.get("TEST_VAR_FROM_CONFIG") == "config_value"

    def test_existing_env_vars_not_overridden(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing environment variables take precedence over config."""
        monkeypatch.setenv("EXISTING_VAR", "shell_value")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
env:
  EXISTING_VAR: config_value
key: value
""",
            encoding="utf-8",
        )

        load_config(str(config_file))
        assert os.environ.get("EXISTING_VAR") == "shell_value"

    def test_env_vars_converted_to_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-string env values are converted to strings."""
        monkeypatch.delenv("INT_VAR", raising=False)
        monkeypatch.delenv("BOOL_VAR", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
env:
  INT_VAR: 42
  BOOL_VAR: true
key: value
""",
            encoding="utf-8",
        )

        load_config(str(config_file))
        assert os.environ.get("INT_VAR") == "42"
        assert os.environ.get("BOOL_VAR") == "True"

    def test_env_section_remains_in_config(self, tmp_path: Path) -> None:
        """The env section is preserved in returned config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
env:
  SOME_VAR: value
key: other
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file))
        assert "env" in config
        assert config["env"]["SOME_VAR"] == "value"


class TestLoadConfigRequiredKeys:
    """Tests for required_keys validation."""

    def test_required_key_present(self, tmp_path: Path) -> None:
        """No error when required key exists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: secret123\n", encoding="utf-8")

        config = load_config(str(config_file), required_keys=["api_key"])
        assert config["api_key"] == "secret123"

    def test_required_key_missing(self, tmp_path: Path) -> None:
        """Raise ValueError when required key is missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("other_key: value\n", encoding="utf-8")

        with pytest.raises(ValueError, match="missing required keys.*api_key"):
            load_config(str(config_file), required_keys=["api_key"])

    def test_required_nested_key_present(self, tmp_path: Path) -> None:
        """Dot-separated keys validate nested paths."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database:
  host: localhost
  port: 5432
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file), required_keys=["database.host", "database.port"])
        assert config["database"]["host"] == "localhost"

    def test_required_nested_key_missing(self, tmp_path: Path) -> None:
        """Raise ValueError when nested required key is missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database:
  host: localhost
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="missing required keys.*database.port"):
            load_config(str(config_file), required_keys=["database.host", "database.port"])

    def test_required_deeply_nested_key(self, tmp_path: Path) -> None:
        """Validate deeply nested required keys."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
level1:
  level2:
    level3:
      key: value
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file), required_keys=["level1.level2.level3.key"])
        assert config["level1"]["level2"]["level3"]["key"] == "value"

    def test_multiple_required_keys_missing(self, tmp_path: Path) -> None:
        """Error message includes all missing keys."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("unrelated: value\n", encoding="utf-8")

        with pytest.raises(ValueError, match=r"api_key.*db\.host|db\.host.*api_key"):
            load_config(str(config_file), required_keys=["api_key", "db.host"])

    def test_required_keys_none(self, tmp_path: Path) -> None:
        """No validation when required_keys is None."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        config = load_config(str(config_file), required_keys=None)
        assert config == {"key": "value"}

    def test_required_keys_empty_list(self, tmp_path: Path) -> None:
        """No validation when required_keys is empty list."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        config = load_config(str(config_file), required_keys=[])
        assert config == {"key": "value"}

    def test_required_key_path_through_non_dict(self, tmp_path: Path) -> None:
        """Missing key when path goes through a non-dict value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database: not_a_dict\n", encoding="utf-8")

        with pytest.raises(ValueError, match="missing required keys.*database.host"):
            load_config(str(config_file), required_keys=["database.host"])

    def test_required_keys_validated_after_includes(self, tmp_path: Path) -> None:
        """Required keys are validated on final merged config."""
        base = tmp_path / "base.yaml"
        base.write_text("api_key: from_base\n", encoding="utf-8")

        main = tmp_path / "config.yaml"
        main.write_text("loaden_include: base.yaml\nother: value\n", encoding="utf-8")

        config = load_config(str(main), required_keys=["api_key"])
        assert config["api_key"] == "from_base"


class TestGet:
    """Tests for get() helper function."""

    def test_simple_key(self) -> None:
        """Get a top-level key."""
        config = {"host": "localhost", "port": 5432}
        assert get(config, "host") == "localhost"
        assert get(config, "port") == 5432

    def test_nested_key(self) -> None:
        """Get a nested key using dot notation."""
        config = {"database": {"host": "localhost", "port": 5432}}
        assert get(config, "database.host") == "localhost"
        assert get(config, "database.port") == 5432

    def test_deeply_nested_key(self) -> None:
        """Get a deeply nested key."""
        config = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        assert get(config, "level1.level2.level3.value") == "deep"

    def test_missing_key_returns_none(self) -> None:
        """Return None for missing key when no default specified."""
        config = {"host": "localhost"}
        assert get(config, "missing") is None
        assert get(config, "database.host") is None

    def test_missing_key_returns_default(self) -> None:
        """Return default value for missing key."""
        config = {"host": "localhost"}
        assert get(config, "missing", "default") == "default"
        assert get(config, "database.host", "fallback") == "fallback"

    def test_default_none_explicit(self) -> None:
        """Explicit None default works."""
        config = {"host": "localhost"}
        assert get(config, "missing", None) is None

    def test_path_through_non_dict(self) -> None:
        """Return default when path goes through non-dict."""
        config = {"database": "not_a_dict"}
        assert get(config, "database.host") is None
        assert get(config, "database.host", "default") == "default"

    def test_empty_config(self) -> None:
        """Handle empty config."""
        config: dict = {}
        assert get(config, "any.key") is None
        assert get(config, "any.key", "default") == "default"

    def test_returns_nested_dict(self) -> None:
        """Can return a nested dict value."""
        config = {"database": {"host": "localhost", "port": 5432}}
        result = get(config, "database")
        assert result == {"host": "localhost", "port": 5432}

    def test_returns_list_value(self) -> None:
        """Can return a list value."""
        config = {"items": [1, 2, 3]}
        assert get(config, "items") == [1, 2, 3]


class TestEnvVarSubstitution:
    """Tests for ${VAR} substitution in values."""

    def test_simple_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Substitute ${VAR} with env var value."""
        monkeypatch.setenv("TEST_HOST", "prod.example.com")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("host: ${TEST_HOST}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["host"] == "prod.example.com"

    def test_substitution_with_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Use default when var not set."""
        monkeypatch.delenv("UNSET_VAR", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text("host: ${UNSET_VAR:-localhost}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["host"] == "localhost"

    def test_substitution_ignores_default_when_var_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ignore default when var is set."""
        monkeypatch.setenv("SET_VAR", "actual_value")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: ${SET_VAR:-default}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == "actual_value"

    def test_unset_var_no_default_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep ${VAR} when unset and no default."""
        monkeypatch.delenv("TOTALLY_UNSET", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: ${TOTALLY_UNSET}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == "${TOTALLY_UNSET}"

    def test_multiple_substitutions_in_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multiple vars in one string."""
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: postgres://${DB_HOST}:${DB_PORT}/mydb\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["url"] == "postgres://localhost:5432/mydb"

    def test_substitution_in_nested_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Substitution works in nested structures."""
        monkeypatch.setenv("NESTED_VAR", "nested_value")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database:
  connection:
    host: ${NESTED_VAR}
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file))
        assert config["database"]["connection"]["host"] == "nested_value"

    def test_substitution_in_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Substitution works in list items."""
        monkeypatch.setenv("ITEM_VAR", "item_value")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("items:\n  - ${ITEM_VAR}\n  - static\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["items"] == ["item_value", "static"]

    def test_expand_vars_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disable substitution with expand_vars=False."""
        monkeypatch.setenv("SHOULD_NOT_EXPAND", "expanded")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: ${SHOULD_NOT_EXPAND}\n", encoding="utf-8")

        config = load_config(str(config_file), expand_vars=False)
        assert config["value"] == "${SHOULD_NOT_EXPAND}"

    def test_empty_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string default."""
        monkeypatch.delenv("EMPTY_DEFAULT_VAR", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: ${EMPTY_DEFAULT_VAR:-}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == ""


class TestLoadEnv:
    """Tests for loaden_env directive."""

    def test_load_dotenv_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Load vars from .env file."""
        monkeypatch.delenv("DOTENV_VAR", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("DOTENV_VAR=from_dotenv\n", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_env: .env\nvalue: ${DOTENV_VAR}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == "from_dotenv"
        assert os.environ.get("DOTENV_VAR") == "from_dotenv"

    def test_load_yaml_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Load vars from YAML env file."""
        monkeypatch.delenv("YAML_ENV_VAR", raising=False)

        env_file = tmp_path / "secrets.yaml"
        env_file.write_text("YAML_ENV_VAR: from_yaml\n", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "loaden_env: secrets.yaml\nvalue: ${YAML_ENV_VAR}\n", encoding="utf-8"
        )

        config = load_config(str(config_file))
        assert config["value"] == "from_yaml"

    def test_load_multiple_env_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Load multiple env files in order."""
        monkeypatch.delenv("MULTI_VAR1", raising=False)
        monkeypatch.delenv("MULTI_VAR2", raising=False)

        env1 = tmp_path / "first.env"
        env1.write_text("MULTI_VAR1=first\n", encoding="utf-8")

        env2 = tmp_path / "second.env"
        env2.write_text("MULTI_VAR2=second\n", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
loaden_env:
  - first.env
  - second.env
var1: ${MULTI_VAR1}
var2: ${MULTI_VAR2}
""",
            encoding="utf-8",
        )

        config = load_config(str(config_file))
        assert config["var1"] == "first"
        assert config["var2"] == "second"

    def test_shell_env_takes_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shell env vars are not overwritten by env files."""
        monkeypatch.setenv("PRECEDENCE_VAR", "from_shell")

        env_file = tmp_path / ".env"
        env_file.write_text("PRECEDENCE_VAR=from_file\n", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_env: .env\nvalue: ${PRECEDENCE_VAR}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == "from_shell"

    def test_dotenv_comments_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Comments in .env files are ignored."""
        monkeypatch.delenv("COMMENT_TEST", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\nCOMMENT_TEST=value\n# Another comment\n",
            encoding="utf-8",
        )

        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_env: .env\nvalue: ${COMMENT_TEST}\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert config["value"] == "value"

    def test_dotenv_quoted_values(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quoted values in .env have quotes stripped."""
        monkeypatch.delenv("QUOTED_DOUBLE", raising=False)
        monkeypatch.delenv("QUOTED_SINGLE", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text(
            "QUOTED_DOUBLE=\"double quoted\"\nQUOTED_SINGLE='single quoted'\n",
            encoding="utf-8",
        )

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "loaden_env: .env\ndouble: ${QUOTED_DOUBLE}\nsingle: ${QUOTED_SINGLE}\n",
            encoding="utf-8",
        )

        config = load_config(str(config_file))
        assert config["double"] == "double quoted"
        assert config["single"] == "single quoted"

    def test_loaden_env_removed_from_result(self, tmp_path: Path) -> None:
        """The loaden_env key is not present in final config."""
        env_file = tmp_path / ".env"
        env_file.write_text("SOME_VAR=value\n", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_env: .env\nkey: value\n", encoding="utf-8")

        config = load_config(str(config_file))
        assert "loaden_env" not in config

    def test_env_file_not_found(self, tmp_path: Path) -> None:
        """Raise error when env file doesn't exist."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("loaden_env: nonexistent.env\n", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="Env file not found"):
            load_config(str(config_file))
