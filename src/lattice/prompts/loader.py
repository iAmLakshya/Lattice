from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompts(category: str) -> dict[str, Any]:
    path = PROMPTS_DIR / f"{category}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def get_prompt(category: str, name: str, **kwargs: Any) -> str:
    prompts = load_prompts(category)
    if name not in prompts:
        raise KeyError(f"Prompt '{name}' not found in category '{category}'")

    prompt_data = prompts[name]
    template = prompt_data.get("template") if isinstance(prompt_data, dict) else prompt_data

    if kwargs:
        return template.format(**kwargs)
    return template


def clear_cache() -> None:
    load_prompts.cache_clear()
