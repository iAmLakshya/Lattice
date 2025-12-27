from pathlib import Path

IGNORE_PATTERNS = [
    "node_modules",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "coverage",
    ".coverage",
    "htmlcov",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
]

IGNORE_PATTERNS_STR = ", ".join(IGNORE_PATTERNS)


class MetadataPrompts:
    def __init__(self, repo_path: Path, project_name: str):
        self.repo_path = repo_path
        self.project_name = project_name

    def get_prompt(self, field_name: str) -> str:
        prompts = {
            "folder_structure": self._folder_structure_prompt(),
            "tech_stack": self._tech_stack_prompt(),
            "dependencies": self._dependencies_prompt(),
            "entry_points": self._entry_points_prompt(),
            "core_features": self._core_features_prompt(),
            "project_overview": self._project_overview_prompt(),
            "architecture_diagram": self._architecture_diagram_prompt(),
        }

        if field_name not in prompts:
            raise ValueError(f"Unknown metadata field: {field_name}")

        return prompts[field_name]

    def _folder_structure_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to generate a hierarchical folder structure showing the main directories and key files.

INSTRUCTIONS:
1. Use Glob to explore the directory structure
2. Use Read to examine key files like README.md for context
3. IGNORE these directories/files: {IGNORE_PATTERNS_STR}
4. Focus on meaningful directories (src, lib, tests, config, etc.)
5. For each directory, determine its PURPOSE
6. Include only the most important files at each level (not every file)
7. Maximum depth of 3 levels for the tree

OUTPUT FORMAT:
Return ONLY a valid JSON object with this exact structure:
```json
{{
  "name": "{self.project_name}",
  "type": "directory",
  "description": "Brief description of the project root",
  "purpose": "Main purpose of this directory",
  "children": [
    {{
      "name": "src",
      "type": "directory",
      "description": "Source code",
      "purpose": "Contains main application code",
      "children": [...]
    }},
    {{
      "name": "README.md",
      "type": "file",
      "description": "Project documentation"
    }}
  ]
}}
```

Start by exploring the directory structure, then return the JSON."""

    def _tech_stack_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to identify the technology stack used in this project.

INSTRUCTIONS:
1. Use Glob to find package/config files: package.json, pyproject.toml, requirements.txt, etc.
2. Read these files to extract framework and tool versions
3. Count files by extension to estimate language percentages: Glob("**/*.py"), Glob("**/*.ts"), etc.
4. Look for Dockerfile, docker-compose.yml, CI configs (.github/workflows, .gitlab-ci.yml) for tools
5. IGNORE: {IGNORE_PATTERNS_STR}

OUTPUT FORMAT:
Return ONLY a valid JSON object:
```json
{{
  "languages": [
    {{"name": "Python", "version": "3.11+", "usage_percentage": 85}},
    {{"name": "TypeScript", "version": "5.0+", "usage_percentage": 15}}
  ],
  "frameworks": [
    {{"name": "FastAPI", "version": "0.100+", "purpose": "REST API framework"}},
    {{"name": "React", "version": "18+", "purpose": "Frontend UI"}}
  ],
  "tools": ["Docker", "pytest", "GitHub Actions", "mypy"],
  "build_system": "hatch",
  "package_manager": "pip"
}}
```

Start by exploring the config files, then return the JSON."""

    def _dependencies_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to extract and categorize project dependencies.

INSTRUCTIONS:
1. Find and read dependency files:
   - Python: pyproject.toml, requirements.txt, setup.py
   - JavaScript/TypeScript: package.json
   - Rust: Cargo.toml
   - Go: go.mod
2. Categorize dependencies as runtime vs development
3. For KEY dependencies (5-10 most important), determine their PURPOSE
4. Count total dependencies

OUTPUT FORMAT:
Return ONLY a valid JSON object:
```json
{{
  "runtime": [
    {{"name": "openai", "version": ">=1.0.0", "purpose": "LLM API client"}},
    {{"name": "fastapi", "version": ">=0.100.0", "purpose": "Web framework"}}
  ],
  "development": [
    {{"name": "pytest", "version": ">=8.0.0", "purpose": "Testing framework"}},
    {{"name": "mypy", "version": ">=1.0.0", "purpose": "Type checking"}}
  ],
  "peer": [],
  "total_count": 25
}}
```

