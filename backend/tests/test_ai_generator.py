import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_generator import AIGenerator

class TestAIGenerator:
    """Test suite for AI Generator functionality"""
    
    def test_init(self, test_config):
        """Test AIGenerator initialization"""
        generator = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
        
        assert generator.model == test_config.ANTHROPIC_MODEL
        assert generator.base_params["model"] == test_config.ANTHROPIC_MODEL
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800
    
    def test_generate_response_without_tools(self, ai_generator_with_mock, mock_anthropic_client):
        """Test basic response generation without tools"""
        # Setup mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="This is a test response")]
        mock_response.stop_reason = "end_turn"
        mock_anthropic_client.messages.create.return_value = mock_response
        
        result = ai_generator_with_mock.generate_response("What is Python?")
        
        assert result == "This is a test response"
        
        # Verify the API call
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args[1]["messages"][0]["content"] == "What is Python?"
        assert "tools" not in call_args[1]
    
    def test_generate_response_with_conversation_history(self, ai_generator_with_mock, mock_anthropic_client):
        """Test response generation with conversation history"""
        mock_response = Mock()
        mock_response.content = [Mock(text="Response with history")]
        mock_response.stop_reason = "end_turn"
        mock_anthropic_client.messages.create.return_value = mock_response
        
        history = "User: Previous question\nAssistant: Previous answer"
        result = ai_generator_with_mock.generate_response("Follow-up question", conversation_history=history)
        
        assert result == "Response with history"
        
        # Verify history is included in system content
        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args[1]["system"]
        assert "Previous conversation:" in system_content
        assert history in system_content
    
    def test_generate_response_with_tools_no_tool_use(self, ai_generator_with_mock, mock_anthropic_client):
        """Test response generation with tools available but not used"""
        # Setup mock response that doesn't use tools
        mock_response = Mock()
        mock_response.content = [Mock(text="Direct answer without tools")]
        mock_response.stop_reason = "end_turn"
        mock_anthropic_client.messages.create.return_value = mock_response
        
        tools = [{"name": "test_tool", "description": "Test tool"}]
        tool_manager = Mock()
        
        result = ai_generator_with_mock.generate_response(
            "General knowledge question",
            tools=tools,
            tool_manager=tool_manager
        )
        
        assert result == "Direct answer without tools"
        
        # Verify tools were provided in the API call
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args[1]["tools"] == tools
        assert call_args[1]["tool_choice"] == {"type": "auto"}
        
        # Verify tool manager was not called
        tool_manager.execute_tool.assert_not_called()
    
    def test_generate_response_with_tool_use(self, ai_generator_with_mock, mock_anthropic_client):
        """Test response generation when AI uses tools"""
        # Setup mock initial response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.input = {"query": "Python basics"}
        mock_tool_block.id = "tool_use_123"
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"
        
        # Setup mock final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response with tool results")]
        
        # Setup mock client to return different responses
        mock_anthropic_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response
        ]
        
        # Setup mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.return_value = "Tool execution result"
        
        tools = [{"name": "search_course_content", "description": "Search tool"}]
        
        result = ai_generator_with_mock.generate_response(
            "Search for Python content",
            tools=tools,
            tool_manager=tool_manager
        )
        
        assert result == "Final response with tool results"
        
        # Verify tool execution was called
        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="Python basics"
        )
        
        # Verify two API calls were made
        assert mock_anthropic_client.messages.create.call_count == 2
    
    def test_handle_tool_execution_single_tool(self, ai_generator_with_mock, mock_anthropic_client):
        """Test tool execution handling with single tool"""
        # Setup mock tool use response
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "test_tool"
        mock_tool_block.input = {"param": "value"}
        mock_tool_block.id = "tool_123"
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        
        # Setup mock final response
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Response after tool use")]
        mock_anthropic_client.messages.create.return_value = mock_final_response
        
        # Setup mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.return_value = "Tool result"
        
        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": "Test system prompt"
        }
        
        result = ai_generator_with_mock._handle_tool_execution(
            mock_initial_response,
            base_params,
            tool_manager
        )
        
        assert result == "Response after tool use"
        
        # Verify tool was executed
        tool_manager.execute_tool.assert_called_once_with("test_tool", param="value")
        
        # Verify final API call structure
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]["messages"]
        
        # Should have: original user message, assistant tool use, user tool results
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["tool_use_id"] == "tool_123"
        assert messages[2]["content"][0]["content"] == "Tool result"
    
    def test_handle_tool_execution_multiple_tools(self, ai_generator_with_mock, mock_anthropic_client):
        """Test tool execution handling with multiple tools"""
        # Setup multiple tool blocks
        mock_tool_block1 = Mock()
        mock_tool_block1.type = "tool_use"
        mock_tool_block1.name = "tool1"
        mock_tool_block1.input = {"param1": "value1"}
        mock_tool_block1.id = "tool_1"
        
        mock_tool_block2 = Mock()
        mock_tool_block2.type = "tool_use"
        mock_tool_block2.name = "tool2"
        mock_tool_block2.input = {"param2": "value2"}
        mock_tool_block2.id = "tool_2"
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block1, mock_tool_block2]
        
        # Setup mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]
        
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response")]
        mock_anthropic_client.messages.create.return_value = mock_final_response
        
        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": "Test system prompt"
        }
        
        result = ai_generator_with_mock._handle_tool_execution(
            mock_initial_response,
            base_params,
            tool_manager
        )
        
        # Verify both tools were executed
        assert tool_manager.execute_tool.call_count == 2
        tool_manager.execute_tool.assert_any_call("tool1", param1="value1")
        tool_manager.execute_tool.assert_any_call("tool2", param2="value2")
        
        # Verify tool results structure
        call_args = mock_anthropic_client.messages.create.call_args
        tool_results = call_args[1]["messages"][2]["content"]
        assert len(tool_results) == 2
        assert tool_results[0]["tool_use_id"] == "tool_1"
        assert tool_results[1]["tool_use_id"] == "tool_2"

