from typing import Any, Dict, List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools for course information.

Tool Usage Guidelines:
- **Content Search Tool**: Use for questions about specific course content or detailed educational materials
- **Course Outline Tool**: Use for questions about course structure, lesson lists, or course outlines
- **Multi-step reasoning**: You can make up to 2 tool calls per query to gather comprehensive information
- **Sequential approach**: Use your first tool call to gather initial information, then analyze results to determine if additional searches are needed
- **Tool strategy examples**:
  - First search for general course content, then search specific lessons if needed
  - Search course outline first, then search specific lesson content based on outline
  - Search one course, then search related courses for comparison
  - Get course outline to identify lesson titles, then search for courses with similar topics
- Synthesize all tool results into accurate, fact-based responses
- If any tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use content search tool, optionally followed by refined searches
- **Course outline/structure questions**: Use outline tool first, then content search if needed for details
- **Multi-step queries**: Break down into logical search steps across your available tool calls
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the outline tool"
 - Do not mention round numbers or tool call sequences

For outline responses, always include:
- Course title
- Course link (when available)
- Complete lesson list with numbers and titles

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to 2 sequential tool calling rounds for complex queries.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize round state
        round_state = {
            "round_number": 1,
            "max_rounds": 2,
            "messages": [{"role": "user", "content": query}],
            "system_content": system_content,
            "tools_available": bool(tools and tool_manager),
        }

        # Execute rounds until termination condition
        while round_state["round_number"] <= round_state["max_rounds"]:
            response = self._execute_round(round_state, tools, tool_manager)

            # Check non-max-round termination conditions first
            if self._should_terminate_early(response, round_state):
                return self._extract_final_text(response)

            # If we've reached max rounds, make one final call without tools
            if round_state["round_number"] >= round_state["max_rounds"]:
                # Prepare next round with tool results
                self._prepare_next_round(response, round_state, tool_manager)
                # Make final call without tools
                round_state["tools_available"] = False
                final_response = self._execute_round(round_state, tools, tool_manager)
                return self._extract_final_text(final_response)

            # Prepare for next round
            self._prepare_next_round(response, round_state, tool_manager)
            round_state["round_number"] += 1

        # Fallback (should not reach here)
        return self._extract_final_text(response)

    def _execute_round(
        self, round_state: Dict[str, Any], tools: Optional[List], tool_manager
    ) -> Any:
        """Execute a single round of conversation with Claude."""

        # Build API parameters for this round
        api_params = {
            **self.base_params,
            "messages": round_state["messages"],
            "system": round_state["system_content"],
        }

        # Add tools if available (they can be used in any round)
        if round_state["tools_available"]:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        try:
            response = self.client.messages.create(**api_params)
            return response
        except Exception as e:
            # Return error response for safe handling
            return self._create_error_response(
                f"API error in round {round_state['round_number']}: {str(e)}"
            )

    def _should_terminate_early(self, response, round_state: Dict[str, Any]) -> bool:
        """Determine if we should terminate early (before max rounds)."""

        # Condition 1: Error response
        if isinstance(response, str):
            return True

        # Condition 2: Tool execution failed in previous round
        if round_state.get("tool_execution_failed", False):
            return True

        # Condition 3: No tool use in response
        if not hasattr(response, "content") or not response.content:
            return True

        has_tool_use = any(
            content_block.type == "tool_use"
            for content_block in response.content
            if hasattr(content_block, "type")
        )
        if not has_tool_use:
            return True

        return False

    def _prepare_next_round(self, response, round_state: Dict[str, Any], tool_manager):
        """Prepare state for next round after tool execution."""

        # Add Claude's response with tools to messages
        round_state["messages"].append(
            {"role": "assistant", "content": response.content}
        )

        # Execute tools and collect results
        tool_results = []
        tool_execution_failed = False

        for content_block in response.content:
            if hasattr(content_block, "type") and content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )
                except Exception as e:
                    # Tool execution failed - mark for termination
                    tool_execution_failed = True
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Tool execution failed: {str(e)}",
                        }
                    )

        # Add tool results to conversation
        if tool_results:
            round_state["messages"].append({"role": "user", "content": tool_results})

        # Mark if tool execution failed
        round_state["tool_execution_failed"] = tool_execution_failed

    def _extract_final_text(self, response) -> str:
        """Safely extract text from final response."""
        try:
            # Handle error responses (strings)
            if isinstance(response, str):
                return response

            # Handle API responses
            if hasattr(response, "content") and response.content:
                return response.content[0].text

            return "I was unable to generate a complete response. Please try again."
        except (AttributeError, IndexError, TypeError):
            return "I encountered an error processing the response. Please try again."

    def _create_error_response(self, error_message: str) -> str:
        """Create a user-friendly error response."""
        return f"I encountered an issue while processing your request: {error_message}. Please try rephrasing your question."

    def _handle_tool_execution(
        self, initial_response, base_params: Dict[str, Any], tool_manager
    ):
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
        }

        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
