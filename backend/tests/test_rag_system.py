from unittest.mock import MagicMock, Mock, patch

import pytest
from rag_system import RAGSystem


class TestRAGSystemInitialization:
    """Test RAG system initialization"""

    def test_init_components(self, test_config):
        """Test that all components are properly initialized"""
        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)

            # Verify all components exist
            assert hasattr(rag_system, "document_processor")
            assert hasattr(rag_system, "vector_store")
            assert hasattr(rag_system, "ai_generator")
            assert hasattr(rag_system, "session_manager")
            assert hasattr(rag_system, "tool_manager")
            assert hasattr(rag_system, "search_tool")
            assert hasattr(rag_system, "outline_tool")

    def test_tool_registration(self, test_config):
        """Test that tools are properly registered"""
        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
        ):

            # Mock the tools
            mock_search_tool = Mock()
            mock_outline_tool = Mock()
            mock_tool_manager = Mock()

            with (
                patch("rag_system.CourseSearchTool", return_value=mock_search_tool),
                patch("rag_system.CourseOutlineTool", return_value=mock_outline_tool),
                patch("rag_system.ToolManager", return_value=mock_tool_manager),
            ):

                rag_system = RAGSystem(test_config)

                # Verify tools were registered
                assert mock_tool_manager.register_tool.call_count == 2
                mock_tool_manager.register_tool.assert_any_call(mock_search_tool)
                mock_tool_manager.register_tool.assert_any_call(mock_outline_tool)


