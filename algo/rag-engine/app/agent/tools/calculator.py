"""
计算器工具 - Calculator Tool

使用 SymPy 进行数学计算和符号运算。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CalculatorTool:
    """计算器工具"""

    def __init__(self):
        """初始化计算器工具"""
        self.name = "calculator"
        self.description = "进行数学计算，支持加减乘除、百分比、幂运算等"
        self.parameters = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '2 + 3', '(100 - 80) / 80 * 100' 等",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行计算

        Args:
            params: 包含 expression

        Returns:
            {
                "text": "计算结果描述",
                "result": 数值结果,
                "expression": 原始表达式
            }
        """
        expression = params.get("expression")

        if not expression:
            raise ValueError("expression 参数不能为空")

        logger.info(f"Calculating: {expression}")

        try:
            # 使用 sympy 计算
            import sympy

            # 安全解析表达式
            result = sympy.sympify(expression)

            # 计算数值结果
            numeric_result = float(result.evalf()) if result.is_number else str(result)

            # 格式化输出
            if isinstance(numeric_result, float):
                # 处理百分比
                if "%" in expression or "百分" in expression:
                    text = f"计算结果：{numeric_result:.2f}%"
                else:
                    # 根据大小决定精度
                    if abs(numeric_result) < 0.01:
                        text = f"计算结果：{numeric_result:.6f}"
                    elif abs(numeric_result) < 1000:
                        text = f"计算结果：{numeric_result:.2f}"
                    else:
                        text = f"计算结果：{numeric_result:,.2f}"
            else:
                text = f"计算结果：{numeric_result}"

            return {
                "text": text,
                "result": numeric_result,
                "expression": expression,
            }

        except Exception as e:
            logger.error(f"Calculation failed: {e}", exc_info=True)

            # 降级：使用 eval（仅支持基本运算）
            try:
                # 安全检查
                if any(
                    keyword in expression.lower() for keyword in ["import", "exec", "eval", "__"]
                ):
                    raise ValueError("表达式包含不安全内容") from e

                # 仅允许基本数学运算
                allowed_chars = set("0123456789+-*/().%eE ")
                if not all(c in allowed_chars for c in expression):
                    raise ValueError("表达式包含不支持的字符") from e

                result = eval(expression, {"__builtins__": {}}, {})

                return {
                    "text": f"计算结果：{result:.2f}"
                    if isinstance(result, float)
                    else f"计算结果：{result}",
                    "result": result,
                    "expression": expression,
                }

            except Exception as fallback_error:
                logger.error(f"Fallback calculation failed: {fallback_error}")
                return {
                    "text": f"计算失败：{str(e)}",
                    "result": None,
                    "expression": expression,
                    "error": str(e),
                }
