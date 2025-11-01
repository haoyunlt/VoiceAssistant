"""
Tool Sandbox for Safe Execution
"""

import asyncio
import io
import logging
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SandboxConfig(BaseModel):
    """Sandbox configuration"""

    network_access: bool = False
    file_system_access: bool = False
    database_access: bool = False
    max_execution_time: int = 30
    max_memory_mb: int = 512
    allowed_modules: list[str] = Field(default_factory=list)


class ToolSandbox:
    """Sandboxed tool execution environment"""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.execution_count = 0
        self.total_execution_time = 0.0

    async def execute_safe(self, tool_func: Callable, *args, **kwargs) -> Any:
        """Execute function safely in sandbox"""
        self.execution_count += 1

        try:
            # Create timeout
            async def _execute_with_timeout():
                return await self._execute_function(tool_func, args, kwargs)

            # Execute with timeout
            result = await asyncio.wait_for(
                _execute_with_timeout(), timeout=self.config.max_execution_time
            )

            logger.info("Tool executed successfully in sandbox")
            return result

        except TimeoutError:
            logger.error(f"Tool execution timed out after {self.config.max_execution_time}s")
            raise ToolExecutionError(f"Execution timeout ({self.config.max_execution_time}s)") from None
        except MemoryError:
            logger.error("Tool exceeded memory limit")
            raise ToolExecutionError("Memory limit exceeded") from None
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            raise ToolExecutionError(f"Execution failed: {str(e)}") from e

    async def _execute_function(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Execute function with restrictions"""
        import time

        start_time = time.time()

        try:
            # Capture stdout/stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Check if function is async
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, func, *args)

            # Log captured output
            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()

            if stdout_text:
                logger.debug(f"Tool stdout: {stdout_text}")
            if stderr_text:
                logger.warning(f"Tool stderr: {stderr_text}")

            execution_time = time.time() - start_time
            self.total_execution_time += execution_time

            logger.info(f"Tool executed in {execution_time:.3f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool failed after {execution_time:.3f}s: {e}")
            raise

    def get_statistics(self) -> dict:
        """Get sandbox statistics"""
        return {
            "execution_count": self.execution_count,
            "total_execution_time": self.total_execution_time,
            "avg_execution_time": (
                self.total_execution_time / self.execution_count if self.execution_count > 0 else 0
            ),
        }


class RestrictedEnvironment:
    """Restricted execution environment"""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.original_builtins = {}

    def __enter__(self):
        """Enter restricted environment"""
        import builtins

        # Save original builtins
        self.original_builtins = {
            "open": builtins.open,
            "__import__": builtins.__import__,
        }

        # Override dangerous builtins
        if not self.config.file_system_access:
            builtins.open = self._restricted_open

        if self.config.allowed_modules:
            builtins.__import__ = self._restricted_import

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit restricted environment"""
        import builtins

        # Restore original builtins
        builtins.open = self.original_builtins["open"]
        builtins.__import__ = self.original_builtins["__import__"]

    def _restricted_open(self, *_args, **_kwargs):
        """Restricted file open"""
        raise PermissionError("File system access not allowed")

    def _restricted_import(self, name, *args, **kwargs):
        """Restricted import"""
        if name not in self.config.allowed_modules:
            raise ImportError(f"Module {name} not allowed")
        return self.original_builtins["__import__"](name, *args, **kwargs)


class ToolExecutionError(Exception):
    """Tool execution error"""

    pass
