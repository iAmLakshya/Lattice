<p align="center">
  <h1 align="center">Lattice</h1>
  <p align="center">
    <strong>Graph-Augmented RAG for Code Intelligence</strong>
  </p>
  <p align="center">
    Build a knowledge graph of your codebase. Ask questions in natural language.<br/>
    Get answers grounded in both code structure and semantics.
  </p>
</p>

---

Lattice is a **hybrid retrieval system** that combines the precision of knowledge graphs with the flexibility of semantic search. Unlike traditional code search that finds files containing keywords, or semantic search that finds similar-looking code, Lattice understands how your code actually connects—the call chains, inheritance hierarchies, and module dependencies that define real software architecture.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   "How does authentication work?"                                           │
│                                                                             │
│         │                                                                   │
│         ▼                                                                   │
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │    Graph    │    │   Vector    │    │   Merged    │                    │
│   │   Search    │ +  │   Search    │ =  │   Results   │                    │
│   │             │    │             │    │             │                    │
│   │ "What calls │    │ "Similar to │    │ Complete    │                    │
│   │  AuthSvc?"  │    │  'login'"   │    │ auth flow   │                    │
│   └─────────────┘    └─────────────┘    └─────────────┘                    │
│                                                                             │
│         │                                                                   │
│         ▼                                                                   │
│                                                                             │
│   Answer: "Authentication flows through AuthMiddleware → AuthService →     │
│   TokenValidator. The middleware intercepts requests at line 45..."        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

