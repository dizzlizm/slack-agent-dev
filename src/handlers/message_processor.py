"""
Async message processor Lambda handler.
Handles actual message processing after Slack events handler returns.
"""
import json
import logging
from typing import Dict, Any

from src.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for async message processing.

    This function is invoked asynchronously by the Slack events handler
    to process messages without blocking the Slack response.

    Args:
        event: Contains message data (text, user_id, channel_id, thread_ts, message_ts)
        context: Lambda context

    Returns:
        Processing result
    """
    logger.info(f"=== MESSAGE PROCESSOR START ===")
    logger.info(f"Event received: {json.dumps(event)}")

    try:
        # Load configuration
        logger.info("Loading configuration...")
        Config.load()
        logger.info("Configuration loaded successfully")

        # Extract message data
        text = event.get('text', '')
        user_id = event.get('user_id', '')
        channel_id = event.get('channel_id', '')
        thread_ts = event.get('thread_ts')
        message_ts = event.get('message_ts')

        logger.info(f"Extracted: text='{text[:50]}...', user={user_id}, channel={channel_id}")

        if not text or not user_id or not channel_id:
            logger.error(f"Missing required fields - text: {bool(text)}, user_id: {bool(user_id)}, channel_id: {bool(channel_id)}")
            return {'statusCode': 400, 'body': 'Missing required fields'}

        # Route the message
        logger.info("Calling route_message...")
        from src.core.message_router import route_message
        route_message(text, user_id, channel_id, thread_ts, message_ts)

        logger.info(f"=== MESSAGE PROCESSOR SUCCESS ===")
        return {'statusCode': 200, 'body': 'Message processed'}

    except Exception as e:
        logger.error(f"=== MESSAGE PROCESSOR FAILED ===")
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {'statusCode': 500, 'body': str(e)}
