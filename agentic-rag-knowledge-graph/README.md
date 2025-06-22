# Agentic RAG with Knowledge Graph

A comprehensive AI agent system that combines traditional RAG (Retrieval Augmented Generation) with knowledge graph capabilities to analyze and provide insights about big tech companies and their AI initiatives.

## Features

- **Hybrid Search**: Combines vector similarity search with knowledge graph traversal
- **Streaming Responses**: Real-time AI agent responses using Server-Sent Events
- **Semantic Chunking**: Intelligent document splitting using LLM-powered semantic analysis
- **Knowledge Graph Integration**: Entity extraction and relationship mapping using Graphiti
- **Production Ready**: FastAPI backend with comprehensive error handling and logging
- **Comprehensive Testing**: Full test suite with mocked dependencies

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │   FastAPI       │        │   Streaming SSE    │     │
│  │   Endpoints     │        │   Responses        │     │
│  └────────┬────────┘        └────────────────────┘     │
│           │                                              │
├───────────┴──────────────────────────────────────────────┤
│                    Agent Layer                           │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │  Pydantic AI    │        │   Agent Tools      │     │
│  │    Agent        │◄──────►│  - Vector Search   │     │
│  └────────┬────────┘        │  - Graph Search    │     │
│           │                 │  - Doc Retrieval   │     │
│           │                 └────────────────────┘     │
├───────────┴──────────────────────────────────────────────┤
│                  Storage Layer                           │
│  ┌─────────────────┐        ┌────────────────────┐     │
│  │   PostgreSQL    │        │      Neo4j         │     │
│  │   + pgvector    │        │   (via Graphiti)   │     │
│  └─────────────────┘        └────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Python 3.11+**: Primary language
- **Pydantic AI**: Agent framework
- **FastAPI**: API framework with streaming support
- **PostgreSQL + pgvector**: Vector database for similarity search
- **Neo4j + Graphiti**: Knowledge graph for relationship analysis
- **OpenAI API**: LLM and embedding generation
- **AsyncPG**: PostgreSQL async driver
- **Pytest**: Testing framework

## Installation

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 15+ with pgvector extension
- Neo4j 5.0+ database
- OpenAI/Gemini API key or Ollama

### System Dependencies

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install postgresql postgresql-contrib postgresql-15-pgvector
sudo apt install neo4j
```

#### macOS
```bash
brew install python@3.11
brew install postgresql
brew install --cask neo4j-desktop
```

#### Windows
- Install Python 3.11 from [python.org](https://python.org)
- Install PostgreSQL from [postgresql.org](https://postgresql.org)
- Install Neo4j Desktop from [neo4j.com](https://neo4j.com)

### Database Setup

#### PostgreSQL with pgvector

1. **Install pgvector extension** (if not already installed):
```bash
# Ubuntu/Debian
sudo apt install postgresql-15-pgvector

# From source
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

2. **Create database and user**:
```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE agentic_rag_db;
CREATE USER raguser WITH PASSWORD 'ragpass123';
GRANT ALL PRIVILEGES ON DATABASE agentic_rag_db TO raguser;
\q
```

3. **Enable pgvector extension**:
```bash
psql -U raguser -d agentic_rag_db
```
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\q
```

#### Neo4j Setup

1. **Install and start Neo4j**:
```bash
# Ubuntu/Debian
sudo systemctl start neo4j
sudo systemctl enable neo4j

# macOS
brew services start neo4j

# Or use Neo4j Desktop with GUI
```

2. **Set up authentication**:
```bash
# Connect to Neo4j
cypher-shell -u neo4j -p neo4j

# Change default password
ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'your_new_password';
:exit
```

### Python Environment Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd agentic-rag-knowledge-graph
```

2. **Create virtual environment**:
```bash
python3.11 -m venv venv_linux
source venv_linux/bin/activate  # Linux/macOS
# or
venv_linux\Scripts\activate     # Windows
```

3. **Install dependencies**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Configuration

1. **Copy environment template**:
```bash
cp .env.example .env
```

2. **Edit `.env` file** with your configuration:
```bash
# Database Configuration
DATABASE_URL=postgresql://raguser:ragpass123@localhost:5432/agentic_rag_db

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-small

# Application Configuration
APP_ENV=development
LOG_LEVEL=INFO
APP_HOST=0.0.0.0
APP_PORT=8000
```

