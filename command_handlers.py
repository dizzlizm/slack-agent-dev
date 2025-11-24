"""
Command handlers for bot commands.
"""
import logging
import json
from typing import Optional

from command_parser import (
    ParsedCommand,
    parse_admin_command,
    require_args
)
from slack_client import SlackClientWrapper
from auth_manager import AuthorizationManager
from conversation_manager import ConversationManager
from gemini_service import GeminiService
from exceptions import (
    BotException,
    IntegrationNotConfiguredError,
    InvalidCommandError
)
from config import Config
from mcp_integration import GeminiMCPOrchestrator

class CommandHandlers:
    """Collection of command handler methods."""
    
    def __init__(
        self,
        slack_client: SlackClientWrapper,
        auth_manager: AuthorizationManager,
        conversation_manager: ConversationManager,
        mcp_orchestrator: Optional[any] = None
    ):
        self.slack = slack_client
        self.auth = auth_manager
        self.conversation = conversation_manager
        self.mcp_orchestrator = mcp_orchestrator  # Singleton MCP orchestrator

        # Initialize services lazily
        self._gemini: Optional[GeminiService] = None

    @property
    def gemini(self) -> GeminiService:
        """Get Gemini service (lazy init)."""
        if self._gemini is None:
            self._gemini = GeminiService()
        return self._gemini
    
    def handle_help(self, cmd: ParsedCommand) -> None:
        """Show help message with available commands."""
        help_text = """
👋 Hello! I'm your intelligent IT assistant powered by AI.

*🎯 Just Ask Me Naturally:*
• `@Systems help me with user john.smith@company.com`
• `@Systems what tickets does jane.doe@company.com have?`
• `@Systems update guest WiFi password to NewSecure2024`
• `@Systems reboot device ABC123`
• `@Systems are there any planned outages?`
• `@Systems show assets for john smith`

I understand natural language - **no special syntax needed!** 🚀

*📋 Available Services:*
• IT Tickets (Freshservice)
• User Management
• WiFi/Network (Meraki)
• Device Management (Intune)
• Asset Tracking
• Change Management

*🔒 Admin Commands:*
• `@Systems admin add @user` - Grant admin access
• `@Systems admin remove @user` - Revoke admin access

*💬 Q&A Commands:*
• `@Systems ask <question>` - Ask any tech question
• `@Systems reset` - Clear conversation history
"""

        # Add triage info if Gemini is enabled
        if Config.is_gemini_enabled() and Config.MONITORED_SLACK_CHANNEL_IDS:
            help_text += """
*🤖 Automatic Triage:*
In monitored channels, I automatically start troubleshooting new support requests without needing to @mention me.
"""
        
        self.slack.post_message(
            channel=cmd.channel_id,
            text=help_text
        )
    
    def handle_admin(self, cmd: ParsedCommand) -> None:
        """Handle admin add/remove commands."""
        # Require authorization to use admin commands
        self.auth.require_authorization(cmd.user_id)
        
        subcommand, target_user_id = parse_admin_command(cmd)
        
        if subcommand == "add":
            self.auth.add_user(target_user_id)
            self.slack.post_message(
                channel=cmd.channel_id,
                text=f"✅ User <@{target_user_id}> has been added to the authorized list."
            )
        elif subcommand == "remove":
            self.auth.remove_user(target_user_id)
            self.slack.post_message(
                channel=cmd.channel_id,
                text=f"🗑️ User <@{target_user_id}> has been removed from the authorized list."
            )
    
    def handle_ask(self, cmd: ParsedCommand) -> None:
        """Handle AI assistant questions."""
        self.auth.require_authorization(cmd.user_id)
        
        # Extra safety: Don't process if somehow we're being called for our own messages
        if cmd.user_id == Config.SLACK_BOT_USER_ID:
            logging.warning("Attempted to process 'ask' command from bot itself, ignoring")
            return
        
        # Get the question (everything after "ask")
        question_parts = cmd.raw_text.split(maxsplit=2)
        if len(question_parts) < 3:
            raise InvalidCommandError(
                "Please provide a question",
                "ask <your question>"
            )
        
        question = question_parts[2]
        
        # Check if this looks like it might be a repeated question (simple dedup)
        history = self.conversation.get_history(cmd.user_id)
        if history.messages and len(history.messages) > 0:
            last_user_message = next((msg for msg in reversed(history.messages) if msg.role == "user"), None)
            if last_user_message and last_user_message.content == question:
                logging.warning(f"Duplicate question detected for user {cmd.user_id}, skipping")
                return
        
        # Post "thinking" message
        thinking_response = self.slack.post_message(
            channel=cmd.channel_id,
            text="🤔 Thinking...",
            thread_ts=cmd.thread_ts
        )
        update_ts = thinking_response.get("ts")
        try:
            # Get conversation history
            history = self.conversation.get_history(cmd.user_id)
            
            # Call Gemini
            answer, response_time_ms = self.gemini.ask_question(question, history)
            
            # Format response with timing
            response_text = f"💬 {answer}\n\n_(⚡ {response_time_ms}ms)_"
            
            # Post response
            self.slack.update_message(
                channel=cmd.channel_id,
                text=response_text,
                ts=update_ts
            )
            
            # Save to history
            self.conversation.add_exchange(cmd.user_id, question, answer)
            
        except IntegrationNotConfiguredError as e:
            self.slack.update_message(
                channel=cmd.channel_id,
                text=e.user_friendly_message,
                ts=update_ts
            )
    
    def handle_reset(self, cmd: ParsedCommand) -> None:
        """Reset conversation history for the user."""
        deleted = self.conversation.delete_history(cmd.user_id)
        
        if deleted:
            message = "🔄 Your conversation history has been cleared."
        else:
            message = "You don't have any conversation history to clear."
        
        self.slack.post_message(
            channel=cmd.channel_id,
            text=message
        )
    
    def handle_smart(self, cmd) -> None:
        """
        Intelligent IT support handler - routes to ANY service automatically.

        Gemini AI automatically determines which backend service to use:
        - Freshservice (tickets, users, assets, changes)
        - Meraki (WiFi management)
        - Intune (device management)

        Usage Examples:
        - @systems help me with user john.smith@company.com
        - @systems update guest WiFi password to NewPass123
        - @systems reboot device ABC123
        - @systems what tickets does jane.doe@company.com have?
        - @systems are there any planned maintenance windows?
        """
        # SECURITY: Require admin authorization for MCP tools
        self.auth.require_authorization(cmd.user_id)

        # 1. Extract query - use raw text for full context
        query_text = cmd.raw_text
        if not query_text:
            self.slack.post_message(
                channel=cmd.channel_id,
                text="ℹ️ Please describe what you need help with. Example: `@systems help me with user john@company.com`",
                thread_ts=cmd.thread_ts
            )
            return

        # 1.5. Extract @user mentions and enrich query with emails
        # If user says "@systems help @john", we'll look up john's email and add it to context
        import re
        user_mentions = re.findall(r'<@([A-Z0-9]+)>', query_text)
        mentioned_user_info = []

        for mentioned_user_id in user_mentions:
            try:
                user_info = self.slack.get_user_info(mentioned_user_id)
                if user_info:
                    user_email = user_info.get("profile", {}).get("email")
                    user_name = user_info.get("real_name", "Unknown")
                    if user_email:
                        mentioned_user_info.append(f"{user_name} ({user_email})")
                        logging.info(f"Resolved @mention {mentioned_user_id} to {user_email}")
            except Exception as e:
                logging.warning(f"Could not resolve @mention {mentioned_user_id}: {e}")

        # Append mentioned users to the query for MCP context
        if mentioned_user_info:
            query_text += f"\n\n[Mentioned users: {', '.join(mentioned_user_info)}]"

        # 2. Acknowledge (Latency hiding)
        slack_post = self.slack.post_message(
            channel=cmd.channel_id,
            text="🤖 *Working on it...*",
            thread_ts=cmd.thread_ts
        )
        update_ts = slack_post.get("ts")
        try:
            # 3. Get Context (User Email)
            # The Orchestrator uses this to look up the requester ID automatically
            user_email = None
            try:
                # Assuming your slack_client has a method to get user info
                user_info = self.slack.get_user_info(cmd.user_id)
                if user_info:
                    user_email = user_info.get("profile", {}).get("email")
            except Exception as e:
                logging.warning(f"Could not fetch user context: {e}")

            # 4. Run the MCP Orchestrator (use singleton for performance)
            # This handles the Loop: Gemini -> Direct Tool Calls -> Gemini -> Final Answer
            if not self.mcp_orchestrator:
                # Fallback: create instance if not provided (shouldn't happen in normal flow)
                logging.warning("MCP Orchestrator not initialized, creating new instance")
                orchestrator = GeminiMCPOrchestrator()
            else:
                orchestrator = self.mcp_orchestrator

            response_text = orchestrator.process_query(user_query=query_text, user_email=user_email)

            # 5. Reply with the Final Answer
            self.slack.update_message(
                channel=cmd.channel_id,
                text=response_text,
                ts=update_ts
            )

        except Exception as e:
            logging.error(f"Error in handle_fresh: {e}", exc_info=True)
            self.slack.post_message(
                channel=cmd.channel_id,
                text=f"❌ Error interacting with IT Services: {str(e)}",
                thread_ts=cmd.thread_ts
            )