# Loaden

YAML config loader with file includes, `${VAR}` substitution, `.env` support, and deep merging.

```yaml
# config.yaml
loaden_include: base.yaml       # compose from multiple files
loaden_env: .env                # load environment files

database:
  host: ${DB_HOST:-localhost}   # env var with default
  password: ${DB_PASSWORD}      # from .env file
```

```python
from loaden import load_config, get

config = load_config("config.yaml")
host = get(config, "database.host", "127.0.0.1")  # safe nested access
```

## Features

- **File includes** - compose configs via `loaden_include: [base.yaml, local.yaml]`
- **Deep merging** - nested dicts merge recursively, later values win
- **`${VAR}` substitution** - expand env vars with optional defaults `${VAR:-default}`
- **`.env` file loading** - load env files via `loaden_env: .env`
- **Safe nested access** - `get(config, "db.host", default)` helper
- **Required key validation** - fail fast on missing config
- **CLI tool** - validate, show, combine, and extract configs

## Installation

```bash
pip install loaden
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

Loaden provides three ways to work with environment variables:

#### 1. Variable Substitution in Values

Use `${VAR}` or `${VAR:-default}` syntax in any string value:

```yaml
database:
  host: ${DB_HOST:-localhost}
  password: ${DB_PASSWORD}
  url: postgres://${DB_HOST:-localhost}:5432/myapp
```

```python
import os
os.environ["DB_HOST"] = "prod.example.com"

config = load_config("config.yaml")
print(config["database"]["host"])  # "prod.example.com"
print(config["database"]["url"])   # "postgres://prod.example.com:5432/myapp"
```

If a variable is not set and has no default, it remains as `${VAR}` in the output.

#### 2. Load Env Files with `loaden_env`

Load environment variables from `.env` or YAML files:

```yaml
loaden_env: .env
# or multiple files:
loaden_env:
  - .env
  - secrets.env

database:
  password: ${DB_PASSWORD}
```

**.env file format:**
```
# Comments are ignored
DB_HOST=localhost
DB_PASSWORD="secret123"
API_KEY='my-api-key'
```

**YAML env file format (secrets.yaml):**
```yaml
DB_PASSWORD: secret123
API_KEY: my-api-key
```

#### 3. Set Env Vars with `env` Section

Set environment variables from config (useful for child processes):

```yaml
env:
  DATABASE_URL: postgres://localhost/myapp
  API_TIMEOUT: 30
```

```python
import os
from loaden import load_config

config = load_config("config.yaml")
print(os.environ["DATABASE_URL"])  # "postgres://localhost/myapp"
```

Shell environment always takes precedence - existing vars are not overwritten.

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

### Safe Nested Access

Use `get()` to safely access nested keys without try/except:

```python
from loaden import load_config, get

config = load_config("config.yaml")

# Safe access with default
host = get(config, "database.host", "localhost")
timeout = get(config, "api.timeout", 30)

# Returns None if not found (no default specified)
optional = get(config, "maybe.missing")
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

### `load_config(config_path, required_keys=None, expand_vars=True)`

Load configuration from a YAML file.

**Parameters:**
- `config_path` (str): Path to the YAML config file
- `required_keys` (list[str] | None): Dot-separated keys that must exist (e.g., `["db.host", "api.key"]`)
- `expand_vars` (bool): Whether to expand `${VAR}` in values (default: True)

**Returns:** `dict[str, Any]` - The configuration dictionary

**Raises:**
- `FileNotFoundError`: Config file doesn't exist
- `yaml.YAMLError`: Invalid YAML syntax
- `ValueError`: Config is not a dict, circular include, or missing required keys

### `get(config, key_path, default=None)`

Safely get a nested key using dot notation.

**Parameters:**
- `config` (dict): Configuration dictionary
- `key_path` (str): Dot-separated path (e.g., `"database.host"`)
- `default` (Any): Value to return if key not found (default: None)

**Returns:** Value at key path, or default if not found

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
