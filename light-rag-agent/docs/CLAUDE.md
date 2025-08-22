### 🔄 Project Awareness & Context
- **Always read `PLANNING.md`** at the start of a new conversation to understand the project's architecture, goals, style, and constraints.
- **Check `TASK.md`** before starting a new task. If the task isn't listed, add it with a brief description and today's date.
- **Use consistent naming conventions, file structure, and architecture patterns** as described in `PLANNING.md`.

### 🧱 Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
- **Use clear, consistent imports** (prefer relative imports within packages).

### 🧪 Testing & Reliability
- **Always create Pytest unit tests for new features** (functions, classes, routes, etc).
- **After updating any logic**, check whether existing unit tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
  - Include at least:
    - 1 test for expected use
    - 1 edge case
    - 1 failure case
- When testing, always activate the virtual environment in venv_linux and run python commands with 'python3'

### 🔌 MCP Server Usage

#### Crawl4AI RAG MCP Server
- **Use for external documentation**: Get docs for Pydantic AI
- **Always check available sources first**: Use `get_available_sources` to see what's crawled.
- **Code examples**: Use `search_code_examples` when looking for implementation patterns.

#### Neon MCP Server  
- **Database project management**: Use `create_project` to create new Neon database projects.
- **Execute SQL**: Use `run_sql` to execute schema and data operations.
- **Table management**: Use `get_database_tables` and `describe_table_schema` for inspection.
- **Always specify project ID**: Pass the project ID to all database operations.
- **Example workflow**:
  1. `create_project` - create new database project
  2. `run_sql` with schema SQL - set up tables
  3. `get_database_tables` - verify schema creation
  4. Use returned connection string for application config

### ✅ Task Completion
- **Mark completed tasks in `TASK.md`** immediately after finishing them.
- Add new sub-tasks or TODOs discovered during development to `TASK.md` under a "Discovered During Work" section.

### 📎 Style & Conventions
- **Use Python** as the primary language.
- **Follow PEP8**, use type hints, and format with `black`.
- **Use `pydantic` for data validation**.
- Use `FastAPI` for APIs and `SQLAlchemy` or `SQLModel` for ORM if applicable.
- Write **docstrings for every function** using the Google style:
  ```python
  def example():
      """
      Brief summary.

      Args:
          param1 (type): Description.

      Returns:
          type: Description.
      """
  ```

### 📚 Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the why, not just the what.

### 🧠 AI Behavior Rules
- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** – only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to or if part of a task from `TASK.md`.

### 🚀 LightRAG Project Specific Guidelines

#### Architecture Overview
- **FastAPI server** with LightRAG backend for semantic search
- **Agent-based chat** using Pydantic AI with RAG tools
- **In-memory conversation management** with TTL cleanup
- **JWT authentication** with API key validation
- **Prometheus metrics** for monitoring

#### AI Model Configuration
- **Primary Model**: `gpt-5-mini` (latest, faster, cost-effective)
- **Fallback Models**: `gpt-4.1` → `gpt-4o-mini` (in priority order)
- **Embedding Model**: `text-embedding-3-large` (highest quality embeddings)
- **Model Selection Strategy**: Always prefer gpt-5-mini for new features, use fallbacks only for compatibility

#### Performance Optimization
- **Agent caching**: Use `@lru_cache(maxsize=256)` for agent instances
- **RAG result caching**: In-memory cache with TTL for frequent queries
- **Async operations**: Use `asyncio.wait_for()` with timeouts to prevent 504 errors
- **Background cleanup**: Automated conversation and cache cleanup

#### Environment Variables
```bash
# Core
OPENAI_API_KEY=your_api_key
RAG_API_KEYS=key1,key2,key3

# AI Models (Updated 2024)
OPENAI_MODEL=gpt-5-mini                    # Primary model (latest)
RAG_LLM_MODEL=gpt-5-mini                   # RAG language model
OPENAI_FALLBACK_MODELS=gpt-4.1,gpt-4o-mini # Fallback chain
RAG_EMBEDDING_MODEL=text-embedding-3-large # Embedding model

# Timeouts
OPENAI_TIMEOUT_SECONDS=45
RAG_AGENT_TIMEOUT_SECONDS=75
RAG_RETRIEVE_TIMEOUT_SECONDS=45

# Caching
RAG_CACHE_TTL_SECONDS=300
RAG_CHAT_CACHE_TTL_SECONDS=1800
RAG_HISTORY_ASYNC_THRESHOLD=20

# Limits
RAG_MAX_HISTORY_MESSAGES=12
RAG_USER_RATE_LIMIT=10
RAG_CONVERSATION_TTL_SECONDS=3600
```

#### File Structure Rules
- **`app/api/`**: FastAPI endpoints and server logic
- **`app/agent/`**: Pydantic AI agent definitions and tools
- **`app/core/`**: RAG management and core business logic
- **`app/utils/`**: Utility functions (auth, ingestion, diagnostics)
- **`tests/`**: Mirror structure of app/ for unit tests