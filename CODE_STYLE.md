# Code Style Guide

This document defines the coding standards and architectural patterns for Lattice. All contributions must adhere to these guidelines.

## Table of Contents

- [Formatting](#formatting)
- [Type Annotations](#type-annotations)
- [Naming Conventions](#naming-conventions)
- [Import Rules](#import-rules)
- [Module Architecture](#module-architecture)
- [Dependency Injection](#dependency-injection)
- [Design Patterns](#design-patterns)
- [File Organization](#file-organization)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Common Antipatterns](#common-antipatterns)

---

## Formatting

### Tooling

All code is automatically formatted and linted using:

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Ruff** | Linting + formatting | `pyproject.toml` |
| **mypy** | Static type checking (strict) | `pyproject.toml` |
| **pre-commit** | Git hooks | `.pre-commit-config.yaml` |
| **EditorConfig** | Editor consistency | `.editorconfig` |

### Line Length

- Maximum **100 characters** per line
- Configured in `pyproject.toml` under `[tool.ruff]`

### Indentation

- **4 spaces** for Python files
- **2 spaces** for YAML, JSON, and TOML files
- **Tabs** for Makefiles
- No trailing whitespace (except in Markdown)

### Imports

Imports are sorted automatically by Ruff in this order:

1. Standard library
2. Third-party packages
3. Local imports

```python
# Standard library
import logging
from collections.abc import Callable
from pathlib import Path

# Third-party
from pydantic import BaseModel

# Local
from lattice.shared import Settings
from lattice.indexing.api import create_pipeline_orchestrator
```

---

## Type Annotations

### Required Everywhere

All function signatures must have complete type annotations:

```python
# Correct
async def process_file(path: Path, options: ProcessOptions) -> ProcessResult:
    ...

# Incorrect - missing types
async def process_file(path, options):
    ...
```

### Union Syntax

Use the modern `|` union syntax, not `Optional` or `Union`:

```python
# Correct
def find_entity(name: str) -> Entity | None:
    ...

def parse(source: str | bytes) -> AST:
    ...

# Incorrect
from typing import Optional, Union

def find_entity(name: str) -> Optional[Entity]:  # Don't use Optional
    ...

def parse(source: Union[str, bytes]) -> AST:  # Don't use Union
    ...
```

### Collections

Use `collections.abc` for abstract types, built-in generics for concrete:

```python
from collections.abc import Callable, Iterable, Mapping, Sequence

# Abstract types from collections.abc
def process_items(items: Iterable[Item]) -> Sequence[Result]:
    ...

def transform(data: Mapping[str, Any], fn: Callable[[str], str]) -> dict[str, Any]:
    ...

# Concrete types use built-in generics
def get_names() -> list[str]:
    ...

def get_counts() -> dict[str, int]:
    ...
```

### Self Type

Use `Self` for methods returning the instance type:

```python
from typing import Self

class Builder:
    def with_option(self, value: str) -> Self:
        self._option = value
        return self
```

---

## Naming Conventions

### General Rules

| Element | Convention | Example |
|---------|------------|---------|
| Modules | `snake_case` | `query_planner.py` |
| Classes | `PascalCase` | `QueryPlanner` |
| Functions | `snake_case` | `create_query_engine` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| Private | `_leading_underscore` | `_internal_state` |
| Type aliases | `PascalCase` | `EntityMap = dict[str, Entity]` |

### Specific Patterns

```python
# Factory functions: create_<thing>
async def create_pipeline_orchestrator(...) -> PipelineOrchestrator:
    ...

# Async methods: use descriptive verbs
async def fetch_entities(self) -> list[Entity]:
    ...

async def process_batch(self, items: list[Item]) -> BatchResult:
    ...

# Boolean functions/properties: use is_, has_, can_, should_
def is_valid(self) -> bool:
    ...

def has_children(self) -> bool:
    ...

# Private instance attributes: single underscore prefix
class Engine:
    def __init__(self, client: Client):
        self._client = client  # Private
```

---

## Import Rules

### 1. Always Import from `api.py`

Each module exposes its public interface through `api.py`. Never import from internal modules:

```python
# Correct: Import from api.py
from lattice.indexing.api import PipelineOrchestrator, create_pipeline_orchestrator
from lattice.querying.api import QueryEngine, create_query_engine
from lattice.documents.api import DocumentService

# Incorrect: Importing from internal modules
from lattice.indexing.orchestrator import PipelineOrchestrator  # NO!
from lattice.querying.engine import QueryEngine  # NO!
```

### 2. Infrastructure Module for Adapters

External system adapters live in `infrastructure/`:

```python
# Database clients
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager
from lattice.infrastructure.postgres import PostgresClient

# LLM providers
from lattice.infrastructure.llm import get_llm_provider, get_embedding_provider
```

### 3. Shared Module for Cross-Cutting Concerns

```python
# Configuration
from lattice.shared import Settings, get_settings

# Exceptions
from lattice.shared import GraphError, QueryError, IndexingError

# Types and enums
from lattice.shared import EntityType, Language, PipelineStage

# Ports (abstract interfaces)
from lattice.shared.ports import GraphReader, GraphWriter, VectorReader

# Protocols
from lattice.shared.protocols import Embedder, VectorStore
```

### 4. Bootstrap for Wired Factories

The CLI bootstrap module provides fully-wired factory functions:

```python
from lattice.cli.bootstrap import (
    create_document_service,
    create_pipeline_orchestrator,
    create_query_engine,
)
```

---

## Module Architecture

Lattice follows **Modular Monolith + Hexagonal Architecture**.

### Bounded Contexts

Each major feature is a bounded context with clear boundaries:

```
src/lattice/
├── indexing/      # Indexing Pipeline context
├── querying/      # Query Engine context
├── documents/     # Documentation context
├── metadata/      # Project Metadata context
├── projects/      # Project Management context
├── parsing/       # Code Parsing support
└── summarization/ # Summarization support
```

### Standard Module Structure

Each bounded context follows this structure:

```
module/
├── api.py           # PUBLIC: Re-exports public interface
├── factory.py       # Creates fully-wired instances
├── service.py       # Main service class (thin orchestrator)
├── operations/      # Standalone operation functions
│   ├── create.py
│   ├── update.py
│   └── delete.py
└── models.py        # Domain models (if needed)
```

### API Files

API files contain only re-exports, no logic:

```python
# module/api.py
from module.factory import create_service
from module.service import Service
from module.models import Model

__all__ = [
    "create_service",
    "Service",
    "Model",
]
```

---

## Dependency Injection

### No Hidden Dependencies

All dependencies MUST be explicit in constructors. No optional parameters with internal fallbacks:

```python
# Correct: All dependencies required
class QueryEngine:
    def __init__(
        self,
        planner: QueryPlanner,
        graph_engine: GraphReasoningEngine,
        vector_searcher: VectorSearcher,
        responder: Responder,
    ):
        self._planner = planner
        self._graph_engine = graph_engine
        self._vector_searcher = vector_searcher
        self._responder = responder

# Incorrect: Hidden factory call
class QueryEngine:
    def __init__(
        self,
        planner: QueryPlanner | None = None,  # NO!
    ):
        self._planner = planner or QueryPlanner()  # Hidden instantiation!
```

### Factory Functions Wire Dependencies

Only factory functions should instantiate and assemble dependencies:

```python
# factory.py
async def create_query_engine() -> QueryEngine:
    settings = get_settings()

    # Create all dependencies
    planner = QueryPlanner(settings.query)
    graph_client = MemgraphClient()
    await graph_client.connect()
    graph_engine = GraphReasoningEngine(graph_client)
    vector_searcher = VectorSearcher(qdrant_client)
    responder = Responder(llm_provider)

    # Wire them together
    return QueryEngine(
        planner=planner,
        graph_engine=graph_engine,
        vector_searcher=vector_searcher,
        responder=responder,
    )
```

### Use Protocols for Abstraction

Define protocols in `shared/ports/` or `shared/protocols.py`:

```python
# shared/ports/graph.py
from typing import Protocol

class GraphReader(Protocol):
    async def find_entity(self, name: str) -> Entity | None: ...
    async def get_relationships(self, entity_id: str) -> list[Relationship]: ...

class GraphWriter(Protocol):
    async def create_entity(self, entity: Entity) -> str: ...
    async def create_relationship(self, rel: Relationship) -> None: ...
```

---

## Design Patterns

### Thin Orchestrators

Orchestrators coordinate but don't contain business logic:

```python
# Correct: Orchestrator delegates everything
class PipelineOrchestrator:
    def __init__(self, stages: list[PipelineStage]):
        self._stages = stages

    async def run(self, context: PipelineContext) -> PipelineResult:
        for stage in self._stages:
            await stage.execute(context)
        return context.result
```

### Stage Pattern

Pipeline stages implement a common protocol:

```python
class PipelineStage(Protocol):
    name: str

    async def execute(self, ctx: PipelineContext) -> None: ...

# Implementation
class ParseStage:
    name = "parse"

    def __init__(self, parser: CodeParser):
        self._parser = parser

    async def execute(self, ctx: PipelineContext) -> None:
        for file in ctx.files:
            ctx.parsed[file] = await self._parser.parse(file)
```

### Operations Pattern

Use standalone functions for discrete operations:

```python
# documents/operations/index.py
async def index_documents(
    path: Path,
    doc_repo: DocumentRepository,
    embedder: Embedder,
) -> IndexingResult:
    documents = await scan_directory(path)
    embeddings = await embedder.embed_batch(documents)
    await doc_repo.store(documents, embeddings)
    return IndexingResult(count=len(documents))
```

### Functions Over Classes

If a class would have no state or only one method, use a function instead:

```python
# Incorrect: Stateless class
class Validator:
    def validate(self, data: dict) -> bool:
        return "name" in data and "value" in data

# Correct: Just a function
def validate(data: dict) -> bool:
    return "name" in data and "value" in data
```

---

## File Organization

### Size Guidelines

| Category | Max Lines | Rationale |
|----------|-----------|-----------|
| Domain logic | 200 | Single responsibility |
| Adapters | 150 | Thin translation layer |
| Orchestrators | 100 | Coordination only |
| CLI commands | 100 | Parse args, call services |
| Stage classes | 80 | Single pipeline step |
| API files | 20 | Just re-exports |

### When to Split

Split a file when:

- It exceeds the size guideline
- It handles multiple distinct responsibilities
- You need to import only part of it frequently
- Testing requires mocking multiple unrelated things

### Directory Structure

```
feature/
├── api.py              # Public exports only
├── factory.py          # Dependency wiring
├── service.py          # Main orchestrator (<100 lines)
├── operations/         # Each operation in its own file
│   ├── create.py
│   └── update.py
├── models.py           # Domain models
└── queries/            # Database queries (if applicable)
    ├── read.py
    └── write.py
```

---

## Configuration

### No Magic Numbers

All configurable values go in `shared/config/defaults.toml`:

```toml
# shared/config/defaults.toml
[query]
default_limit = 15
max_results = 100
timeout_seconds = 30

[indexing]
batch_size = 50
max_concurrent_requests = 10
```

Access via settings:

```python
from lattice.shared import get_settings

settings = get_settings()
limit = settings.query.default_limit
```

### Externalized Prompts

LLM prompts live in `prompts/*.yaml`:

```yaml
# prompts/query.yaml
system_prompt: |
  You are a code analysis assistant. Your role is to help
  developers understand codebases by answering questions
  about structure, relationships, and implementation details.

entity_extraction: |
  Extract the following from the user query:
  - Entity names (functions, classes, modules)
  - Relationship types (calls, imports, extends)
  - Intent (explain, find, compare)
```

---

## Documentation

### No Comments

Code should be self-documenting through clear naming:

```python
# Incorrect: Comment explains what code does
# Check if the entity exists in the graph
if await graph.find_entity(name):
    ...

# Correct: Code is self-explanatory
if await graph.entity_exists(name):
    ...
```

### No Docstrings for Obvious Methods

Don't add docstrings that just repeat the method signature:

```python
# Incorrect: Docstring adds no value
async def get_user(self, user_id: str) -> User | None:
    """Get a user by their ID.

    Args:
        user_id: The ID of the user.

    Returns:
        The user if found, None otherwise.
    """
    return await self._repo.find(user_id)

# Correct: No docstring needed
async def get_user(self, user_id: str) -> User | None:
    return await self._repo.find(user_id)
```

### When to Use Docstrings

Add docstrings only when they provide non-obvious information:

```python
async def resolve_call(self, call: FunctionCall) -> Entity | None:
    """Resolve a function call to its target entity.

    Resolution order:
    1. Local scope (same module)
    2. Imported names (direct and aliased)
    3. Wildcard imports
    4. Built-in functions

    Returns None if the call cannot be resolved (e.g., dynamic calls).
    """
    ...
```

---

## Common Antipatterns

| Antipattern | Problem | Correct Pattern |
|-------------|---------|-----------------|
| Import from internal modules | Breaks encapsulation | Import from `api.py` |
| `Optional[T]` syntax | Outdated style | Use `T \| None` |
| Optional deps with fallback | Hidden dependencies | Required deps in constructor |
| God classes (500+ lines) | Too many responsibilities | Split into stages/operations |
| Hardcoded prompts | Hard to modify | Load from `prompts/*.yaml` |
| Magic numbers | Unclear meaning | Define in `defaults.toml` |
| Comments explaining code | Code not self-documenting | Use better naming |
| Docstrings restating types | Noise, no value | Omit obvious docstrings |
| Stateless single-method classes | Unnecessary abstraction | Use plain functions |
| Deeply nested code | Hard to follow | Early returns, extract functions |

### Examples

```python
# Antipattern: Deep nesting
def process(data):
    if data:
        if data.is_valid:
            if data.items:
                for item in data.items:
                    # ... buried logic

# Correct: Early returns
def process(data):
    if not data or not data.is_valid:
        return

    if not data.items:
        return

    for item in data.items:
        # ... clear logic
```

```python
# Antipattern: God class
class DataProcessor:
    def parse(self): ...
    def validate(self): ...
    def transform(self): ...
    def store(self): ...
    def notify(self): ...
    def cleanup(self): ...
    # 500+ lines...

# Correct: Split into focused components
class Parser: ...
class Validator: ...
class Transformer: ...
class Repository: ...
class Notifier: ...
```
