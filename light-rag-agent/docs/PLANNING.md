# LightRAG API Server - Project Planning

## 🎯 Project Goals
- **Primary**: Provide REST API for LightRAG semantic search and chat functionality
- **Secondary**: Support document ingestion, conversation management, and monitoring
- **Performance**: Sub-50s response times with caching and timeout management

## 🏗️ Architecture Overview

### Core Components
1. **FastAPI Server** (`app/api/server.py`)
   - REST endpoints for chat, documents, configuration
   - JWT authentication with API key validation
   - Prometheus metrics collection
   - CORS middleware for web clients

2. **RAG Agent** (`app/agent/rag_agent.py`)
   - Pydantic AI agent with LightRAG integration
   - Cached agent instances for performance
   - Timeout management for long-running queries

3. **RAG Manager** (`app/core/rag.py`)
   - LightRAG initialization and lifecycle management
   - Dynamic OpenAI model selection with fallbacks
   - Temperature auto-adjustment for model compatibility

4. **Utilities**
   - **Authentication** (`app/utils/auth.py`): JWT token management
   - **Ingestion** (`app/utils/ingestion.py`): Document processing
   - **Diagnostics** (`app/utils/diagnostics.py`): Health checks

### Data Flow
```
Client Request → FastAPI → JWT Auth → RAG Agent → LightRAG → OpenAI API
                     ↓
              Conversation Storage → Response with Sources
```

## 🔧 Technology Stack
- **Framework**: FastAPI 0.110.0
- **RAG Engine**: LightRAG-HKU 1.3.0 with NanoVectorDB
- **AI Framework**: Pydantic AI with OpenAI integration
- **Authentication**: PyJWT 2.9.0
- **Async**: Built on asyncio with timeout management

## 📁 File Structure
```
LightRAG/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py          # FastAPI application (1182 lines - needs refactoring)
│   ├── agent/
│   │   ├── __init__.py
│   │   └── rag_agent.py       # Pydantic AI agent with caching
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration management
│   │   └── rag.py             # RAG manager and OpenAI integration
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # JWT authentication
│       ├── diagnostics.py     # Health checks and monitoring
│       ├── ingestion.py       # Document processing
│       └── logging.py         # Logging configuration
├── tests/                     # TO BE CREATED
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Container orchestration
└── terraform/                 # AWS deployment scripts
```

## 🚨 Current Issues & Technical Debt

### Critical (Needs Immediate Attention)
1. **Large Files**: `app/api/server.py` (1182 lines) violates 500-line rule
2. **Missing Tests**: No unit tests exist for any components
3. **504 Timeouts**: Recently fixed with timeout management

### Performance Optimizations (Recently Implemented)
- ✅ Agent caching increased from 32 to 256 instances
- ✅ RAG query caching with 5-minute TTL
- ✅ Async history building with lowered threshold (80→20)
- ✅ Optimized conversation cleanup with batching
- ✅ Comprehensive timeout management

## 🔐 Security & Authentication
- **JWT Bearer Tokens**: Required for most endpoints
- **API Key Authentication**: Required for token issuance
- **Rate Limiting**: Per-user request limits with sliding window
- **CORS**: Configured for cross-origin requests

## 📊 Monitoring & Observability
- **Prometheus Metrics**: Request counts, latencies, error rates
- **Structured Logging**: JSON logs with request IDs and phases
- **Health Endpoints**: `/health`, `/alb-health`, `/health-secure`

## 🔄 Deployment
- **Docker**: Multi-stage builds with production optimization
- **AWS**: Terraform scripts for ALB, ECS, and supporting infrastructure
- **Environment**: Support for `.env` files and environment variables

## 📋 Naming Conventions
- **Files**: snake_case (e.g., `rag_agent.py`)
- **Classes**: PascalCase (e.g., `RAGManager`)
- **Functions**: snake_case (e.g., `create_agent`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_HISTORY_MESSAGES`)
- **Environment Variables**: PREFIX_UPPER_SNAKE_CASE (e.g., `RAG_API_KEYS`)

## 🎯 Next Steps Priority
1. **Refactor server.py**: Split into multiple modules (<500 lines each)
2. **Add comprehensive tests**: Unit tests for all major components
3. **Documentation**: API documentation and setup guides
4. **Performance monitoring**: Add more detailed metrics collection