3. **Initialize database schema**:
```bash
psql -U raguser -d agentic_rag_db -f sql/schema.sql
```

## Usage

### Running the System

#### 1. Start the API Server
```bash
# Activate virtual environment
source venv_linux/bin/activate

# Start the FastAPI server
python -m agent.api

# Or with custom settings
uvicorn agent.api:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Ingest Documents

First, add your markdown documents to the `documents/` folder:

```bash
# Create documents directory if it doesn't exist
mkdir -p documents

# Add your markdown files to the documents/ folder
# Example: documents/tech_company_analysis.md
#          documents/ai_research_overview.md
```

Then run the ingestion pipeline:

```bash
# Basic ingestion
python -m ingestion.ingest

# Clean existing data and re-ingest
python -m ingestion.ingest --clean

# Custom chunk size and settings
python -m ingestion.ingest --chunk-size 800 --chunk-overlap 150

# Disable semantic chunking for faster processing
python -m ingestion.ingest --no-semantic

# Verbose output
python -m ingestion.ingest --verbose
```

#### 3. Test the API

**Health Check**:
```bash
curl http://localhost:8000/health
```

**Chat (Non-streaming)**:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are Google'\''s main AI initiatives?",
    "search_type": "hybrid"
  }'
```

**Streaming Chat**:
```bash
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Compare Microsoft and Google'\''s AI strategies",
    "search_type": "hybrid"
  }'
```

**Vector Search**:
```bash
curl -X POST "http://localhost:8000/search/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "large language models",
    "limit": 5
  }'
```

**Knowledge Graph Search**:
```bash
curl -X POST "http://localhost:8000/search/graph" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Microsoft OpenAI partnership",
    "limit": 5
  }'
```

### API Documentation

Once the server is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc

### Example Queries

The system works best with queries about big tech companies and AI:

- "What AI research is Google working on?"
- "How are Microsoft and OpenAI related?"
- "Compare Apple's AI strategy with Google's approach"
- "What partnerships exist between tech companies for AI?"
- "Show me the timeline of Meta's AI announcements"
- "Which companies are investing in large language models?"

## Testing

### Running Tests

```bash
# Activate virtual environment
source venv_linux/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=agent --cov=ingestion --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Exclude slow tests

# Run specific test files
pytest tests/agent/test_models.py
pytest tests/ingestion/test_chunker.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Test Coverage

The test suite includes:

- **Unit Tests**: Individual component testing with mocked dependencies
- **Integration Tests**: End-to-end workflow testing
- **API Tests**: FastAPI endpoint testing
- **Database Tests**: PostgreSQL operation testing
- **Chunking Tests**: Document processing validation
- **Agent Tests**: Pydantic AI agent functionality

Target coverage: **>80%**

### Mocking

Tests use comprehensive mocking for:
- OpenAI API calls
- Database connections
- Neo4j/Graphiti operations
- File system operations

## Project Structure

```
agentic-rag-knowledge-graph/
├── agent/                          # AI agent components
│   ├── __init__.py
│   ├── agent.py                    # Main Pydantic AI agent
│   ├── api.py                      # FastAPI application
│   ├── db_utils.py                 # PostgreSQL utilities
│   ├── graph_utils.py              # Neo4j/Graphiti utilities
│   ├── models.py                   # Pydantic data models
│   ├── prompts.py                  # System prompts
│   └── tools.py                    # Agent tools
├── ingestion/                      # Document ingestion system
│   ├── __init__.py
│   ├── chunker.py                  # Semantic document chunking
│   ├── embedder.py                 # Embedding generation
│   ├── graph_builder.py            # Knowledge graph building
│   └── ingest.py                   # Main ingestion pipeline
├── sql/                            # Database schema
│   ├── schema.sql                  # Main schema file
│   └── migrations/                 # Migration scripts
├── tests/                          # Test suite
│   ├── agent/                      # Agent tests
│   ├── ingestion/                  # Ingestion tests
│   └── conftest.py                 # Pytest configuration
├── documents/                      # Document storage
│   └── sample_tech_companies.md    # Example document
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
├── pytest.ini                     # Pytest configuration
├── requirements.txt                # Python dependencies
├── PLANNING.md                     # Project architecture
├── TASK.md                         # Task tracking
└── README.md                       # This file
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI model for agent | `gpt-4-turbo-preview` |
| `EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `APP_ENV` | Application environment | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CHUNK_SIZE` | Default chunk size | `1000` |
| `CHUNK_OVERLAP` | Default chunk overlap | `200` |

