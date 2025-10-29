#!/usr/bin/env python3
"""
修复所有Python服务的import问题

主要修复：
1. 统一使用绝对导入
2. 添加必要的__init__.py文件
3. 修复common模块导入
4. 添加proto生成代码的正确导入路径
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 颜色输出
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
ALGO_DIR = PROJECT_ROOT / "algo"

# Python服务列表
PYTHON_SERVICES = [
    "rag-engine",
    "agent-engine",
    "retrieval-service",
    "knowledge-service",
    "voice-engine",
    "multimodal-engine",
    "indexing-service",
    "vector-store-adapter",
    "model-adapter"
]


def print_color(color: str, message: str):
    """彩色输出"""
    print(f"{color}{message}{NC}")


def create_init_files():
    """为所有需要的目录创建__init__.py文件"""
    print_color(GREEN, "\n=== 创建__init__.py文件 ===")

    init_files_created = 0

    # 为每个服务的app目录及其子目录创建__init__.py
    for service in PYTHON_SERVICES:
        service_dir = ALGO_DIR / service
        if not service_dir.exists():
            continue

        app_dir = service_dir / "app"
        if not app_dir.exists():
            continue

        # 遍历所有子目录
        for root, dirs, files in os.walk(app_dir):
            root_path = Path(root)

            # 跳过venv和__pycache__
            if 'venv' in root_path.parts or '__pycache__' in root_path.parts:
                continue

            init_file = root_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Package initialization."""\n')
                print(f"  {GREEN}✓{NC} 创建: {init_file.relative_to(PROJECT_ROOT)}")
                init_files_created += 1

    # 确保api/gen/python有__init__.py
    api_gen_python = PROJECT_ROOT / "api" / "gen" / "python"
    if api_gen_python.exists():
        for root, dirs, files in os.walk(api_gen_python):
            root_path = Path(root)
            init_file = root_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Generated proto package."""\n')
                print(f"  {GREEN}✓{NC} 创建: {init_file.relative_to(PROJECT_ROOT)}")
                init_files_created += 1

    print(f"\n总共创建了 {init_files_created} 个 __init__.py 文件")


def fix_relative_imports(file_path: Path) -> int:
    """
    修复文件中的相对导入为绝对导入

    例如：from ..core import xxx -> from app.core import xxx
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # 确定服务名称
        service_name = None
        for service in PYTHON_SERVICES:
            if service in file_path.parts:
                service_name = service
                break

        if not service_name:
            return 0

        # 获取文件在app目录中的相对位置
        try:
            app_index = file_path.parts.index('app')
            relative_parts = file_path.parts[app_index + 1:-1]  # 不包括文件名
        except ValueError:
            return 0

        # 替换相对导入
        lines = content.split('\n')
        modified = False

        for i, line in enumerate(lines):
            # 匹配 from .. 或 from ...  形式的导入
            match = re.match(r'^from (\.*)([\w.]+)? import (.+)$', line.strip())
            if match:
                dots, module, imports = match.groups()
                if dots:  # 有相对导入
                    # 计算绝对路径
                    up_levels = len(dots) - 1

                    # 从当前位置往上
                    current_parts = list(relative_parts)
                    for _ in range(up_levels):
                        if current_parts:
                            current_parts.pop()

                    # 构建新的导入路径
                    if module:
                        new_module = 'app.' + '.'.join(current_parts + [module]) if current_parts else f'app.{module}'
                    else:
                        new_module = 'app.' + '.'.join(current_parts) if current_parts else 'app'

                    new_line = f"from {new_module} import {imports}"
                    lines[i] = line.replace(match.group(0), new_line)
                    modified = True

        if modified:
            content = '\n'.join(lines)
            file_path.write_text(content, encoding='utf-8')
            return 1

        return 0

    except Exception as e:
        print(f"  {RED}✗{NC} 处理文件失败: {file_path}: {e}")
        return 0


