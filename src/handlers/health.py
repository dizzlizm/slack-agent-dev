"""
AWS Lambda handler for health checks.
"""
import json
import os
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for health checks.
    Returns basic health status without requiring full config.
    """
    try:
        environment = os.environ.get("ENVIRONMENT", "unknown")

        health_status = {
            "status": "healthy",
            "environment": environment,
            "version": "2.0.0"
        }

        # Try to load full config for detailed status
        try:
            from src.config import Config
            Config.load()
            health_status["integrations"] = {
                "gemini": Config.is_gemini_enabled(),
                "freshservice": Config.is_freshservice_enabled(),
                "intune": Config.is_intune_enabled()
            }
            health_status["config_loaded"] = True
        except Exception as config_error:
            logger.warning(f"Config not fully loaded: {config_error}")
            health_status["config_loaded"] = False
            health_status["config_error"] = str(config_error)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(health_status, indent=2)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({"status": "unhealthy", "error": str(e)})
        }
