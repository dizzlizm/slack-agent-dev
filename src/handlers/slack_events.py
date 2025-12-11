"""
AWS Lambda handler for Slack events.
"""
import json
import logging
from typing import Dict, Any

from src.config import Config
from src.security import (
    get_request_verifier,
    get_rate_limiter,
    get_message_deduplicator
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for Slack events.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    # Get raw body and headers
    body = event.get('body', '')
    headers = event.get('headers', {})
    is_base64 = event.get('isBase64Encoded', False)

    # Handle base64 encoding if needed
    if is_base64:
        import base64
        body = base64.b64decode(body).decode('utf-8')

    # Parse body
    try:
        if isinstance(body, str):
            req_body = json.loads(body)
        else:
            req_body = body
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return _response(400, "Invalid JSON")

    # Handle URL verification challenge BEFORE loading config
    # This allows Slack to verify the endpoint before secrets are configured
    if req_body.get('type') == 'url_verification':
        challenge = req_body.get('challenge', '')
        logger.info("Responding to Slack URL verification challenge")
        return _response(200, challenge, content_type='text/plain')

    # Load configuration (only needed for actual event processing)
    Config.load()

    # Verify Slack signature
    timestamp = headers.get('x-slack-request-timestamp') or headers.get('X-Slack-Request-Timestamp', '')
    signature = headers.get('x-slack-signature') or headers.get('X-Slack-Signature', '')

    verifier = get_request_verifier()
    raw_body = body.encode('utf-8') if isinstance(body, str) else body
    is_valid, error_msg = verifier.verify_request(raw_body, timestamp, signature)

    if not is_valid:
        logger.warning(f"Slack signature verification failed: {error_msg}")
        return _response(401, "Unauthorized")

    # Handle event callbacks
    if req_body.get('type') == 'event_callback':
        return _handle_event_callback(req_body)

    return _response(200, "OK")


def _handle_event_callback(req_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Slack event callbacks.

    Args:
        req_body: The parsed request body

    Returns:
        API Gateway response
    """
    event = req_body.get('event', {})

    # Only process message events
    if event.get("type") != "message":
        return _response(200, "OK")

    # Ignore bot messages and edits
    if event.get("bot_id") or event.get("subtype") is not None:
        logger.debug("Ignoring bot message or subtype")
        return _response(200, "OK")

    # Ignore our own messages
    user_id = event.get("user")
    if user_id == Config.SLACK_BOT_USER_ID:
        logger.debug("Ignoring our own bot message")
        return _response(200, "OK")

    text = event.get("text", "").strip()
    channel_id = event.get("channel")
    message_ts = event.get("ts")

    if not text or not user_id:
        return _response(200, "OK")

    # Check rate limit
    rate_limiter = get_rate_limiter()
    is_allowed, retry_after = rate_limiter.is_allowed(user_id)

    if not is_allowed:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return _response(200, "OK")  # Silent rejection

    # Check for duplicates
    deduplicator = get_message_deduplicator()
    if deduplicator.is_duplicate(channel_id, message_ts):
        return _response(200, "OK")

    logger.info(f"[{user_id}] Message in {channel_id}: {text[:50]}...")

    # Process the message
    # Note: In production, you'd want to invoke another Lambda asynchronously
    # or use SQS to avoid Slack's 3-second timeout
    try:
        from src.core.message_router import route_message

        thread_ts = event.get("thread_ts")
        route_message(text, user_id, channel_id, thread_ts, message_ts)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

    return _response(200, "OK")


def _response(
    status_code: int,
    body: str,
    content_type: str = 'application/json'
) -> Dict[str, Any]:
    """
    Build an API Gateway response.

    Args:
        status_code: HTTP status code
        body: Response body
        content_type: Content type header

    Returns:
        API Gateway response dict
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': content_type
        },
        'body': body if content_type == 'text/plain' else json.dumps({'message': body})
    }
