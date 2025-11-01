"""
SQL 查询工具 - SQL Query Tool

将自然语言转换为 SQL 查询，执行结构化数据查询。
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SQLQueryTool:
    """SQL 查询工具"""

    def __init__(self, llm_client=None, database_client=None):
        """
        初始化 SQL 查询工具

        Args:
            llm_client: LLM 客户端（用于 Text-to-SQL）
            database_client: 数据库客户端（可选）
        """
        self.llm_client = llm_client
        self.database_client = database_client
        self.name = "sql_query"
        self.description = "查询结构化数据表，适用于产品列表、销售数据、统计信息等场景"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询描述（自然语言），如'找出销量最高的产品'",
                },
                "table_schema": {
                    "type": "string",
                    "description": "表结构描述（可选），如'products(id, name, sales)'",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 SQL 查询

        Args:
            params: 包含 query, table_schema

        Returns:
            {
                "text": "查询结果文本描述",
                "sql": "生成的 SQL 语句",
                "results": [...],
                "count": 5
            }
        """
        query = params.get("query")
        table_schema = params.get("table_schema")

        if not query:
            raise ValueError("query 参数不能为空")

        logger.info(f"SQL query: {query[:50]}")

        try:
            # Step 1: Text-to-SQL（自然语言转SQL）
            if self.llm_client:
                sql = await self._text_to_sql(query, table_schema)
            else:
                # 降级：使用规则匹配
                sql = self._rule_based_sql(query)

            logger.info(f"Generated SQL: {sql}")

            # Step 2: 执行 SQL（如果有数据库连接）
            if self.database_client:
                results = await self._execute_sql(sql)
            else:
                # 模拟结果
                results = self._mock_results(query)

            # Step 3: 格式化结果
            text = self._format_results(query, sql, results)

            return {
                "text": text,
                "sql": sql,
                "results": results,
                "count": len(results),
            }

        except Exception as e:
            logger.error(f"SQL query failed: {e}", exc_info=True)
            return {
                "text": f"SQL 查询失败：{str(e)}",
                "sql": "",
                "results": [],
                "count": 0,
                "error": str(e),
            }

    async def _text_to_sql(self, query: str, table_schema: str | None) -> str:
        """
        使用 LLM 将自然语言转换为 SQL

        Args:
            query: 自然语言查询
            table_schema: 表结构

        Returns:
            SQL 语句
        """
        schema_prompt = ""
        if table_schema:
            schema_prompt = f"\n表结构：{table_schema}"

        prompt = f"""将以下自然语言查询转换为 SQL 语句：

查询：{query}{schema_prompt}

要求：
1. 只返回 SQL 语句，不要解释
2. 使用标准 SQL 语法
3. 确保查询安全（防止 SQL 注入）

SQL：
"""

        response = await self.llm_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )

        sql = response.choices[0].message.content.strip()

        # 清理 SQL（移除可能的代码块标记）
        sql = sql.replace("```sql", "").replace("```", "").strip()

        return sql

    def _rule_based_sql(self, query: str) -> str:
        """基于规则的 SQL 生成（降级方案）"""
        query_lower = query.lower()

        # 简单的模式匹配
        if "销量" in query and "最高" in query:
            return "SELECT * FROM products ORDER BY sales DESC LIMIT 10"
        elif "平均" in query and "销量" in query:
            return "SELECT AVG(sales) as avg_sales FROM products"
        elif "总" in query and "销量" in query:
            return "SELECT SUM(sales) as total_sales FROM products"
        elif "产品" in query:
            return "SELECT * FROM products LIMIT 10"
        else:
            return "SELECT * FROM products LIMIT 10"

    async def _execute_sql(self, sql: str) -> list[Dict[str, Any]]:
        """执行 SQL 查询（需要数据库连接）"""
        # 这里应该连接真实数据库
        # 当前返回空，因为没有配置数据库
        logger.warning("Database client not configured, skipping execution")
        return []

    def _mock_results(self, query: str) -> list[Dict[str, Any]]:
        """模拟查询结果"""
        return [
            {"id": 1, "name": "产品A", "sales": 1000, "price": 99.99},
            {"id": 2, "name": "产品B", "sales": 800, "price": 149.99},
            {"id": 3, "name": "产品C", "sales": 600, "price": 79.99},
        ]

    def _format_results(self, query: str, sql: str, results: list) -> str:
        """格式化查询结果"""
        text_parts = [f"查询：{query}", f"SQL：{sql}\n"]

        if results:
            text_parts.append(f"找到 {len(results)} 条记录：")

            # 格式化为表格（简化版）
            for i, row in enumerate(results[:5], 1):
                row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                text_parts.append(f"{i}. {row_str}")

            if len(results) > 5:
                text_parts.append(f"... 还有 {len(results) - 5} 条记录")
        else:
            text_parts.append("未找到记录（使用模拟数据）")

        return "\n".join(text_parts)
