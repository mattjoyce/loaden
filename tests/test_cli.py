"""Tests for the loaden command-line interface."""

from __future__ import annotations

from pathlib import Path

import pytest

from loaden.cli import _print_error, main


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestCmdValidate:
    def test_valid_config_returns_zero(self, tmp_path: Path) -> None:
        cfg = _write(tmp_path / "config.yaml", "key: value\n")
        assert main(["validate", str(cfg)]) == 0

    def test_verbose_prints_key_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "a: 1\nb: 2\n")
        assert main(["validate", str(cfg), "-v"]) == 0
        out = capsys.readouterr().out
        assert "Valid:" in out
        assert "Keys: 2" in out

    def test_required_key_present_returns_zero(self, tmp_path: Path) -> None:
        cfg = _write(tmp_path / "config.yaml", "db:\n  host: localhost\n")
        assert main(["validate", str(cfg), "-r", "db.host"]) == 0

    def test_required_key_missing_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "db:\n  host: localhost\n")
        assert main(["validate", str(cfg), "-r", "db.port"]) == 1
        assert "missing required keys" in capsys.readouterr().err

    def test_missing_file_returns_one_and_prints_hint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["validate", str(tmp_path / "nope.yaml")]) == 1
        err = capsys.readouterr().err
        assert "Error: Config file not found" in err
        assert "Hint: pass the config file path" in err


class TestCmdShow:
    def test_full_config_dumped_as_yaml(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "name: demo\nport: 8080\n")
        assert main(["show", str(cfg)]) == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "port: 8080" in out

    def test_scalar_key_printed(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = _write(tmp_path / "config.yaml", "db:\n  host: prod.example.com\n")
        assert main(["show", str(cfg), "-k", "db.host"]) == 0
        assert "prod.example.com" in capsys.readouterr().out

    def test_dict_key_dumped_as_yaml(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "db:\n  host: localhost\n  port: 5432\n")
        assert main(["show", str(cfg), "-k", "db"]) == 0
        out = capsys.readouterr().out
        assert "host: localhost" in out
        assert "port: 5432" in out

    def test_unknown_key_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "a: 1\n")
        assert main(["show", str(cfg), "-k", "missing"]) == 1
        assert "Key not found: missing" in capsys.readouterr().err

    def test_missing_file_prints_error_and_hint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["show", str(tmp_path / "nope.yaml")]) == 1
        err = capsys.readouterr().err
        assert "Error: Config file not found" in err
        assert "Hint: pass the config file path" in err


class TestCmdCombine:
    def test_merges_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        a = _write(tmp_path / "a.yaml", "shared: 1\nonly_a: a\n")
        b = _write(tmp_path / "b.yaml", "shared: 2\nonly_b: b\n")
        assert main(["combine", str(a), str(b)]) == 0
        out = capsys.readouterr().out
        assert "shared: 2" in out  # later file wins
        assert "only_a: a" in out
        assert "only_b: b" in out

    def test_output_file_written(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        a = _write(tmp_path / "a.yaml", "x: 1\n")
        b = _write(tmp_path / "b.yaml", "y: 2\n")
        out_file = tmp_path / "out.yaml"
        assert main(["combine", str(a), str(b), "-o", str(out_file)]) == 0
        assert "Written to:" in capsys.readouterr().out
        written = out_file.read_text(encoding="utf-8")
        assert "x: 1" in written
        assert "y: 2" in written


class TestCmdExtract:
    def test_section_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = _write(
            tmp_path / "config.yaml",
            "database:\n  host: localhost\n  port: 5432\napi:\n  key: secret\n",
        )
        assert main(["extract", str(cfg), "database"]) == 0
        out = capsys.readouterr().out
        assert "host: localhost" in out
        assert "key: secret" not in out

    def test_section_to_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = _write(tmp_path / "config.yaml", "database:\n  host: localhost\n")
        out_file = tmp_path / "db.yaml"
        assert main(["extract", str(cfg), "database", "-o", str(out_file)]) == 0
        assert "Extracted 'database' to:" in capsys.readouterr().out
        assert "host: localhost" in out_file.read_text(encoding="utf-8")

    def test_non_dict_key_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "name: demo\n")
        assert main(["extract", str(cfg), "name"]) == 1
        assert "is not a section" in capsys.readouterr().err

    def test_unknown_key_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg = _write(tmp_path / "config.yaml", "a: 1\n")
        assert main(["extract", str(cfg), "missing"]) == 1
        assert "Key not found: missing" in capsys.readouterr().err


class TestMain:
    def test_no_subcommand_exits(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_unknown_subcommand_exits(self) -> None:
        with pytest.raises(SystemExit):
            main(["frobnicate"])


class TestPrintError:
    def test_filenotfound_appends_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        _print_error(FileNotFoundError("Config file not found: x.yaml"))
        err = capsys.readouterr().err
        assert "Error: Config file not found: x.yaml" in err
        assert "Hint: pass the config file path" in err

    def test_other_error_has_no_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        _print_error(ValueError("bad config"))
        err = capsys.readouterr().err
        assert "Error: bad config" in err
        assert "Hint:" not in err
