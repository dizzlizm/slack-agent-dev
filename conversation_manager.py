"""
Conversation history management for the 'ask' command.
"""
import logging
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

from models import ConversationHistory
from exceptions import StorageError
from config import Config


class ConversationManager:
    """Manages conversation history using Azure Table Storage."""
    
    def __init__(self, table_client: TableClient):
        self.table_client = table_client
    
    def get_history(self, user_id: str) -> ConversationHistory:
        """
        Fetch conversation history for a user.
        
        Args:
            user_id: The Slack user ID
            
        Returns:
            ConversationHistory object (empty if not found)
        """
        try:
            entity = self.table_client.get_entity(
                partition_key="Conversation",
                row_key=user_id
            )
            history_json = entity.get("History", "[]")
            history = ConversationHistory.from_json(user_id, history_json)
            
            # Prune on retrieval to prevent unbounded growth
            if len(history.messages) > Config.MAX_CONVERSATION_HISTORY:
                history.messages = history.messages[-Config.MAX_CONVERSATION_HISTORY:]
                self.save_history(history)
            
            logging.debug(f"Retrieved {len(history.messages)} messages for user {user_id}")
            return history
            
        except ResourceNotFoundError:
            logging.debug(f"No conversation history found for user {user_id}")
            return ConversationHistory(user_id=user_id)
        except AzureError as e:
            logging.error(f"Error retrieving conversation history for {user_id}: {e}")
            # Return empty history rather than crashing
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
            
            entity = {
                "PartitionKey": "Conversation",
                "RowKey": history.user_id,
                "History": history.to_json()
            }
            self.table_client.upsert_entity(entity)
            logging.debug(f"Saved {len(history.messages)} messages for user {history.user_id}")
        except AzureError as e:
            logging.error(f"Failed to save conversation history for {history.user_id}: {e}")
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
            self.table_client.delete_entity(
                partition_key="Conversation",
                row_key=user_id
            )
            logging.info(f"Deleted conversation history for user {user_id}")
            return True
        except ResourceNotFoundError:
            logging.debug(f"No conversation history to delete for user {user_id}")
            return False
        except AzureError as e:
            logging.error(f"Failed to delete conversation history for {user_id}: {e}")
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
