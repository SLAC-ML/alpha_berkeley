"""
Conversational Capability for Hello World Weather Tutorial.

Implements general conversational interaction capability for the Alpha Berkeley Agent
Framework, demonstrating how to handle chat history queries, greetings, meta questions,
and general conversation. This capability serves as a chatbot mode that activates when
users engage in conversation rather than requesting specific tasks.

The capability integrates with the framework's chat history system to provide context-aware
conversational responses, enabling the agent to answer questions about previous interactions,
engage in casual conversation, and provide information about its own capabilities.

Architecture Integration:
    The capability integrates with multiple framework systems:

    1. **Chat History System**: Access to full conversation history via state["messages"]
    2. **LLM Integration**: Uses configured language model for natural conversation
    3. **State Management**: Context storage through StateManager utilities
    4. **Orchestration**: Planning guidance for conversational workflow integration
    5. **Classification**: Task analysis guidance for conversational query detection

Business Logic:
    The capability implements a complete conversational workflow:

    1. **Query Classification**: Determines type of conversational interaction
    2. **History Access**: Retrieves full chat history for context-aware responses
    3. **LLM Processing**: Generates natural language responses using language model
    4. **Context Creation**: Packages responses in ConversationalContext
    5. **State Storage**: Framework integration via StateManager utilities

.. note::
   This capability complements task-specific capabilities like current_weather,
   enabling the agent to function as both a task-oriented assistant and a
   general conversational chatbot.

.. warning::
   The capability uses LLM calls for response generation, which may have
   latency implications. Consider caching strategies for production use.
"""

import asyncio
from typing import Dict, Any, Optional

from framework.base import (
    BaseCapability, capability_node,
    OrchestratorGuide, OrchestratorExample, PlannedStep,
    ClassifierActions, ClassifierExample, TaskClassifierGuide
)
from framework.base.errors import ErrorClassification, ErrorSeverity
from framework.registry import get_registry
from framework.state import AgentState, StateManager, ChatHistoryFormatter
from framework.models import get_chat_completion
from configs.logger import get_logger
from configs.config import get_model_config
from configs.streaming import get_streamer

from applications.hello_world_weather.context_classes import ConversationalContext

logger = get_logger("hello_world_weather", "conversational")
registry = get_registry()


