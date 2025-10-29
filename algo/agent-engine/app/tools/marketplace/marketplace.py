"""
Tool Marketplace - Plugin registration and execution
"""

import hashlib
import importlib
import inspect
import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.tools.marketplace.sandbox import SandboxConfig, ToolSandbox
from app.tools.marketplace.security import SecurityChecker

logger = logging.getLogger(__name__)


class ToolMetadata(BaseModel):
    """Tool metadata"""
    name: str = Field(..., description="Tool name")
    version: str = Field(..., description="Semantic version")
    author: str = Field(..., description="Author email/name")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category")
    tags: list[str] = Field(default_factory=list, description="Tool tags")
    requires_auth: bool = Field(default=False, description="Requires authentication")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Parameter schema")
    examples: list[dict] = Field(default_factory=list, description="Usage examples")


class ToolPermissions(BaseModel):
    """Tool execution permissions"""
    network_access: bool = Field(default=False, description="Network access allowed")
    file_system_access: bool = Field(default=False, description="File system access allowed")
    database_access: bool = Field(default=False, description="Database access allowed")
    max_execution_time: int = Field(default=30, description="Max execution time in seconds")
    max_memory_mb: int = Field(default=512, description="Max memory in MB")
    allowed_modules: list[str] = Field(default_factory=list, description="Allowed import modules")


