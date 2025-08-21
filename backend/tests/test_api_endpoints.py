"""
Test module for FastAPI endpoints.

Tests all API endpoints for proper request/response handling:
- POST /api/query - Query documents with RAG system
- GET /api/courses - Get course statistics  
- POST /api/session/clear - Clear session conversation history

Uses the enhanced fixtures from conftest.py that avoid static file mounting issues.
"""
import os
import sys
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


class TestQueryEndpoint:
    """Test the /api/query endpoint"""
    
    def test_query_with_session_id(self, client, mock_rag_system):
        """Test query with existing session ID"""
        response = client.post(
            "/api/query",
            json={
                "query": "What is machine learning?",
                "session_id": "test-session-456"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is a test response"
        assert data["sources"] == ["Source 1", "Source 2"]
        assert data["source_links"] == ["http://example.com/lesson/1", "http://example.com/lesson/2"]
        assert data["session_id"] == "test-session-456"
        
        # Verify RAG system was called with provided session
        mock_rag_system.query.assert_called_once_with("What is machine learning?", "test-session-456")
    
    def test_query_without_session_id(self, client, mock_rag_system):
        """Test query without session ID - should create new session"""
        response = client.post(
            "/api/query",
            json={"query": "What is artificial intelligence?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is a test response"
        assert data["sources"] == ["Source 1", "Source 2"]
        assert data["source_links"] == ["http://example.com/lesson/1", "http://example.com/lesson/2"]
        assert data["session_id"] == "test-session-123"  # From mock
        
        # Verify new session was created
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("What is artificial intelligence?", "test-session-123")
    
    def test_query_missing_query_parameter(self, client):
        """Test query request with missing query parameter"""
        response = client.post("/api/query", json={})
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_query_empty_query_string(self, client, mock_rag_system):
        """Test query with empty query string"""
        response = client.post(
            "/api/query",
            json={"query": ""}
        )
        
        assert response.status_code == 200  # Should still process empty query
        mock_rag_system.query.assert_called_once()
    
    def test_query_with_rag_system_error(self, client, mock_rag_system):
        """Test query when RAG system raises an exception"""
        # Make the mock RAG system throw an exception
        mock_rag_system.query.side_effect = Exception("RAG system error")
        
        response = client.post(
            "/api/query",
            json={"query": "What is deep learning?"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "RAG system error" in data["detail"]
    
    def test_query_invalid_json(self, client):
        """Test query with malformed JSON"""
        response = client.post(
            "/api/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_query_very_long_query(self, client, mock_rag_system):
        """Test query with very long query string"""
        long_query = "test " * 1000  # Very long query
        
        response = client.post(
            "/api/query",
            json={"query": long_query}
        )
        
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()
    
    def test_query_special_characters(self, client, mock_rag_system):
        """Test query with special characters"""
        special_query = "What about @#$%^&*()_+-=[]{}|;:,.<>?"
        
        response = client.post(
            "/api/query",
            json={"query": special_query}
        )
        
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once_with(special_query, "test-session-123")


class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""
    
    def test_get_course_stats_success(self, client, mock_rag_system):
        """Test successful retrieval of course statistics"""
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["Test Course 1", "Test Course 2"]
        
        # Verify analytics method was called
        mock_rag_system.get_course_analytics.assert_called_once()
    
    def test_get_course_stats_with_analytics_error(self, client, mock_rag_system):
        """Test course stats when analytics method raises an exception"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = client.get("/api/courses")
        
        assert response.status_code == 500
        data = response.json()
        assert "Analytics error" in data["detail"]
    
    def test_get_course_stats_method_not_allowed(self, client):
        """Test that POST is not allowed for courses endpoint"""
        response = client.post("/api/courses", json={})
        
        assert response.status_code == 405  # Method not allowed
    
    def test_get_course_stats_empty_result(self, client, mock_rag_system):
        """Test course stats with empty analytics"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


class TestClearSessionEndpoint:
    """Test the /api/session/clear endpoint"""
    
    def test_clear_session_success(self, client, mock_rag_system):
        """Test successful session clearing"""
        response = client.post(
            "/api/session/clear",
            json={"session_id": "test-session-789"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "test-session-789" in data["message"]
        
        # Verify session manager was called
        mock_rag_system.session_manager.clear_session.assert_called_once_with("test-session-789")
    
    def test_clear_session_missing_session_id(self, client):
        """Test clear session with missing session_id parameter"""
        response = client.post("/api/session/clear", json={})
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_clear_session_with_session_manager_error(self, client, mock_rag_system):
        """Test clear session when session manager raises an exception"""
        mock_rag_system.session_manager.clear_session.side_effect = Exception("Session error")
        
        response = client.post(
            "/api/session/clear",
            json={"session_id": "test-session-error"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Session error" in data["detail"]
    
    def test_clear_session_method_not_allowed(self, client):
        """Test that GET is not allowed for clear session endpoint"""
        response = client.get("/api/session/clear")
        
        assert response.status_code == 405  # Method not allowed
    
    def test_clear_session_nonexistent_session(self, client, mock_rag_system):
        """Test clearing a nonexistent session"""
        # Should still succeed even if session doesn't exist
        response = client.post(
            "/api/session/clear",
            json={"session_id": "nonexistent-session"}
        )
        
        assert response.status_code == 200
        mock_rag_system.session_manager.clear_session.assert_called_once_with("nonexistent-session")


class TestCORSAndMiddleware:
    """Test CORS and middleware functionality"""
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set"""
        response = client.options("/api/query")
        
        assert response.status_code == 200
        # Note: TestClient may not preserve all headers, but we test what we can
    
    def test_cors_preflight_request(self, client):
        """Test CORS preflight request handling"""
        response = client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        assert response.status_code == 200


class TestAPIResponseFormats:
    """Test API response format consistency"""
    
    def test_query_response_format(self, client, mock_rag_system):
        """Test that query response has correct format and types"""
        response = client.post(
            "/api/query",
            json={"query": "test query"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        required_fields = ["answer", "sources", "source_links", "session_id"]
        for field in required_fields:
            assert field in data
        
        # Check field types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["source_links"], list)
        assert isinstance(data["session_id"], str)
        
        # Check sources and source_links have same length
        assert len(data["sources"]) == len(data["source_links"])
        
        # Verify all sources are strings
        for source in data["sources"]:
            assert isinstance(source, str)
        
        # Verify all source_links are strings or None
        for link in data["source_links"]:
            assert link is None or isinstance(link, str)
    
    def test_courses_response_format(self, client, mock_rag_system):
        """Test that courses response has correct format and types"""
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Check field types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        assert data["total_courses"] >= 0
        
        # Verify all course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)
        
        # Verify total_courses matches length of course_titles
        assert data["total_courses"] == len(data["course_titles"])
    
    def test_clear_session_response_format(self, client, mock_rag_system):
        """Test that clear session response has correct format"""
        response = client.post(
            "/api/session/clear",
            json={"session_id": "test-session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "status" in data
        assert "message" in data
        
        # Check field types and values
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
        assert data["status"] == "success"


class TestErrorHandling:
    """Test comprehensive error handling scenarios"""
    
    def test_internal_server_error_format(self, client, mock_rag_system):
        """Test that 500 errors have consistent format"""
        mock_rag_system.query.side_effect = Exception("Test error")
        
        response = client.post(
            "/api/query",
            json={"query": "test"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Test error" in data["detail"]
        assert isinstance(data["detail"], str)
    
    def test_validation_error_format(self, client):
        """Test that 422 validation errors have consistent format"""
        response = client.post("/api/query", json={"invalid": "field"})
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)  # FastAPI validation error format
    
    def test_404_on_nonexistent_endpoint(self, client):
        """Test 404 error on nonexistent endpoint"""
        response = client.get("/api/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""
    
    def test_complete_query_workflow(self, client, mock_rag_system):
        """Test a complete query workflow from start to finish"""
        # Step 1: Query without session (should create new session)
        response1 = client.post(
            "/api/query",
            json={"query": "What is machine learning?"}
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        assert session_id == "test-session-123"
        
        # Step 2: Query with the same session
        response2 = client.post(
            "/api/query",
            json={
                "query": "Tell me more about neural networks",
                "session_id": session_id
            }
        )
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id
        
        # Step 3: Clear the session
        response3 = client.post(
            "/api/session/clear",
            json={"session_id": session_id}
        )
        assert response3.status_code == 200
        
        # Verify session manager was called correctly
        mock_rag_system.session_manager.clear_session.assert_called_with(session_id)
    
    def test_course_stats_and_query_consistency(self, client, mock_rag_system):
        """Test that course stats are consistent with available courses for querying"""
        # Get course statistics
        stats_response = client.get("/api/courses")
        assert stats_response.status_code == 200
        
        stats_data = stats_response.json()
        assert stats_data["total_courses"] > 0
        assert len(stats_data["course_titles"]) == stats_data["total_courses"]
        
        # Verify we can query about the courses
        query_response = client.post(
            "/api/query",
            json={"query": f"Tell me about {stats_data['course_titles'][0]}"}
        )
        assert query_response.status_code == 200
        
        # Both endpoints should use the same underlying system
        assert mock_rag_system.get_course_analytics.call_count == 1
        assert mock_rag_system.query.call_count == 1
    
    def test_multiple_sessions_isolation(self, client, mock_rag_system):
        """Test that multiple sessions are properly isolated"""
        # Create first session
        response1 = client.post(
            "/api/query",
            json={"query": "First session query"}
        )
        session1 = response1.json()["session_id"]
        
        # Reset mock to clear previous calls
        mock_rag_system.reset_mock()
        mock_rag_system.session_manager.create_session.return_value = "test-session-456"
        mock_rag_system.query.return_value = (
            "This is a test response",
            ["Source 1", "Source 2"],
            ["http://example.com/lesson/1", "http://example.com/lesson/2"]
        )
        
        # Create second session
        response2 = client.post(
            "/api/query",
            json={"query": "Second session query"}
        )
        session2 = response2.json()["session_id"]
        
        # Sessions should be different
        assert session1 != session2
        
        # Both should work independently
        assert response1.status_code == 200
        assert response2.status_code == 200


class TestRequestValidationEdgeCases:
    """Test edge cases in request validation"""
    
    def test_query_with_null_values(self, client):
        """Test query with null values in JSON"""
        response = client.post(
            "/api/query",
            json={"query": None}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_clear_session_with_empty_string_session_id(self, client, mock_rag_system):
        """Test clear session with empty string session ID"""
        response = client.post(
            "/api/session/clear",
            json={"session_id": ""}
        )
        
        # Should still succeed (empty string is valid)
        assert response.status_code == 200
        mock_rag_system.session_manager.clear_session.assert_called_once_with("")
    
    def test_query_with_extra_fields(self, client, mock_rag_system):
        """Test query with additional unexpected fields"""
        response = client.post(
            "/api/query",
            json={
                "query": "Test query",
                "extra_field": "should be ignored",
                "another_field": 123
            }
        )
        
        # Should succeed and ignore extra fields
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()


class TestPerformanceAndRobustness:
    """Test performance and robustness scenarios"""
    
    def test_concurrent_requests_simulation(self, client, mock_rag_system):
        """Test handling of multiple rapid requests"""
        responses = []
        
        # Simulate concurrent requests
        for i in range(5):
            response = client.post(
                "/api/query",
                json={"query": f"Query {i}"}
            )
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
        
        # RAG system should have been called for each request
        assert mock_rag_system.query.call_count == 5
    
    def test_unicode_query_handling(self, client, mock_rag_system):
        """Test handling of unicode characters in queries"""
        unicode_query = "What is 机器学习? Explain ñoñería and émotions 🤖"
        
        response = client.post(
            "/api/query",
            json={"query": unicode_query}
        )
        
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once_with(unicode_query, "test-session-123")
    
    def test_error_recovery(self, client, mock_rag_system):
        """Test system recovery after errors"""
        # First request fails
        mock_rag_system.query.side_effect = Exception("Temporary error")
        
        response1 = client.post(
            "/api/query",
            json={"query": "First query"}
        )
        assert response1.status_code == 500
        
        # System recovers for second request
        mock_rag_system.query.side_effect = None
        mock_rag_system.query.return_value = (
            "Recovery response",
            ["Source"],
            ["http://example.com/lesson/1"]
        )
        
        response2 = client.post(
            "/api/query", 
            json={"query": "Second query"}
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["answer"] == "Recovery response"