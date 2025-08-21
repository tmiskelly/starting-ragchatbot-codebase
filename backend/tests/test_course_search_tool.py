from unittest.mock import Mock, patch

import pytest
from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test suite for CourseSearchTool functionality"""

    def test_get_tool_definition(self, course_search_tool):
        """Test that tool definition is properly formatted"""
        definition = course_search_tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert "query" in definition["input_schema"]["required"]

    def test_execute_basic_query(self, course_search_tool, mock_vector_store):
        """Test basic query execution"""
        # Setup mock response
        mock_vector_store.search.return_value = Mock(
            documents=["Test content about Python"],
            metadata=[{"course_title": "Python Course", "lesson_number": 1}],
            distances=[0.1],
            error=None,
            is_empty=Mock(return_value=False),
        )
        mock_vector_store.get_lesson_link.return_value = "http://example.com/lesson/1"

        result = course_search_tool.execute("Python basics")

        # Verify the call
        mock_vector_store.search.assert_called_once_with(
            query="Python basics", course_name=None, lesson_number=None
        )

        # Verify result format
        assert isinstance(result, str)
        assert "[Python Course - Lesson 1]" in result
        assert "Test content about Python" in result

    def test_execute_with_course_filter(self, course_search_tool, mock_vector_store):
        """Test query execution with course name filter"""
        mock_vector_store.search.return_value = Mock(
            documents=["Course specific content"],
            metadata=[{"course_title": "Advanced Python", "lesson_number": 2}],
            distances=[0.1],
            error=None,
            is_empty=Mock(return_value=False),
        )

        result = course_search_tool.execute("advanced topics", course_name="Python")

        # Verify the call includes course filter
        mock_vector_store.search.assert_called_once_with(
            query="advanced topics", course_name="Python", lesson_number=None
        )

        assert "[Advanced Python - Lesson 2]" in result

    def test_execute_with_lesson_filter(self, course_search_tool, mock_vector_store):
        """Test query execution with lesson number filter"""
        mock_vector_store.search.return_value = Mock(
            documents=["Lesson specific content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 3}],
            distances=[0.1],
            error=None,
            is_empty=Mock(return_value=False),
        )

        result = course_search_tool.execute("lesson content", lesson_number=3)

        # Verify the call includes lesson filter
        mock_vector_store.search.assert_called_once_with(
            query="lesson content", course_name=None, lesson_number=3
        )

        assert "[Test Course - Lesson 3]" in result

    def test_execute_with_both_filters(self, course_search_tool, mock_vector_store):
        """Test query execution with both course and lesson filters"""
        result = course_search_tool.execute(
            "specific content", course_name="Python", lesson_number=1
        )

        mock_vector_store.search.assert_called_once_with(
            query="specific content", course_name="Python", lesson_number=1
        )

    def test_execute_with_search_error(self, course_search_tool, mock_vector_store):
        """Test handling of search errors"""
        mock_vector_store.search.return_value = Mock(
            documents=[],
            metadata=[],
            distances=[],
            error="Search failed: Connection error",
            is_empty=Mock(return_value=True),
        )

        result = course_search_tool.execute("test query")

        assert result == "Search failed: Connection error"

    def test_execute_with_empty_results(self, course_search_tool, mock_vector_store):
        """Test handling of empty search results"""
        mock_vector_store.search.return_value = Mock(
            documents=[],
            metadata=[],
            distances=[],
            error=None,
            is_empty=Mock(return_value=True),
        )

        result = course_search_tool.execute("nonexistent content")

        assert "No relevant content found" in result

    def test_execute_with_empty_results_and_filters(
        self, course_search_tool, mock_vector_store
    ):
        """Test empty results message includes filter information"""
        mock_vector_store.search.return_value = Mock(
            documents=[],
            metadata=[],
            distances=[],
            error=None,
            is_empty=Mock(return_value=True),
        )

        result = course_search_tool.execute(
            "test", course_name="Python", lesson_number=5
        )

        assert "No relevant content found in course 'Python' in lesson 5" in result

    def test_format_results_with_sources_tracking(
        self, course_search_tool, mock_vector_store
    ):
        """Test that sources and source links are properly tracked"""
        mock_vector_store.search.return_value = Mock(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
            error=None,
            is_empty=Mock(return_value=False),
        )
        mock_vector_store.get_lesson_link.side_effect = ["http://link1", "http://link2"]

        result = course_search_tool.execute("test query")

        # Check that sources were tracked
        assert len(course_search_tool.last_sources) == 2
        assert "Course A - Lesson 1" in course_search_tool.last_sources
        assert "Course B - Lesson 2" in course_search_tool.last_sources

        # Check that source links were tracked
        assert len(course_search_tool.last_source_links) == 2
        assert "http://link1" in course_search_tool.last_source_links
        assert "http://link2" in course_search_tool.last_source_links

    def test_format_results_without_lesson_numbers(
        self, course_search_tool, mock_vector_store
    ):
        """Test formatting when lesson numbers are not available"""
        mock_vector_store.search.return_value = Mock(
            documents=["General course content"],
            metadata=[{"course_title": "General Course", "lesson_number": None}],
            distances=[0.1],
            error=None,
            is_empty=Mock(return_value=False),
        )
        mock_vector_store.get_course_link.return_value = "http://course-link"

        result = course_search_tool.execute("general content")

        assert "[General Course]" in result
        assert "Lesson" not in result.split("[General Course]")[1].split("]")[0]


class TestCourseSearchToolWithRealVectorStore:
    """Integration tests with real vector store (if available)"""

    @pytest.mark.integration
    def test_execute_with_real_vector_store(self, real_vector_store):
        """Test with real vector store to check actual search functionality"""
        if real_vector_store is None:
            pytest.skip("Real vector store not available")

        tool = CourseSearchTool(real_vector_store)

        # This test will show us if the real vector store has any issues
        try:
            result = tool.execute("test query")
            # Should either return results or "No relevant content found"
            assert isinstance(result, str)
            assert len(result) > 0
        except Exception as e:
            pytest.fail(f"Real vector store integration failed: {e}")


class TestCourseSearchToolEdgeCases:
    """Test edge cases and error conditions"""

    def test_execute_with_none_query(self, course_search_tool):
        """Test handling of None query"""
        with pytest.raises(TypeError):
            course_search_tool.execute(None)

    def test_execute_with_empty_query(self, course_search_tool, mock_vector_store):
        """Test handling of empty query string"""
        mock_vector_store.search.return_value = Mock(
            error=None, is_empty=Mock(return_value=True)
        )

        result = course_search_tool.execute("")

        # Should still call search but might return no results
        mock_vector_store.search.assert_called_once()

    def test_execute_with_very_long_query(self, course_search_tool, mock_vector_store):
        """Test handling of very long queries"""
        long_query = "test " * 1000  # Very long query

        mock_vector_store.search.return_value = Mock(
            error=None, is_empty=Mock(return_value=True)
        )

        result = course_search_tool.execute(long_query)

        # Should handle long queries gracefully
        mock_vector_store.search.assert_called_once_with(
            query=long_query, course_name=None, lesson_number=None
        )

    def test_execute_with_special_characters(
        self, course_search_tool, mock_vector_store
    ):
        """Test handling of queries with special characters"""
        special_query = "test @#$%^&*()_+-=[]{}|;:,.<>?"

        mock_vector_store.search.return_value = Mock(
            error=None, is_empty=Mock(return_value=True)
        )

        result = course_search_tool.execute(special_query)

        # Should handle special characters without crashing
        mock_vector_store.search.assert_called_once()