class TestSequentialToolCalling:
    """Test suite for sequential tool calling functionality"""
    
    def test_sequential_tool_calling_two_rounds(self, ai_generator_with_mock, mock_anthropic_client):
        """Test successful two-round tool calling scenario"""
        # Setup mock responses for two rounds
        
        # Round 1: AI uses outline tool
        mock_tool_block_1 = Mock()
        mock_tool_block_1.type = "tool_use"
        mock_tool_block_1.name = "get_course_outline"
        mock_tool_block_1.input = {"course_title": "Python Course"}
        mock_tool_block_1.id = "tool_1"
        
        mock_round1_response = Mock()
        mock_round1_response.content = [mock_tool_block_1]
        mock_round1_response.stop_reason = "tool_use"
        
        # Round 2: AI uses search tool based on outline results
        mock_tool_block_2 = Mock()
        mock_tool_block_2.type = "tool_use"
        mock_tool_block_2.name = "search_course_content"
        mock_tool_block_2.input = {"query": "lesson 4 content"}
        mock_tool_block_2.id = "tool_2"
        
        mock_round2_response = Mock()
        mock_round2_response.content = [mock_tool_block_2]
        mock_round2_response.stop_reason = "tool_use"
        
        # Final response without tools (Round 3 - after max rounds reached)
        mock_text_block = Mock(text="Based on the course outline and lesson content, here's the answer...")
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        mock_final_response.stop_reason = "end_turn"
        
        # Configure mock client for sequential responses
        mock_anthropic_client.messages.create.side_effect = [
            mock_round1_response,    # Round 1: tool use
            mock_round2_response,    # Round 2: tool use
            mock_final_response      # Round 3: final response (max rounds reached)
        ]
        
        # Setup mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = [
            "Course outline with lesson 4: Advanced Functions",
            "Lesson 4 content about advanced functions"
        ]
        
        tools = [
            {"name": "get_course_outline", "description": "Get course outline"},
            {"name": "search_course_content", "description": "Search course content"}
        ]
        
        result = ai_generator_with_mock.generate_response(
            "What topics are covered in lesson 4 of Python Course?",
            tools=tools,
            tool_manager=tool_manager
        )
        
        # Verify final response
        assert result == "Based on the course outline and lesson content, here's the answer..."
        
        # Verify three API calls were made (2 tool rounds + 1 final)
        assert mock_anthropic_client.messages.create.call_count == 3
        
        # Verify both tools were executed
        assert tool_manager.execute_tool.call_count == 2
        tool_manager.execute_tool.assert_any_call("get_course_outline", course_title="Python Course")
        tool_manager.execute_tool.assert_any_call("search_course_content", query="lesson 4 content")
    
    def test_sequential_tool_calling_terminates_after_first_round_no_tools(self, ai_generator_with_mock, mock_anthropic_client):
        """Test that sequential calling terminates when AI doesn't use tools in first round"""
        # Round 1: AI responds without using tools
        mock_text_block = Mock(text="I can answer this directly without tools")
        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        
        mock_anthropic_client.messages.create.return_value = mock_response
        
        tool_manager = Mock()
        tools = [{"name": "test_tool", "description": "Test tool"}]
        
        result = ai_generator_with_mock.generate_response(
            "What is Python?",
            tools=tools,
            tool_manager=tool_manager
        )
        
        # Verify response
        assert result == "I can answer this directly without tools"
        
        # Verify only one API call was made
        assert mock_anthropic_client.messages.create.call_count == 1
        
        # Verify no tools were executed
        tool_manager.execute_tool.assert_not_called()
    
    def test_sequential_tool_calling_max_rounds_reached(self, ai_generator_with_mock, mock_anthropic_client):
        """Test that sequential calling respects max rounds limit"""
        # Round 1: AI uses tool
        mock_tool_block_1 = Mock()
        mock_tool_block_1.type = "tool_use"
        mock_tool_block_1.name = "search_tool"
        mock_tool_block_1.input = {"query": "search 1"}
        mock_tool_block_1.id = "tool_1"
        
        mock_round1_response = Mock()
        mock_round1_response.content = [mock_tool_block_1]
        mock_round1_response.stop_reason = "tool_use"
        
        # Round 2: AI tries to use tool again but hits max rounds
        mock_tool_block_2 = Mock()
        mock_tool_block_2.type = "tool_use"
        mock_tool_block_2.name = "search_tool"
        mock_tool_block_2.input = {"query": "search 2"}
        mock_tool_block_2.id = "tool_2"
        
        mock_round2_response = Mock()
        mock_round2_response.content = [mock_tool_block_2]
        mock_round2_response.stop_reason = "tool_use"
        
        # Final response after max rounds (no tools available)
        mock_text_block = Mock(text="Final response after max rounds")
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        mock_final_response.stop_reason = "end_turn"
        
        mock_anthropic_client.messages.create.side_effect = [
            mock_round1_response,    # Round 1: tool use
            mock_round2_response,    # Round 2: tool use (max rounds)
            mock_final_response      # Final call: no tools
        ]
        
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = ["Tool result 1", "Tool result 2"]
        
        tools = [{"name": "search_tool", "description": "Search tool"}]
        
        result = ai_generator_with_mock.generate_response(
            "Complex query requiring multiple searches",
            tools=tools,
            tool_manager=tool_manager
        )
        
        # Verify final response
        assert result == "Final response after max rounds"
        
        # Verify exactly 3 API calls (2 tool rounds + 1 final)
        assert mock_anthropic_client.messages.create.call_count == 3
        
        # Verify first two rounds had tools, final round did not
        call_args_round1 = mock_anthropic_client.messages.create.call_args_list[0]
        call_args_round2 = mock_anthropic_client.messages.create.call_args_list[1]
        call_args_final = mock_anthropic_client.messages.create.call_args_list[2]
        
        # Rounds 1 and 2 should have tools
        assert "tools" in call_args_round1[1]
        assert "tools" in call_args_round2[1]
        # Final round should not have tools
        assert "tools" not in call_args_final[1]
        
        # Verify both tools were executed
        assert tool_manager.execute_tool.call_count == 2
    
    def test_sequential_tool_calling_with_tool_execution_error(self, ai_generator_with_mock, mock_anthropic_client):
        """Test handling of tool execution errors in sequential rounds"""
        # Round 1: AI uses tool that fails
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "failing_tool"
        mock_tool_block.input = {"param": "value"}
        mock_tool_block.id = "tool_1"
        
        mock_round1_response = Mock()
        mock_round1_response.content = [mock_tool_block]
        mock_round1_response.stop_reason = "tool_use"
        
        # Round 2: Final response after tool failure
        mock_text_block = Mock(text="Response despite tool failure")
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        mock_final_response.stop_reason = "end_turn"
        
        mock_anthropic_client.messages.create.side_effect = [
            mock_round1_response,
            mock_final_response
        ]
        
        # Tool manager that raises exception
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        
        tools = [{"name": "failing_tool", "description": "Tool that fails"}]
        
        result = ai_generator_with_mock.generate_response(
            "Query that triggers tool failure",
            tools=tools,
            tool_manager=tool_manager
        )
        
        # Should get final response despite tool failure
        assert result == "Response despite tool failure"
        
        # Verify two API calls were made
        assert mock_anthropic_client.messages.create.call_count == 2
        
        # Verify tool was attempted
        tool_manager.execute_tool.assert_called_once()