class ToolMarketplace:
    """Tool marketplace for dynamic tool loading"""

    def __init__(self, registry_path: str = "./tool_registry"):
        self.registry_path = registry_path
        self.tools: dict[str, dict] = {}
        self.security_checker = SecurityChecker()
        self._ensure_registry_dir()
        self.load_registry()

    def _ensure_registry_dir(self):
        """Ensure registry directory exists"""
        os.makedirs(self.registry_path, exist_ok=True)

    def load_registry(self):
        """Load tool registry from disk"""
        registry_file = f"{self.registry_path}/registry.json"
        if os.path.exists(registry_file):
            try:
                with open(registry_file) as f:
                    self.tools = json.load(f)
                logger.info(f"Loaded {len(self.tools)} tools from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
                self.tools = {}
        else:
            self.tools = {}

    def save_registry(self):
        """Save tool registry to disk"""
        registry_file = f"{self.registry_path}/registry.json"
        try:
            with open(registry_file, 'w') as f:
                json.dump(self.tools, f, indent=2, default=str)
            logger.info(f"Saved {len(self.tools)} tools to registry")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_tool(
        self,
        tool_func: Callable,
        metadata: ToolMetadata,
        permissions: ToolPermissions
    ) -> str:
        """Register a new tool"""
        try:
            # 1. Validate function signature
            sig = inspect.signature(tool_func)
            self._validate_signature(sig, metadata.parameters)

            # 2. Security check
            if not self.security_checker.check_function(tool_func, permissions):
                raise SecurityError("Tool failed security check")

            # 3. Generate tool ID
            tool_id = self._generate_tool_id(metadata)

            # 4. Calculate checksum
            checksum = self._calculate_checksum(tool_func)

            # 5. Save tool info
            tool_info = {
                "id": tool_id,
                "metadata": metadata.dict(),
                "permissions": permissions.dict(),
                "function_path": f"{tool_func.__module__}.{tool_func.__name__}",
                "checksum": checksum,
                "registered_at": datetime.utcnow().isoformat(),
                "usage_count": 0,
                "last_used": None
            }

            self.tools[tool_id] = tool_info
            self.save_registry()

            logger.info(f"Registered tool: {metadata.name} ({tool_id})")
            return tool_id

        except Exception as e:
            logger.error(f"Tool registration failed: {e}")
            raise

    async def execute_tool(
        self,
        tool_id: str,
        inputs: dict[str, Any],
        user_id: str | None = None
    ) -> Any:
        """Execute a tool"""
        try:
            # 1. Get tool info
            tool_info = self.tools.get(tool_id)
            if not tool_info:
                raise ToolNotFoundError(f"Tool {tool_id} not found")

            # 2. Check authentication
            if tool_info["metadata"]["requires_auth"] and not user_id:
                raise AuthenticationError("Tool requires authentication")

            # 3. Load tool function
            tool_func = self._load_tool_function(tool_info["function_path"])

            # 4. Verify checksum
            current_checksum = self._calculate_checksum(tool_func)
            if current_checksum != tool_info["checksum"]:
                logger.warning(f"Tool {tool_id} checksum mismatch - code may have changed")

            # 5. Create sandbox
            sandbox_config = SandboxConfig(**tool_info["permissions"])
            sandbox = ToolSandbox(sandbox_config)

            # 6. Execute in sandbox
            result = await sandbox.execute_safe(tool_func, **inputs)

            # 7. Update usage stats
            tool_info["usage_count"] += 1
            tool_info["last_used"] = datetime.utcnow().isoformat()
            self.save_registry()

            logger.info(f"Executed tool {tool_id} successfully")
            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            raise

    def search_tools(
        self,
        query: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None
    ) -> list[dict]:
        """Search for tools"""
        results = []

        for tool_id, tool_info in self.tools.items():
            metadata = tool_info["metadata"]

            # Category filter
            if category and metadata["category"] != category:
                continue

            # Tags filter
            if tags and not set(tags).intersection(set(metadata["tags"])):
                continue

            # Query filter
            if query:
                searchable = f"{metadata['name']} {metadata['description']}".lower()
                if query.lower() not in searchable:
                    continue

            # Add to results
            results.append({
                "id": tool_id,
                "name": metadata["name"],
                "description": metadata["description"],
                "category": metadata["category"],
                "author": metadata["author"],
                "version": metadata["version"],
                "usage_count": tool_info.get("usage_count", 0)
            })

        # Sort by usage count
        results.sort(key=lambda x: x["usage_count"], reverse=True)

        return results

    def get_tool_info(self, tool_id: str) -> dict | None:
        """Get detailed tool information"""
        return self.tools.get(tool_id)

    def unregister_tool(self, tool_id: str) -> bool:
        """Unregister a tool"""
        if tool_id in self.tools:
            del self.tools[tool_id]
            self.save_registry()
            logger.info(f"Unregistered tool: {tool_id}")
            return True
        return False

    def _validate_signature(
        self,
        sig: inspect.Signature,
        params: dict[str, Any]
    ):
        """Validate function signature matches parameter definition"""
        sig_params = set(sig.parameters.keys())
        declared_params = set(params.keys())

        if sig_params != declared_params:
            raise ValueError(
                f"Parameter mismatch: {sig_params} vs {declared_params}"
            )

    def _generate_tool_id(self, metadata: ToolMetadata) -> str:
        """Generate unique tool ID"""
        content = f"{metadata.name}{metadata.version}{metadata.author}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_checksum(self, func: Callable) -> str:
        """Calculate function checksum"""
        try:
            source = inspect.getsource(func)
            return hashlib.sha256(source.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate checksum: {e}")
            return ""

    def _load_tool_function(self, function_path: str) -> Callable:
        """Dynamically load tool function"""
        module_path, func_name = function_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name)

    def get_statistics(self) -> dict[str, Any]:
        """Get marketplace statistics"""
        total_tools = len(self.tools)
        total_usage = sum(t.get("usage_count", 0) for t in self.tools.values())

        categories = {}
        for tool_info in self.tools.values():
            category = tool_info["metadata"]["category"]
            categories[category] = categories.get(category, 0) + 1

        return {
            "total_tools": total_tools,
            "total_usage": total_usage,
            "categories": categories,
            "avg_usage_per_tool": total_usage / total_tools if total_tools > 0 else 0
        }


class ToolNotFoundError(Exception):
    """Tool not found error"""
    pass


class AuthenticationError(Exception):
    """Authentication error"""
    pass


class SecurityError(Exception):
    """Security error"""
    pass

