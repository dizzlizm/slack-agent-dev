"""
Comprehensive input validation and sanitization for security.

Provides validation for various input types including emails, ticket IDs,
serial numbers, and custom fields. Includes sanitization to prevent
injection attacks and data integrity issues.
"""

import re
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class DataClassification(Enum):
    """Data sensitivity classification levels."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class InputValidator:
    """Comprehensive input validation and sanitization."""

    # Email validation regex (RFC 5322 simplified)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    # URL validation
    URL_PATTERN = re.compile(
        r'^https?://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?$'
    )

    # Device serial number patterns (common formats)
    SERIAL_PATTERNS = [
        re.compile(r'^[A-Z0-9]{8,20}$'),  # Alphanumeric 8-20 chars
        re.compile(r'^[A-Z]{2}\d{8,12}$'),  # 2 letters + 8-12 digits
    ]

    # PII patterns for detection
    PII_PATTERNS = {
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'employee_id': re.compile(r'\b[A-Z]{2}\d{6}\b'),
        'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    }

    # Dangerous characters for injection prevention
    DANGEROUS_CHARS = ['<', '>', '"', "'", '&', ';', '|', '`', '$', '(', ')']

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)", re.IGNORECASE),
        re.compile(r"(--|;|\/\*|\*\/|xp_|sp_)", re.IGNORECASE),
        re.compile(r"(\bOR\b.*=.*)", re.IGNORECASE),
        re.compile(r"(\bAND\b.*=.*)", re.IGNORECASE),
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r'[;&|`$\n]'),
        re.compile(r'\$\(.*\)'),
        re.compile(r'`.*`'),
    ]

    @staticmethod
    def validate_email(email: str, allowed_domains: Optional[List[str]] = None) -> bool:
        """
        Validate email format and optionally check domain.
        
        Args:
            email: Email address to validate
            allowed_domains: Optional list of allowed email domains
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email or not isinstance(email, str):
            raise ValidationError("Email must be a non-empty string")

        email = email.strip().lower()

        if not InputValidator.EMAIL_PATTERN.match(email):
            raise ValidationError(f"Invalid email format: {email}")

        if allowed_domains:
            domain = email.split('@')[1]
            if domain not in allowed_domains:
                raise ValidationError(f"Email domain not allowed: {domain}")

        return True

    @staticmethod
    def validate_ticket_id(ticket_id: Any) -> int:
        """
        Validate ticket ID format and range.
        
        Args:
            ticket_id: Ticket ID to validate
            
        Returns:
            Validated ticket ID as integer
            
        Raises:
            ValidationError: If ticket ID is invalid
        """
        try:
            tid = int(ticket_id)
        except (TypeError, ValueError):
            raise ValidationError(f"Ticket ID must be an integer: {ticket_id}")

        if tid <= 0:
            raise ValidationError(f"Ticket ID must be positive: {tid}")

        if tid > 9999999999:  # Reasonable upper bound
            raise ValidationError(f"Ticket ID exceeds maximum value: {tid}")

        return tid

    @staticmethod
    def validate_serial_number(serial: str) -> str:
        """
        Validate device serial number format.
        
        Args:
            serial: Serial number to validate
            
        Returns:
            Validated serial number
            
        Raises:
            ValidationError: If serial number is invalid
        """
        if not serial or not isinstance(serial, str):
            raise ValidationError("Serial number must be a non-empty string")

        serial = serial.strip().upper()

        # Check against known patterns
        if not any(pattern.match(serial) for pattern in InputValidator.SERIAL_PATTERNS):
            raise ValidationError(f"Invalid serial number format: {serial}")

        return serial

    @staticmethod
    def validate_priority(priority: Any) -> int:
        """
        Validate ticket/incident priority.
        
        Args:
            priority: Priority value to validate (1-4)
            
        Returns:
            Validated priority
            
        Raises:
            ValidationError: If priority is invalid
        """
        try:
            p = int(priority)
        except (TypeError, ValueError):
            raise ValidationError(f"Priority must be an integer: {priority}")

        if p not in [1, 2, 3, 4]:
            raise ValidationError(f"Priority must be 1-4: {p}")

        return p

    @staticmethod
    def validate_status(status: Any, valid_statuses: List[int]) -> int:
        """
        Validate status value against allowed values.
        
        Args:
            status: Status value to validate
            valid_statuses: List of valid status codes
            
        Returns:
            Validated status
            
        Raises:
            ValidationError: If status is invalid
        """
        try:
            s = int(status)
        except (TypeError, ValueError):
            raise ValidationError(f"Status must be an integer: {status}")

        if s not in valid_statuses:
            raise ValidationError(f"Invalid status {s}. Must be one of: {valid_statuses}")

        return s

    @staticmethod
    def validate_url(url: str) -> str:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")

        url = url.strip()

        if not InputValidator.URL_PATTERN.match(url):
            raise ValidationError(f"Invalid URL format: {url}")

        return url

    @staticmethod
    def sanitize_user_input(text: str, max_length: int = 10000) -> str:
        """
        Sanitize user input to remove potential injection attempts.
        
        Args:
            text: Text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
            
        Raises:
            ValidationError: If input contains dangerous patterns
        """
        if not isinstance(text, str):
            raise ValidationError("Input must be a string")

        # Check length
        if len(text) > max_length:
            raise ValidationError(f"Input exceeds maximum length of {max_length}")

        # Check for SQL injection patterns
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(f"Potential SQL injection detected in input")
                raise ValidationError("Input contains potentially dangerous SQL patterns")

        # Check for command injection patterns
        for pattern in InputValidator.COMMAND_INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(f"Potential command injection detected in input")
                raise ValidationError("Input contains potentially dangerous command patterns")

        # Remove null bytes
        text = text.replace('\x00', '')

        return text

    @staticmethod
    def validate_custom_fields(custom_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate custom fields dictionary.
        
        Args:
            custom_fields: Custom fields to validate
            
        Returns:
            Validated custom fields
            
        Raises:
            ValidationError: If custom fields are invalid
        """
        if not isinstance(custom_fields, dict):
            raise ValidationError("Custom fields must be a dictionary")

        validated = {}
        for key, value in custom_fields.items():
            # Validate key
            if not isinstance(key, str):
                raise ValidationError(f"Custom field key must be string: {key}")
            
            if not key.strip():
                raise ValidationError("Custom field key cannot be empty")

            # Sanitize string values
            if isinstance(value, str):
                value = InputValidator.sanitize_user_input(value, max_length=5000)

            validated[key] = value

        return validated

    @staticmethod
    def classify_data_sensitivity(text: str) -> DataClassification:
        """
        Classify data sensitivity level.
        
        Args:
            text: Text to classify
            
        Returns:
            Data classification level
        """
        if not text:
            return DataClassification.PUBLIC

        # Check for PII patterns
        for pii_type, pattern in InputValidator.PII_PATTERNS.items():
            if pattern.search(text):
                logger.info(f"Detected {pii_type} pattern in text")
                return DataClassification.RESTRICTED

        # Check for sensitive keywords
        sensitive_keywords = [
            'password', 'secret', 'api_key', 'token', 'credential',
            'ssn', 'credit card', 'bank account', 'salary'
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in sensitive_keywords):
            return DataClassification.CONFIDENTIAL

        # Default to internal
        return DataClassification.INTERNAL

    @staticmethod
    def redact_pii(text: str) -> str:
        """
        Redact PII from text for safe logging.
        
        Args:
            text: Text containing potential PII
            
        Returns:
            Text with PII redacted
        """
        if not text:
            return text

        redacted = text

        # Redact PII patterns
        for pii_type, pattern in InputValidator.PII_PATTERNS.items():
            redacted = pattern.sub(f'[REDACTED_{pii_type.upper()}]', redacted)

        # Redact email addresses
        redacted = InputValidator.EMAIL_PATTERN.sub('[REDACTED_EMAIL]', redacted)

        return redacted

    @staticmethod
    def validate_slack_user_id(user_id: str) -> str:
        """
        Validate Slack user ID format.
        
        Args:
            user_id: Slack user ID to validate
            
        Returns:
            Validated user ID
            
        Raises:
            ValidationError: If user ID is invalid
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("User ID must be a non-empty string")

        # Slack user IDs start with U and are alphanumeric
        if not re.match(r'^U[A-Z0-9]{8,}$', user_id):
            raise ValidationError(f"Invalid Slack user ID format: {user_id}")

        return user_id

    @staticmethod
    def validate_json_structure(data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate JSON structure has required fields.
        
        Args:
            data: JSON data to validate
            required_fields: List of required field names
            
        Raises:
            ValidationError: If required fields are missing
        """
        if not isinstance(data, dict):
            raise ValidationError("Data must be a dictionary")

        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    @staticmethod
    def validate_limit(limit: Any, min_val: int = 1, max_val: int = 100) -> int:
        """
        Validate limit parameter for pagination.
        
        Args:
            limit: Limit value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            
        Returns:
            Validated limit
            
        Raises:
            ValidationError: If limit is invalid
        """
        try:
            lim = int(limit)
        except (TypeError, ValueError):
            raise ValidationError(f"Limit must be an integer: {limit}")

        if lim < min_val or lim > max_val:
            raise ValidationError(f"Limit must be between {min_val} and {max_val}: {lim}")

        return lim
