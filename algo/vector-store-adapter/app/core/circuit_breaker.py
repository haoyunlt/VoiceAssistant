"""Circuit Breaker implementation for fault tolerance"""

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: After timeout, try to recover

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before trying to recover (half-open)
        expected_exception: Exception type to catch (default: Exception)
        name: Name for logging
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state"""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)"""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)"""
        return self._state == CircuitState.HALF_OPEN

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            # Check if we should try to recover
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"[{self.name}] Circuit breaker entering HALF_OPEN state")
                else:
                    raise Exception(f"[{self.name}] Circuit breaker is OPEN")

        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovered successfully
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"[{self.name}] Circuit breaker recovered, entering CLOSED state")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self):
        """Handle failed call"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery, go back to OPEN
                self._state = CircuitState.OPEN
                logger.warning(
                    f"[{self.name}] Circuit breaker failed during recovery, back to OPEN state"
                )
            elif self._failure_count >= self.failure_threshold:
                # Too many failures, open the circuit
                self._state = CircuitState.OPEN
                logger.error(
                    f"[{self.name}] Circuit breaker OPENED "
                    f"(failures: {self._failure_count}/{self.failure_threshold})"
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    async def reset(self):
        """Manually reset circuit breaker"""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info(f"[{self.name}] Circuit breaker manually reset")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }
