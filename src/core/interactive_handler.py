"""
Handler for Slack interactive components (button clicks).
"""
import logging
import json
from typing import Dict, Any

from src.integrations.slack_client import SlackClientWrapper
from src.storage.auth_manager import AuthorizationManager
from src.storage import TriageSessionManager
# from triage_manager import TriageSessionManager
from src.exceptions import BotException


class InteractiveHandler:
    """Handles Slack interactive component callbacks."""
    
    def __init__(
        self,
        slack_client: SlackClientWrapper,
        auth_manager: AuthorizationManager,
        triage_manager: TriageSessionManager
    ):
        self.slack = slack_client
        self.auth = auth_manager
        self.triage = triage_manager

        # Lazy-loaded services
        self._freshservice_tools = None

    @property
    def freshservice_tools(self):
        """Get Freshservice MCP tools instance."""
        if self._freshservice_tools is None:
            from src.integrations.mcp_tools import FreshserviceTools
            self._freshservice_tools = FreshserviceTools()
        return self._freshservice_tools
     
    def handle_payload(self, payload: Dict[str, Any]) -> None:
        """
        Route interactive payload to appropriate handler.
        
        Args:
            payload: The Slack interactive payload
        """
        if payload.get('type') != 'block_actions':
            logging.debug(f"Ignoring non-block_actions payload type: {payload.get('type')}")
            return
        
        action_id = payload['actions'][0]['action_id']
        user_id = payload['user']['id']
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        
        logging.info(f"[{user_id}] Interactive action: {action_id}")
        
        # Check authorization
        if not self.auth.is_authorized(user_id):
            logging.warning(f"Unauthorized user {user_id} attempted button click: {action_id}")
            self.slack.post_message(
                channel=channel_id,
                text="⛔️ Your click was ignored because you are not an authorized user.",
                thread_ts=message_ts
            )
            return
        
        # Route to appropriate handler
        try:
            if action_id == "fresh_confirm_create":
                self.handle_fresh_confirm(payload)
            elif action_id.startswith("fresh_priority_"):
                self.handle_fresh_priority_selection(payload)
            elif action_id == "fresh_cancel_create":
                self.handle_fresh_cancel(payload)
            else:
                logging.warning(f"Unknown action_id: {action_id}")
        
        except BotException as e:
            logging.error(f"Error handling {action_id}: {e}")
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ {e.user_friendly_message}",
                thread_ts=message_ts
            )
        except Exception as e:
            logging.error(f"Unexpected error handling {action_id}: {e}", exc_info=True)
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ An unexpected error occurred: {e}",
                thread_ts=message_ts
            )

    def handle_fresh_confirm(self, payload: Dict[str, Any]) -> None:
        """Handle initial ticket creation request - ask for priority first."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']

        # Parse button value
        button_value = json.loads(payload['actions'][0]['value'])
        title = button_value['title']
        description = button_value['description']
        original_user_id = button_value['user_id']
        original_ts = button_value['original_ts']

        # Update message to ask for priority
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Please select a priority level for this ticket:",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "📋 *Ready to create ticket!*\n\n"
                            f"*Title:* {title}\n"
                            f"*User:* <@{original_user_id}>\n\n"
                            "Please select a priority level:"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🟢 Low"},
                            "style": "primary",
                            "value": json.dumps({
                                "title": title,
                                "description": description,
                                "user_id": original_user_id,
                                "original_ts": original_ts,
                                "priority": 1
                            }),
                            "action_id": "fresh_priority_low"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🟡 Medium"},
                            "value": json.dumps({
                                "title": title,
                                "description": description,
                                "user_id": original_user_id,
                                "original_ts": original_ts,
                                "priority": 2
                            }),
                            "action_id": "fresh_priority_medium"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🟠 High"},
                            "value": json.dumps({
                                "title": title,
                                "description": description,
                                "user_id": original_user_id,
                                "original_ts": original_ts,
                                "priority": 3
                            }),
                            "action_id": "fresh_priority_high"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔴 Urgent"},
                            "style": "danger",
                            "value": json.dumps({
                                "title": title,
                                "description": description,
                                "user_id": original_user_id,
                                "original_ts": original_ts,
                                "priority": 4
                            }),
                            "action_id": "fresh_priority_urgent"
                        }
                    ]
                }
            ]
        )

    def handle_fresh_priority_selection(self, payload: Dict[str, Any]) -> None:
        """Handle priority selection and create the ticket."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']

        # Parse button value
        button_value = json.loads(payload['actions'][0]['value'])
        title = button_value['title']
        description = button_value['description']
        original_user_id = button_value['user_id']
        original_ts = button_value['original_ts']
        priority = button_value['priority']

        priority_names = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}

        # Update message
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text=f"✅ Creating {priority_names[priority]} priority ticket for <@{original_user_id}>...",
            blocks=[]
        )

        try:
            # Update reactions on original message
            self.slack.remove_reaction(channel_id, original_ts, "eyes")
            self.slack.add_reaction(channel_id, original_ts, "ticket")

            # Get user email
            user_email = self.slack.get_user_email(original_user_id)

            # Create ticket using MCP tools
            result = self.freshservice_tools.create_ticket(
                subject=title,
                description=description,
                requester_email=user_email,
                priority=priority,
                status=2  # Open
            )

            # Post success message
            self.slack.post_message(
                channel=channel_id,
                text=(
                    f"✅ <@{original_user_id}> Success! "
                    f"New {priority_names[priority]} priority ticket created: "
                    f"<{result['ticket_url']}|Ticket #{result['ticket_id']}>"
                ),
                thread_ts=original_ts
            )

            # Clean up the triage session
            self.triage.delete_session(channel_id, original_ts)

        except Exception as e:
            logging.error(f"Ticket creation failed: {e}")
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ <@{original_user_id}> Failed to create ticket: {str(e)}",
                thread_ts=original_ts
            )
    
    def handle_fresh_cancel(self, payload: Dict[str, Any]) -> None:
        """Handle Freshservice ticket creation cancellation."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        
        # Parse button value to get original thread
        try:
            button_value = json.loads(payload['actions'][0].get('value', '{}'))
            original_ts = button_value.get('original_ts')
        except (json.JSONDecodeError, KeyError):
            original_ts = None
        
        # Update message
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text="Ok, I won't create a ticket. This session is now closed.",
            blocks=[]
        )
        
        # Clean up reactions and session
        if original_ts:
            self.slack.remove_reaction(channel_id, original_ts, "eyes")
            self.triage.delete_session(channel_id, original_ts)


# Module-level function for Lambda handler
_handler_instance = None


def handle_interactive_payload(payload: Dict[str, Any]) -> None:
    """
    Module-level function to handle interactive payloads.
    Called by the Lambda handler.

    Args:
        payload: The Slack interactive payload
    """
    global _handler_instance

    try:
        if _handler_instance is None:
            logging.info("Initializing interactive handler services...")
            # Initialize handler with required dependencies
            slack_client = SlackClientWrapper()
            logging.debug("SlackClientWrapper initialized")

            auth_manager = AuthorizationManager()
            logging.debug("AuthorizationManager initialized")

            triage_manager = TriageSessionManager()
            logging.debug("TriageSessionManager initialized")

            _handler_instance = InteractiveHandler(
                slack_client=slack_client,
                auth_manager=auth_manager,
                triage_manager=triage_manager
            )
            logging.info("Interactive handler services initialized")

        _handler_instance.handle_payload(payload)

    except Exception as e:
        logging.error(f"Error in interactive handler: {e}", exc_info=True)
        raise