def add_proto_imports():
    """为需要使用proto的服务添加proto导入路径"""
    print_color(GREEN, "\n=== 添加Proto导入支持 ===")

    # 创建proto导入辅助模块
    for service in PYTHON_SERVICES:
        service_dir = ALGO_DIR / service
        if not service_dir.exists():
            continue

        app_dir = service_dir / "app"
        if not app_dir.exists():
            continue

        # 创建proto_imports.py
        proto_imports_file = app_dir / "proto_imports.py"
        proto_imports_content = '''"""
Proto imports helper

自动添加proto生成代码到Python路径
"""

import sys
from pathlib import Path

# 添加proto生成代码目录到Python路径
_proto_path = Path(__file__).parent.parent.parent.parent / "api" / "gen" / "python"
if _proto_path.exists() and str(_proto_path) not in sys.path:
    sys.path.insert(0, str(_proto_path))

# 现在可以导入proto生成的模块
# 例如：
# from rag.v1 import rag_pb2, rag_pb2_grpc
# from retrieval.v1 import retrieval_pb2, retrieval_pb2_grpc
'''

        if not proto_imports_file.exists():
            proto_imports_file.write_text(proto_imports_content)
            print(f"  {GREEN}✓{NC} 创建: {proto_imports_file.relative_to(PROJECT_ROOT)}")


def fix_common_imports():
    """修复common模块的导入方式"""
    print_color(GREEN, "\n=== 修复Common模块导入 ===")

    fixed = 0

    for service in PYTHON_SERVICES:
        service_dir = ALGO_DIR / service
        if not service_dir.exists():
            continue

        # 修改main.py
        main_file = service_dir / "main.py"
        if main_file.exists():
            content = main_file.read_text(encoding='utf-8')

            # 检查是否需要修改
            if "sys.path.insert(0, str(Path(__file__).parent.parent / \"common\"))" in content:
                # 替换为更清晰的方式
                new_import = '''# 添加common目录到Python路径
import sys
from pathlib import Path

_common_path = Path(__file__).parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))
'''
                # 找到并替换
                pattern = r'# 添加 common 模块到路径\nsys\.path\.insert\(0, str\(Path\(__file__\)\.parent\.parent / "common"\)\)'
                if re.search(pattern, content):
                    content = re.sub(pattern, new_import.strip(), content)
                    main_file.write_text(content, encoding='utf-8')
                    print(f"  {GREEN}✓{NC} 修复: {main_file.relative_to(PROJECT_ROOT)}")
                    fixed += 1

    print(f"\n修复了 {fixed} 个文件的common导入")


def scan_and_fix_all():
    """扫描并修复所有Python文件"""
    print_color(GREEN, "\n=== 扫描并修复所有Python文件 ===")

    total_files = 0
    fixed_files = 0

    for service in PYTHON_SERVICES:
        service_dir = ALGO_DIR / service
        if not service_dir.exists():
            continue

        app_dir = service_dir / "app"
        if not app_dir.exists():
            continue

        print(f"\n{YELLOW}处理服务: {service}{NC}")

        # 遍历所有Python文件
        for py_file in app_dir.rglob("*.py"):
            # 跳过venv和__pycache__
            if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue

            total_files += 1

            # 修复相对导入
            if fix_relative_imports(py_file):
                print(f"  {GREEN}✓{NC} 修复: {py_file.relative_to(PROJECT_ROOT)}")
                fixed_files += 1

    print(f"\n{GREEN}扫描了 {total_files} 个文件，修复了 {fixed_files} 个文件{NC}")


