# Loaden

A reusable Python configuration loading module with YAML include support, deep merging, and validation.

## Features

- **YAML configuration loading** with clear error messages
- **Include support** - compose configs from multiple files
- **Deep merging** - nested dictionaries merge recursively
- **Environment variable injection** - set env vars from config
- **Required key validation** - fail fast on missing config
- **Circular include detection** - prevents infinite loops

## Installation

```bash
pip install -e .
```

Or add to your project's dependencies:

```toml
[project]
dependencies = [
    "loaden @ git+https://github.com/youruser/loaden.git",
]
```

## Quick Start

```python
from loaden import load_config

config = load_config("config.yaml")
print(config["database"]["host"])
```

## Usage

### Basic Configuration

Create a `config.yaml`:

```yaml
database:
  host: localhost
  port: 5432
  name: myapp

logging:
  level: INFO
```

Load it:

```python
from loaden import load_config

config = load_config("config.yaml")
# config = {"database": {"host": "localhost", "port": 5432, ...}, ...}
```

### Include Files

Split configuration across multiple files using `loaden_include`:

**base.yaml:**
```yaml
database:
  host: localhost
  port: 5432

logging:
  level: INFO
```

**config.yaml:**
```yaml
loaden_include: base.yaml

database:
  name: production_db

api:
  key: secret123
```

Result after loading `config.yaml`:
```python
{
    "database": {"host": "localhost", "port": 5432, "name": "production_db"},
    "logging": {"level": "INFO"},
    "api": {"key": "secret123"}
}
```

### Multiple Includes

Include multiple files - they merge in order, with later files overriding earlier ones:

```yaml
loaden_include:
  - defaults.yaml
  - database.yaml
  - local.yaml

app:
  name: myapp
```

### Nested Includes

Included files can include other files:

**common/logging.yaml:**
```yaml
logging:
  format: "%(levelname)s - %(message)s"
```

**base.yaml:**
```yaml
loaden_include: common/logging.yaml

database:
  pool_size: 5
```

**config.yaml:**
```yaml
loaden_include: base.yaml

database:
  host: prod.example.com
```

### Environment Variables

Set environment variables from config. Shell environment takes precedence:

```yaml
env:
  DATABASE_URL: postgres://localhost/myapp
  API_TIMEOUT: 30

database:
  url: ${DATABASE_URL}
```

```python
import os
from loaden import load_config

config = load_config("config.yaml")
print(os.environ["DATABASE_URL"])  # "postgres://localhost/myapp"
```

If `DATABASE_URL` is already set in your shell, the config value is ignored.

### Required Keys Validation

Fail fast if required configuration is missing:

```python
from loaden import load_config

config = load_config(
    "config.yaml",
    required_keys=["database.host", "database.port", "api.key"]
)
```

Raises `ValueError` with clear message if any key is missing:
```
ValueError: Invalid config: missing required keys in config.yaml: api.key
```

### Deep Merge

Use `deep_merge` directly for custom merging:

```python
from loaden import deep_merge

base = {"a": 1, "b": {"c": 2, "d": 3}}
overlay = {"b": {"d": 99, "e": 4}, "f": 5}

result = deep_merge(base, overlay)
# {"a": 1, "b": {"c": 2, "d": 99, "e": 4}, "f": 5}
```

## CLI

Loaden includes a command-line tool for working with config files.

### Validate

Check if a config file is valid:

```bash
loaden validate config.yaml
loaden validate config.yaml -v                    # verbose
loaden validate config.yaml -r "db.host,api.key"  # check required keys
```

### Show

Display resolved config (with includes merged):

```bash
loaden show config.yaml           # full config
loaden show config.yaml -k database  # specific section
```

### Combine

Merge multiple config files (later files override earlier):

```bash
loaden combine defaults.yaml local.yaml           # output to stdout
loaden combine defaults.yaml local.yaml -o out.yaml  # output to file
```

### Extract

Extract a section to a new file:

```bash
loaden extract config.yaml database              # output to stdout
loaden extract config.yaml database -o db.yaml   # output to file
```

## Merge Precedence

When using includes, values are merged with this precedence (highest wins):

1. Main config file
2. Later includes override earlier includes
3. Included files (in order listed)

## API Reference

### `load_config(config_path, required_keys=None)`

Load configuration from a YAML file.

**Parameters:**
- `config_path` (str): Path to the YAML config file
- `required_keys` (list[str] | None): Dot-separated keys that must exist (e.g., `["db.host", "api.key"]`)

**Returns:** `dict[str, Any]` - The configuration dictionary

**Raises:**
- `FileNotFoundError`: Config file doesn't exist
- `yaml.YAMLError`: Invalid YAML syntax
- `ValueError`: Config is not a dict, circular include, or missing required keys

### `deep_merge(base, overlay)`

Recursively merge two dictionaries.

**Parameters:**
- `base` (dict): Base dictionary
- `overlay` (dict): Dictionary to merge on top (takes precedence)

**Returns:** `dict` - New merged dictionary (inputs not modified)

## Development

```bash
# Create virtual environment
python3 -m venv ~/Environments/loaden
source ~/Environments/loaden/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint and format
ruff check .
ruff format .
```

## License

MIT