- [Why Lattice?](#why-lattice)
- [How It Works](#how-it-works)
  - [The Indexing Pipeline](#the-indexing-pipeline)
  - [The Query Pipeline](#the-query-pipeline)
  - [Hybrid Ranking](#hybrid-ranking)
- [Features](#features)
  - [Structural Code Understanding](#structural-code-understanding)
  - [Documentation Intelligence](#documentation-intelligence)
  - [Multi-Project Support](#multi-project-support)
  - [MCP Integration](#mcp-integration)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Technology Stack](#technology-stack)
- [Status & Roadmap](#status--roadmap)

---

## Why Lattice?

Modern codebases are complex graphs of interconnected components. When you ask "How does payment processing work?", the answer isn't in a single file—it's spread across API handlers, service classes, validation logic, database operations, and error handlers, all connected through function calls and inheritance relationships.

Traditional search approaches each solve part of this problem:

| Approach | Strengths | Limitations |
|----------|-----------|-------------|
| **Keyword Search** | Fast, exact matches | Misses synonyms, can't follow relationships |
| **Semantic Search** | Understands meaning, finds similar code | No structural awareness, can't trace call chains |
| **Graph Traversal** | Maps exact relationships, traces dependencies | Requires knowing what to look for |

Lattice combines all three. When you query "What functions validate user input?", Lattice:

1. **Searches the knowledge graph** for entities with "validate" in their name or relationships
2. **Searches vector embeddings** for code semantically similar to "input validation"
3. **Fuses results** using a hybrid ranking algorithm that rewards code appearing in both searches
4. **Expands context** by traversing the graph to find callers, callees, and related classes
5. **Synthesizes an answer** grounded in actual code paths with source citations

This approach is inspired by [Microsoft's GraphRAG research](https://www.microsoft.com/en-us/research/project/graphrag/), which demonstrated that combining knowledge graphs with retrieval-augmented generation produces more comprehensive, grounded answers than either technique alone. The [original paper](https://arxiv.org/abs/2404.16130) showed particular improvements for questions requiring synthesis across multiple sources—exactly the kind of questions developers ask about codebases.

---

## How It Works

### The Indexing Pipeline

When you run `lattice index`, the system processes your codebase through six stages to build a queryable knowledge base:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INDEXING PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────┘

  Your Codebase
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 1: SCAN                                                          │
  │                                                                         │
  │  Recursively finds source files, respecting .gitignore patterns.        │
  │  Computes SHA-256 content hashes for incremental re-indexing.           │
  │  Only changed files are reprocessed on subsequent runs.                 │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 2: PARSE                                                         │
  │                                                                         │
  │  Uses tree-sitter to build Abstract Syntax Trees for each file.         │
  │  Extracts classes, functions, methods, imports, and their metadata.     │
  │  Resolves function calls to their targets using type inference.         │
  │  Tracks inheritance hierarchies and module dependencies.                │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 3: BUILD GRAPH                                                   │
  │                                                                         │
  │  Creates nodes for each code entity (Project, File, Class, Function).   │
  │  Creates edges for relationships (CALLS, EXTENDS, IMPORTS, DEFINES).    │
  │  Stores in Memgraph for sub-millisecond traversal queries.              │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 4: SUMMARIZE                                                     │
  │                                                                         │
  │  LLM generates natural language descriptions for each entity.           │
  │  Captures purpose, parameters, return values, and usage patterns.       │
  │  Summaries enable semantic matching even for poorly-named code.         │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 5: CHUNK                                                         │
  │                                                                         │
  │  Splits code into token-bounded segments (default: 1000 tokens).        │
  │  Maintains overlap between chunks (default: 200 tokens) for context.    │
  │  Preserves entity boundaries—functions aren't split mid-body.           │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  STAGE 6: EMBED                                                         │
  │                                                                         │
  │  Generates vector embeddings using your configured provider.            │
  │  Stores vectors in Qdrant with metadata linking back to graph nodes.    │
  │  Enables semantic similarity search across the entire codebase.         │
  └─────────────────────────────────────────────────────────────────────────┘
```

**Why Tree-sitter?** [Tree-sitter](https://github.com/tree-sitter/tree-sitter) is an incremental parsing library used by editors like VS Code, Neovim, and GitHub. It produces concrete syntax trees that are:
- **Fast**: Parses thousands of lines per millisecond
- **Incremental**: Re-parses only changed portions on file updates
- **Error-tolerant**: Produces useful ASTs even for syntactically incomplete code
- **Multi-language**: Supports 40+ languages with community-maintained grammars

### The Query Pipeline

When you ask a question, Lattice orchestrates multiple search strategies in parallel:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              QUERY PIPELINE                                  │
└──────────────────────────────────────────────────────────────────────────────┘

  "What functions call PaymentService.charge()?"
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  QUERY PLANNER                                                          │
  │                                                                         │
  │  Analyzes query intent using an LLM. Determines:                        │
  │  • Query type (find callers, explain implementation, search, etc.)      │
  │  • Target entities mentioned in the query                               │
  │  • Whether multi-hop graph traversal is needed                          │
  │  • Optimal weighting between graph and vector search                    │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                          ┌────────────────────────────────────────┴─────┐
                          │              PARALLEL EXECUTION              │
              ┌───────────┴───────────┐                    ┌─────────────┴───────────┐
              ▼                       │                    │                         ▼
  ┌───────────────────────┐           │                    │           ┌───────────────────────┐
  │     GRAPH SEARCH      │           │                    │           │    VECTOR SEARCH      │
  │                       │           │                    │           │                       │
  │  1. Locate target     │           │                    │           │  1. Embed the query   │
  │     entities by name  │           │                    │           │     using same model  │
  │                       │           │                    │           │                       │
  │  2. Traverse CALLS    │           │                    │           │  2. Search Qdrant for │
  │     relationships     │           │                    │           │     similar chunks    │
  │     (up to N hops)    │           │                    │           │                       │
  │                       │           │                    │           │  3. Return top-K with │
  │  3. Gather callers,   │           │                    │           │     similarity scores │
  │     callees, context  │           │                    │           │                       │
  └───────────┬───────────┘           │                    │           └───────────┬───────────┘
              │                       │                    │                       │
              └───────────────────────┴────────┬───────────┴───────────────────────┘
                                               │
                                               ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  HYBRID RANKER                                                          │
  │                                                                         │
  │  Merges results from both searches. For each result, computes:          │
  │  • Graph score: relationship proximity, entity match, centrality        │
  │  • Vector score: semantic similarity, code quality signals              │
  │  • Hybrid bonus: 10% boost for results appearing in both searches       │
  │                                                                         │
  │  Deduplicates by entity, applies per-file limits, returns top results.  │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                                                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  RESPONDER                                                              │
  │                                                                         │
  │  Builds context from ranked results: code snippets, summaries, paths.   │
  │  LLM synthesizes a natural language answer with source citations.       │
  │  Returns answer + sources with file paths and line numbers.             │
  └─────────────────────────────────────────────────────────────────────────┘
```

**Query Types**: The planner recognizes 17 different query intents, each with optimized handling:

| Intent | Example Query | Primary Strategy |
|--------|---------------|------------------|
| Find callers | "What calls this function?" | Graph traversal (CALLS edges) |
| Find callees | "What does this function call?" | Graph traversal (CALLS edges) |
| Trace call chain | "How does data flow from A to B?" | Graph pathfinding |
| Class hierarchy | "What inherits from BaseHandler?" | Graph traversal (EXTENDS edges) |
| Explain implementation | "How does caching work?" | Balanced graph + vector |
| Semantic search | "Find error handling code" | Vector-heavy ranking |
| Locate entity | "Where is the User class defined?" | Graph lookup + vector fallback |

### Hybrid Ranking

Combining graph and vector search requires careful result fusion. Lattice uses an approach inspired by [Reciprocal Rank Fusion (RRF)](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking), adapted for the code domain:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              HYBRID RANKING                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  Graph Results                              Vector Results
  ─────────────                              ──────────────
  1. PaymentService.charge (primary)         1. PaymentProcessor.run (0.92)
  2. OrderHandler.submit (caller, depth 1)   2. PaymentService.charge (0.89)
  3. CheckoutFlow.process (caller, depth 2)  3. StripeGateway.execute (0.85)
  4. PaymentValidator.check (callee)         4. OrderHandler.submit (0.81)

       │                                           │
       └─────────────────┬─────────────────────────┘
                         │
                         ▼

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  SCORING SIGNALS                                                        │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                         │
  │  Graph Signals:                     Vector Signals:                     │
  │  • Relationship type weight         • Cosine similarity score           │
  │  • Distance from target (decay)     • Content length penalty            │
  │  • Entity name match                • Entity type boost                 │
  │  • Centrality (in/out degree)       • Centrality (same as graph)        │
  │  • Context richness (has docs?)                                         │
  │                                                                         │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                                                                   ▼

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  ADAPTIVE WEIGHTING                                                     │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                         │
  │  Weights adjust based on query intent:                                  │
  │                                                                         │
  │  Intent              Graph Weight    Vector Weight                      │
  │  ──────────────────  ────────────    ─────────────                      │
  │  Find callers        0.80            0.20                               │
  │  Find hierarchy      0.85            0.15                               │
  │  Explain impl.       0.50            0.50                               │
  │  Semantic search     0.25            0.75                               │
  │  Find similar        0.20            0.80                               │
  │                                                                         │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                                                                   ▼

  Merged Results (Deduplicated)
  ─────────────────────────────
  1. PaymentService.charge    (0.95) ← Hybrid boost: in both lists
  2. OrderHandler.submit      (0.87) ← Hybrid boost: in both lists
  3. PaymentProcessor.run     (0.82)
  4. CheckoutFlow.process     (0.78)
  5. StripeGateway.execute    (0.71)
```

This adaptive approach ensures structural queries ("What calls X?") leverage the graph's precision, while exploratory queries ("Find code related to payments") leverage vectors' semantic flexibility.

---

## Features

### Structural Code Understanding

Lattice builds a property graph that captures the architecture of your codebase:

```
                         ┌───────────────────┐
                         │     Project       │
                         │   "my-project"    │
                         └─────────┬─────────┘
                                   │
                              CONTAINS
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │      File       │  │      File       │  │      File       │
     │  "auth.py"      │  │  "users.py"     │  │  "handlers.py"  │
     └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
              │                    │                    │
           DEFINES              DEFINES              DEFINES
              │                    │                    │
              ▼                    ▼                    ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │     Class       │  │     Class       │  │    Function     │
     │  "AuthService"  │  │  "UserModel"    │  │  "handle_req"   │
     └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
              │                    │                    │
       DEFINES_METHOD         EXTENDS                CALLS
              │                    │                    │
              ▼                    ▼                    ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │     Method      │  │     Class       │  │     Method      │
     │   "validate"    │  │   "BaseModel"   │  │   "validate"    │
     └─────────────────┘  └─────────────────┘  └─────────────────┘
```

**What relationships are captured:**

| Relationship | Meaning | Use Case |
|--------------|---------|----------|
| `CONTAINS` | Project contains files | Scope queries to a project |
| `DEFINES` | File defines class/function | Find where code is defined |
| `DEFINES_METHOD` | Class defines method | Navigate class structure |
| `EXTENDS` | Class inherits from parent | Trace inheritance hierarchies |
| `CALLS` | Function/method invokes another | Find all callers/callees |
| `IMPORTS` | File imports module | Trace dependencies |

**Advanced call resolution**: Lattice doesn't just track direct calls—it resolves:
- Method chains (`user.profile.save()`)
- Super calls with inheritance traversal
- Import aliases and re-exports
- IIFE patterns in JavaScript
- Built-in detection (won't create spurious edges for `print()`, `console.log()`, etc.)

This is powered by a type inference engine that tracks variable assignments and infers types from context, enabling accurate call graph construction even in dynamically-typed languages.

### Documentation Intelligence

Codebases often have documentation that drifts out of sync with actual implementation. Lattice treats documentation as a first-class citizen:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENTATION PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────┘

  docs/
  ├── api.md
  ├── architecture.md
  └── guides/
      └── auth.md
         │
         ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  DOCUMENT CHUNKING                                                      │
  │                                                                         │
  │  Unlike code chunking, documents are split by heading hierarchy:        │
  │                                                                         │
  │  # Authentication           ──────▶  Chunk 1: "Authentication"          │
  │  ## OAuth Flow                       heading_path: ["Authentication"]   │
  │  The OAuth flow starts...   ──────▶  Chunk 2: "OAuth Flow"              │
  │  ## Token Refresh                    heading_path: ["Authentication",   │
  │  Tokens expire after...                            "OAuth Flow"]        │
  │                                                                         │
  │  Heading context is preserved for better semantic matching.             │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                                                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  ENTITY LINKING                                                         │
  │                                                                         │
  │  Documents are linked to code entities through:                         │
  │                                                                         │
  │  • Explicit references: backticks like `AuthService.validate()`         │
  │  • Implicit links: semantic similarity to code summaries                │
  │                                                                         │
  │  Each link includes a confidence score and reasoning.                   │
  └────────────────────────────────────────────────────────────────┬────────┘
                                                                   │
                                                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  DRIFT DETECTION                                                        │
  │                                                                         │
  │  Lattice monitors alignment between docs and code:                      │
  │                                                                         │
  │  ┌─────────────────────────────────────────────────────────────────┐   │
  │  │ Document           │ Entity              │ Status    │ Score   │   │
  │  ├─────────────────────────────────────────────────────────────────┤   │
  │  │ docs/api.md        │ PaymentService      │ Aligned   │ 0.12    │   │
  │  │ docs/auth.md       │ AuthService         │ Minor     │ 0.45    │   │
  │  │ docs/cache.md      │ CacheManager        │ Major     │ 0.78    │   │
  │  └─────────────────────────────────────────────────────────────────┘   │
  │                                                                         │
  │  "Major drift" means the documentation describes behavior that          │
  │  no longer matches the implementation. Time to update docs!             │
  └─────────────────────────────────────────────────────────────────────────┘
```

**CLI for documentation:**

```bash
# Index documentation alongside code
lattice docs index ./docs --project my-project

# Check which docs have drifted
lattice docs drift --project my-project

# See how a specific doc links to code
lattice docs links --document docs/api.md --project my-project
```

### Multi-Project Support

Lattice isolates each indexed codebase as a separate project. This enables:

- **Cross-project queries**: Search across all projects or scope to one
- **Independent lifecycles**: Re-index one project without affecting others
- **Team workflows**: Different teams index their own services

```bash
# Index multiple projects
lattice index ./auth-service --name auth
lattice index ./payment-service --name payments
lattice index ./api-gateway --name gateway

# Query specific project
lattice query "How does token refresh work?" --project auth

# Query across all projects
lattice query "Where is PaymentIntent created?"

# Manage projects
lattice projects list
lattice projects show auth
lattice projects delete old-project --yes
```

### MCP Integration

[Model Context Protocol (MCP)](https://www.anthropic.com/news/model-context-protocol) is an open standard from Anthropic for connecting AI assistants to external tools. Lattice includes an MCP server that exposes its capabilities to Claude Code, Claude Desktop, and other MCP-compatible clients.

**What is MCP?** Think of MCP as a "USB-C for AI"—a standardized way for AI models to interact with external tools and data sources. Instead of building custom integrations for each AI assistant, you implement MCP once and any compatible client can use your tool.

**Available Tools:**

| Tool | Description | Example Use |
|------|-------------|-------------|
| `index_repository` | Index a codebase into the knowledge graph | "Index this repo so I can ask questions about it" |
| `query_code_graph` | Natural language questions with hybrid search | "How does the authentication flow work?" |
| `get_code_snippet` | Retrieve source code by fully qualified name | "Show me the code for PaymentService.charge" |
| `semantic_search` | Find code by functionality or intent | "Find all error handling code" |

**Setup with Claude Code:**

```bash
# Add Lattice as an MCP server
claude mcp add lattice -- uv run lattice mcp-server

# Or with a specific target repository
claude mcp add lattice \
  --env TARGET_REPO_PATH=/path/to/project \
  -- uv run lattice mcp-server
```

Once configured, Claude Code can automatically use Lattice to answer questions about your codebase, find relevant code, and trace through call chains—all without you explicitly invoking commands.

---

## Quick Start

### Prerequisites

- **Python 3.11+**: Required runtime
- **Docker**: For running Memgraph, Qdrant, and PostgreSQL
- **LLM API Key**: One of:
  - [OpenAI API key](https://platform.openai.com/api-keys) (default, recommended)
  - [Anthropic API key](https://console.anthropic.com/settings/keys) (Claude)
  - [Google AI API key](https://aistudio.google.com/app/apikey) (Gemini)
  - [Ollama](https://ollama.ai) installed locally (free, no API key)

### Step 1: Install Lattice

```bash
git clone https://github.com/your-org/lattice.git
cd lattice

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API key:

```env
# Option 1: OpenAI (default, easiest)
OPENAI_API_KEY=sk-...

# Option 2: Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
EMBEDDING_PROVIDER=openai  # Claude doesn't provide embeddings

# Option 3: Google Gemini
GOOGLE_API_KEY=...
LLM_PROVIDER=google
EMBEDDING_PROVIDER=google

# Option 4: Ollama (local, free)
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
# Make sure Ollama is running: ollama serve
# Pull a model: ollama pull llama3.2
```

### Step 3: Start Infrastructure

```bash
docker-compose up -d
```

This starts three services:

| Service | Port | Purpose |
|---------|------|---------|
| [Memgraph](https://github.com/memgraph/memgraph) | 7687 | Graph database for code structure |
| [Memgraph Lab](https://memgraph.com/docs/data-visualization) | 3000 | Visual graph explorer (optional) |
| [Qdrant](https://qdrant.tech) | 6333 | Vector database for semantic search |
| PostgreSQL | 5432 | Document metadata and drift tracking |

Verify everything is running:

```bash
docker ps
# Should show: memgraph, memgraph-lab, qdrant, postgres
```

### Step 4: Index Your First Project

```bash
lattice index /path/to/your/codebase --name my-project
```

You'll see progress through each stage:

```
Scanning files...                    ████████████████████ 100%
Parsing AST...                       ████████████████████ 100%
Building graph...                    ████████████████████ 100%
Generating summaries...              ████████████████████ 100%
Creating embeddings...               ████████████████████ 100%

✓ Indexed my-project
  Files: 247
  Entities: 1,832
  Graph nodes: 2,156
  Chunks embedded: 3,891
  Time: 2m 34s
```

### Step 5: Start Querying

```bash
# Ask a question
lattice query "How does user authentication work?"

# Search for code semantically
lattice search "database connection pooling"

# Get detailed reasoning
lattice query "What calls the PaymentService?" --verbose

# Check system status
lattice status
```

---

## CLI Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `lattice index <path>` | Index a codebase |
| `lattice query "<question>"` | Ask a natural language question |
| `lattice search "<query>"` | Semantic code search |
| `lattice status` | Show database statistics |
| `lattice settings` | Show current configuration |

**Index options:**

```bash
lattice index <path> \
  --name <project-name>    # Custom name (default: directory name)
  --force                  # Re-index all files, ignore cache
  --skip-metadata          # Skip AI metadata generation (faster)
```

**Query options:**

```bash
lattice query "<question>" \
  --project <name>         # Scope to specific project
  --limit <n>              # Max results (default: 15)
  --verbose                # Show reasoning and execution stats
```

### Project Management

```bash
# List all indexed projects with stats
lattice projects list

# Show detailed info for a project
lattice projects show <name>

# Delete a project and all its data
lattice projects delete <name> [--yes]
```

### Documentation

```bash
# Index markdown documentation
lattice docs index <path> --project <name> [--force]

# Check for documentation drift
lattice docs drift --project <name> [--document <path>] [--entity <name>]

# List indexed documents
lattice docs list --project <name> [--drifted] [--json]

# Show document details and chunks
lattice docs show <path> --project <name> [--chunks]

# View document-to-code links
lattice docs links --project <name> [--document <path>] [--entity <name>]
```

### Metadata

Lattice generates AI-powered project metadata including architecture diagrams, tech stack analysis, and feature documentation.

```bash
# View all metadata
lattice metadata show <name>

# View specific field
lattice metadata show <name> --field <field>
# Fields: overview, architecture, tech, features, deps, entry, folders

# Output as JSON
lattice metadata show <name> --json

# Regenerate metadata
lattice metadata regenerate <name> [--field <field>]
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LATTICE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌───────────────────────────────────────────────────────────────────┐   │
│    │                         DATA LAYER                                 │   │
│    ├───────────────────────────────────────────────────────────────────┤   │
│    │                                                                    │   │
│    │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │   │
│    │   │   Memgraph   │   │    Qdrant    │   │  PostgreSQL  │          │   │
│    │   │              │   │              │   │              │          │   │
│    │   │  Knowledge   │   │   Vector     │   │  Documents   │          │   │
│    │   │   Graph      │   │  Embeddings  │   │  & Metadata  │          │   │
│    │   │              │   │              │   │              │          │   │
│    │   │  Cypher      │   │  HNSW Index  │   │   asyncpg    │          │   │
│    │   │  Queries     │   │  Cosine Sim  │   │   Driver     │          │   │
│    │   └──────────────┘   └──────────────┘   └──────────────┘          │   │
│    │                                                                    │   │
│    └────────────────────────────────┬──────────────────────────────────┘   │
│                                     │                                       │
│    ┌────────────────────────────────┴──────────────────────────────────┐   │
│    │                        CORE ENGINE                                 │   │
│    ├───────────────────────────────────────────────────────────────────┤   │
│    │                                                                    │   │
│    │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │   │
│    │   │   Parsing    │   │   Indexing   │   │   Querying   │          │   │
│    │   │              │   │              │   │              │          │   │
│    │   │ Tree-sitter  │   │  Pipeline    │   │   Hybrid     │          │   │
│    │   │ Type Infer   │   │  Orchestr.   │   │   Ranking    │          │   │
│    │   │ Call Resol.  │   │  Stages      │   │   Planner    │          │   │
│    │   └──────────────┘   └──────────────┘   └──────────────┘          │   │
│    │                                                                    │   │
│    └────────────────────────────────┬──────────────────────────────────┘   │
│                                     │                                       │
│    ┌────────────────────────────────┴──────────────────────────────────┐   │
│    │                        AI PROVIDERS                                │   │
│    ├───────────────────────────────────────────────────────────────────┤   │
│    │                                                                    │   │
│    │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │   │
│    │   │  OpenAI  │  │Anthropic │  │  Google  │  │  Ollama  │         │   │
│    │   │          │  │          │  │          │  │          │         │   │
│    │   │ GPT-4o   │  │ Claude   │  │ Gemini   │  │ Llama    │         │   │
│    │   │ Ada-3    │  │ Sonnet   │  │ 1.5/2.0  │  │ Mistral  │         │   │
│    │   └──────────┘  └──────────┘  └──────────┘  └──────────┘         │   │
│    │                                                                    │   │
│    └───────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Database Details

| Component | Technology | Why We Chose It |
|-----------|------------|-----------------|
| **Graph Database** | [Memgraph](https://github.com/memgraph/memgraph) | In-memory graph DB with Cypher support, sub-millisecond traversals, MAGE algorithm library |
| **Vector Database** | [Qdrant](https://github.com/qdrant/qdrant) | Rust-based, high-performance HNSW indexing, rich filtering, excellent Python SDK |
| **Metadata Store** | PostgreSQL | Reliable, async driver (asyncpg), good for structured document metadata |

### Parsing

| Component | Technology | Purpose |
|-----------|------------|---------|
| **AST Parser** | [Tree-sitter](https://github.com/tree-sitter/tree-sitter) | Fast, incremental, error-tolerant parsing for 40+ languages |
| **Python Grammar** | tree-sitter-python | Extract classes, functions, decorators, type hints |
| **JS/TS Grammar** | tree-sitter-javascript, tree-sitter-typescript | Extract classes, functions, JSX, interfaces, type aliases |

### Supported Languages

| Language | Extensions | Features Extracted |
|----------|-----------|-------------------|
| Python | `.py` | Classes, functions, methods, decorators, type annotations, docstrings |
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs` | Classes, functions, arrow functions, methods, JSX components |
| TypeScript | `.ts`, `.tsx`, `.mts`, `.cts` | Classes, functions, interfaces, type aliases, generics |

### LLM Providers

| Provider | LLM Models | Embedding Models | Notes |
|----------|-----------|-----------------|-------|
| **OpenAI** | GPT-4o, GPT-4, GPT-3.5 | text-embedding-3-small (1536d), text-embedding-3-large (3072d) | Default, best quality |
| **Anthropic** | Claude Sonnet, Claude Opus, Claude Haiku | *(none—use another provider)* | Great for analysis |
| **Google** | Gemini 1.5 Flash/Pro, Gemini 2.0 | text-embedding-004 (768d) | Good alternative |
| **Ollama** | Llama 3.2, CodeLlama, Mistral, DeepSeek | nomic-embed-text, mxbai-embed-large | Free, local, private |

---

## Status & Roadmap

> **Work in Progress**: Lattice is under active development and not yet production-ready. APIs may change. We welcome feedback and contributions.

### What Works Today

- Index Python, TypeScript, and JavaScript codebases
- Hybrid graph+vector querying with natural language
- Documentation indexing with drift detection
- Multi-project support with isolation
- MCP server for Claude Code integration
- Incremental indexing (only changed files reprocessed)
- Multiple LLM/embedding provider options

### Roadmap

| Feature | Description | Status |
|---------|-------------|--------|
| **Git Integration** | Leverage commit history, blame data, and PR context for richer answers | Planned |
| **External Docs** | Index documentation from Notion, Confluence, and other hosted sources | Planned |
| **More Languages** | Go, Rust, Java, C/C++, Ruby parser support | Planned |
| **Agentic Analysis** | Autonomous code review, security scanning, and quality alerts | Planned |
| **Hosted Version** | Managed Lattice service—no infrastructure to run | Planned |
| **IDE Plugins** | VS Code, JetBrains integrations for in-editor querying | Exploring |

---

## Development

### Setup

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_parsing.py

# Specific test with verbose output
pytest tests/test_parsing.py::test_function_name -v

# With coverage
pytest --cov=lattice
```

### Code Quality

```bash
# Type checking
mypy src/lattice

# Linting
ruff check src/lattice

# Format code
ruff format src/lattice
```

### Infrastructure for Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f memgraph

# Stop services
docker-compose down

# Reset all data
docker-compose down -v
```

---

## Contributing

We welcome contributions! Whether it's:

- Bug reports and feature requests (open an issue)
- Documentation improvements
- New language parser support
- Performance optimizations
- Test coverage improvements

Please open an issue first to discuss significant changes.

---

## License

MIT

---

<p align="center">
  Built with <a href="https://memgraph.com">Memgraph</a>, <a href="https://qdrant.tech">Qdrant</a>, and <a href="https://github.com/tree-sitter/tree-sitter">Tree-sitter</a>
</p>