Start by reading the dependency files, then return the JSON."""

    def _entry_points_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to find all entry points - ways to run or use this project.

INSTRUCTIONS:
1. Check pyproject.toml for [project.scripts] (Python CLI entry points)
2. Check package.json for "scripts" and "bin" fields
3. Use Grep to find: if __name__ == "__main__"
4. Look for common entry files: main.py, app.py, server.py, index.js, index.ts
5. Check for Makefile targets
6. Look for app factory patterns: create_app(), app = FastAPI()

Entry point types:
- "cli": Command-line interface
- "api": REST/GraphQL API server
- "web": Web application
- "library": Python/npm package to import
- "script": Standalone script

OUTPUT FORMAT:
Return ONLY a valid JSON array:
```json
[
  {{
    "path": "src/myproject/main.py",
    "type": "cli",
    "description": "Main CLI entry point",
    "main_function": "main"
  }},
  {{
    "path": "src/myproject/api/app.py",
    "type": "api",
    "description": "FastAPI REST API server",
    "main_function": "app"
  }}
]
```

Start by exploring entry point patterns, then return the JSON."""

    def _core_features_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to identify the 5-10 core features/capabilities of this project.

INSTRUCTIONS:
1. Read README.md for high-level feature descriptions
2. Explore main source directories (src/, lib/, app/)
3. Look for distinct modules that represent features
4. For each feature, identify:
   - A clear name (e.g., "User Authentication", "Data Pipeline", "Graph Search")
   - A description of what it does
   - Key files that implement it
   - Related code entities (classes, functions)

IGNORE: {IGNORE_PATTERNS_STR}

OUTPUT FORMAT:
Return ONLY a valid JSON array:
```json
[
  {{
    "name": "Graph-based Code Search",
    "description": "Searches code relationships using Memgraph knowledge graph",
    "key_files": ["src/project/graph/search.py", "src/project/graph/builder.py"],
    "related_entities": ["GraphSearch", "GraphBuilder", "build_graph"]
  }},
  {{
    "name": "Vector Embeddings",
    "description": "Creates and indexes code embeddings for semantic search",
    "key_files": ["src/project/embeddings/embedder.py"],
    "related_entities": ["OpenAIEmbedder", "VectorIndexer"]
  }}
]
```

Start by exploring the codebase structure, then return the JSON."""

    def _project_overview_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to write a comprehensive 3-5 paragraph overview of this project.

INSTRUCTIONS:
1. Read README.md for official documentation
2. Read main entry points to understand what the project does
3. Explore the source structure to understand architecture

Write paragraphs covering:
1. **Purpose**: What the project IS and its main goals
2. **Architecture**: HOW it works at a high level
3. **Technology**: KEY technologies used and why
4. **Users**: WHO this project is for (target audience)
5. **Status**: Current capabilities and maturity

OUTPUT FORMAT:
Return your response as plain text paragraphs (NOT JSON).
Each paragraph should be 3-5 sentences.
Be specific and technical - reference actual module names, technologies, and patterns used.
Do not use markdown headers, just plain paragraphs separated by blank lines.

Start by reading the README and key files, then write the overview."""

    def _architecture_diagram_prompt(self) -> str:
        return f"""You are analyzing the codebase at: {self.repo_path}
Project name: {self.project_name}

Your task is to create an ASCII architecture diagram showing the main components and data flow.

INSTRUCTIONS:
1. Read key source files to understand the main components
2. Identify data flow between components
3. Include external services (databases, APIs)
4. Show user interaction points

DIAGRAM GUIDELINES:
- Use ASCII boxes: +--------+
- Use arrows for data flow: -->, <--, <-->
- Keep it readable (max 80 characters wide)
- Include a legend if needed
- Show 5-10 main components maximum

OUTPUT FORMAT:
Return ONLY the ASCII diagram as plain text. Example:

```
                    +------------------+
                    |     User/CLI     |
                    +--------+---------+
                             |
                             v
+----------------+    +------+------+    +----------------+
|   File Scanner |<---|  Pipeline   |--->|  Graph Builder |
+----------------+    +------+------+    +-------+--------+
                             |                   |
                             v                   v
                    +--------+--------+   +------+------+
                    |   Embedder      |   |  Memgraph   |
                    +--------+--------+   +-------------+
                             |
                             v
                    +--------+--------+
                    |     Qdrant      |
                    +-----------------+
```

Start by understanding the architecture, then create the diagram."""
