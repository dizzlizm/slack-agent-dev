"""
Conversation history management using DynamoDB.
Drop-in replacement for Azure Table Storage version.
"""
import logging
import time
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from src.models.models import ConversationHistory
from src.exceptions import StorageError
from src.config import Config

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history using DynamoDB."""

    def __init__(self, table_name: Optional[str] = None):
        self.dynamodb = boto3.resource('dynamodb', region_name=Config.AWS_REGION)
        self.table_name = table_name or Config.get_table_name("ConversationHistory")
        self.table = self.dynamodb.Table(self.table_name)

    def get_history(self, user_id: str) -> ConversationHistory:
        """
        Fetch conversation history for a user.

        Args:
            user_id: The Slack user ID

        Returns:
            ConversationHistory object (empty if not found)
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f"USER#{user_id}",
                    'SK': "HISTORY"
                }
            )

            if 'Item' not in response:
                logger.debug(f"No conversation history found for user {user_id}")
                return ConversationHistory(user_id=user_id)

            item = response['Item']
            history_json = item.get("History", "[]")
            history = ConversationHistory.from_json(user_id, history_json)

            # Prune on retrieval to prevent unbounded growth
            if len(history.messages) > Config.MAX_CONVERSATION_HISTORY:
                history.messages = history.messages[-Config.MAX_CONVERSATION_HISTORY:]
                self.save_history(history)

            logger.debug(f"Retrieved {len(history.messages)} messages for user {user_id}")
            return history

        except ClientError as e:
            logger.error(f"Error retrieving conversation history for {user_id}: {e}")
            return ConversationHistory(user_id=user_id)

    def save_history(self, history: ConversationHistory) -> None:
        """
        Save conversation history for a user.

        Args:
            history: The ConversationHistory object to save

        Raises:
            StorageError: If the operation fails
        """
        try:
            # Enforce message limit before saving
            if len(history.messages) > Config.MAX_CONVERSATION_HISTORY:
                history.messages = history.messages[-Config.MAX_CONVERSATION_HISTORY:]

            # TTL: 30 days from now
            ttl = int(time.time()) + (30 * 24 * 60 * 60)

            self.table.put_item(
                Item={
                    'PK': f"USER#{history.user_id}",
                    'SK': "HISTORY",
                    'History': history.to_json(),
                    'TTL': ttl
                }
            )
            logger.debug(f"Saved {len(history.messages)} messages for user {history.user_id}")

        except ClientError as e:
            logger.error(f"Failed to save conversation history for {history.user_id}: {e}")
            raise StorageError("save_conversation_history", str(e))

    def delete_history(self, user_id: str) -> bool:
        """
        Delete conversation history for a user.

        Args:
            user_id: The Slack user ID

        Returns:
            True if history was deleted, False if no history existed
        """
        try:
            self.table.delete_item(
                Key={
                    'PK': f"USER#{user_id}",
                    'SK': "HISTORY"
                }
            )
            logger.info(f"Deleted conversation history for user {user_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete conversation history for {user_id}: {e}")
            raise StorageError("delete_conversation_history", str(e))

    def add_exchange(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str
    ) -> ConversationHistory:
        """
        Add a user-assistant exchange to the conversation history.

        Args:
            user_id: The Slack user ID
            user_message: The user's message
            assistant_message: The assistant's response

        Returns:
            Updated ConversationHistory object
        """
        history = self.get_history(user_id)
        history.add_message("user", user_message)
        history.add_message("assistant", assistant_message)
        self.save_history(history)
        return history