class TestRAGSystemQuery:
    """Test RAG system query processing"""

    def test_query_without_session(self, test_config):
        """Test query processing without session ID"""
        # Mock all dependencies
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test response"

        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []
        mock_tool_manager.get_last_sources.return_value = ["Source 1"]
        mock_tool_manager.get_last_source_links.return_value = ["http://link1"]

        mock_session_manager = Mock()

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            response, sources, source_links = rag_system.query("What is Python?")

            assert response == "Test response"
            assert sources == ["Source 1"]
            assert source_links == ["http://link1"]

            # Verify AI generator was called correctly
            mock_ai_generator.generate_response.assert_called_once()
            call_args = mock_ai_generator.generate_response.call_args
            assert (
                call_args[1]["query"]
                == "Answer this question about course materials: What is Python?"
            )
            assert call_args[1]["conversation_history"] is None
            assert call_args[1]["tool_manager"] == mock_tool_manager

    def test_query_with_session(self, test_config):
        """Test query processing with session ID"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Response with history"

        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []
        mock_tool_manager.get_last_sources.return_value = []
        mock_tool_manager.get_last_source_links.return_value = []

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = (
            "Previous conversation"
        )

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            response, sources, source_links = rag_system.query(
                "Follow-up question", session_id="test_session"
            )

            # Verify session history was retrieved
            mock_session_manager.get_conversation_history.assert_called_once_with(
                "test_session"
            )

            # Verify AI generator received history
            call_args = mock_ai_generator.generate_response.call_args
            assert call_args[1]["conversation_history"] == "Previous conversation"

            # Verify session was updated
            mock_session_manager.add_exchange.assert_called_once_with(
                "test_session", "Follow-up question", "Response with history"
            )

    def test_query_tool_definitions_passed(self, test_config):
        """Test that tool definitions are passed to AI generator"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Tool-aware response"

        mock_tool_manager = Mock()
        tool_definitions = [
            {"name": "search_course_content", "description": "Search tool"},
            {"name": "get_course_outline", "description": "Outline tool"},
        ]
        mock_tool_manager.get_tool_definitions.return_value = tool_definitions
        mock_tool_manager.get_last_sources.return_value = []
        mock_tool_manager.get_last_source_links.return_value = []

        mock_session_manager = Mock()

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            response, sources, source_links = rag_system.query("Search for content")

            # Verify tools were passed to AI generator
            call_args = mock_ai_generator.generate_response.call_args
            assert call_args[1]["tools"] == tool_definitions

    def test_query_sources_reset(self, test_config):
        """Test that sources are reset after retrieval"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Response"

        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []
        mock_tool_manager.get_last_sources.return_value = ["Source"]
        mock_tool_manager.get_last_source_links.return_value = ["Link"]

        mock_session_manager = Mock()

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            response, sources, source_links = rag_system.query("Test query")

            # Verify sources were reset after retrieval
            mock_tool_manager.reset_sources.assert_called_once()


class TestRAGSystemDocumentProcessing:
    """Test document processing functionality"""

    def test_add_course_document_success(self, test_config):
        """Test successful course document addition"""
        mock_document_processor = Mock()
        mock_course = Mock()
        mock_course.title = "Test Course"
        mock_chunks = [Mock(), Mock()]  # 2 chunks
        mock_document_processor.process_course_document.return_value = (
            mock_course,
            mock_chunks,
        )

        mock_vector_store = Mock()

        with (
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
            patch("rag_system.ToolManager"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.document_processor = mock_document_processor
            rag_system.vector_store = mock_vector_store

            course, chunk_count = rag_system.add_course_document("/path/to/course.pdf")

            assert course == mock_course
            assert chunk_count == 2

            # Verify document processing was called
            mock_document_processor.process_course_document.assert_called_once_with(
                "/path/to/course.pdf"
            )

            # Verify vector store operations
            mock_vector_store.add_course_metadata.assert_called_once_with(mock_course)
            mock_vector_store.add_course_content.assert_called_once_with(mock_chunks)

    def test_add_course_document_error(self, test_config):
        """Test handling of document processing errors"""
        mock_document_processor = Mock()
        mock_document_processor.process_course_document.side_effect = Exception(
            "Processing failed"
        )

        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
            patch("rag_system.ToolManager"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.document_processor = mock_document_processor

            course, chunk_count = rag_system.add_course_document("/invalid/path")

            assert course is None
            assert chunk_count == 0

    def test_add_course_folder_skip_existing(self, test_config):
        """Test that existing courses are skipped"""
        mock_document_processor = Mock()
        mock_course = Mock()
        mock_course.title = "Existing Course"
        mock_document_processor.process_course_document.return_value = (mock_course, [])

        mock_vector_store = Mock()
        mock_vector_store.get_existing_course_titles.return_value = ["Existing Course"]

        with (
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
            patch("rag_system.ToolManager"),
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["course1.pdf"]),
            patch("os.path.isfile", return_value=True),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.document_processor = mock_document_processor
            rag_system.vector_store = mock_vector_store

            courses, chunks = rag_system.add_course_folder("/docs")

            assert courses == 0  # No new courses added
            assert chunks == 0  # No new chunks added

            # Verify course was processed but not added to vector store
            mock_document_processor.process_course_document.assert_called_once()
            mock_vector_store.add_course_metadata.assert_not_called()
            mock_vector_store.add_course_content.assert_not_called()


class TestRAGSystemAnalytics:
    """Test analytics functionality"""

    def test_get_course_analytics(self, test_config):
        """Test course analytics retrieval"""
        mock_vector_store = Mock()
        mock_vector_store.get_course_count.return_value = 5
        mock_vector_store.get_existing_course_titles.return_value = [
            "Course 1",
            "Course 2",
        ]

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.SessionManager"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
            patch("rag_system.ToolManager"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.vector_store = mock_vector_store

            analytics = rag_system.get_course_analytics()

            assert analytics["total_courses"] == 5
            assert analytics["course_titles"] == ["Course 1", "Course 2"]


class TestRAGSystemErrorHandling:
    """Test error handling in RAG system"""

    def test_query_with_ai_generator_error(self, test_config):
        """Test handling of AI generator errors"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.side_effect = Exception("AI Error")

        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []

        mock_session_manager = Mock()

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            with pytest.raises(Exception) as exc_info:
                rag_system.query("Test query")

            assert "AI Error" in str(exc_info.value)

    def test_query_with_tool_manager_error(self, test_config):
        """Test handling of tool manager errors"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Response"

        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []
        mock_tool_manager.get_last_sources.side_effect = Exception("Tool Manager Error")

        mock_session_manager = Mock()

        with (
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.VectorStore"),
            patch("rag_system.CourseSearchTool"),
            patch("rag_system.CourseOutlineTool"),
        ):

            rag_system = RAGSystem(test_config)
            rag_system.ai_generator = mock_ai_generator
            rag_system.tool_manager = mock_tool_manager
            rag_system.session_manager = mock_session_manager

            with pytest.raises(Exception):
                rag_system.query("Test query")
