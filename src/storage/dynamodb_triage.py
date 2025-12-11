"""
Triage session management using DynamoDB.
Drop-in replacement for Azure Table Storage version.
"""
import logging
import time
from datetime import datetime
from typing import Optional, List
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.models.models import TriageSession
from src.exceptions import SessionNotFoundError, StorageError
from src.config import Config

logger = logging.getLogger(__name__)


class TriageSessionManager:
    """Manages active troubleshooting triage sessions using DynamoDB."""

    def __init__(self, table_name: Optional[str] = None):
        self.dynamodb = boto3.resource('dynamodb', region_name=Config.AWS_REGION)
        self.table_name = table_name or Config.get_table_name("TriageSessions")
        self.table = self.dynamodb.Table(self.table_name)

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
            response = self.table.get_item(
                Key={
                    'PK': f"CHANNEL#{channel_id}",
                    'SK': f"THREAD#{thread_ts}"
                }
            )

            if 'Item' not in response:
                logger.debug(f"Session not found: {channel_id}-{thread_ts}")
                return None

            session = TriageSession.from_dynamodb_item(response['Item'])

            # Check if session is stale
            if session.is_stale(Config.TRIAGE_SESSION_TIMEOUT_HOURS):
                logger.warning(
                    f"Session {channel_id}-{thread_ts} is stale "
                    f"(last updated: {session.last_updated})"
                )

            logger.debug(f"Retrieved session {channel_id}-{thread_ts}")
            return session

        except ClientError as e:
            logger.error(f"Error retrieving session {channel_id}-{thread_ts}: {e}")
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
        logger.info(f"Created new session {channel_id}-{thread_ts}")
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

            # TTL: 24 hours from now (configurable)
            ttl = int(time.time()) + (Config.TRIAGE_SESSION_TIMEOUT_HOURS * 60 * 60)

            item = session.to_dynamodb_item()
            item['PK'] = f"CHANNEL#{session.channel_id}"
            item['SK'] = f"THREAD#{session.thread_ts}"
            item['TTL'] = ttl
            item['OriginalUserID'] = session.original_user_id  # For GSI

            self.table.put_item(Item=item)
            logger.debug(f"Saved session {session.channel_id}-{session.thread_ts}")

        except ClientError as e:
            logger.error(
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
            self.table.delete_item(
                Key={
                    'PK': f"CHANNEL#{channel_id}",
                    'SK': f"THREAD#{thread_ts}"
                }
            )
            logger.info(f"Deleted session {channel_id}-{thread_ts}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete session {channel_id}-{thread_ts}: {e}")
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

    def get_active_sessions_for_user(self, user_id: str) -> List[TriageSession]:
        """
        Get all active sessions for a specific user using GSI.

        Args:
            user_id: The Slack user ID

        Returns:
            List of active TriageSession objects
        """
        try:
            # Use the UserIndex GSI
            response = self.table.query(
                IndexName='UserIndex',
                KeyConditionExpression=Key('OriginalUserID').eq(user_id),
                FilterExpression=Attr('Status').eq('active')
            )

            sessions = []
            for item in response.get('Items', []):
                session = TriageSession.from_dynamodb_item(item)
                if not session.is_stale(Config.TRIAGE_SESSION_TIMEOUT_HOURS):
                    sessions.append(session)

            return sessions

        except ClientError as e:
            logger.error(f"Failed to get active sessions for {user_id}: {e}")
            return []
