# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Course Materials RAG (Retrieval-Augmented Generation) System that enables users to query course materials using semantic search and AI-powered responses. The system uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides a web interface for interaction.

## Development Commands

### Starting the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Package Management
```bash
# Install dependencies
uv sync

# Run Python commands in the virtual environment
uv run <command>
```

### Code Quality Tools
```bash
# Auto-format code (black + isort)
./scripts/format.sh

# Run quality checks (black, isort, flake8, mypy)
./scripts/quality.sh

# Individual commands
uv run black backend/           # Format with black
uv run isort backend/           # Sort imports
uv run flake8 backend/          # Lint with flake8
uv run mypy backend/            # Type check with mypy
```

### Environment Setup
- Create `.env` file with `ANTHROPIC_API_KEY=your_key_here`
- The application requires Python 3.13 or higher

## Architecture Overview

### Backend Structure (`/backend/`)
- **FastAPI Application** (`app.py`): Main web server with CORS, static file serving, and API endpoints
- **RAG System** (`rag_system.py`): Central orchestrator managing all components
- **Vector Store** (`vector_store.py`): ChromaDB-based storage with separate collections for course metadata and content
- **AI Generator** (`ai_generator.py`): Anthropic Claude integration with tool support
- **Document Processor** (`document_processor.py`): Processes course documents into structured data and chunks
- **Search Tools** (`search_tools.py`): Tool-based search system for AI to query the vector store
- **Session Manager** (`session_manager.py`): Manages conversation history
- **Models** (`models.py`): Pydantic models for Course, Lesson, and CourseChunk
- **Config** (`config.py`): Centralized configuration using environment variables

### Frontend Structure (`/frontend/`)
- Simple HTML/CSS/JavaScript interface served as static files
- Chat interface for querying course materials
- Course statistics sidebar

### Key Architectural Patterns

1. **Tool-Based AI Search**: The AI uses tools to search the vector store rather than direct RAG, allowing for more sophisticated query handling and course resolution.

2. **Dual Vector Collections**: 
   - `course_catalog`: Stores course metadata for semantic course name resolution
   - `course_content`: Stores actual course content chunks for retrieval

3. **Session Management**: Maintains conversation history with configurable limits (default: 2 exchanges).

4. **Incremental Loading**: Documents are only processed if they don't already exist in the vector store.

## Key Configuration Settings

Located in `backend/config.py`:
- `CHUNK_SIZE: 800` - Size of text chunks for vector storage
- `CHUNK_OVERLAP: 100` - Characters to overlap between chunks  
- `MAX_RESULTS: 5` - Maximum search results to return
- `MAX_HISTORY: 2` - Number of conversation messages to remember
- `EMBEDDING_MODEL: "all-MiniLM-L6-v2"` - Sentence transformer model
- `ANTHROPIC_MODEL: "claude-sonnet-4-20250514"` - Claude model version

## Data Flow

1. Course documents in `/docs/` are processed on startup
2. Documents are chunked and stored in ChromaDB with metadata
3. User queries trigger AI generation with tool access
4. AI uses search tools to find relevant course content
5. Response is generated using retrieved context and conversation history

## Important Notes

- The system automatically loads documents from `../docs` on startup
- ChromaDB data is persisted in `backend/chroma_db/`
- No traditional testing framework is configured - manual testing via the web interface
- The application serves the frontend at the root path and API at `/api/*`
- always use uv to run the server do not use pip directly
- make to use uv to manage all dependencies