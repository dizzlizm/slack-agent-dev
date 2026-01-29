"""
Base tools and utilities shared across all integrations.
"""
import logging
import time
import requests


def retry_on_failure(max_retries=3, backoff_factor=1.0):
    """
    Decorator to retry a function on transient failures.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Check if it's a retryable error (5xx, timeouts, connection errors)
                        should_retry = False
                        if isinstance(
                            e,
                            (
                                requests.exceptions.Timeout,
                                requests.exceptions.ConnectionError,
                            ),
                        ):
                            should_retry = True
                        elif hasattr(e, "response") and e.response is not None:
                            if 500 <= e.response.status_code < 600:
                                should_retry = True

                        if should_retry:
                            sleep_time = backoff_factor * (2**attempt)
                            logging.warning(
                                f"API call failed (attempt {attempt + 1}/{max_retries}), "
                                f"retrying in {sleep_time}s: {e}"
                            )
                            time.sleep(sleep_time)
                        else:
                            # Non-retryable error, raise immediately
                            raise
                    else:
                        logging.error(
                            f"API call failed after {max_retries} attempts: {e}"
                        )
                        raise
            raise last_exception

        return wrapper

    return decorator
