"""
Azure Functions application for Slack bot.
Refactored with clean architecture and error handling.
"""
import azure.functions as func
import logging
import json
import threading
from typing import Optional

from azure.data.tables import TableServiceClient

# Local imports
from config import Config, ConfigurationError
from slack_client import SlackClientWrapper
from auth_manager import AuthorizationManager
from conversation_manager import ConversationManager
from triage_manager import TriageSessionManager
from command_parser import CommandRouter, CommandParser
from command_handlers import CommandHandlers
from interactive_handler import InteractiveHandler
from triage_workflow import TriageWorkflow
from exceptions import BotException
from mcp_tools import get_freshservice_tools

# =========================================================================
# INITIALIZATION
# =========================================================================

# Initialize the Azure Function app
app = func.FunctionApp()

# Global singletons (initialized on first request)
_slack_client: Optional[SlackClientWrapper] = None
_auth_manager: Optional[AuthorizationManager] = None
_conversation_manager: Optional[ConversationManager] = None
_triage_manager: Optional[TriageSessionManager] = None
_command_router: Optional[CommandRouter] = None
_command_handlers: Optional[CommandHandlers] = None
_interactive_handler: Optional[InteractiveHandler] = None
_triage_workflow: Optional[TriageWorkflow] = None
_mcp_orchestrator: Optional[any] = None  # GeminiMCPOrchestrator singleton
_initialized = False


def initialize_app() -> None:
    """Initialize all services and handlers (called on first request)."""
    global _slack_client, _auth_manager, _conversation_manager, _triage_manager
    global _command_router, _command_handlers, _interactive_handler, _triage_workflow
    global _mcp_orchestrator, _initialized
    
    if _initialized:
        return
    
    try:
        logging.info("=" * 60)
        logging.info("INITIALIZING SLACK BOT APPLICATION")
        logging.info("=" * 60)
        
        # Load configuration
        Config.load()
        
        # Initialize Azure Table Storage
        table_service = TableServiceClient.from_connection_string(
            conn_str=Config.AZURE_STORAGE_CONNECTION_STRING
        )
        
        auth_table = table_service.get_table_client(Config.AUTH_TABLE_NAME)
        convo_table = table_service.get_table_client(Config.CONVO_TABLE_NAME)
        triage_table = table_service.get_table_client(Config.TRIAGE_TABLE_NAME)
        
        # Initialize core services
        _slack_client = SlackClientWrapper()
        _auth_manager = AuthorizationManager(auth_table)
        _conversation_manager = ConversationManager(convo_table)
        _triage_manager = TriageSessionManager(triage_table)

        # Initialize MCP orchestrator if Gemini is enabled (needed by command handlers)
        if Config.is_gemini_enabled():
            try:
                from mcp_integration import GeminiMCPOrchestrator
                _mcp_orchestrator = GeminiMCPOrchestrator()
                logging.info("✅ MCP Orchestrator initialized")
            except Exception as e:
                logging.warning(f"MCP Orchestrator not initialized: {e}")

        # Initialize command system (pass MCP orchestrator for 'fresh' command)
        _command_handlers = CommandHandlers(
            _slack_client,
            _auth_manager,
            _conversation_manager,
            _mcp_orchestrator  # Pass singleton orchestrator
        )
        
        _command_router = CommandRouter()

        # Register specific commands (non-MCP)
        _command_router.register("help", _command_handlers.handle_help)
        _command_router.register("admin", _command_handlers.handle_admin)
        _command_router.register("ask", _command_handlers.handle_ask)
        _command_router.register("reset", _command_handlers.handle_reset)

        # Set default handler for ALL other commands → intelligent MCP routing
        # This means ANY @systems <query> will go to Gemini for intelligent routing
        # No need to say "@systems fresh" or "@systems meraki" - just "@systems help me with X"
        if Config.is_gemini_enabled():
            _command_router.set_default_handler(_command_handlers.handle_smart)
            logging.info("✅ Intelligent MCP routing enabled - all unknown commands will be handled by AI")
        
        # Initialize interactive handler
        _interactive_handler = InteractiveHandler(
            _slack_client,
            _auth_manager,
            _triage_manager
        )
        
        # Initialize triage workflow (if Gemini is enabled)
        if Config.is_gemini_enabled():
            _triage_workflow = TriageWorkflow(
                _slack_client,
                _triage_manager
            )

        _initialized = True
        logging.info("✅ Bot initialization complete")
        logging.info(f"✅ Registered commands: {_command_router.get_available_commands()}")
        logging.info("=" * 60)
        
    except ConfigurationError as e:
        logging.error(f"❌ Configuration error: {e}")
        raise
    except Exception as e:
        logging.error(f"❌ Initialization failed: {e}", exc_info=True)
        raise


# =========================================================================
# AZURE FUNCTION HANDLERS
# =========================================================================


