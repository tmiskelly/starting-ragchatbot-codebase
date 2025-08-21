from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol

from vector_store import SearchResults, VectorStore


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search
        self.last_source_links = []  # Track source links from last search

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(
        self,
        query: str,
        course_name: Optional[str] = None,
        lesson_number: Optional[int] = None,
    ) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."

        # Format and return results
        return self._format_results(results)

    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track sources for the UI
        source_links = []  # Track links for the UI

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get("course_title", "unknown")
            lesson_num = meta.get("lesson_number")

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Track source for the UI
            source = course_title
            if lesson_num is not None:
                source += f" - Lesson {lesson_num}"
            sources.append(source)

            # Get the lesson link if available
            link = None
            if lesson_num is not None:
                link = self.store.get_lesson_link(course_title, lesson_num)
            elif course_title != "unknown":
                # If no lesson number, try to get course link
                link = self.store.get_course_link(course_title)
            source_links.append(link)

            formatted.append(f"{header}\n{doc}")

        # Store sources and links for retrieval
        self.last_sources = sources
        self.last_source_links = source_links

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for getting course outlines with lesson lists"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get a course outline including title, course link, and complete lesson list",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_title": {
                        "type": "string",
                        "description": "Course title to get outline for (partial matches work, e.g. 'MCP', 'Introduction')",
                    }
                },
                "required": ["course_title"],
            },
        }

    def execute(self, course_title: str) -> str:
        """
        Execute the outline tool to get course structure.

        Args:
            course_title: Course title to look up

        Returns:
            Formatted course outline or error message
        """
        import json

        # Resolve course name using vector search
        resolved_title = self.store._resolve_course_name(course_title)
        if not resolved_title:
            return f"No course found matching '{course_title}'"

        # Get course metadata from catalog
        try:
            results = self.store.course_catalog.get(ids=[resolved_title])
            if not results or not results.get("metadatas"):
                return f"Course metadata not found for '{resolved_title}'"

            metadata = results["metadatas"][0]

            # Extract course information
            title = metadata.get("title", "Unknown Course")
            course_link = metadata.get("course_link")
            lessons_json = metadata.get("lessons_json", "[]")

            # Parse lessons
            try:
                lessons = json.loads(lessons_json)
            except json.JSONDecodeError:
                lessons = []

            # Format the outline
            outline_parts = [f"**{title}**"]

            if course_link:
                outline_parts.append(f"Course Link: {course_link}")
            else:
                outline_parts.append("Course Link: Not available")

            if lessons:
                outline_parts.append("\n**Lessons:**")
                for lesson in sorted(lessons, key=lambda x: x.get("lesson_number", 0)):
                    lesson_num = lesson.get("lesson_number", "Unknown")
                    lesson_title = lesson.get("lesson_title", "Untitled")
                    outline_parts.append(f"{lesson_num}. {lesson_title}")
            else:
                outline_parts.append("\nNo lessons found for this course.")

            return "\n".join(outline_parts)

        except Exception as e:
            return f"Error retrieving course outline: {str(e)}"


class ToolManager:
    """Manages available tools for the AI"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        return self.tools[tool_name].execute(**kwargs)

    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, "last_sources") and tool.last_sources:
                return tool.last_sources
        return []

    def get_last_source_links(self) -> list:
        """Get source links from the last search operation"""
        # Check all tools for last_source_links attribute
        for tool in self.tools.values():
            if hasattr(tool, "last_source_links") and tool.last_source_links:
                return tool.last_source_links
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
            if hasattr(tool, "last_source_links"):
                tool.last_source_links = []
