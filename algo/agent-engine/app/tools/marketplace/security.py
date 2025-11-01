"""
Security Checker for Tool Registration
"""

import ast
import inspect
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class SecurityChecker:
    """Security checker for tool functions"""

    DANGEROUS_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "system",
        "popen",
        "spawn",
        "fork",
        "rmdir",
        "remove",
        "unlink",
        "rmtree",
    }

    DANGEROUS_MODULES = {"os", "sys", "subprocess", "shutil", "pickle", "shelve", "marshal"}

    FILE_OPERATIONS = {"open", "read", "write", "remove", "mkdir", "rmdir", "listdir"}

    NETWORK_MODULES = {"requests", "urllib", "http", "socket", "ftplib", "smtplib", "telnetlib"}

    def check_function(self, func: Callable, permissions) -> bool:
        """Check if function is safe to execute"""
        try:
            # Get function source code
            source = inspect.getsource(func)

            # Parse AST
            tree = ast.parse(source)

            # Check for dangerous operations
            issues = []

            # Check function calls
            issues.extend(self._check_function_calls(tree, permissions))

            # Check imports
            issues.extend(self._check_imports(tree, permissions))

            # Check attribute access
            issues.extend(self._check_attributes(tree, permissions))

            if issues:
                for issue in issues:
                    logger.warning(f"Security issue: {issue}")
                return False

            return True

        except Exception as e:
            logger.error(f"Security check failed: {e}")
            return False

    def _check_function_calls(self, tree: ast.AST, permissions) -> list[str]:
        """Check for dangerous function calls"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)

                # Check dangerous functions
                if func_name in self.DANGEROUS_FUNCTIONS:
                    issues.append(f"Dangerous function: {func_name}")

                # Check file operations
                if func_name in self.FILE_OPERATIONS:  # noqa: SIM102
                    if not permissions.file_system_access:
                        issues.append(f"File operation without permission: {func_name}")

        return issues

    def _check_imports(self, tree: ast.AST, permissions) -> list[str]:
        """Check for dangerous imports"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name

                    # Check dangerous modules
                    if module in self.DANGEROUS_MODULES:
                        issues.append(f"Dangerous module: {module}")

                    # Check network modules
                    if module in self.NETWORK_MODULES:  # noqa: SIM102
                        if not permissions.network_access:
                            issues.append(f"Network module without permission: {module}")

            elif isinstance(node, ast.ImportFrom):
                module = node.module
                if module:
                    # Check dangerous modules
                    if module in self.DANGEROUS_MODULES:
                        issues.append(f"Dangerous module: {module}")

                    # Check network modules
                    if module in self.NETWORK_MODULES:  # noqa: SIM102
                        if not permissions.network_access:
                            issues.append(f"Network module without permission: {module}")

        return issues

    def _check_attributes(self, tree: ast.AST, _permissions) -> list[str]:
        """Check for dangerous attribute access"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                attr_name = node.attr

                # Check dangerous attributes
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    issues.append(f"Accessing dunder attribute: {attr_name}")

        return issues

    def _get_function_name(self, node: ast.AST) -> str:
        """Get function name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        else:
            return ""

    def check_code_complexity(self, func: Callable) -> dict:
        """Check code complexity metrics"""
        try:
            source = inspect.getsource(func)
            tree = ast.parse(source)

            # Count nodes
            node_count = sum(1 for _ in ast.walk(tree))

            # Count loops
            loop_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While)))

            # Count conditionals
            conditional_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.If))

            # Calculate cyclomatic complexity (simplified)
            complexity = 1 + loop_count + conditional_count

            return {
                "node_count": node_count,
                "loop_count": loop_count,
                "conditional_count": conditional_count,
                "complexity": complexity,
                "is_simple": complexity < 10,
            }

        except Exception as e:
            logger.error(f"Complexity check failed: {e}")
            return {"complexity": 999, "is_simple": False}
