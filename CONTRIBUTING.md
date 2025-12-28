# Contributing to Lattice

This document outlines the standards and expectations for contributing to Lattice. For development setup instructions, see [README.md](README.md).

## Table of Contents

-   [Contribution Principles](#contribution-principles)
-   [Code Standards](#code-standards)
-   [Testing Requirements](#testing-requirements)
-   [Pull Request Requirements](#pull-request-requirements)
-   [Commit Conventions](#commit-conventions)
-   [Issue Guidelines](#issue-guidelines)
-   [Review Criteria](#review-criteria)

---

## Contribution Principles

### Scope and Focus

Every contribution should be **atomic and focused**. A pull request should address a single concern:

| Good                             | Bad                                        |
| -------------------------------- | ------------------------------------------ |
| Fix null pointer in query parser | Fix null pointer + refactor unrelated code |
| Add Rust language support        | Add Rust support + update CI + fix typos   |
| Refactor embedding pipeline      | Refactor + add new feature + update docs   |

If you find unrelated issues while working, open separate issues or PRs for them.

### Architectural Alignment

Contributions must align with Lattice's architecture:

-   **Modular Monolith**: Each bounded context (indexing, querying, documents) has clear boundaries
-   **Hexagonal Architecture**: Core logic is isolated from infrastructure adapters
-   **Dependency Injection**: No hidden dependencies; all dependencies are explicit in constructors

### Backwards Compatibility

Breaking changes require discussion before implementation. If your change:

-   Modifies public API signatures
-   Changes configuration file formats
-   Alters database schemas
-   Removes or renames exported symbols

Open an issue first to discuss the migration path.

---

## Code Standards

All contributions must follow the [Code Style Guide](CODE_STYLE.md). Key requirements:

### Type Safety

-   **Complete type annotations** on all function signatures
-   **Strict mypy compliance** with no `# type: ignore` without justification
-   **Modern syntax**: `str | None` not `Optional[str]`

```python
# Required
async def process(items: list[Item], limit: int | None = None) -> ProcessResult:
    ...

# Rejected
async def process(items, limit=None):  # Missing types
    ...
```

### Import Discipline

-   **Import from `api.py`** modules, never from internal implementation files
-   **Use infrastructure module** for external system adapters
-   **Use shared module** for cross-cutting concerns

```python
# Correct
from lattice.indexing.api import create_pipeline_orchestrator
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.shared import Settings, GraphError

# Rejected
from lattice.indexing.orchestrator import PipelineOrchestrator  # Internal import
```

### Dependency Injection

-   **No optional dependencies with fallbacks** in constructors
-   **Factory functions** handle all dependency wiring
-   **Protocols** define abstractions, not concrete classes

```python
# Correct: All dependencies required
class QueryEngine:
    def __init__(self, planner: QueryPlanner, searcher: VectorSearcher):
        self._planner = planner
        self._searcher = searcher

# Rejected: Hidden instantiation
class QueryEngine:
    def __init__(self, planner: QueryPlanner | None = None):
        self._planner = planner or QueryPlanner()  # Hidden dependency
```

### File Size Limits

| File Type               | Maximum Lines |
| ----------------------- | ------------- |
| Domain logic            | 200           |
| Infrastructure adapters | 150           |
| Orchestrators           | 100           |
| CLI commands            | 100           |
| Pipeline stages         | 80            |
| API files (re-exports)  | 20            |

Split files exceeding these limits into focused modules.

### Documentation Policy

-   **No comments** explaining what code does (code should be self-documenting)
-   **No redundant docstrings** that restate type signatures
-   **Docstrings only** when explaining non-obvious behavior, algorithms, or invariants

```python
# Rejected: Redundant docstring
async def get_user(self, user_id: str) -> User | None:
    """Get a user by ID."""  # Adds no value
    ...

# Accepted: Explains non-obvious behavior
async def resolve_call(self, call: FunctionCall) -> Entity | None:
    """Resolution order: local scope, imports, wildcards, builtins.
    Returns None for dynamic/unresolvable calls."""
    ...
```

---

## Testing Requirements

### Coverage Expectations

| Change Type | Testing Requirement                      |
| ----------- | ---------------------------------------- |
| New feature | Tests covering happy path and edge cases |
| Bug fix     | Regression test reproducing the bug      |
| Refactor    | Existing tests must continue to pass     |
| Performance | Benchmark showing improvement            |

### Test Quality Standards

Tests must be:

-   **Isolated**: No dependency on external services for unit tests
-   **Deterministic**: Same result on every run
-   **Fast**: Unit tests complete in milliseconds
-   **Descriptive**: Test names explain the scenario

```python
# Good test naming
async def test_parser_extracts_nested_class_methods() -> None: ...
async def test_query_engine_returns_empty_list_when_no_matches() -> None: ...
async def test_embedder_raises_on_invalid_input() -> None: ...

# Poor test naming
async def test_parser() -> None: ...
async def test_it_works() -> None: ...
```

### Integration Tests

Integration tests (requiring Docker services) must:

-   Be marked with `@pytest.mark.integration`
-   Clean up any created data
-   Not assume specific database state

---

## Pull Request Requirements

### Pre-Submission Checklist

Before opening a PR, ensure:

-   [ ] All tests pass (`pytest`)
-   [ ] Linting passes (`ruff check src/lattice`)
-   [ ] Formatting is correct (`ruff format --check src/lattice`)
-   [ ] Type checking passes (`mypy src/lattice`)
-   [ ] No unrelated changes included
-   [ ] Commit history is clean and logical

### PR Title Format

```
<type>: <concise description>
```

| Type       | Use When                              |
| ---------- | ------------------------------------- |
| `feat`     | Adding new functionality              |
| `fix`      | Correcting a bug                      |
| `refactor` | Restructuring without behavior change |
| `perf`     | Performance improvement               |
| `test`     | Adding or improving tests             |
| `docs`     | Documentation changes                 |
| `chore`    | Maintenance tasks (deps, CI, etc.)    |

Examples:

```
feat: add Rust language parser
fix: prevent null pointer in batch indexer
refactor: extract embedding logic to dedicated module
perf: optimize graph traversal with connection pooling
```

### PR Description

The description must include:

-   **Summary**: What this PR does and why
-   **Changes**: Bullet list of key modifications
-   **Testing**: How the changes were verified
-   **Related Issues**: Links using `Fixes #123` or `Relates to #123`

### Review Readiness

A PR is ready for review when:

-   CI passes (all automated checks green)
-   Description is complete
-   Changes are self-contained
-   No WIP or TODO comments remain

---

## Commit Conventions

### Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Subject Line Rules

-   Use **imperative mood**: "add" not "added" or "adds"
-   Maximum **72 characters**
-   No period at the end
-   Reference the component being changed

```
# Good
feat(parsing): add Python type stub support
fix(query): handle empty vector search results
refactor(indexing): split monolithic stage into focused modules

# Bad
Added python type stub support.  # Past tense, period, no type
fix stuff  # Vague, no scope
feat(parsing): Add support for parsing Python type stub files (.pyi)  # Too long
```

### Body Guidelines

-   Explain **why** the change was made, not what (the diff shows what)
-   Wrap at 72 characters
-   Use bullet points for multiple items

### Footer

-   Reference issues: `Fixes #123`, `Closes #456`
-   Note breaking changes: `BREAKING CHANGE: description`

### Example

```
feat(mcp): add semantic search tool

Enable Claude Code to find code by functionality description
rather than requiring exact function/class names.

- Implements vector similarity search over code embeddings
- Returns top-k results with relevance scores
- Supports filtering by language and entity type

Fixes #42
```

---

## Issue Guidelines

### Bug Reports

A useful bug report includes:

| Section          | Content                                   |
| ---------------- | ----------------------------------------- |
| **Description**  | Clear, concise explanation of the problem |
| **Reproduction** | Minimal steps to trigger the bug          |
| **Expected**     | What should happen                        |
| **Actual**       | What actually happens                     |
| **Environment**  | OS, Python version, Lattice version       |
| **Logs**         | Relevant error messages or stack traces   |

### Feature Requests

A useful feature request includes:

| Section          | Content                              |
| ---------------- | ------------------------------------ |
| **Problem**      | What limitation or pain point exists |
| **Proposal**     | Suggested solution                   |
| **Alternatives** | Other approaches considered          |
| **Context**      | Use cases, examples, or mockups      |

### Issue Labels

| Label              | Meaning                        |
| ------------------ | ------------------------------ |
| `bug`              | Something isn't working        |
| `enhancement`      | New feature or improvement     |
| `good first issue` | Suitable for new contributors  |
| `help wanted`      | Extra attention needed         |
| `breaking`         | Would require breaking changes |
| `wontfix`          | Not planned for implementation |

---

## Review Criteria

PRs are evaluated against these criteria:

### Must Pass

-   [ ] All CI checks green
-   [ ] Code follows [CODE_STYLE.md](CODE_STYLE.md)
-   [ ] Tests cover new/changed behavior
-   [ ] No security vulnerabilities introduced
-   [ ] No breaking changes without prior discussion

### Quality Factors

| Factor           | Expectation                                      |
| ---------------- | ------------------------------------------------ |
| **Clarity**      | Code is readable without comments explaining it  |
| **Simplicity**   | Solution is not over-engineered                  |
| **Consistency**  | Follows existing patterns in the codebase        |
| **Completeness** | Edge cases handled, errors reported meaningfully |
| **Testability**  | New code is easy to test in isolation            |

### Common Rejection Reasons

| Issue                          | Resolution                    |
| ------------------------------ | ----------------------------- |
| Imports from internal modules  | Use `api.py` exports          |
| Missing type annotations       | Add complete signatures       |
| Hidden dependencies            | Make dependencies explicit    |
| God classes (500+ lines)       | Split into focused components |
| Tests missing for new code     | Add comprehensive tests       |
| Unrelated changes bundled      | Split into separate PRs       |
| Magic numbers/hardcoded values | Use configuration             |

---

## Resources

-   [CODE_STYLE.md](CODE_STYLE.md) - Detailed coding standards
-   [README.md](README.md) - Project overview and setup
