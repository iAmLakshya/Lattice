"""Prompt templates for AI summarization."""

FILE_CODE_MAX_CHARS = 8000
FUNCTION_CODE_MAX_CHARS = 4000
CLASS_CODE_MAX_CHARS = 6000


class SummaryPrompts:
    """Collection of prompts for generating code summaries."""

    FILE_SUMMARY = """Analyze this source code file and create a search-optimized summary.

File: {file_path}
Language: {language}

Code:
```{language}
{content}
```

Create a summary that enables developers to find this file when searching. Include:

1. **Primary Purpose**: What problem does this file solve? What functionality does it
   provide? (Start with an action verb: "Handles...", "Provides...", "Implements...")

2. **Key Components**: List the main classes/functions with their purposes.
   Use terminology developers would search for.

3. **Integration Points**: What does this file depend on? What depends on it?
   (APIs, databases, external services, other modules)

4. **Technical Patterns**: Name any design patterns, architectural patterns, or
   notable techniques (e.g., "singleton", "repository pattern", "event-driven").

Write 3-5 sentences in natural language. Prioritize SEARCHABLE TERMS - include
action verbs (create, validate, transform, fetch, authenticate) and domain-specific
keywords that developers would use when looking for this functionality."""

    FUNCTION_SUMMARY = """Analyze this function and create a search-optimized summary.

Function: {name}
File: {file_path}
Signature: {signature}

Code:
```{language}
{code}
```

{docstring_section}

Create a summary optimized for semantic search. Structure your response as:

**What it does**: Start with a strong ACTION VERB describing the primary behavior
(e.g., "Validates...", "Transforms...", "Fetches...", "Calculates..."). Be specific
about WHAT is being acted upon.

**How it works**: Briefly describe the key logic, algorithms, or techniques used.
Mention any important libraries, APIs, or patterns.

**When to use**: What problem does this solve? In what scenarios would a developer
look for this function?

Write 2-3 sentences total. Use terminology that matches how developers would search
(e.g., "hash password" not "process credential", "parse JSON" not "handle data")."""

    CLASS_SUMMARY = """Analyze this class and create a search-optimized summary.

Class: {name}
File: {file_path}

Code:
```{language}
{code}
```

{docstring_section}

Create a summary optimized for semantic search. Include:

**Role & Responsibility**: What is this class's single responsibility? Use domain
terms (e.g., "Repository for user data", "Service for payment processing",
"Controller for API endpoints", "Model representing order entities").

**Design Pattern**: If applicable, name the pattern (Factory, Singleton, Strategy,
Observer, Repository, Service, DTO, Entity, etc.).

**Key Capabilities**: What are the 2-3 most important methods? What operations does
this class enable? Use action verbs.

**Relationships**: What does it inherit from? What interfaces does it implement?
What are its key dependencies?

Write 3-4 sentences. Focus on SEARCHABLE TERMINOLOGY that developers would use when
looking for this functionality. Include both the abstract concept ("handles auth")
and concrete details ("validates JWT tokens")."""

    CODEBASE_OVERVIEW = """Based on the file summaries, create a codebase overview.

File summaries:
{summaries}

Create an overview that helps developers understand and navigate this codebase:

**1. Purpose & Domain**: What problem does this codebase solve? What domain does it
   operate in? (e.g., "E-commerce platform", "API gateway", "Data pipeline")

**2. Architecture**: Describe the high-level architecture and patterns used:
   - Architectural style (monolith, microservices, layered, event-driven, etc.)
   - Key design patterns employed
   - Technology stack highlights

**3. Core Components**: List the main modules/packages and their responsibilities:
   - What each major component does
   - How they interact with each other

**4. Key Flows**: Describe 2-3 important workflows:
   - Entry points (main functions, API endpoints, event handlers)
   - Critical data flows or request paths

**5. Developer Guide**: What would a new developer need to know?
   - Where to look for common tasks
   - Important conventions or patterns to follow

Use clear, searchable terminology. This overview helps developers find relevant code
when they have questions about the system."""

    @staticmethod
    def _build_docstring_section(docstring: str | None) -> str:
        if docstring:
            return f"Existing docstring:\n{docstring}"
        return ""

    @classmethod
    def get_file_prompt(
        cls,
        file_path: str,
        language: str,
        content: str,
    ) -> str:
        return cls.FILE_SUMMARY.format(
            file_path=file_path,
            language=language,
            content=content[:FILE_CODE_MAX_CHARS],
        )

    @classmethod
    def get_function_prompt(
        cls,
        name: str,
        file_path: str,
        signature: str,
        code: str,
        language: str,
        docstring: str | None = None,
    ) -> str:
        return cls.FUNCTION_SUMMARY.format(
            name=name,
            file_path=file_path,
            signature=signature,
            code=code[:FUNCTION_CODE_MAX_CHARS],
            language=language,
            docstring_section=cls._build_docstring_section(docstring),
        )

    @classmethod
    def get_class_prompt(
        cls,
        name: str,
        file_path: str,
        code: str,
        language: str,
        docstring: str | None = None,
    ) -> str:
        return cls.CLASS_SUMMARY.format(
            name=name,
            file_path=file_path,
            code=code[:CLASS_CODE_MAX_CHARS],
            language=language,
            docstring_section=cls._build_docstring_section(docstring),
        )