def _classify_query_type(query: str) -> str:
    """Classify the type of conversational query for analytics.

    Simple pattern matching to categorize different types of conversational
    interactions. This helps with analytics and future optimization.

    :param query: The user's query text
    :type query: str
    :return: Query type classification
    :rtype: str
    """
    query_lower = query.lower()

    # Chat history patterns
    if any(word in query_lower for word in ["first question", "asked", "said", "conversation", "earlier", "previous"]):
        return "chat_history"

    # Greeting patterns
    if any(word in query_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
        return "greeting"

    # Meta/capability patterns
    if any(word in query_lower for word in ["can you", "what can", "help me", "capabilities", "what tools", "what do you"]):
        return "meta"

    # General conversation
    return "general"


@capability_node
class ConversationalCapability(BaseCapability):
    """General conversational interaction capability for chatbot functionality.

    Implements comprehensive conversational capabilities including chat history analysis,
    greetings, meta questions, and general conversation. This capability enables the
    agent to function as a natural chatbot when users engage in conversation rather
    than requesting specific tasks.

    The capability leverages the framework's chat history system to provide context-aware
    responses, enabling sophisticated conversational interactions that reference previous
    messages, maintain conversation flow, and provide helpful information about the
    agent's capabilities.

    Capability Characteristics:
        - **Name**: "conversational" (unique identifier for registry and routing)
        - **Description**: Handles general conversation and chatbot interactions
        - **Provides**: ["CONVERSATIONAL_RESPONSE"] - Conversational response context
        - **Requires**: [] - No input context dependencies (uses chat history directly)
        - **LangGraph Integration**: Full node integration via @capability_node decorator

    Execution Workflow:
        The capability implements a structured conversational pattern:

        1. **Initialization**: Extract current step and initialize streaming support
        2. **History Access**: Retrieve full conversation history from agent state
        3. **Query Classification**: Determine type of conversational interaction
        4. **Prompt Construction**: Build context-aware LLM prompt with chat history
        5. **LLM Processing**: Generate natural language response
        6. **Context Creation**: Package response in ConversationalContext
        7. **State Storage**: Store context using StateManager utilities
        8. **Status Updates**: Provide real-time progress feedback via streaming

    Conversational Patterns:
        The capability handles multiple interaction types:

        - **Chat History**: "What was my first question?", "What did we discuss?"
        - **Greetings**: "Hello", "How are you?", "Good morning"
        - **Meta Questions**: "What can you do?", "What tools do you have?"
        - **General Chat**: "Tell me a joke", "How's the weather looking?"

    Error Handling:
        The capability implements conversational-specific error classification:

        - **Retriable Errors**: LLM timeouts and transient API failures
        - **Critical Errors**: All other exceptions requiring immediate attention
        - **Retry Policy**: 3 attempts with exponential backoff (0.5s base, 1.5x factor)

    .. note::
       This capability is designed to complement task-specific capabilities,
       not replace them. The classifier should prefer specific capabilities
       (like current_weather) when applicable, using conversational as fallback.

    .. warning::
       Conversational responses depend on LLM quality and prompt engineering.
       Production implementations should monitor response quality and implement
       content filtering as needed.

    Examples:
        Typical conversational interactions::

            >>> # Chat history query
            >>> state = AgentState({
            ...     "messages": [
            ...         HumanMessage("What's the weather in SF?"),
            ...         AIMessage("San Francisco is 16°C and Sunny"),
            ...         HumanMessage("What was my first question?")
            ...     ],
            ...     "task_current_task": "What was my first question?"
            ... })
            >>> result = await ConversationalCapability.execute(state)

            >>> # Greeting
            >>> state = AgentState({
            ...     "messages": [HumanMessage("Hello!")],
            ...     "task_current_task": "Hello!"
            ... })
            >>> result = await ConversationalCapability.execute(state)

    .. seealso::
       :class:`framework.base.BaseCapability` : Base class with required method implementations
       :func:`framework.base.capability_node` : Decorator providing LangGraph integration
       :class:`ConversationalContext` : Context class for conversational data storage
       :class:`framework.state.ChatHistoryFormatter` : Chat history formatting utilities
       :class:`framework.state.StateManager` : State management utilities
    """

    # Required class attributes for registry configuration
    name = "conversational"
    description = "Handle general conversation, chat history queries, greetings, and meta questions"
    provides = ["CONVERSATIONAL_RESPONSE"]
    requires = []

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute conversational interaction workflow with chat history context.

        Implements the core business logic for conversational interactions including
        chat history access, query classification, LLM processing, and context creation.
        This method demonstrates essential patterns for building conversational capabilities
        within the Alpha Berkeley Agent Framework.

        The execution workflow follows a structured pattern that integrates with
        multiple framework systems while maintaining clear separation of concerns
        between conversational logic, state management, and user feedback systems.

        Execution Steps:
            1. **State Extraction**: Retrieve current execution step and task information
            2. **Streaming Setup**: Initialize real-time status updates for user feedback
            3. **History Access**: Retrieve full conversation history from agent state
            4. **Query Classification**: Determine type of conversational interaction
            5. **Prompt Construction**: Build LLM prompt with chat history context
            6. **LLM Processing**: Generate natural language response
            7. **Context Creation**: Package response in ConversationalContext
            8. **State Integration**: Store context using framework state management
            9. **Status Updates**: Provide completion feedback via streaming system

        Prompt Construction:
            The LLM prompt includes:

            - **System Instructions**: Role and behavior guidance
            - **Conversation History**: Full formatted chat history for context
            - **Current Query**: User's current conversational request
            - **Response Guidelines**: Natural, helpful interaction style

        State Management Integration:
            The method uses StateManager utilities for proper framework integration:

            - **Context Storage**: Stores conversational data using registry context types
            - **Key Management**: Uses step context key for unique identification
            - **State Updates**: Returns LangGraph-compatible state update dictionary

        :param state: Current agent state containing execution context and chat history
        :type state: AgentState
        :param kwargs: Additional execution parameters (unused in current implementation)
        :type kwargs: Any
        :return: LangGraph-compatible state update dictionary containing stored context data
        :rtype: Dict[str, Any]
        :raises Exception: Re-raises all exceptions for framework error handling coordination

        .. note::
           This method is called automatically by the @capability_node decorator
           which provides comprehensive error handling, retry coordination, and
           execution tracking around the business logic.

        .. warning::
           The method makes synchronous LLM calls wrapped in asyncio.to_thread.
           Consider implementing streaming responses for better user experience
           in production systems.

        Examples:
            Typical execution flow::

                >>> state = AgentState({
                ...     "messages": [...],
                ...     "task_current_task": "What was my first question?",
                ...     "planning_execution_plan": {...},
                ...     "planning_current_step_index": 0
                ... })
                >>> updates = await ConversationalCapability.execute(state)
                >>> conv_data = updates["capability_context_data"]["CONVERSATIONAL_RESPONSE"]
                >>> print(f"Response: {list(conv_data.keys())}")
                Response: ['step_0']

        .. seealso::
           :class:`framework.state.StateManager` : State management utilities used by this method
           :class:`ConversationalContext` : Context class created during execution
           :func:`get_streamer` : Streaming utilities for real-time status updates
           :class:`ChatHistoryFormatter` : Chat history formatting utilities
        """
        step = StateManager.get_current_step(state)
        streamer = get_streamer("hello_world_weather", "conversational", state)

        try:
            streamer.status("Analyzing conversational query...")

            # Get current task and chat history
            current_task = StateManager.get_current_task(state)
            messages = state.get("messages", [])

            # Classify query type for analytics
            query_type = _classify_query_type(current_task)
            logger.info(f"Conversational query type: {query_type}")

            streamer.status("Retrieving conversation history...")

            # Format chat history for LLM
            chat_history = ChatHistoryFormatter.format_for_llm(messages) if messages else "No previous conversation"

            streamer.status("Generating conversational response...")

            # Create LLM prompt with chat history context
            prompt = f"""You are a helpful AI assistant. Answer this conversational query based on the conversation history.

CONVERSATION HISTORY:
{chat_history}

CURRENT USER QUERY: {current_task}

Provide a natural, helpful response. If the query is about the conversation history,
reference specific messages. If it's a greeting, respond warmly. If it's a meta question
about your capabilities, be informative."""

            # Get LLM response (run in thread pool for async compatibility)
            response_text = await asyncio.to_thread(
                get_chat_completion,
                message=prompt,
                model_config=get_model_config("framework", "response")
            )

            # Handle response format
            if isinstance(response_text, list):
                # Handle structured responses
                response_text = str(response_text)
            elif not isinstance(response_text, str):
                response_text = str(response_text)

            logger.success(f"Generated conversational response (type: {query_type})")

            # Create context object
            context = ConversationalContext(
                response_text=response_text,
                query_type=query_type
            )

            # Store context in framework state
            context_updates = StateManager.store_context(
                state,
                registry.context_types.CONVERSATIONAL_RESPONSE,
                step.get("context_key"),
                context
            )

            streamer.status(f"Conversational response ready ({query_type})")
            return context_updates

        except Exception as e:
            logger.error(f"Conversational interaction error: {e}")
            raise

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """Classify conversational interaction errors for intelligent retry coordination.

        Analyzes exceptions from conversational interaction operations and provides
        domain-specific error classification to guide the framework's retry and
        error handling systems.

        :param exc: Exception raised during conversational interaction operations
        :type exc: Exception
        :param context: Execution context dictionary containing state and configuration
        :type context: dict
        :return: Error classification with severity level, user message, and technical details
        :rtype: ErrorClassification
        """
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message="Conversational service timeout, retrying...",
                metadata={"technical_details": str(exc)}
            )

        return ErrorClassification(
            severity=ErrorSeverity.CRITICAL,
            user_message=f"Conversational interaction error: {str(exc)}",
            metadata={"technical_details": f"Error: {type(exc).__name__}"}
        )

    @staticmethod
    def get_retry_policy() -> Dict[str, Any]:
        """Define retry policy configuration for conversational operations.

        :return: Dictionary containing retry policy configuration
        :rtype: Dict[str, Any]
        """
        return {
            "max_attempts": 3,
            "delay_seconds": 0.5,
            "backoff_factor": 1.5
        }

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Provide orchestration guidance for conversational capability planning.

        Creates comprehensive guidance for the framework's orchestration system to
        understand when and how to include conversational interactions in execution plans.

        :return: Complete orchestrator guidance for conversational integration
        :rtype: Optional[OrchestratorGuide]
        """
        example = OrchestratorExample(
            step=PlannedStep(
                context_key="conversational_response",
                capability="conversational",
                task_objective="Handle conversational query with chat history context",
                expected_output=registry.context_types.CONVERSATIONAL_RESPONSE,
                success_criteria="Natural conversational response generated",
                inputs=[]
            ),
            scenario_description="Handling general conversation or chat history query",
            notes=f"Output stored as {registry.context_types.CONVERSATIONAL_RESPONSE} with conversational response."
        )

        return OrchestratorGuide(
            instructions=f"""**When to plan "conversational" steps:**
- When users engage in general conversation or greetings
- For questions about conversation history ("What was my first question?")
- For meta questions about assistant capabilities ("What can you do?")
- As fallback when no specific task capability applies

**Output: {registry.context_types.CONVERSATIONAL_RESPONSE}**
- Contains: response_text, query_type
- Has full access to chat history for context-aware responses
- Suitable for general chatbot interactions

**Usage Pattern:**
- Use for conversational queries, NOT for specific tasks
- Weather queries should use current_weather capability instead
- This is the chatbot mode of the assistant""",
            examples=[example],
            order=1  # Low priority - only use when no specific task capability applies
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Provide task classification guidance for conversational capability selection.

        Creates comprehensive guidance for the framework's task classification system
        to understand when user queries require conversational interaction capabilities.

        :return: Complete task classifier guidance for conversational activation
        :rtype: Optional[TaskClassifierGuide]
        """
        return TaskClassifierGuide(
            instructions="Activate for conversational queries, greetings, chat history questions, and meta questions about the assistant",
            examples=[
                ClassifierExample(
                    query="What was my first question?",
                    result=True,
                    reason="Question about conversation history - needs chat history access"
                ),
                ClassifierExample(
                    query="Hello, how are you?",
                    result=True,
                    reason="General greeting/conversation - conversational capability"
                ),
                ClassifierExample(
                    query="What can you do?",
                    result=True,
                    reason="Meta question about capabilities - conversational response"
                ),
                ClassifierExample(
                    query="Tell me a joke",
                    result=True,
                    reason="Conversational request - general interaction"
                ),
                ClassifierExample(
                    query="How's it going?",
                    result=True,
                    reason="Casual conversation - conversational capability"
                ),
                ClassifierExample(
                    query="What's the weather in SF?",
                    result=False,
                    reason="Specific task requiring current_weather capability, not conversational"
                ),
                ClassifierExample(
                    query="What was the temperature you mentioned?",
                    result=True,
                    reason="Question about previous response - needs chat history analysis"
                ),
                ClassifierExample(
                    query="Calculate the square root of 16",
                    result=True,
                    reason="May need previous context if references prior data, otherwise conversational"
                ),
            ],
            actions_if_true=ClassifierActions()
        )
