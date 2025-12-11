"""
Slack client wrapper with enhanced error handling and retry logic.
"""
import logging
import time
from typing import Optional, Dict, Any, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config


class SlackClientWrapper:
    """Wrapper around Slack WebClient with retry logic and error handling."""
    
    def __init__(self):
        self.client = WebClient(token=Config.SLACK_BOT_TOKEN)
        self.bot_user_id = Config.SLACK_BOT_USER_ID
    
    def _retry_on_rate_limit(self, func, *args, max_retries: int = 3, **kwargs):
        """
        Execute a Slack API call with automatic retry on rate limits.
        
        Args:
            func: The Slack API function to call
            max_retries: Maximum number of retry attempts
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the API call
            
        Raises:
            SlackApiError: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except SlackApiError as e:
                if e.response.get("error") == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 1))
                    logging.warning(
                        f"Rate limited by Slack. Retrying after {retry_after}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                raise
    
    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Post a message to a Slack channel.
        
        Args:
            channel: Channel ID
            text: Message text
            thread_ts: Optional thread timestamp to reply in thread
            blocks: Optional blocks for rich formatting
            
        Returns:
            Response from Slack API
        """
        try:
            kwargs = {
                "channel": channel,
                "text": text
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            if blocks:
                kwargs["blocks"] = blocks
            
            response = self._retry_on_rate_limit(
                self.client.chat_postMessage,
                **kwargs
            )
            logging.debug(f"Posted message to {channel}")
            return response
            
        except SlackApiError as e:
            logging.error(f"Failed to post message to {channel}: {e}")
            raise
    
    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing Slack message.
        
        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
            blocks: Optional new blocks
            
        Returns:
            Response from Slack API
        """
        try:
            kwargs = {
                "channel": channel,
                "ts": ts,
                "text": text
            }
            if blocks is not None:  # Allow empty list to clear blocks
                kwargs["blocks"] = blocks
            
            response = self._retry_on_rate_limit(
                self.client.chat_update,
                **kwargs
            )
            logging.debug(f"Updated message {ts} in {channel}")
            return response
            
        except SlackApiError as e:
            logging.error(f"Failed to update message {ts} in {channel}: {e}")
            raise
    
    def add_reaction(
        self,
        channel: str,
        timestamp: str,
        reaction: str
    ) -> None:
        """
        Add a reaction emoji to a message.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            reaction: Emoji name (without colons)
        """
        try:
            self._retry_on_rate_limit(
                self.client.reactions_add,
                channel=channel,
                timestamp=timestamp,
                name=reaction
            )
            logging.debug(f"Added :{reaction}: to {timestamp} in {channel}")
        except SlackApiError as e:
            # Don't fail on reaction errors - they're not critical
            logging.warning(f"Failed to add reaction :{reaction}:: {e}")
    
    def remove_reaction(
        self,
        channel: str,
        timestamp: str,
        reaction: str
    ) -> None:
        """
        Remove a reaction emoji from a message.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            reaction: Emoji name (without colons)
        """
        try:
            self._retry_on_rate_limit(
                self.client.reactions_remove,
                channel=channel,
                timestamp=timestamp,
                name=reaction
            )
            logging.debug(f"Removed :{reaction}: from {timestamp} in {channel}")
        except SlackApiError as e:
            logging.warning(f"Failed to remove reaction :{reaction}:: {e}")
    
    def get_reactions(
        self,
        channel: str,
        timestamp: str
    ) -> List[Dict[str, Any]]:
        """
        Get reactions on a message.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            
        Returns:
            List of reaction objects
        """
        try:
            response = self._retry_on_rate_limit(
                self.client.reactions_get,
                channel=channel,
                timestamp=timestamp
            )
            return response.get("message", {}).get("reactions", [])
        except SlackApiError as e:
            logging.warning(f"Failed to get reactions: {e}")
            return []
    
    def has_bot_reaction(
        self,
        channel: str,
        timestamp: str,
        reaction: str
    ) -> bool:
        """
        Check if the bot has already reacted with a specific emoji.
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            reaction: Emoji name to check for
            
        Returns:
            True if bot has reacted, False otherwise
        """
        reactions = self.get_reactions(channel, timestamp)
        for r in reactions:
            if r.get("name") == reaction and self.bot_user_id in r.get("users", []):
                return True
        return False
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get information about a Slack user.
        
        Args:
            user_id: The user ID
            
        Returns:
            User info dict
        """
        try:
            response = self._retry_on_rate_limit(
                self.client.users_info,
                user=user_id
            )
            return response.get("user", {})
        except SlackApiError as e:
            logging.error(f"Failed to get user info for {user_id}: {e}")
            return {}
    
    def get_user_email(self, user_id: str) -> str:
        """
        Get a user's email address.
        
        Args:
            user_id: The user ID
            
        Returns:
            Email address, or a fallback if not available
        """
        user_info = self.get_user_info(user_id)
        return user_info.get("profile", {}).get("email", f"{user_id}@slack.com")
    
    def get_user_real_name(self, user_id: str) -> str:
        """
        Get a user's real name.
        
        Args:
            user_id: The user ID
            
        Returns:
            Real name, or a fallback if not available
        """
        user_info = self.get_user_info(user_id)
        return user_info.get("real_name", f"Slack User {user_id}")