def create_import_guide():
    """创建导入指南文档"""
    print_color(GREEN, "\n=== 创建导入指南 ===")

    guide_content = '''# Python Import 规范指南

## 1. 目录结构

```
algo/
├── common/              # 共享工具模块
│   ├── __init__.py
│   ├── cors_config.py
│   ├── llm_client.py
│   └── ...
├── {service}/           # 各个服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── proto_imports.py   # Proto导入辅助
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── main.py
│   └── requirements.txt
api/gen/python/          # Proto生成的代码
    ├── __init__.py
    ├── rag/v1/
    ├── retrieval/v1/
    └── ...
```

## 2. 导入规范

### 2.1 服务内部导入（推荐绝对导入）

```python
# ✅ 推荐：使用绝对导入
from app.core.config import ConfigManager
from app.services.llm_service import LLMService
from app.models.requests import QueryRequest

# ❌ 不推荐：使用相对导入
from ..core.config import ConfigManager
from .llm_service import LLMService
```

### 2.2 Common模块导入

在 `main.py` 中：

```python
# 添加common目录到Python路径
import sys
from pathlib import Path

_common_path = Path(__file__).parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))

# 然后可以直接导入
from cors_config import get_cors_config
from llm_client import UnifiedLLMClient
from structured_logging import setup_logging
```

在其他文件中（如 `app/services/*.py`）：

```python
import sys
from pathlib import Path

# 添加common目录
_common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))

from llm_client import UnifiedLLMClient
```

### 2.3 Proto生成代码导入

使用 `app/proto_imports.py` 辅助模块：

```python
# 在需要使用proto的文件中
from app.proto_imports import *  # 自动添加proto路径

# 然后可以导入proto模块
from rag.v1 import rag_pb2, rag_pb2_grpc
from retrieval.v1 import retrieval_pb2, retrieval_pb2_grpc
from agent.v1 import agent_pb2, agent_pb2_grpc
```

或者手动添加：

```python
import sys
from pathlib import Path

_proto_path = Path(__file__).parent.parent.parent.parent / "api" / "gen" / "python"
if _proto_path.exists() and str(_proto_path) not in sys.path:
    sys.path.insert(0, str(_proto_path))

from rag.v1 import rag_pb2
```

## 3. 最佳实践

### 3.1 服务启动文件（main.py）

```python
import sys
from pathlib import Path

# 1. 添加common路径（必须在最前面）
_common_path = Path(__file__).parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))

# 2. 导入第三方库
from fastapi import FastAPI
from prometheus_client import make_asgi_app

# 3. 导入common模块
from cors_config import get_cors_config
from structured_logging import setup_logging

# 4. 导入应用模块（使用绝对导入）
from app.api.dependencies import get_engine
from app.core.config import ConfigManager
from app.services import ServiceManager
```

### 3.2 服务内部文件（app/**/*.py）

```python
# 1. 标准库导入
import logging
from typing import List, Dict, Optional

# 2. 第三方库导入
from fastapi import Depends, HTTPException
from pydantic import BaseModel

# 3. 应用内部导入（绝对导入）
from app.core.config import ConfigManager
from app.models.requests import QueryRequest
from app.services.llm_service import LLMService

# 4. Common模块导入（如需要）
import sys
from pathlib import Path
_common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))
from llm_client import UnifiedLLMClient
```

## 4. 常见问题

### Q1: ModuleNotFoundError: No module named 'app'

**原因**：使用了绝对导入但Python找不到app模块

**解决**：
```python
# 方案1：运行时从项目根目录运行
cd /path/to/service
python main.py

# 方案2：使用python -m运行
cd /path/to/algo/{service}
python -m app.main

# 方案3：添加PYTHONPATH
export PYTHONPATH=/path/to/algo/{service}:$PYTHONPATH
python main.py
```

### Q2: ImportError: attempted relative import beyond top-level package

**原因**：相对导入层级过多

**解决**：改用绝对导入
```python
# ❌ from ....common import xxx
# ✅
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "common"))
from xxx import yyy
```

### Q3: 无法导入proto生成的模块

**原因**：proto生成代码路径未添加到sys.path

**解决**：使用 `app/proto_imports.py`
```python
from app.proto_imports import *
from rag.v1 import rag_pb2
```

## 5. 自动化工具

```bash
# 运行import修复脚本
python scripts/fix-python-imports.py

# 检查导入问题
python scripts/check-imports.py
```

## 6. IDE配置

### VS Code

在 `.vscode/settings.json` 中添加：

```json
{
    "python.analysis.extraPaths": [
        "${workspaceFolder}/algo/common",
        "${workspaceFolder}/api/gen/python"
    ]
}
```

### PyCharm

1. Mark Directory as -> Sources Root:
   - `algo/common`
   - `api/gen/python`
   - 各个服务的根目录

2. Settings -> Project Structure -> Add Content Root
'''

    guide_file = PROJECT_ROOT / "PYTHON_IMPORT_GUIDE.md"
    guide_file.write_text(guide_content)
    print(f"  {GREEN}✓{NC} 创建: {guide_file.relative_to(PROJECT_ROOT)}")


def main():
    """主函数"""
    print_color(GREEN, "=" * 60)
    print_color(GREEN, "Python Import 修复工具")
    print_color(GREEN, "=" * 60)

    # 1. 创建所有必要的__init__.py文件
    create_init_files()

    # 2. 添加proto导入支持
    add_proto_imports()

    # 3. 修复common模块导入
    fix_common_imports()

    # 4. 扫描并修复所有文件
    scan_and_fix_all()

    # 5. 创建导入指南
    create_import_guide()

    print_color(GREEN, "\n" + "=" * 60)
    print_color(GREEN, "✓ 所有修复完成！")
    print_color(GREEN, "=" * 60)

    print(f"\n{YELLOW}下一步操作：{NC}")
    print("1. 查看导入指南: cat PYTHON_IMPORT_GUIDE.md")
    print("2. 测试各个服务:")
    print("   cd algo/rag-engine && python main.py")
    print("3. 运行测试确保没有破坏现有功能")


if __name__ == "__main__":
    main()