@app.route(route="slack/events", auth_level=func.AuthLevel.ANONYMOUS, methods=['POST'])
def SlackEventsHandler(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle Slack event callbacks (DMs, mentions, messages).
    """
    try:
        req_body = req.get_json()
    except ValueError:
        logging.error("Invalid JSON in request body")
        return func.HttpResponse("Invalid JSON", status_code=400)
    
    # Handle URL verification challenge
    if req_body.get('type') == 'url_verification':
        challenge = req_body.get('challenge', '')
        logging.info("Responding to Slack URL verification challenge")
        return func.HttpResponse(challenge, status_code=200, mimetype="text/plain")
    
    # Initialize app on first request
    initialize_app()
    
    # Handle event callbacks
    if req_body.get('type') == 'event_callback':
        event = req_body.get('event', {})
        
        # Only process message events
        if event.get("type") != "message":
            return func.HttpResponse(status_code=200)
        
        # CRITICAL: Ignore bot messages and edits to prevent loops
        # Check multiple conditions to ensure we don't process our own messages
        if event.get("bot_id"):
            logging.debug("Ignoring message from bot (bot_id present)")
            return func.HttpResponse(status_code=200)
        
        if event.get("subtype") is not None:
            logging.debug(f"Ignoring message with subtype: {event.get('subtype')}")
            return func.HttpResponse(status_code=200)
        
        # Additional check: Ignore if message is from our bot user
        user_id = event.get("user")
        if user_id == Config.SLACK_BOT_USER_ID:
            logging.debug(f"Ignoring message from our own bot user: {user_id}")
            return func.HttpResponse(status_code=200)
        
        # Extract event details
        user_id = event.get("user")
        text = event.get("text", "").strip()
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        message_ts = event.get("ts")
        
        if not text or not user_id:
            logging.debug("Ignoring message with no text or user_id")
            return func.HttpResponse(status_code=200)
        
        # Deduplicate: Check if we've seen this exact message recently
        # (Slack sometimes sends duplicate events during retries)
        message_key = f"{channel_id}-{message_ts}"
        if not hasattr(SlackEventsHandler, '_recent_messages'):
            SlackEventsHandler._recent_messages = set()

        if message_key in SlackEventsHandler._recent_messages:
            logging.warning(f"Duplicate event detected: {message_key}, ignoring")
            return func.HttpResponse(status_code=200)

        SlackEventsHandler._recent_messages.add(message_key)

        # Keep only last 1000 message keys to prevent memory leak
        if len(SlackEventsHandler._recent_messages) > 1000:
            # Remove oldest entries (convert to list, slice, convert back)
            SlackEventsHandler._recent_messages = set(list(SlackEventsHandler._recent_messages)[-1000:])
        
        logging.info(f"[{user_id}] Message in {channel_id}: {text[:50]}...")

        # Process in background thread to avoid Slack 3-second timeout
        # If we don't return 200 OK within 3 seconds, Slack will retry the event
        thread = threading.Thread(
            target=_route_message,
            args=(text, user_id, channel_id, thread_ts, message_ts)
        )
        thread.start()

    # Immediately return 200 OK to prevent Slack retries
    return func.HttpResponse(status_code=200)


@app.route(route="slack/interactive", auth_level=func.AuthLevel.ANONYMOUS, methods=['POST'])
def SlackInteractiveHandler(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle Slack interactive component callbacks (button clicks).
    """
    try:
        payload_str = req.form.get('payload')
        if not payload_str:
            logging.error("No payload in interactive request")
            return func.HttpResponse("Missing payload", status_code=400)
        
        # Initialize app on first request
        initialize_app()
        
        # Process in background thread to avoid 3-second timeout
        thread = threading.Thread(
            target=_process_interactive_payload,
            args=(payload_str,)
        )
        thread.start()
        
        # Immediately return 200 OK to Slack
        return func.HttpResponse(status_code=200)
        
    except Exception as e:
        logging.error(f"Error in interactive handler: {e}", exc_info=True)
        return func.HttpResponse(status_code=500)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS, methods=['GET'])
