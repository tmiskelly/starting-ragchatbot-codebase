import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
import tempfile
import shutil

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from vector_store import VectorStore
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator
from rag_system import RAGSystem

@pytest.fixture
def test_config():
    """Test configuration with minimal settings"""
    config = Config()
    config.ANTHROPIC_API_KEY = "test-key"
    config.CHROMA_PATH = "./test_chroma_db"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 3
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    return config

@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing"""
    mock_store = Mock(spec=VectorStore)
    
    # Mock the search method
    mock_store.search.return_value = Mock(
        documents=["Test document content", "Another test document"],
        metadata=[
            {"course_title": "Test Course", "lesson_number": 1},
            {"course_title": "Test Course", "lesson_number": 2}
        ],
        distances=[0.1, 0.2],
        error=None,
        is_empty=Mock(return_value=False)
    )
    
    # Mock course resolution
    mock_store._resolve_course_name.return_value = "Test Course"
    
    # Mock course catalog access
    mock_store.course_catalog = Mock()
    mock_store.course_catalog.get.return_value = {
        'metadatas': [{
            'title': 'Test Course',
            'course_link': 'http://example.com/course',
            'lessons_json': '[{"lesson_number": 1, "lesson_title": "Introduction"}, {"lesson_number": 2, "lesson_title": "Advanced Topics"}]'
        }]
    }
    
    # Mock link methods
    mock_store.get_lesson_link.return_value = "http://example.com/lesson/1"
    mock_store.get_course_link.return_value = "http://example.com/course"
    
    return mock_store

@pytest.fixture
def real_vector_store(test_config):
    """Real vector store for integration testing"""
    # Only create if we have the necessary components
    try:
        return VectorStore(test_config.CHROMA_PATH, test_config.EMBEDDING_MODEL, test_config.MAX_RESULTS)
    except Exception as e:
        pytest.skip(f"Cannot create real vector store: {e}")

@pytest.fixture
def course_search_tool(mock_vector_store):
    """CourseSearchTool with mock vector store"""
    return CourseSearchTool(mock_vector_store)

@pytest.fixture
def course_outline_tool(mock_vector_store):
    """CourseOutlineTool with mock vector store"""
    return CourseOutlineTool(mock_vector_store)

@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """ToolManager with registered tools"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock_client = Mock()
    
    # Mock successful response
    mock_response = Mock()
    mock_response.content = [Mock(text="Test AI response")]
    mock_response.stop_reason = "end_turn"
    
    mock_client.messages.create.return_value = mock_response
    
    return mock_client

@pytest.fixture
def ai_generator_with_mock(test_config, mock_anthropic_client):
    """AI Generator with mocked Anthropic client"""
    generator = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
    generator.client = mock_anthropic_client
    return generator

@pytest.fixture
def mock_rag_system(test_config):
    """Mock RAG system for API testing"""
    mock_rag = Mock(spec=RAGSystem)
    
    # Mock successful query response
    mock_rag.query.return_value = (
        "This is a test response",
        ["Source 1", "Source 2"],
        ["http://example.com/lesson/1", "http://example.com/lesson/2"]
    )
    
    # Mock course analytics
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course 1", "Test Course 2"]
    }
    
    # Mock session manager
    mock_session_manager = Mock()
    mock_session_manager.create_session.return_value = "test-session-123"
    mock_session_manager.clear_session.return_value = None
    mock_rag.session_manager = mock_session_manager
    
    return mock_rag

@pytest.fixture
def test_app(mock_rag_system):
    """FastAPI test app with mocked dependencies and no static files"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from pydantic import BaseModel
    from typing import List, Optional
    
    # Create minimal test app without static file mounting
    app = FastAPI(title="Course Materials RAG System - Test", root_path="")
    
    # Add middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Request/Response models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[str]
        source_links: List[Optional[str]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    class ClearSessionRequest(BaseModel):
        session_id: str
    
    # API endpoints
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        from fastapi import HTTPException
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            
            answer, sources, source_links = mock_rag_system.query(request.query, session_id)
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                source_links=source_links,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        from fastapi import HTTPException
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/session/clear")
    async def clear_session(request: ClearSessionRequest):
        from fastapi import HTTPException
        try:
            mock_rag_system.session_manager.clear_session(request.session_id)
            return {"status": "success", "message": f"Session {request.session_id} cleared"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app

@pytest.fixture
def client(test_app):
    """FastAPI test client"""
    return TestClient(test_app)

@pytest.fixture
def temp_directory():
    """Temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)