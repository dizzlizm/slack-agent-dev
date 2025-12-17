"""
Message routing for Slack messages.
Routes incoming messages to appropriate handlers.
"""
import logging
from typing import Optional

from src.config import Config
from src.integrations.slack_client import SlackClientWrapper
from src.storage import ConversationManager, TriageSessionManager, AuthorizationManager

logger = logging.getLogger(__name__)

# Global singletons (initialized on first use)
_slack_client: Optional[SlackClientWrapper] = None
_conversation_manager: Optional[ConversationManager] = None
_triage_manager: Optional[TriageSessionManager] = None
_auth_manager: Optional[AuthorizationManager] = None
_mcp_orchestrator: Optional[any] = None
_initialized = False


def _initialize():
    """Initialize services on first use."""
    global _slack_client, _conversation_manager, _triage_manager
    global _auth_manager, _mcp_orchestrator, _initialized

    if _initialized:
        return

    logger.info("Initializing message router services...")

    try:
        # Initialize Slack client
        _slack_client = SlackClientWrapper()
        logger.debug("SlackClientWrapper initialized")

        # Initialize storage managers
        _conversation_manager = ConversationManager()
        logger.debug("ConversationManager initialized")

        _triage_manager = TriageSessionManager()
        logger.debug("TriageSessionManager initialized")

        _auth_manager = AuthorizationManager()
        logger.debug("AuthorizationManager initialized")

        # Initialize MCP orchestrator if Gemini is enabled
        if Config.is_gemini_enabled():
            try:
                from src.integrations.mcp_integration import GeminiMCPOrchestrator
                _mcp_orchestrator = GeminiMCPOrchestrator()
                logger.info("MCP Orchestrator initialized")
            except Exception as e:
                logger.warning(f"MCP Orchestrator not initialized: {e}")

        _initialized = True
        logger.info("Message router services initialized")

    except Exception as e:
        logger.error(f"Failed to initialize message router services: {e}", exc_info=True)
        raise


def route_message(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str] = None,
    message_ts: Optional[str] = None
) -> None:
    """
    Route an incoming message to the appropriate handler.

    Args:
        text: The message text
        user_id: Slack user ID who sent the message
        channel_id: Slack channel ID where message was sent
        thread_ts: Thread timestamp if in a thread
        message_ts: Message timestamp
    """
    logger.info(f"=== ROUTE MESSAGE START ===")
    logger.info(f"user={user_id}, channel={channel_id}, thread_ts={thread_ts}, message_ts={message_ts}")
    logger.info(f"text: {text[:100]}")

    try:
        # Initialize services (must be inside try block)
        logger.info("Initializing services...")
        _initialize()
        logger.info("Services initialized successfully")

        # Check if user is authorized
        logger.info(f"Checking authorization for {user_id}...")
        if not _auth_manager.is_authorized(user_id):
            logger.warning(f"Unauthorized user {user_id} attempted to use bot")
            _slack_client.post_message(
                channel=channel_id,
                text="Sorry, you're not authorized to use this bot. Please contact an administrator.",
                thread_ts=thread_ts or message_ts
            )
            return

        logger.info(f"User {user_id} is authorized")

        # Check if this is part of an active triage session
        if thread_ts:
            logger.info(f"Checking for active triage session in thread {thread_ts}")
            session = _triage_manager.get_session(channel_id, thread_ts)
            if session and session.is_active():
                logger.info("Active triage session found, routing to triage handler")
                _handle_triage_message(text, user_id, channel_id, thread_ts, session)
                return

        # Route to MCP orchestrator for natural language processing
        if _mcp_orchestrator:
            logger.info("MCP orchestrator available, routing to MCP handler")
            _handle_mcp_message(text, user_id, channel_id, thread_ts, message_ts)
        else:
            logger.warning("MCP orchestrator not available, sending fallback message")
            # Fallback: just acknowledge the message
            _slack_client.post_message(
                channel=channel_id,
                text="I received your message, but AI processing is not configured. Please add GEMINI_API_KEY to secrets.",
                thread_ts=thread_ts or message_ts
            )

        logger.info("=== ROUTE MESSAGE SUCCESS ===")

    except Exception as e:
        logger.error(f"=== ROUTE MESSAGE FAILED ===")
        logger.error(f"Error routing message: {e}", exc_info=True)
        # Only try to send error message if slack client was initialized
        if _slack_client is not None:
            try:
                _slack_client.post_message(
                    channel=channel_id,
                    text="Sorry, I encountered an error processing your request. Please try again.",
                    thread_ts=thread_ts or message_ts
                )
            except Exception as post_err:
                logger.error(f"Failed to send error message to Slack: {post_err}", exc_info=True)


def _handle_mcp_message(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str],
    message_ts: Optional[str]
) -> None:
    """Handle a message using the MCP orchestrator."""
    logger.info(f"=== MCP MESSAGE HANDLER START ===")
    logger.info(f"Processing message for user {user_id} in channel {channel_id}")
    logger.info(f"thread_ts={thread_ts}, message_ts={message_ts}")

    # Determine timestamps for different operations
    # Reactions go on the actual message (message_ts)
    # Replies go in the thread (thread_ts) or start a new thread (message_ts)
    reaction_ts = message_ts
    reply_ts = thread_ts or message_ts

    try:
        # Add thinking indicator to the user's message
        logger.info(f"Adding thinking reaction to message {reaction_ts}...")
        _slack_client.add_reaction(channel_id, reaction_ts, "thinking_face")

        # Get user's email for context (MCP orchestrator uses email for user lookups)
        logger.info("Getting user email from Slack...")
        user_email = _slack_client.get_user_email(user_id)
        logger.info(f"User email: {user_email}")

        # Process with MCP orchestrator
        # Note: process_query takes user_query and optional user_email
        logger.info("Calling MCP orchestrator process_query...")
        response = _mcp_orchestrator.process_query(
            user_query=text,
            user_email=user_email
        )
        logger.info(f"MCP orchestrator returned response: {len(response) if response else 0} chars")

        # Remove thinking indicator
        logger.info(f"Removing thinking reaction from message {reaction_ts}...")
        _slack_client.remove_reaction(channel_id, reaction_ts, "thinking_face")

        # Validate response
        if not response or not response.strip():
            logger.warning("MCP orchestrator returned empty response, using fallback")
            response = "I processed your message but couldn't generate a response. Please try again."

        # Post response in thread
        logger.info(f"Posting response to Slack (length: {len(response)}), reply_ts={reply_ts}...")
        _slack_client.post_message(
            channel=channel_id,
            text=response,
            thread_ts=reply_ts
        )
        logger.info("Response posted successfully")

        # Save to conversation history
        logger.info("Saving to conversation history...")
        _conversation_manager.add_exchange(user_id, text, response)

        logger.info("=== MCP MESSAGE HANDLER SUCCESS ===")

    except Exception as e:
        logger.error(f"=== MCP MESSAGE HANDLER FAILED ===")
        logger.error(f"Error in MCP message handling: {e}", exc_info=True)
        _slack_client.remove_reaction(channel_id, reaction_ts, "thinking_face")
        raise


def _handle_triage_message(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: str,
    session
) -> None:
    """Handle a message in an active triage session."""
    try:
        from src.core.triage_workflow import TriageWorkflow

        workflow = TriageWorkflow(
            slack_client=_slack_client,
            triage_manager=_triage_manager
        )

        workflow.continue_triage(
            session=session,
            user_response=text,
            channel_id=channel_id,
            thread_ts=thread_ts
        )

    except Exception as e:
        logger.error(f"Error in triage handling: {e}", exc_info=True)
        raise