def HealthCheck(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint to verify bot is running and configured.
    """
    try:
        initialize_app()

        health_status = {
            "status": "healthy",
            "integrations": {
                "meraki": Config.is_meraki_enabled(),
                "gemini": Config.is_gemini_enabled(),
                "freshservice": Config.is_freshservice_enabled(),
                "intune": Config.is_intune_enabled()
            },
            "monitored_channels": len(Config.MONITORED_SLACK_CHANNEL_IDS)
        }

        return func.HttpResponse(
            json.dumps(health_status, indent=2),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        error_response = {
            "status": "unhealthy",
            "error": str(e)
        }
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=503,
            mimetype="application/json"
        )


@app.route(route="mcp/tools", auth_level=func.AuthLevel.FUNCTION, methods=['POST'])
def McpToolServer(req: func.HttpRequest) -> func.HttpResponse:
    """
    MCP Tool Server endpoint for Freshservice tools.
    Handles JSON-RPC 2.0 requests for Freshservice operations.

    This endpoint allows the bot (or external clients) to execute Freshservice tools
    via a standardized JSON-RPC interface.
    """
    logging.info('MCP Tool Server received a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        logging.error("Invalid JSON in MCP request body")
        return func.HttpResponse("Invalid JSON", status_code=400)

    # Initialize app to ensure config is loaded
    initialize_app()

    # Extract JSON-RPC fields
    method_name = req_body.get("method")
    params = req_body.get("params", {})
    req_id = req_body.get("id")

    if not method_name:
        error_response = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: method is required"},
            "id": req_id
        }
        return func.HttpResponse(
            json.dumps(error_response),
            mimetype="application/json",
            status_code=200
        )

    logging.info(f"MCP Tool Request: {method_name} with params {params}")

    result = None
    error = None

    try:
        # Get the unified tools instance (Freshservice, Meraki, Intune)
        from mcp_tools import get_unified_tools
        unified_tools = get_unified_tools()

        # Execute the tool (automatically routes to correct backend)
        result = unified_tools.execute_tool(method_name, params)

    except ValueError as ve:
        # Client error (invalid params, tool not found, etc.)
        logging.warning(f"Tool execution failed (client error): {ve}")
        error = {"code": -32602, "message": str(ve)}

    except Exception as ex:
        # Server error (unexpected)
        logging.error(f"Tool execution failed (server error): {ex}", exc_info=True)
        error = {"code": -32603, "message": f"Internal Error: {str(ex)}"}

    # Build JSON-RPC response
    if error:
        response_data = {"jsonrpc": "2.0", "error": error, "id": req_id}
    else:
        response_data = {"jsonrpc": "2.0", "result": result, "id": req_id}

    return func.HttpResponse(
        json.dumps(response_data),
        mimetype="application/json",
        status_code=200
    )


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================


def _route_message(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str],
    message_ts: str
) -> None:
    """
    Route a message to the appropriate handler.
    
    Args:
        text: The message text
        user_id: The user ID
        channel_id: The channel ID
        thread_ts: Thread timestamp (if threaded)
        message_ts: The message timestamp
    """
    parser = CommandParser()
    
    # Check if this is a bot mention (command)
    if parser.is_bot_mention(text):
        _handle_command(text, user_id, channel_id, thread_ts)
        return
    
    # Check if this is a threaded reply to an active triage session
    if thread_ts:
        _handle_threaded_reply(channel_id, thread_ts, user_id, text)
        return
    
    # Check if this is a new message in a monitored channel (potential triage)
    if channel_id in Config.MONITORED_SLACK_CHANNEL_IDS and _triage_workflow:
        _handle_potential_triage(text, user_id, channel_id, message_ts)
        return
    
    # Otherwise, ignore
    logging.debug(f"Message in {channel_id} not routed (no matching handler)")


def _handle_command(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str]
) -> None:
    """Handle a bot mention command."""
    parser = CommandParser()
    
    parsed_command = parser.parse_mention_command(
        text, user_id, channel_id, thread_ts
    )
    
    if not parsed_command:
        # Just a mention, no command
        return
    
    logging.info(f"[{user_id}] Command: {parsed_command.command}")
    
    try:
        # Get the handler and execute
        handler = _command_router.route(parsed_command)
        handler(parsed_command)
        
    except BotException as e:
        logging.warning(f"Bot exception in command {parsed_command.command}: {e}")
        _slack_client.post_message(
            channel=channel_id,
            text=e.user_friendly_message,
            thread_ts=thread_ts
        )
    except Exception as e:
        logging.error(f"Unexpected error in command {parsed_command.command}: {e}", exc_info=True)
        _slack_client.post_message(
            channel=channel_id,
            text=f"❌ An unexpected error occurred: {e}",
            thread_ts=thread_ts
        )


def _handle_threaded_reply(
    channel_id: str,
    thread_ts: str,
    user_id: str,
    text: str
) -> None:
    """Handle a threaded reply (potentially part of triage)."""
    if not _triage_workflow:
        return
    
    # Process in background thread
    thread = threading.Thread(
        target=_triage_workflow.handle_triage_reply,
        args=(channel_id, thread_ts, user_id, text)
    )
    thread.start()


def _handle_potential_triage(
    text: str,
    user_id: str,
    channel_id: str,
    message_ts: str
) -> None:
    """Handle a message that might need triage."""
    if not _triage_workflow:
        return
    
    # Process in background thread
    thread = threading.Thread(
        target=_triage_workflow.start_triage,
        args=(text, user_id, channel_id, message_ts)
    )
    thread.start()


def _process_interactive_payload(payload_str: str) -> None:
    """
    Process an interactive payload in a background thread.
    
    Args:
        payload_str: JSON string of the payload
    """
    try:
        payload = json.loads(payload_str)
        _interactive_handler.handle_payload(payload)
    except Exception as e:
        logging.error(f"Error processing interactive payload: {e}", exc_info=True)


# =========================================================================
# STARTUP
# =========================================================================

def get_mcp_orchestrator():
    """Get the singleton MCP orchestrator instance."""
    if not _initialized:
        initialize_app()
    return _mcp_orchestrator


logging.info("Slack bot Azure Functions module loaded")