"""
AWS Lambda handler for health checks.
"""
import json
import logging
from typing import Dict, Any

from src.config import Config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for health checks.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response with health status
    """
    try:
        # Load configuration
        Config.load()

        health_status = {
            "status": "healthy",
            "environment": Config.ENVIRONMENT,
            "integrations": {
                "gemini": Config.is_gemini_enabled(),
                "freshservice": Config.is_freshservice_enabled(),
                "intune": Config.is_intune_enabled()
            },
            "monitored_channels": len(Config.MONITORED_SLACK_CHANNEL_IDS),
            "version": "2.0.0"  # AWS Lambda version
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(health_status, indent=2)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)

        return {
            'statusCode': 503,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                "status": "unhealthy",
                "error": "Configuration or service error"
            })
        }
