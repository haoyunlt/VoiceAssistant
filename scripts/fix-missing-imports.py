#!/usr/bin/env python3
"""
批量修复 Python 文件中缺失的导入
"""

import re
from pathlib import Path

# 定义需要修复的文件和对应的导入
FIXES = [
    {
        "file": "algo/agent-engine/app/memory/memory_manager.py",
        "search": r"^(import .*|from .* import .*)\n",
        "add_import": "from typing import Any\n",
        "check": "LLMClient"
    },
    {
        "file": "algo/agent-engine/main.py",
        "search": r"^(from fastapi import .*)\n",
        "add_import": "from starlette.middleware.base import BaseHTTPMiddleware\n",
        "check": "BaseHTTPMiddleware"
    },
    {
        "file": "algo/retrieval-service/app/routers/query_enhancement.py",
        "search": r"^(from typing import .*)\n",
        "add_import": None,
        "replace_line": "from typing import Any",
        "check": "Dict"
    },
    {
        "file": "algo/retrieval-service/app/services/query/expansion_service.py",
        "search": r"^(import .*)\n",
        "add_import": "import logging\nlogger = logging.getLogger(__name__)\n",
        "check": "logger"
    },
    {
        "file": "algo/vector-store-adapter/app/core/base_backend.py",
        "search": r"^(from typing import .*)\n",
        "add_import": "from typing import Any\n",
        "check": "BaseBackend"
    },
    {
        "file": "algo/vector-store-adapter/main.py",
        "search": r"^(from fastapi import .*)\n",
        "add_import": "from fastapi import Response\n",
        "check": "Response"
    },
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

print("🔧 批量修复缺失的导入...")

for fix in FIXES:
    file_path = PROJECT_ROOT / fix["file"]

    if not file_path.exists():
        print(f"  ⚠️  文件不存在: {fix['file']}")
        continue

    content = file_path.read_text()

    # 检查是否需要修复
    if fix["check"] not in content or (fix.get("add_import") and fix["add_import"] in content):
        print(f"  ✓ 跳过（已修复或不需要）: {fix['file']}")
        continue

    # 执行修复
    if fix.get("replace_line"):
        # 替换导入行
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                if "Dict" in line or "List" in line:
                    lines[i] = fix["replace_line"]
                    break
        content = "\n".join(lines)
    elif fix.get("add_import"):
        # 添加导入
        pattern = re.compile(fix["search"], re.MULTILINE)
        matches = list(pattern.finditer(content))
        if matches:
            last_import = matches[-1]
            insert_pos = last_import.end()
            content = content[:insert_pos] + fix["add_import"] + content[insert_pos:]

    # 写回文件
    file_path.write_text(content)
    print(f"  ✅ 修复: {fix['file']}")

print("\n✨ 批量修复完成！")
