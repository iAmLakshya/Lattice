import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULTS_PATH = Path(__file__).parent / "defaults.toml"


@lru_cache(maxsize=1)
def load_defaults() -> dict[str, Any]:
    with DEFAULTS_PATH.open("rb") as f:
        return tomllib.load(f)


def get_config_value(*keys: str, default: Any = None) -> Any:
    config = load_defaults()
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value
