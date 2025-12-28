"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


@pytest.fixture
def sample_project_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture
def sample_python_file(sample_project_path: Path) -> Path:
    return sample_project_path / "src" / "models" / "user.py"


@pytest.fixture
def sample_typescript_file(sample_project_path: Path) -> Path:
    return sample_project_path / "frontend" / "components" / "LoginForm.tsx"


@pytest.fixture
def sample_docs_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_docs"


@pytest.fixture
def sample_markdown_file(sample_docs_path: Path) -> Path:
    return sample_docs_path / "authentication.md"


@pytest.fixture
def sample_markdown_content() -> str:
    return """# Test Document

## Overview

This is a test document for the `TestClass` implementation.

## TestClass

The `TestClass` handles operations like:

- Processing data
- Validating input
- Generating output

### process_data

```python
def process_data(input: str) -> dict
```

Processes the input data and returns a dictionary.

### validate

```python
def validate(data: dict) -> bool
```

Validates the data structure. Returns True if valid.

## Configuration

Set `MAX_RETRIES` to 3 for automatic retry on failure.
"""


@pytest.fixture
def sample_code_entities() -> set[str]:
    return {
        "TestClass",
        "TestClass.process_data",
        "TestClass.validate",
        "utils.helpers.format_output",
        "config.MAX_RETRIES",
    }