### Chunking Configuration

- **Chunk Size**: 100-5000 characters (recommended: 1000)
- **Chunk Overlap**: 0-1000 characters (recommended: 200)
- **Max Chunk Size**: 500-10000 characters (recommended: 2000)
- **Semantic Chunking**: Uses LLM for intelligent splitting
- **Entity Extraction**: Identifies companies, technologies, people

### Search Configuration

- **Vector Similarity Threshold**: 0.0-1.0 (recommended: 0.7)
- **Search Result Limit**: 1-50 (recommended: 10)
- **Text Weight in Hybrid Search**: 0.0-1.0 (recommended: 0.3)

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Problem**: `connection to server at "localhost", port 5432 failed`

**Solutions**:
```bash
# Check PostgreSQL service
sudo systemctl status postgresql
sudo systemctl start postgresql

# Verify connection
psql -U raguser -d agentic_rag_db -c "SELECT 1;"
```

#### 2. pgvector Extension Missing

**Problem**: `extension "vector" does not exist`

**Solutions**:
```bash
# Install pgvector
sudo apt install postgresql-15-pgvector

# Or compile from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector && make && sudo make install

# Enable in database
psql -U raguser -d agentic_rag_db -c "CREATE EXTENSION vector;"
```

#### 3. Neo4j Connection Issues

**Problem**: `Failed to establish connection to server`

**Solutions**:
```bash
# Check Neo4j status
sudo systemctl status neo4j

# Check Neo4j configuration
sudo nano /etc/neo4j/neo4j.conf

# Restart Neo4j
sudo systemctl restart neo4j
```

#### 4. OpenAI API Rate Limits

**Problem**: `Rate limit exceeded`

**Solutions**:
- Check your OpenAI API usage and limits
- Implement retry logic (already included)
- Use smaller batch sizes for ingestion
- Consider using a different model tier

#### 5. Memory Issues During Ingestion

**Problem**: `Out of memory` during large document processing

**Solutions**:
```bash
# Reduce batch size
python -m ingestion.ingest --batch-size 10

# Disable semantic chunking
python -m ingestion.ingest --no-semantic

# Process documents individually
python -m ingestion.ingest --documents /path/to/single/doc.md
```

### Performance Optimization

#### Database Optimization

```sql
-- Increase shared_buffers for PostgreSQL
-- In postgresql.conf:
shared_buffers = 256MB
work_mem = 64MB
maintenance_work_mem = 256MB

-- Optimize vector search
REINDEX INDEX idx_chunks_embedding;
ANALYZE chunks;
```

#### Neo4j Optimization

```
# In neo4j.conf:
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
```

#### Application Optimization

- Use connection pooling (already configured)
- Enable Redis caching for embeddings (optional)
- Implement batch processing for large ingestions
- Use async operations throughout

### Monitoring

#### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
psql -U raguser -d agentic_rag_db -c "SELECT COUNT(*) FROM documents;"

# Neo4j health
cypher-shell -u neo4j -p password "MATCH (n) RETURN count(n) LIMIT 1;"
```

#### Logs

```bash
# Application logs
tail -f /var/log/agentic-rag.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-15-main.log

# Neo4j logs
tail -f /var/log/neo4j/neo4j.log
```

## Development

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run code formatting
black agent/ ingestion/ tests/
ruff check agent/ ingestion/ tests/

# Type checking
mypy agent/ ingestion/
```

### Adding New Features

1. **Create feature branch**:
```bash
git checkout -b feature/new-feature
```

2. **Write tests first** (TDD approach):
```bash
# Add tests in tests/
pytest tests/test_new_feature.py
```

3. **Implement feature**:
```bash
# Add implementation
# Update documentation
```

4. **Run full test suite**:
```bash
pytest --cov=agent --cov=ingestion
```

5. **Submit pull request**

### Code Style

- **Formatting**: Black (line length: 88)
- **Linting**: Ruff
- **Type Hints**: Required for all functions
- **Docstrings**: Google style for all public functions
- **Tests**: Comprehensive coverage >80%

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Implement the feature
5. Ensure all tests pass
6. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Search existing GitHub issues
3. Create a new issue with detailed information
4. Include logs and configuration details

---

Built with ❤️ using Pydantic AI, FastAPI, PostgreSQL, and Neo4j.