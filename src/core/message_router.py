"""
Message routing for Slack messages.
Routes incoming messages to appropriate handlers.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def route_message(
    text: str,
    user_id: str,
    channel_id: str,
    thread_ts: Optional[str] = None,
    message_ts: Optional[str] = None
) -> None:
    """
    Route an incoming message to the appropriate handler.

    Args:
        text: The message text
        user_id: Slack user ID who sent the message
        channel_id: Slack channel ID where message was sent
        thread_ts: Thread timestamp if in a thread
        message_ts: Message timestamp
    """
    logger.info(f"Routing message from {user_id} in {channel_id}: {text[:100]}")

    # TODO: Implement message routing logic
    # - Check if user is authorized
    # - Determine message intent (triage, ask, ticket, etc.)
    # - Route to appropriate handler

    # For now, just log that we received the message
    logger.info("Message router stub - no action taken")
