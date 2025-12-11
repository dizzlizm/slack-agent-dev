"""
Triage session management for troubleshooting workflows.
"""
import logging
from datetime import datetime
from typing import Optional, List
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

from src.models.models import TriageSession
from src.exceptions import SessionNotFoundError, StorageError
from src.config import Config


class TriageSessionManager:
    """Manages active troubleshooting triage sessions."""
    
    def __init__(self, table_client: TableClient):
        self.table_client = table_client
    
    def get_session(self, channel_id: str, thread_ts: str) -> Optional[TriageSession]:
        """
        Fetch an active triage session.
        
        Args:
            channel_id: The Slack channel ID
            thread_ts: The thread timestamp
            
        Returns:
            TriageSession object if found, None otherwise
        """
        try:
            entity = self.table_client.get_entity(
                partition_key=channel_id,
                row_key=thread_ts
            )
            session = TriageSession.from_storage_entity(entity)
            
            # Check if session is stale
            if session.is_stale(Config.TRIAGE_SESSION_TIMEOUT_HOURS):
                logging.warning(
                    f"Session {channel_id}-{thread_ts} is stale "
                    f"(last updated: {session.last_updated})"
                )
                # Could auto-cleanup here, but let's just log for now
            
            logging.debug(f"Retrieved session {channel_id}-{thread_ts}")
            return session
            
        except ResourceNotFoundError:
            logging.debug(f"Session not found: {channel_id}-{thread_ts}")
            return None
        except AzureError as e:
            logging.error(f"Error retrieving session {channel_id}-{thread_ts}: {e}")
            return None
    
    def require_session(self, channel_id: str, thread_ts: str) -> TriageSession:
        """
        Get a session, raising an exception if not found.
        
        Args:
            channel_id: The Slack channel ID
            thread_ts: The thread timestamp
            
        Returns:
            TriageSession object
            
        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = self.get_session(channel_id, thread_ts)
        if not session:
            raise SessionNotFoundError(channel_id, thread_ts)
        return session
    
    def create_session(
        self,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        title: str,
        description: str,
        first_question: str
    ) -> TriageSession:
        """
        Create a new triage session.
        
        Args:
            channel_id: The Slack channel ID
            thread_ts: The thread timestamp
            user_id: The user who initiated the session
            title: Suggested ticket title
            description: Initial problem description
            first_question: First troubleshooting question
            
        Returns:
            The created TriageSession object
        """
        now = datetime.utcnow()
        session = TriageSession(
            channel_id=channel_id,
            thread_ts=thread_ts,
            original_user_id=user_id,
            status="active",
            suggested_title=title,
            description=description,
            created_at=now,
            last_updated=now
        )
        
        # Add the initial exchange to history
        session.add_message("user", f"Original issue: {description}")
        session.add_message("assistant", first_question)
        
        self.save_session(session)
        logging.info(f"Created new session {channel_id}-{thread_ts}")
        return session
    
    def save_session(self, session: TriageSession) -> None:
        """
        Save or update a triage session.
        
        Args:
            session: The TriageSession to save
            
        Raises:
            StorageError: If the operation fails
        """
        try:
            session.last_updated = datetime.utcnow()
            entity = session.to_storage_entity()
            self.table_client.upsert_entity(entity)
            logging.debug(f"Saved session {session.channel_id}-{session.thread_ts}")
        except AzureError as e:
            logging.error(
                f"Failed to save session {session.channel_id}-{session.thread_ts}: {e}"
            )
            raise StorageError("save_triage_session", str(e))
    
    def delete_session(self, channel_id: str, thread_ts: str) -> bool:
        """
        Delete a triage session.
        
        Args:
            channel_id: The Slack channel ID
            thread_ts: The thread timestamp
            
        Returns:
            True if deleted, False if didn't exist
        """
        try:
            self.table_client.delete_entity(
                partition_key=channel_id,
                row_key=thread_ts
            )
            logging.info(f"Deleted session {channel_id}-{thread_ts}")
            return True
        except ResourceNotFoundError:
            logging.debug(f"Session already deleted: {channel_id}-{thread_ts}")
            return False
        except AzureError as e:
            logging.error(f"Failed to delete session {channel_id}-{thread_ts}: {e}")
            raise StorageError("delete_triage_session", str(e))
    
    def update_status(
        self,
        session: TriageSession,
        status: str,
        save: bool = True
    ) -> None:
        """
        Update the status of a session.
        
        Args:
            session: The session to update
            status: New status ("active", "resolved", "escalated")
            save: Whether to immediately save to storage
        """
        session.status = status
        session.last_updated = datetime.utcnow()
        if save:
            self.save_session(session)
    
    def cleanup_stale_sessions(self) -> int:
        """
        Clean up sessions that have timed out.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            entities = self.table_client.list_entities()
            cleaned = 0
            
            for entity in entities:
                session = TriageSession.from_storage_entity(entity)
                if session.is_stale(Config.TRIAGE_SESSION_TIMEOUT_HOURS):
                    self.delete_session(session.channel_id, session.thread_ts)
                    cleaned += 1
            
            if cleaned > 0:
                logging.info(f"Cleaned up {cleaned} stale triage sessions")
            
            return cleaned
            
        except AzureError as e:
            logging.error(f"Failed to cleanup stale sessions: {e}")
            return 0
    
    def get_active_sessions_for_user(self, user_id: str) -> List[TriageSession]:
        """
        Get all active sessions for a specific user.
        
        Args:
            user_id: The Slack user ID
            
        Returns:
            List of active TriageSession objects
        """
        try:
            entities = self.table_client.list_entities()
            sessions = []
            
            for entity in entities:
                session = TriageSession.from_storage_entity(entity)
                if (session.original_user_id == user_id and 
                    session.status == "active" and
                    not session.is_stale(Config.TRIAGE_SESSION_TIMEOUT_HOURS)):
                    sessions.append(session)
            
            return sessions
            
        except AzureError as e:
            logging.error(f"Failed to get active sessions for {user_id}: {e}")
            return []
