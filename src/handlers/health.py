"""
AWS Lambda handler for enhanced health checks with dependency monitoring.
"""
import json
import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

import boto3
from botocore.exceptions import ClientError

from src.observability.metrics import get_metrics_collector

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class HealthChecker:
    """Enhanced health check with dependency monitoring.
    
    COST NOTE: External API calls (FreshService) only performed when detailed=true
    to avoid unnecessary API usage and rate limiting.
    """

    def __init__(self, enable_external_checks: bool = True):
        """
        Initialize health checker.
        
        Args:
            enable_external_checks: Whether to check external APIs (costs API calls)
        """
        self.metrics = get_metrics_collector()
        self.enable_external_checks = enable_external_checks

    def check_dynamodb(self, table_name: str) -> Tuple[bool, str, float]:
        """
        Check DynamoDB table health.
        
        Returns:
            (healthy, message, response_time_ms)
        """
        start = time.time()
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(table_name)
            # Simple describe operation to check connectivity
            table.table_status
            duration_ms = (time.time() - start) * 1000
            return True, "OK", duration_ms
        except ClientError as e:
            duration_ms = (time.time() - start) * 1000
            return False, f"Error: {e}", duration_ms
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return False, f"Unexpected error: {e}", duration_ms

    def check_secrets_manager(self, secret_name: str) -> Tuple[bool, str, float]:
        """
        Check Secrets Manager connectivity.
        
        Returns:
            (healthy, message, response_time_ms)
        """
        start = time.time()
        try:
            client = boto3.client('secretsmanager')
            # Just describe the secret, don't retrieve actual value
            client.describe_secret(SecretId=secret_name)
            duration_ms = (time.time() - start) * 1000
            return True, "OK", duration_ms
        except ClientError as e:
            duration_ms = (time.time() - start) * 1000
            return False, f"Error: {e.response['Error']['Code']}", duration_ms
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return False, f"Unexpected error: {e}", duration_ms

    def check_freshservice_api(self, api_url: str, api_key: str) -> Tuple[bool, str, float]:
        """
        Check FreshService API health.
        
        Returns:
            (healthy, message, response_time_ms)
        """
        start = time.time()
        try:
            import requests
            headers = {
                'Authorization': f'Basic {api_key}',
                'Content-Type': 'application/json'
            }
            # Simple API call to check connectivity
            response = requests.get(
                f"{api_url}/api/v2/agents/me",
                headers=headers,
                timeout=5
            )
            duration_ms = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return True, "OK", duration_ms
            else:
                return False, f"HTTP {response.status_code}", duration_ms
                
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return False, f"Error: {str(e)}", duration_ms

    def perform_comprehensive_health_check(self, config) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all dependencies.
        
        Returns:
            Health status dictionary
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "metrics": {}
        }

        all_healthy = True

        # Check DynamoDB tables
        conversation_table = f"{config.ENVIRONMENT}-ConversationState"
        db_healthy, db_msg, db_time = self.check_dynamodb(conversation_table)
        health_status["checks"]["dynamodb"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "message": db_msg,
            "response_time_ms": round(db_time, 2),
            "table": conversation_table
        }
        self.metrics.record_system_health("DynamoDB", db_healthy, db_time)
        all_healthy = all_healthy and db_healthy

        # Check Secrets Manager
        secret_name = f"{config.ENVIRONMENT}/SystemsBot/Config"
        sm_healthy, sm_msg, sm_time = self.check_secrets_manager(secret_name)
        health_status["checks"]["secrets_manager"] = {
            "status": "healthy" if sm_healthy else "unhealthy",
            "message": sm_msg,
            "response_time_ms": round(sm_time, 2),
            "secret": secret_name
        }
        self.metrics.record_system_health("SecretsManager", sm_healthy, sm_time)
        all_healthy = all_healthy and sm_healthy

        # Check FreshService if enabled and external checks allowed
        if config.is_freshservice_enabled() and self.enable_external_checks:
            fs_healthy, fs_msg, fs_time = self.check_freshservice_api(
                config.FRESHSERVICE_URL,
                config.FRESHSERVICE_API_KEY
            )
            health_status["checks"]["freshservice"] = {
                "status": "healthy" if fs_healthy else "unhealthy",
                "message": fs_msg,
                "response_time_ms": round(fs_time, 2)
            }
            self.metrics.record_system_health("FreshService", fs_healthy, fs_time)
            all_healthy = all_healthy and fs_healthy
        elif config.is_freshservice_enabled():
            health_status["checks"]["freshservice"] = {
                "status": "skipped",
                "message": "External health checks disabled (use ?detailed=true&external=true to enable)"
            }
        else:
            health_status["checks"]["freshservice"] = {
                "status": "disabled",
                "message": "FreshService integration not enabled"
            }

        # Overall status
        health_status["status"] = "healthy" if all_healthy else "degraded"
        
        # Add summary metrics
        health_status["metrics"]["total_checks"] = len(health_status["checks"])
        health_status["metrics"]["healthy_checks"] = sum(
            1 for c in health_status["checks"].values() 
            if c.get("status") == "healthy"
        )
        health_status["metrics"]["unhealthy_checks"] = sum(
            1 for c in health_status["checks"].values() 
            if c.get("status") == "unhealthy"
        )

        return health_status


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point for health checks.
    Returns comprehensive health status with dependency checks.
    """
    from src.config import Config

    try:
        environment = os.environ.get("ENVIRONMENT", "unknown")

        health_status = {
            "status": "healthy",
            "environment": environment,
            "version": Config.APP_VERSION,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Try to load full config for detailed status
        try:
            Config.load()
            health_status["integrations"] = {
                "gemini": Config.is_gemini_enabled(),
                "freshservice": Config.is_freshservice_enabled(),
                "intune": Config.is_intune_enabled()
            }
            health_status["config_loaded"] = True

            # Perform comprehensive health check if requested
            query_params = event.get('queryStringParameters') or {}
            if query_params.get('detailed') == 'true':
                # Allow external checks only if explicitly requested
                enable_external = query_params.get('external') == 'true'
                checker = HealthChecker(enable_external_checks=enable_external)
                comprehensive_status = checker.perform_comprehensive_health_check(Config)
                health_status.update(comprehensive_status)

        except Exception as config_error:
            logger.warning(f"Config not fully loaded: {config_error}")
            health_status["config_loaded"] = False
            health_status["config_error"] = str(config_error)
            health_status["status"] = "degraded"

        # Determine HTTP status code
        status_code = 200
        if health_status["status"] == "unhealthy":
            status_code = 503
        elif health_status["status"] == "degraded":
            status_code = 200  # Still return 200 for degraded (partial functionality)

        return {
            'statusCode': status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(health_status, indent=2)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        }
