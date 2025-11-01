"""
代码解释器工具 - Code Interpreter Tool

安全地执行 Python 代码片段，用于复杂计算、数据处理等。
"""

import ast
import io
import logging
from contextlib import redirect_stdout
from typing import Any

logger = logging.getLogger(__name__)


class CodeInterpreterTool:
    """代码解释器工具"""

    def __init__(self, timeout_seconds: int = 5):
        """
        初始化代码解释器工具

        Args:
            timeout_seconds: 执行超时时间（秒）
        """
        self.timeout_seconds = timeout_seconds
        self.name = "code_interpreter"
        self.description = "执行 Python 代码进行复杂计算、数据处理、绘图等。支持 NumPy, Pandas 等库"
        self.parameters = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python 代码（多行字符串）",
                },
                "description": {
                    "type": "string",
                    "description": "代码功能描述（可选）",
                },
            },
            "required": ["code"],
        }

        # 允许的模块白名单
        self.allowed_modules = {
            "math",
            "statistics",
            "json",
            "datetime",
            "collections",
            "itertools",
            "functools",
            # 数据科学库（如果已安装）
            "numpy",
            "pandas",
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行 Python 代码

        Args:
            params: 包含 code, description

        Returns:
            {
                "text": "执行结果文本",
                "output": "标准输出",
                "result": "返回值",
                "error": "错误信息（如果有）"
            }
        """
        code = params.get("code")
        description = params.get("description", "")

        if not code:
            raise ValueError("code 参数不能为空")

        logger.info(f"Code interpreter: {description or code[:50]}")

        try:
            # Step 1: 安全检查
            if not self._is_safe_code(code):
                return {
                    "text": "代码包含不安全内容，执行被拒绝",
                    "output": "",
                    "result": None,
                    "error": "unsafe_code",
                }

            # Step 2: 执行代码（沙箱环境）
            output, result, error = await self._execute_code(code)

            # Step 3: 格式化结果
            text = f"代码执行出错：{error}" if error else self._format_result(code, output, result)

            return {
                "text": text,
                "output": output,
                "result": result,
                "error": error,
            }

        except Exception as e:
            logger.error(f"Code execution failed: {e}", exc_info=True)
            return {
                "text": f"代码执行失败：{str(e)}",
                "output": "",
                "result": None,
                "error": str(e),
            }

    def _is_safe_code(self, code: str) -> bool:
        """
        检查代码是否安全

        Args:
            code: Python 代码

        Returns:
            是否安全
        """
        # 黑名单检查
        dangerous_keywords = [
            "import os",
            "import sys",
            "import subprocess",
            "exec(",
            "eval(",
            "__import__",
            "open(",
            "file(",
            "compile(",
        ]

        for keyword in dangerous_keywords:
            if keyword in code:
                logger.warning(f"Unsafe code detected: {keyword}")
                return False

        # AST 解析检查
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # 禁止导入非白名单模块
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in self.allowed_modules:
                            logger.warning(f"Module not allowed: {alias.name}")
                            return False

                if isinstance(node, ast.ImportFrom):  # noqa: SIM102
                    if node.module and node.module not in self.allowed_modules:
                        logger.warning(f"Module not allowed: {node.module}")
                        return False

        except SyntaxError as e:
            logger.error(f"Syntax error in code: {e}")
            return False

        return True

    async def _execute_code(self, code: str) -> tuple[str, Any, str | None]:
        """
        在沙箱环境中执行代码

        Args:
            code: Python 代码

        Returns:
            (标准输出, 返回值, 错误信息)
        """
        # 准备执行环境
        local_vars = {}
        global_vars = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "sum": sum,
                "max": max,
                "min": min,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "list": list,
                "dict": dict,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
            }
        }

        # 尝试导入常用库
        try:
            import math

            global_vars["math"] = math
        except ImportError:
            pass

        try:
            import statistics

            global_vars["statistics"] = statistics
        except ImportError:
            pass

        # 捕获标准输出
        output_buffer = io.StringIO()
        result = None
        error = None

        try:
            with redirect_stdout(output_buffer):
                # 执行代码
                exec(code, global_vars, local_vars)

                # 获取返回值（如果代码中有赋值给 result）
                if "result" in local_vars:
                    result = local_vars["result"]

        except Exception as e:
            error = str(e)
            logger.error(f"Code execution error: {e}", exc_info=True)

        output = output_buffer.getvalue()

        return output, result, error

    def _format_result(self, code: str, output: str, result: Any) -> str:
        """格式化执行结果"""
        text_parts = ["代码执行成功！\n"]

        # 显示代码（截断）
        code_preview = code[:200] + "..." if len(code) > 200 else code
        text_parts.append(f"代码：\n{code_preview}\n")

        # 显示输出
        if output:
            output_preview = output[:500] + "..." if len(output) > 500 else output
            text_parts.append(f"输出：\n{output_preview}\n")

        # 显示返回值
        if result is not None:
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            text_parts.append(f"返回值：{result_str}")

        return "\n".join(text_parts)
