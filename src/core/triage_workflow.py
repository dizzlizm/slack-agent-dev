"""
Triage workflow for automatic troubleshooting.
"""
import logging
import json

from src.integrations.slack_client import SlackClientWrapper
from src.storage import TriageSessionManager
from src.integrations.gemini_service import GeminiService
from src.exceptions import BotException, IntegrationNotConfiguredError
from src.config import Config


class TriageWorkflow:
    """Manages the automatic troubleshooting triage workflow."""
    
    def __init__(
        self,
        slack_client: SlackClientWrapper,
        triage_manager: TriageSessionManager
    ):
        self.slack = slack_client
        self.triage = triage_manager
        self._gemini = None
    
    @property
    def gemini(self) -> GeminiService:
        if self._gemini is None:
            if not Config.is_gemini_enabled():
                raise IntegrationNotConfiguredError("Gemini AI")
            self._gemini = GeminiService()
        return self._gemini
    
    def should_process_message(
        self,
        channel_id: str,
        message_ts: str
    ) -> bool:
        """
        Check if a message should be processed for triage.
        
        Args:
            channel_id: The channel ID
            message_ts: The message timestamp
            
        Returns:
            True if should process, False otherwise
        """
        # Check if already processed (has bot reactions)
        if self.slack.has_bot_reaction(channel_id, message_ts, "ticket"):
            logging.debug(f"Message {message_ts} already has :ticket:, skipping")
            return False
        
        if self.slack.has_bot_reaction(channel_id, message_ts, "eyes"):
            logging.debug(f"Message {message_ts} already has :eyes:, skipping")
            return False
        
        return True
    
    def start_triage(
        self,
        message_text: str,
        user_id: str,
        channel_id: str,
        message_ts: str
    ) -> None:
        """
        Start a new triage session for a support request.
        
        Args:
            message_text: The user's message
            user_id: The user ID
            channel_id: The channel ID
            message_ts: The message timestamp
        """
        logging.info(f"[{user_id}] Starting triage for message {message_ts}")
        
        # Check if should process
        if not self.should_process_message(channel_id, message_ts):
            logging.info(f"Message {message_ts} already processed, skipping triage")
            return
        
        # Add :eyes: reaction to indicate processing
        self.slack.add_reaction(channel_id, message_ts, "eyes")
        
        try:
            # Call Gemini to make triage decision
            decision = self.gemini.make_triage_decision(message_text)
            
            if not decision.requires_ticket:
                # Not a support request, remove reaction
                logging.info(f"Message {message_ts} does not require triage")
                self.slack.remove_reaction(channel_id, message_ts, "eyes")
                return
            
            # Validate we have a first question
            if not decision.first_question:
                logging.error("LLM did not provide a first question for triage")
                self.slack.remove_reaction(channel_id, message_ts, "eyes")
                return
            
            # Post the first troubleshooting question
            confirmation_text = (
                f"Hi <@{user_id}>, I see you're having an issue. "
                "I'd like to ask a few questions to help troubleshoot."
            )
            
            self.slack.post_message(
                channel=channel_id,
                thread_ts=message_ts,
                text=confirmation_text,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": confirmation_text}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"👉 *{decision.first_question}*"}
                    }
                ]
            )
            
            # Create the triage session
            self.triage.create_session(
                channel_id=channel_id,
                thread_ts=message_ts,
                user_id=user_id,
                title=decision.suggested_title or "New Support Request",
                description=decision.initial_description or message_text,
                first_question=decision.first_question
            )
            
            logging.info(f"[{user_id}] Triage session created for {channel_id}-{message_ts}")
            
        except BotException as e:
            logging.error(f"Error starting triage: {e}")
            self.slack.remove_reaction(channel_id, message_ts, "eyes")
        except Exception as e:
            logging.error(f"Unexpected error starting triage: {e}", exc_info=True)
            self.slack.remove_reaction(channel_id, message_ts, "eyes")
    
    def handle_triage_reply(
        self,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        reply_text: str
    ) -> None:
        """
        Handle a user's reply in an active triage session.
        
        Args:
            channel_id: The channel ID
            thread_ts: The thread timestamp
            user_id: The user ID
            reply_text: The user's reply text
        """
        logging.info(f"[{user_id}] Triage reply in {channel_id}-{thread_ts}")
        
        # Get the session
        session = self.triage.get_session(channel_id, thread_ts)
        
        if not session:
            logging.debug(f"No active triage session for {channel_id}-{thread_ts}")
            return
        
        if not session.is_active():
            logging.debug(f"Session {channel_id}-{thread_ts} is not active (status: {session.status})")
            return
        
        # Check if reply is from the original user
        if session.original_user_id != user_id:
            logging.debug(f"Reply from {user_id} doesn't match session user {session.original_user_id}")
            return
        
        try:
            # Add user's reply to session history FIRST (before API call)
            # This prevents infinite loops if the API call fails
            session.add_message("user", reply_text)
            self.triage.save_session(session)
            
            # Get next troubleshooting step from Gemini
            step = self.gemini.get_troubleshoot_step(session, reply_text)
            
            # Update description if needed
            if step.updated_description:
                session.description = step.updated_description
            
            # Post next question if available
            if step.next_question:
                self.slack.post_message(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"👉 {step.next_question}"
                )
                session.add_message("assistant", step.next_question)
            
            # Handle resolution or escalation
            if step.is_resolved:
                logging.info(f"Session {channel_id}-{thread_ts} resolved")
                self.triage.update_status(session, "resolved", save=True)
                self.slack.remove_reaction(channel_id, thread_ts, "eyes")
                self.slack.add_reaction(channel_id, thread_ts, "white_check_mark")
                
            elif step.suggestions_exhausted:
                logging.info(f"Session {channel_id}-{thread_ts} escalated")
                self.triage.update_status(session, "escalated", save=True)
                
                # Offer to create a ticket
                button_payload = {
                    "title": session.suggested_title,
                    "description": session.description,
                    "user_id": session.original_user_id,
                    "original_ts": thread_ts
                }
                
                self.slack.post_message(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=(
                        "I'm out of automated suggestions. "
                        "Would you like me to create a ticket with this information?"
                    ),
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    "I'm out of automated suggestions. "
                                    "Would you like me to create a ticket with this information?\n\n"
                                    f"📝 *Proposed Ticket:*\n"
                                    f"_*Title:* {session.suggested_title}_\n"
                                    f"_*Description:* {session.description}_"
                                )
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "Create Ticket ✅"},
                                    "style": "primary",
                                    "value": json.dumps(button_payload),
                                    "action_id": "fresh_confirm_create"
                                },
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "Cancel ❌"},
                                    "style": "danger",
                                    "value": json.dumps({"original_ts": thread_ts}),
                                    "action_id": "fresh_cancel_create"
                                }
                            ]
                        }
                    ]
                )
            else:
                # Continue troubleshooting
                self.triage.save_session(session)
            
        except BotException as e:
            logging.error(f"Error in triage step: {e}")
            
            # Post error message and save session state
            error_message = (
                "I'm sorry, I had a temporary error. "
                "Could you please rephrase that or try again?"
            )
            self.slack.post_message(
                channel=channel_id,
                thread_ts=thread_ts,
                text=error_message
            )
            
            session.add_message("assistant", error_message)
            self.triage.save_session(session)
            
        except Exception as e:
            logging.error(f"Unexpected error in triage step: {e}", exc_info=True)
            
            # Save session state and notify user
            error_message = "An unexpected error occurred. Please try again."
            self.slack.post_message(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ {error_message}"
            )
            
            session.add_message("assistant", error_message)
            self.triage.save_session(session)