class TestAIGeneratorErrorHandling:
    """Test error handling in AI Generator"""
    
    def test_anthropic_api_error(self, ai_generator_with_mock, mock_anthropic_client):
        """Test handling of Anthropic API errors"""
        # Setup mock to raise an exception
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")
        
        result = ai_generator_with_mock.generate_response("Test query")
        
        # Should return user-friendly error message instead of raising exception
        assert "I encountered an issue while processing your request" in result
        assert "API Error" in result
    
    def test_tool_execution_error(self, ai_generator_with_mock, mock_anthropic_client):
        """Test handling of tool execution errors"""
        # Setup mock tool use response
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "failing_tool"
        mock_tool_block.input = {"param": "value"}
        mock_tool_block.id = "tool_123"
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        
        # Setup mock tool manager to raise exception
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        
        mock_anthropic_client.messages.create.side_effect = [mock_initial_response]
        
        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": "Test system prompt"
        }
        
        # The tool execution error should propagate
        with pytest.raises(Exception):
            ai_generator_with_mock._handle_tool_execution(
                mock_initial_response,
                base_params,
                tool_manager
            )
    
    def test_malformed_tool_response(self, ai_generator_with_mock, mock_anthropic_client):
        """Test handling of malformed tool responses"""
        # Setup mock response with non-tool content
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Some text"
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_text_block]  # No tool_use blocks
        
        tool_manager = Mock()
        
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response")]
        mock_anthropic_client.messages.create.return_value = mock_final_response
        
        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": "Test system prompt"
        }
        
        # Should handle gracefully with no tool executions
        result = ai_generator_with_mock._handle_tool_execution(
            mock_initial_response,
            base_params,
            tool_manager
        )
        
        # No tools should be executed
        tool_manager.execute_tool.assert_not_called()

class TestAIGeneratorIntegration:
    """Integration tests for AI Generator"""
    
    @pytest.mark.integration
    def test_real_anthropic_api_call(self, test_config):
        """Test with real Anthropic API (requires valid API key)"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-key":
            pytest.skip("No valid Anthropic API key for integration test")
        
        generator = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
        
        try:
            result = generator.generate_response("What is 2+2?")
            assert isinstance(result, str)
            assert len(result) > 0
        except Exception as e:
            pytest.fail(f"Real Anthropic API integration failed: {e}")