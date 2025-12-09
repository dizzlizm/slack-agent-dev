"""
AWS Lambda handler for Slack interactive components.
"""
import json
import logging
import urllib.parse
from typing import Dict, Any

from src.config import Config
from src.security import get_request_verifier

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for Slack interactive callbacks.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    # Load configuration
    Config.load()

    # Get raw body and headers
    body = event.get('body', '')
    headers = event.get('headers', {})
    is_base64 = event.get('isBase64Encoded', False)

    # Handle base64 encoding if needed
    if is_base64:
        import base64
        body = base64.b64decode(body).decode('utf-8')

    # Parse form data to get payload
    try:
        if body.startswith('payload='):
            payload_str = urllib.parse.unquote(body.replace('payload=', ''))
        else:
            # Try to find payload in form data
            parsed = urllib.parse.parse_qs(body)
            payload_str = parsed.get('payload', [''])[0]

        if not payload_str:
            logger.error("No payload in interactive request")
            return _response(400, "Missing payload")

        payload = json.loads(payload_str)

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse payload: {e}")
        return _response(400, "Invalid payload")

    # Verify Slack signature
    timestamp = headers.get('x-slack-request-timestamp') or headers.get('X-Slack-Request-Timestamp', '')
    signature = headers.get('x-slack-signature') or headers.get('X-Slack-Signature', '')

    verifier = get_request_verifier()
    raw_body = body.encode('utf-8') if isinstance(body, str) else body
    is_valid, error_msg = verifier.verify_request(raw_body, timestamp, signature)

    if not is_valid:
        logger.warning(f"Interactive signature verification failed: {error_msg}")
        return _response(401, "Unauthorized")

    # Process the interactive payload
    try:
        from src.core.interactive_handler import handle_interactive_payload
        handle_interactive_payload(payload)

    except Exception as e:
        logger.error(f"Error processing interactive payload: {e}", exc_info=True)

    return _response(200, "OK")


def _response(status_code: int, body: str) -> Dict[str, Any]:
    """Build an API Gateway response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'message': body})
    }
