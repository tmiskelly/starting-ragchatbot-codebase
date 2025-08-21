import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAPIEndpoints:
    """Test API endpoints functionality"""
    
    @pytest.fixture
    def mock_rag_system(self):
        """Mock RAG system for testing"""
        mock_rag = Mock()
        
        # Mock query method
        mock_rag.query.return_value = (
            "Test response",
            ["Test Source"],
            ["http://test-link.com"]
        )
        
        # Mock session manager
        mock_rag.session_manager = Mock()
        mock_rag.session_manager.create_session.return_value = "test_session_123"
        
        # Mock analytics
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 4,
            "course_titles": ["Course 1", "Course 2", "Course 3", "Course 4"]
        }
        
        return mock_rag
    
    @pytest.fixture
    def test_client(self, mock_rag_system):
        """Test client with mocked RAG system"""
        with patch('app.rag_system', mock_rag_system):
            from app import app
            return TestClient(app)
    
    def test_query_endpoint_without_session(self, test_client, mock_rag_system):
        """Test /api/query endpoint without session ID"""
        response = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Test response"
        assert data["sources"] == ["Test Source"]
        assert data["source_links"] == ["http://test-link.com"]
        assert data["session_id"] == "test_session_123"
        
        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with("What is Python?", "test_session_123")
        mock_rag_system.session_manager.create_session.assert_called_once()
    
    def test_query_endpoint_with_session(self, test_client, mock_rag_system):
        """Test /api/query endpoint with existing session ID"""
        response = test_client.post(
            "/api/query",
            json={"query": "Follow-up question", "session_id": "existing_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == "existing_session"
        
        # Verify RAG system was called with existing session
        mock_rag_system.query.assert_called_once_with("Follow-up question", "existing_session")
        mock_rag_system.session_manager.create_session.assert_not_called()
    
    def test_query_endpoint_rag_error(self, test_client, mock_rag_system):
        """Test /api/query endpoint when RAG system raises error"""
        mock_rag_system.query.side_effect = Exception("RAG system error")
        
        response = test_client.post(
            "/api/query",
            json={"query": "Test query"}
        )
        
        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]
    
    def test_query_endpoint_invalid_request(self, test_client):
        """Test /api/query endpoint with invalid request data"""
        # Missing required 'query' field
        response = test_client.post("/api/query", json={})
        
        assert response.status_code == 422  # Validation error
    
    def test_query_endpoint_empty_query(self, test_client, mock_rag_system):
        """Test /api/query endpoint with empty query"""
        response = test_client.post(
            "/api/query",
            json={"query": ""}
        )
        
        assert response.status_code == 200
        # Should still call RAG system with empty query
        mock_rag_system.query.assert_called_once()
    
    def test_courses_endpoint(self, test_client, mock_rag_system):
        """Test /api/courses endpoint"""
        response = test_client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 4
        assert len(data["course_titles"]) == 4
        assert "Course 1" in data["course_titles"]
        
        # Verify analytics method was called
        mock_rag_system.get_course_analytics.assert_called_once()
    
    def test_courses_endpoint_error(self, test_client, mock_rag_system):
        """Test /api/courses endpoint when analytics fails"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = test_client.get("/api/courses")
        
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]
    
    def test_clear_session_endpoint(self, test_client, mock_rag_system):
        """Test /api/session/clear endpoint"""
        response = test_client.post(
            "/api/session/clear",
            json={"session_id": "test_session"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "test_session" in data["message"]
        
        # Verify session manager was called
        mock_rag_system.session_manager.clear_session.assert_called_once_with("test_session")
    
    def test_clear_session_endpoint_error(self, test_client, mock_rag_system):
        """Test /api/session/clear endpoint when clear fails"""
        mock_rag_system.session_manager.clear_session.side_effect = Exception("Clear error")
        
        response = test_client.post(
            "/api/session/clear",
            json={"session_id": "test_session"}
        )
        
        assert response.status_code == 500
        assert "Clear error" in response.json()["detail"]
    
    def test_clear_session_endpoint_invalid_request(self, test_client):
        """Test /api/session/clear endpoint with invalid request"""
        # Missing required 'session_id' field
        response = test_client.post("/api/session/clear", json={})
        
        assert response.status_code == 422  # Validation error

class TestAPIEndpointsWithRealRAGSystem:
    """Integration tests with real RAG system (if available)"""
    
    @pytest.fixture
    def real_app_client(self):
        """Test client with real app (may require valid configuration)"""
        try:
            from app import app
            return TestClient(app)
        except Exception as e:
            pytest.skip(f"Cannot create real app client: {e}")
    
    @pytest.mark.integration
    def test_real_courses_endpoint(self, real_app_client):
        """Test /api/courses endpoint with real RAG system"""
        if real_app_client is None:
            pytest.skip("Real app client not available")
        
        response = real_app_client.get("/api/courses")
        
        # Should succeed regardless of data
        assert response.status_code == 200
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
    
    @pytest.mark.integration
    def test_real_query_endpoint_simple(self, real_app_client):
        """Test /api/query endpoint with real RAG system using simple query"""
        if real_app_client is None:
            pytest.skip("Real app client not available")
        
        response = real_app_client.post(
            "/api/query",
            json={"query": "What is 2+2?"}  # Simple question that shouldn't require tools
        )
        
        # This will help us see what's actually happening
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "source_links" in data
        assert "session_id" in data
    
    @pytest.mark.integration
    def test_real_query_endpoint_course_content(self, real_app_client):
        """Test /api/query endpoint with course content query"""
        if real_app_client is None:
            pytest.skip("Real app client not available")
        
        response = real_app_client.post(
            "/api/query",
            json={"query": "Tell me about Python programming"}
        )
        
        print(f"Course content query response status: {response.status_code}")
        print(f"Course content query response body: {response.text}")
        
        # Even if it fails, we want to see the response format
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
        else:
            # This will help us understand the actual error
            print(f"Error response: {response.json() if response.headers.get('content-type') == 'application/json' else response.text}")

class TestAPIEndpointRequestValidation:
    """Test request validation and edge cases"""
    
    @pytest.fixture
    def basic_client(self):
        """Basic test client for validation testing"""
        from app import app
        return TestClient(app)
    
    def test_query_endpoint_large_query(self, basic_client):
        """Test handling of very large queries"""
        large_query = "test " * 10000  # Very large query
        
        with patch('app.rag_system') as mock_rag:
            mock_rag.query.return_value = ("Response", [], [])
            mock_rag.session_manager.create_session.return_value = "session"
            
            response = basic_client.post(
                "/api/query",
                json={"query": large_query}
            )
            
            assert response.status_code == 200
    
    def test_query_endpoint_special_characters(self, basic_client):
        """Test handling of special characters in queries"""
        special_query = "What about @#$%^&*()_+-=[]{}|;:,.<>?"
        
        with patch('app.rag_system') as mock_rag:
            mock_rag.query.return_value = ("Response", [], [])
            mock_rag.session_manager.create_session.return_value = "session"
            
            response = basic_client.post(
                "/api/query",
                json={"query": special_query}
            )
            
            assert response.status_code == 200
    
    def test_clear_session_invalid_session_id(self, basic_client):
        """Test clearing session with invalid session ID"""
        with patch('app.rag_system') as mock_rag:
            mock_rag.session_manager.clear_session.return_value = None
            
            response = basic_client.post(
                "/api/session/clear",
                json={"session_id": "nonexistent_session"}
            )
            
            # Should still succeed
            assert response.status_code == 200

class TestAPIEndpointResponseFormat:
    """Test response format compliance"""
    
    def test_query_response_format(self, test_client, mock_rag_system):
        """Test that query response matches expected format"""
        response = test_client.post(
            "/api/query",
            json={"query": "Test query"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        required_fields = ["answer", "sources", "source_links", "session_id"]
        for field in required_fields:
            assert field in data
        
        # Verify field types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["source_links"], list)
        assert isinstance(data["session_id"], str)
        
        # Verify sources and source_links have same length
        assert len(data["sources"]) == len(data["source_links"])
    
    def test_courses_response_format(self, test_client, mock_rag_system):
        """Test that courses response matches expected format"""
        response = test_client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Verify field types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        
        # Verify all course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)