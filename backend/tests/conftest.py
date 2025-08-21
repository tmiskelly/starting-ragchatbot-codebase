import os
import sys
from unittest.mock import MagicMock, Mock

import pytest

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after path setup to avoid import errors
from ai_generator import AIGenerator  # noqa: E402
from config import Config  # noqa: E402
from rag_system import RAGSystem  # noqa: E402
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager  # noqa: E402
from vector_store import VectorStore  # noqa: E402


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
            {"course_title": "Test Course", "lesson_number": 2},
        ],
        distances=[0.1, 0.2],
        error=None,
        is_empty=Mock(return_value=False),
    )

    # Mock course resolution
    mock_store._resolve_course_name.return_value = "Test Course"

    # Mock course catalog access
    mock_store.course_catalog = Mock()
    mock_store.course_catalog.get.return_value = {
        "metadatas": [
            {
                "title": "Test Course",
                "course_link": "http://example.com/course",
                "lessons_json": '[{"lesson_number": 1, "lesson_title": "Introduction"}, {"lesson_number": 2, "lesson_title": "Advanced Topics"}]',
            }
        ]
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
        return VectorStore(
            test_config.CHROMA_PATH,
            test_config.EMBEDDING_MODEL,
            test_config.MAX_RESULTS,
        )
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
