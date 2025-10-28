#!/usr/bin/env python3
"""
VoiceHelper 未使用代码分析脚本
用途: 深度分析未使用代码，生成详细报告和建议
"""

import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
REPORT_DIR = PROJECT_ROOT / ".reports"


class CodeAnalyzer:
    """代码分析器"""

    def __init__(self):
        self.go_unused = defaultdict(list)
        self.py_unused = defaultdict(list)
        self.stats = {
            "go_total": 0,
            "py_total": 0,
            "go_by_type": defaultdict(int),
            "py_by_type": defaultdict(int),
        }

    def analyze_go_code(self) -> None:
        """分析 Go 代码"""
        print("🔍 分析 Go 代码...")

        try:
            # 使用 staticcheck
            result = subprocess.run(
                ["staticcheck", "./cmd/...", "./pkg/...", "./internal/..."],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # 解析输出
            for line in result.stdout.split("\n"):
                if "unused" in line.lower() or "U1000" in line:
                    self._parse_go_line(line)

        except subprocess.TimeoutExpired:
            print("⚠️  Go 分析超时")
        except FileNotFoundError:
            print("⚠️  staticcheck 未安装")
        except Exception as e:
            print(f"⚠️  Go 分析失败: {e}")

    def _parse_go_line(self, line: str) -> None:
        """解析 Go 分析结果行"""
        # 格式: path/file.go:line:col: message
        match = re.match(r"([^:]+):(\d+):(\d+):\s+(.+)", line)
        if not match:
            return

        file_path, line_num, _, message = match.groups()

        # 分类
        if "function" in message.lower():
            category = "function"
        elif "variable" in message.lower():
            category = "variable"
        elif "const" in message.lower():
            category = "const"
        elif "type" in message.lower():
            category = "type"
        else:
            category = "other"

        self.go_unused[category].append({"file": file_path, "line": line_num, "message": message})

        self.stats["go_total"] += 1
        self.stats["go_by_type"][category] += 1

    def analyze_python_code(self) -> None:
        """分析 Python 代码"""
        print("🔍 分析 Python 代码...")

        try:
            # 使用 vulture
            result = subprocess.run(
                ["vulture", ".", "--min-confidence", "80", "--exclude", "venv,__pycache__,.pytest_cache"],
                cwd=PROJECT_ROOT / "algo",
                capture_output=True,
                text=True,
                timeout=60,
            )

            # 解析输出
            for line in result.stdout.split("\n"):
                if line.strip():
                    self._parse_python_line(line)

        except subprocess.TimeoutExpired:
            print("⚠️  Python 分析超时")
        except FileNotFoundError:
            print("⚠️  vulture 未安装")
        except Exception as e:
            print(f"⚠️  Python 分析失败: {e}")

    def _parse_python_line(self, line: str) -> None:
        """解析 Python 分析结果行"""
        # 格式: path/file.py:line: unused function/variable/... 'name'
        match = re.match(r"([^:]+):(\d+):\s+unused\s+(\w+)\s+(.+)", line)
        if not match:
            return

        file_path, line_num, item_type, name = match.groups()

        self.py_unused[item_type].append({"file": file_path, "line": line_num, "name": name})

        self.stats["py_total"] += 1
        self.stats["py_by_type"][item_type] += 1

    def generate_report(self, output_file: str = None) -> str:
        """生成 Markdown 报告"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = REPORT_DIR / f"unused-code-analysis-{timestamp}.md"
        else:
            output_file = Path(output_file)

        # 确保目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            self._write_header(f)
            self._write_summary(f)
            self._write_go_details(f)
            self._write_python_details(f)
            self._write_recommendations(f)

        return str(output_file)

    def _write_header(self, f) -> None:
        """写入报告头部"""
        f.write("# VoiceHelper 未使用代码详细分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

    def _write_summary(self, f) -> None:
        """写入摘要"""
        f.write("## 📊 摘要统计\n\n")

        total = self.stats["go_total"] + self.stats["py_total"]

        f.write(f"- **总计**: {total} 个未使用项\n")
        f.write(f"- **Go**: {self.stats['go_total']} 个\n")
        f.write(f"- **Python**: {self.stats['py_total']} 个\n\n")

        # Go 分类统计
        if self.stats["go_by_type"]:
            f.write("### Go 分类统计\n\n")
            for category, count in sorted(self.stats["go_by_type"].items(), key=lambda x: x[1], reverse=True):
                f.write(f"- **{category.title()}**: {count}\n")
            f.write("\n")

        # Python 分类统计
        if self.stats["py_by_type"]:
            f.write("### Python 分类统计\n\n")
            for item_type, count in sorted(self.stats["py_by_type"].items(), key=lambda x: x[1], reverse=True):
                f.write(f"- **{item_type.title()}**: {count}\n")
            f.write("\n")

        f.write("---\n\n")

    def _write_go_details(self, f) -> None:
        """写入 Go 详细信息"""
        if not self.go_unused:
            return

        f.write("## 🔵 Go 未使用代码详情\n\n")

        for category in sorted(self.go_unused.keys()):
            items = self.go_unused[category]
            f.write(f"### {category.title()} ({len(items)} 项)\n\n")

            # 按文件分组
            by_file = defaultdict(list)
            for item in items:
                by_file[item["file"]].append(item)

            for file_path in sorted(by_file.keys()):
                f.write(f"#### `{file_path}`\n\n")

                for item in sorted(by_file[file_path], key=lambda x: int(x["line"])):
                    f.write(f"- **Line {item['line']}**: {item['message']}\n")

                f.write("\n")

        f.write("---\n\n")

    def _write_python_details(self, f) -> None:
        """写入 Python 详细信息"""
        if not self.py_unused:
            return

        f.write("## 🟡 Python 未使用代码详情\n\n")

        for item_type in sorted(self.py_unused.keys()):
            items = self.py_unused[item_type]
            f.write(f"### {item_type.title()} ({len(items)} 项)\n\n")

            # 按文件分组
            by_file = defaultdict(list)
            for item in items:
                by_file[item["file"]].append(item)

            for file_path in sorted(by_file.keys()):
                f.write(f"#### `{file_path}`\n\n")

                for item in sorted(by_file[file_path], key=lambda x: int(x["line"])):
                    f.write(f"- **Line {item['line']}**: {item['name']}\n")

                f.write("\n")

        f.write("---\n\n")

    def _write_recommendations(self, f) -> None:
        """写入建议"""
        f.write("## 💡 清理建议\n\n")

        total = self.stats["go_total"] + self.stats["py_total"]

        if total == 0:
            f.write("✅ 未发现未使用代码，代码整洁度良好！\n\n")
            return

        f.write("### 优先级分类\n\n")

        f.write("#### P0 - 立即清理（安全）\n\n")
        f.write("- 未使用的导入语句\n")
        f.write("- 未使用的变量声明\n")
        f.write("- 明显的死代码\n\n")

        f.write("#### P1 - 谨慎清理（需确认）\n\n")
        f.write("- 未使用的私有函数（可能是测试辅助函数）\n")
        f.write("- 未使用的类型定义（可能用于接口约束）\n")
        f.write("- 未使用的常量（可能用于文档）\n\n")

        f.write("#### P2 - 保留（特殊情况）\n\n")
        f.write("- 公共 API 函数（即使当前未使用）\n")
        f.write("- 接口方法实现\n")
        f.write("- 实验性功能\n\n")

        f.write("### 清理步骤\n\n")
        f.write("1. **审查**: 确认代码确实未使用且可以删除\n")
        f.write("2. **备份**: 提交前确保代码已提交到 Git\n")
        f.write("3. **测试**: 删除后运行完整测试套件\n")
        f.write("4. **提交**: 使用语义化提交信息，如 `chore: remove unused functions`\n\n")

        f.write("### 自动化工具\n\n")
        f.write("- **Go**: `goimports -w .` 自动移除未使用导入\n")
        f.write("- **Python**: `ruff check --select F401 --fix .` 自动移除未使用导入\n")
        f.write("- **全局**: `./scripts/check-unused-code.sh --fix` 一键修复\n\n")

        f.write("### 预防措施\n\n")
        f.write("- 在 CI 中集成未使用代码检查\n")
        f.write("- 使用 IDE 插件实时提示未使用代码\n")
        f.write("- 定期（每月）运行此分析脚本\n\n")

        f.write("---\n\n")
        f.write("*生成工具: analyze-unused-code.py*\n")


def main():
    """主函数"""
    print("=" * 50)
    print("VoiceHelper 未使用代码分析")
    print("=" * 50)
    print()

    # 解析参数
    output_file = sys.argv[1] if len(sys.argv) > 1 else None

    # 创建分析器
    analyzer = CodeAnalyzer()

    # 分析代码
    analyzer.analyze_go_code()
    analyzer.analyze_python_code()

    # 生成报告
    print()
    print("📝 生成报告...")
    report_path = analyzer.generate_report(output_file)

    # 显示结果
    print()
    print("=" * 50)
    print("分析完成")
    print("=" * 50)
    print()
    print(f"总计: {analyzer.stats['go_total'] + analyzer.stats['py_total']} 个未使用项")
    print(f"Go: {analyzer.stats['go_total']} 个")
    print(f"Python: {analyzer.stats['py_total']} 个")
    print()
    print(f"✅ 详细报告: {report_path}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  分析被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
