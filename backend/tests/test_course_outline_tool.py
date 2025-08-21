from unittest.mock import Mock, patch

import pytest
from search_tools import CourseOutlineTool


class TestCourseOutlineTool:
    """Test suite for CourseOutlineTool functionality"""

    def test_get_tool_definition(self, course_outline_tool):
        """Test that tool definition is properly formatted"""
        definition = course_outline_tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "course_title" in definition["input_schema"]["properties"]
        assert "course_title" in definition["input_schema"]["required"]

    def test_execute_successful_outline(self, course_outline_tool, mock_vector_store):
        """Test successful course outline retrieval"""
        # Setup mock course resolution
        mock_vector_store._resolve_course_name.return_value = "Test Course"

        # Setup mock course catalog response
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": "http://example.com/course",
                    "lessons_json": '[{"lesson_number": 1, "lesson_title": "Introduction"}, {"lesson_number": 2, "lesson_title": "Advanced Topics"}]',
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        # Verify course resolution was called
        mock_vector_store._resolve_course_name.assert_called_once_with("Test")

        # Verify course catalog was queried
        mock_vector_store.course_catalog.get.assert_called_once_with(
            ids=["Test Course"]
        )

        # Verify result format
        assert "**Test Course**" in result
        assert "Course Link: http://example.com/course" in result
        assert "**Lessons:**" in result
        assert "1. Introduction" in result
        assert "2. Advanced Topics" in result

    def test_execute_course_not_found(self, course_outline_tool, mock_vector_store):
        """Test handling when course is not found"""
        mock_vector_store._resolve_course_name.return_value = None

        result = course_outline_tool.execute("Nonexistent Course")

        assert result == "No course found matching 'Nonexistent Course'"

        # Should not query course catalog if course not resolved
        mock_vector_store.course_catalog.get.assert_not_called()

    def test_execute_no_metadata(self, course_outline_tool, mock_vector_store):
        """Test handling when course metadata is not found"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {"metadatas": []}

        result = course_outline_tool.execute("Test")

        assert "Course metadata not found for 'Test Course'" in result

    def test_execute_no_course_link(self, course_outline_tool, mock_vector_store):
        """Test handling when course link is not available"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": None,  # No course link
                    "lessons_json": "[]",
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        assert "**Test Course**" in result
        assert "Course Link: Not available" in result

    def test_execute_no_lessons(self, course_outline_tool, mock_vector_store):
        """Test handling when course has no lessons"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": "http://example.com/course",
                    "lessons_json": "[]",  # No lessons
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        assert "**Test Course**" in result
        assert "No lessons found for this course." in result

    def test_execute_malformed_lessons_json(
        self, course_outline_tool, mock_vector_store
    ):
        """Test handling of malformed lessons JSON"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": "http://example.com/course",
                    "lessons_json": "invalid json",  # Malformed JSON
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        assert "**Test Course**" in result
        assert "No lessons found for this course." in result

    def test_execute_lessons_sorted_by_number(
        self, course_outline_tool, mock_vector_store
    ):
        """Test that lessons are sorted by lesson number"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": "http://example.com/course",
                    "lessons_json": '[{"lesson_number": 3, "lesson_title": "Third"}, {"lesson_number": 1, "lesson_title": "First"}, {"lesson_number": 2, "lesson_title": "Second"}]',
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        # Check that lessons appear in the correct order
        lines = result.split("\n")
        lesson_lines = [
            line
            for line in lines
            if line.strip() and any(char.isdigit() for char in line) and "." in line
        ]

        assert len(lesson_lines) == 3
        assert "1. First" in lesson_lines[0]
        assert "2. Second" in lesson_lines[1]
        assert "3. Third" in lesson_lines[2]

    def test_execute_missing_lesson_data(self, course_outline_tool, mock_vector_store):
        """Test handling of lessons with missing data"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Test Course",
                    "course_link": "http://example.com/course",
                    "lessons_json": '[{"lesson_number": 1}, {"lesson_title": "No Number"}, {"lesson_number": 2, "lesson_title": "Complete"}]',
                }
            ]
        }

        result = course_outline_tool.execute("Test")

        # Should handle missing data gracefully
        assert "1. Untitled" in result  # Missing title
        assert "Unknown. No Number" in result  # Missing number
        assert "2. Complete" in result  # Complete lesson

    def test_execute_database_error(self, course_outline_tool, mock_vector_store):
        """Test handling of database errors"""
        mock_vector_store._resolve_course_name.return_value = "Test Course"
        mock_vector_store.course_catalog.get.side_effect = Exception("Database error")

        result = course_outline_tool.execute("Test")

        assert "Error retrieving course outline: Database error" in result

    def test_execute_partial_course_name_match(
        self, course_outline_tool, mock_vector_store
    ):
        """Test that partial course name matching works"""
        mock_vector_store._resolve_course_name.return_value = "Full Course Name"
        mock_vector_store.course_catalog.get.return_value = {
            "metadatas": [
                {
                    "title": "Full Course Name",
                    "course_link": "http://example.com/course",
                    "lessons_json": '[{"lesson_number": 1, "lesson_title": "Lesson 1"}]',
                }
            ]
        }

        result = course_outline_tool.execute("Course")  # Partial name

        # Should resolve to full name and return outline
        mock_vector_store._resolve_course_name.assert_called_once_with("Course")
        assert "**Full Course Name**" in result


class TestCourseOutlineToolEdgeCases:
    """Test edge cases and error conditions"""

    def test_execute_with_none_course_title(self, course_outline_tool):
        """Test handling of None course title"""
        with pytest.raises(TypeError):
            course_outline_tool.execute(None)

    def test_execute_with_empty_course_title(
        self, course_outline_tool, mock_vector_store
    ):
        """Test handling of empty course title string"""
        mock_vector_store._resolve_course_name.return_value = None

        result = course_outline_tool.execute("")

        assert "No course found matching ''" in result

    def test_execute_with_very_long_course_title(
        self, course_outline_tool, mock_vector_store
    ):
        """Test handling of very long course titles"""
        long_title = "Course " * 1000
        mock_vector_store._resolve_course_name.return_value = None

        result = course_outline_tool.execute(long_title)

        # Should handle gracefully
        assert "No course found matching" in result

    def test_execute_with_special_characters(
        self, course_outline_tool, mock_vector_store
    ):
        """Test handling of course titles with special characters"""
        special_title = "Course @#$%^&*()"
        mock_vector_store._resolve_course_name.return_value = None

        result = course_outline_tool.execute(special_title)

        # Should handle special characters without crashing
        mock_vector_store._resolve_course_name.assert_called_once_with(special_title)


class TestCourseOutlineToolIntegration:
    """Integration tests with real vector store (if available)"""

    @pytest.mark.integration
    def test_execute_with_real_vector_store(self, real_vector_store):
        """Test with real vector store to check actual outline functionality"""
        if real_vector_store is None:
            pytest.skip("Real vector store not available")

        tool = CourseOutlineTool(real_vector_store)

        # This test will show us if the real vector store has course data
        try:
            # Try a generic course name that might exist
            result = tool.execute("Course")

            # Should either return an outline or "No course found"
            assert isinstance(result, str)
            assert len(result) > 0

            # If it found a course, should have the outline format
            if "No course found" not in result:
                assert "**" in result  # Should have course title formatted

        except Exception as e:
            pytest.fail(f"Real vector store integration failed: {e}")
