"""
Prompt Generator - Prompt 生成器

支持多种模式：
- Simple: 简单问答
- Advanced: 复杂推理
- Precise: 精确引用
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class PromptGenerator:
    """Prompt 生成器"""

    def __init__(self):
        """初始化 Prompt 生成器"""
        # Prompt 模板
        self.templates = self._initialize_templates()
        logger.info("Prompt generator created")

    def _initialize_templates(self) -> Dict[str, str]:
        """初始化 Prompt 模板"""
        return {
            "simple": """你是一个专业的AI助手。请根据以下参考资料回答用户的问题。

参考资料：
{context}

用户问题：{query}

请基于参考资料回答问题。如果参考资料中没有相关信息，请诚实地告诉用户。

回答：""",
            "advanced": """你是一个专业的AI助手，擅长深度思考和复杂推理。请根据以下参考资料回答用户的问题。

参考资料：
{context}

用户问题：{query}

请按照以下步骤回答：
1. 分析问题的核心要点
2. 从参考资料中提取相关信息
3. 进行逻辑推理和综合分析
4. 给出清晰、结构化的回答

如果参考资料不足以回答问题，请说明需要哪些额外信息。

回答：""",
            "precise": """你是一个严谨的AI助手。请根据以下参考资料回答用户的问题，并明确标注信息来源。

参考资料：
{context}

用户问题：{query}

请按照以下格式回答：
1. 直接回答问题
2. 在每个关键论点后标注来源（如：[文档 1]）
3. 如果某些信息不在参考资料中，明确说明

回答：""",
        }

    async def generate(self, query: str, context: str, mode: str = "simple") -> str:
        """
        生成 Prompt

        Args:
            query: 用户查询
            context: 上下文
            mode: 模式 (simple/advanced/precise)

        Returns:
            生成的 Prompt
        """
        # 获取模板
        template = self.templates.get(mode, self.templates["simple"])

        # 填充模板
        prompt = template.format(query=query, context=context)

        logger.info(f"Generated prompt in '{mode}' mode: {len(prompt)} chars")

        return prompt

    def add_custom_template(self, name: str, template: str):
        """
        添加自定义模板

        Args:
            name: 模板名称
            template: 模板内容（需包含 {query} 和 {context} 占位符）
        """
        self.templates[name] = template
        logger.info(f"Added custom template: {name}")
