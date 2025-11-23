"""
Handler for Slack interactive components (button clicks).
"""
import logging
import json
from typing import Dict, Any

from slack_client import SlackClientWrapper
from auth_manager import AuthorizationManager
from meraki_service import MerakiService
from triage_manager import TriageSessionManager
from exceptions import BotException


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
        self._meraki = None
        self._freshservice = None
    
    @property
    def meraki(self) -> MerakiService:
        if self._meraki is None:
            self._meraki = MerakiService()
        return self._meraki
     
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
            if action_id == "meraki_confirm_update":
                self.handle_meraki_confirm(payload)
            elif action_id == "meraki_cancel_update":
                self.handle_meraki_cancel(payload)
            elif action_id == "fresh_confirm_create":
                self.handle_fresh_confirm(payload)
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
    
    def handle_meraki_confirm(self, payload: Dict[str, Any]) -> None:
        """Handle Meraki password update confirmation."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        user_id = payload['user']['id']
        
        # Parse button value
        button_value = json.loads(payload['actions'][0]['value'])
        ssid_name = button_value['ssid']
        new_password = button_value['password']
        
        # Update message to show progress
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text=f"🚀 Roger that! Updating all SSIDs named *{ssid_name}*. Please wait...",
            blocks=[]
        )
        
        try:
            # Execute the update
            result = self.meraki.update_ssids_by_name(ssid_name, new_password)
            
            if result['total_updated'] == 0:
                response = f"⚠️ Could not find any SSIDs named *{ssid_name}* to update."
            else:
                # Build summary
                summary_lines = [
                    f"✅ **Password Update Complete!**",
                    f"Updated {result['total_updated']} SSID(s) across {result['networks_affected']} network(s):\n"
                ]
                
                for detail in result['details']:
                    summary_lines.append(
                        f"• ✅ {detail['ssids_updated']} SSID(s) on network *{detail['network_name']}*"
                    )
                
                response = "\n".join(summary_lines)
            
            self.slack.post_message(
                channel=channel_id,
                text=response,
                thread_ts=message_ts
            )
            
        except BotException as e:
            logging.error(f"Meraki update failed: {e}")
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ <@{user_id}> {e.user_friendly_message}",
                thread_ts=message_ts
            )
    
    def handle_meraki_cancel(self, payload: Dict[str, Any]) -> None:
        """Handle Meraki password update cancellation."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text="🚫 Operation cancelled by user.",
            blocks=[]
        )
    
    def handle_fresh_confirm(self, payload: Dict[str, Any]) -> None:
        """Handle Freshservice ticket creation confirmation."""
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        
        # Parse button value
        button_value = json.loads(payload['actions'][0]['value'])
        title = button_value['title']
        description = button_value['description']
        original_user_id = button_value['user_id']
        original_ts = button_value['original_ts']
        
        # Update message
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text=f"✅ Got it! Creating a ticket for <@{original_user_id}>...",
            blocks=[]
        )
        
        try:
            # Update reactions on original message
            self.slack.remove_reaction(channel_id, original_ts, "eyes")
            self.slack.add_reaction(channel_id, original_ts, "ticket")
            
            # Get user info
            user_email = self.slack.get_user_email(original_user_id)
            user_name = self.slack.get_user_real_name(original_user_id)
            
            # Create ticket
            ticket_id, ticket_url = self.freshservice.create_ticket(
                title=title,
                description=description,
                requester_email=user_email,
                requester_name=user_name
            )
            
            # Post success message
            self.slack.post_message(
                channel=channel_id,
                text=(
                    f"✅ <@{original_user_id}> Success! "
                    f"New ticket created: <{ticket_url}|Ticket #{ticket_id}>"
                ),
                thread_ts=original_ts
            )
            
            # Clean up the triage session
            self.triage.delete_session(channel_id, original_ts)
            
        except BotException as e:
            logging.error(f"Ticket creation failed: {e}")
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ <@{original_user_id}> {e.user_friendly_message}",
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
