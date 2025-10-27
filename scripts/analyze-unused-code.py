#!/usr/bin/env python3
"""
未使用代码分析脚本
用于生成详细的未使用代码报告
"""

import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class UnusedCodeAnalyzer:
    """未使用代码分析器"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results = {
            'go': {'unused': [], 'deadcode': [], 'unparam': []},
            'python': {'unused': [], 'deadcode': []},
            'summary': {}
        }

    def analyze_go_code(self):
        """分析 Go 代码"""
        print("🔍 正在分析 Go 代码...")

        # 运行 golangci-lint
        try:
            cmd = [
                'golangci-lint', 'run',
                '--enable=unused,deadcode,unparam,ineffassign,varcheck,structcheck',
                '--out-format=json',
                '--issues-exit-code=0',
                './...'
            ]
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    issues = data.get('Issues', [])

                    for issue in issues:
                        linter = issue.get('FromLinter', '')
                        if linter in ['unused', 'deadcode', 'unparam']:
                            self.results['go'][linter].append({
                                'file': issue.get('Pos', {}).get('Filename', ''),
                                'line': issue.get('Pos', {}).get('Line', 0),
                                'message': issue.get('Text', ''),
                                'severity': issue.get('Severity', 'warning')
                            })
                except json.JSONDecodeError:
                    print("⚠️ 无法解析 golangci-lint JSON 输出")

        except FileNotFoundError:
            print("❌ golangci-lint 未安装，跳过 Go 代码分析")
        except subprocess.TimeoutExpired:
            print("⚠️ Go 代码分析超时")
        except Exception as e:
            print(f"❌ Go 代码分析出错: {e}")

    def analyze_python_code(self):
        """分析 Python 代码"""
        print("🔍 正在分析 Python 代码...")

        # 使用 vulture 检测死代码
        try:
            cmd = [
                'vulture',
                'algo/',
                '--min-confidence', '80',
                '--sort-by-size'
            ]
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.stdout:
                # 解析 vulture 输出
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('//'):
                        match = re.match(r'(.+):(\d+):\s*(.+)', line)
                        if match:
                            self.results['python']['deadcode'].append({
                                'file': match.group(1),
                                'line': int(match.group(2)),
                                'message': match.group(3),
                                'severity': 'warning'
                            })

        except FileNotFoundError:
            print("⚠️ vulture 未安装，跳过 Python 死代码检测")
        except Exception as e:
            print(f"❌ Python 死代码分析出错: {e}")

        # 使用 ruff 检测未使用的导入和变量
        try:
            cmd = [
                'ruff', 'check',
                'algo/',
                '--select', 'F401,F841,ARG',
                '--output-format', 'json'
            ]
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.stdout:
                try:
                    issues = json.loads(result.stdout)
                    for issue in issues:
                        self.results['python']['unused'].append({
                            'file': issue.get('filename', ''),
                            'line': issue.get('location', {}).get('row', 0),
                            'message': issue.get('message', ''),
                            'code': issue.get('code', ''),
                            'severity': 'warning'
                        })
                except json.JSONDecodeError:
                    pass

        except FileNotFoundError:
            print("⚠️ ruff 未安装，跳过 Python 未使用代码检测")
        except Exception as e:
            print(f"❌ Python 未使用代码分析出错: {e}")

    def generate_summary(self):
        """生成摘要"""
        self.results['summary'] = {
            'go_unused': len(self.results['go']['unused']),
            'go_deadcode': len(self.results['go']['deadcode']),
            'go_unparam': len(self.results['go']['unparam']),
            'py_unused': len(self.results['python']['unused']),
            'py_deadcode': len(self.results['python']['deadcode']),
            'total': (
                len(self.results['go']['unused']) +
                len(self.results['go']['deadcode']) +
                len(self.results['go']['unparam']) +
                len(self.results['python']['unused']) +
                len(self.results['python']['deadcode'])
            ),
            'timestamp': datetime.now().isoformat()
        }

    def generate_report(self) -> str:
        """生成 Markdown 报告"""
        report = []

        report.append("# 未使用代码分析报告")
        report.append("")
        report.append(f"> 生成时间: {self.results['summary']['timestamp']}")
        report.append(f"> 项目路径: {self.project_root.absolute()}")
        report.append("")

        # 摘要
        report.append("## 📊 摘要")
        report.append("")
        summary = self.results['summary']
        report.append(f"- **Go 未使用代码**: {summary['go_unused']} 个")
        report.append(f"- **Go 死代码**: {summary['go_deadcode']} 个")
        report.append(f"- **Go 未使用参数**: {summary['go_unparam']} 个")
        report.append(f"- **Python 未使用代码**: {summary['py_unused']} 个")
        report.append(f"- **Python 死代码**: {summary['py_deadcode']} 个")
        report.append(f"- **总计**: {summary['total']} 个问题")
        report.append("")

        # Go 代码详情
        if any(self.results['go'].values()):
            report.append("## Go 代码分析")
            report.append("")

            for category, issues in self.results['go'].items():
                if issues:
                    report.append(f"### {category.upper()} ({len(issues)} 个)")
                    report.append("")

                    # 按文件分组
                    by_file = defaultdict(list)
                    for issue in issues:
                        by_file[issue['file']].append(issue)

                    for file, file_issues in sorted(by_file.items())[:10]:  # 只显示前10个文件
                        report.append(f"**{file}**:")
                        report.append("")
                        for issue in file_issues[:5]:  # 每个文件最多显示5个问题
                            report.append(f"- Line {issue['line']}: {issue['message']}")
                        if len(file_issues) > 5:
                            report.append(f"- ... 还有 {len(file_issues) - 5} 个问题")
                        report.append("")

                    if len(by_file) > 10:
                        report.append(f"... 还有 {len(by_file) - 10} 个文件")
                        report.append("")

        # Python 代码详情
        if any(self.results['python'].values()):
            report.append("## Python 代码分析")
            report.append("")

            for category, issues in self.results['python'].items():
                if issues:
                    report.append(f"### {category.upper()} ({len(issues)} 个)")
                    report.append("")

                    # 按文件分组
                    by_file = defaultdict(list)
                    for issue in issues:
                        by_file[issue['file']].append(issue)

                    for file, file_issues in sorted(by_file.items())[:10]:
                        report.append(f"**{file}**:")
                        report.append("")
                        for issue in file_issues[:5]:
                            msg = issue.get('message', '')
                            code = issue.get('code', '')
                            report.append(f"- Line {issue['line']}: [{code}] {msg}")
                        if len(file_issues) > 5:
                            report.append(f"- ... 还有 {len(file_issues) - 5} 个问题")
                        report.append("")

                    if len(by_file) > 10:
                        report.append(f"... 还有 {len(by_file) - 10} 个文件")
                        report.append("")

        # 建议
        report.append("## 💡 建议")
        report.append("")
        if summary['total'] == 0:
            report.append("✅ 未发现明显的未使用代码，代码质量良好！")
        else:
            report.append("### 优先级处理建议")
            report.append("")
            report.append("1. **P0 - 立即处理**")
            report.append("   - 检查并删除确认不需要的导出函数")
            report.append("   - 移除明确的死代码")
            report.append("")
            report.append("2. **P1 - 短期处理**")
            report.append("   - 检查未使用的参数，考虑重构")
            report.append("   - 确认 Wire 依赖注入使用的构造函数")
            report.append("")
            report.append("3. **P2 - 长期处理**")
            report.append("   - 审查预留功能的必要性")
            report.append("   - 更新文档说明预留代码")

        report.append("")
        report.append("---")
        report.append("")
        report.append("使用以下命令手动运行分析:")
        report.append("```bash")
        report.append("# Go 代码")
        report.append("golangci-lint run --enable=unused,deadcode,unparam")
        report.append("")
        report.append("# Python 代码")
        report.append("ruff check algo/ --select F401,F841,ARG")
        report.append("vulture algo/ --min-confidence 80")
        report.append("```")

        return "\n".join(report)

    def save_report(self, output_file: str = "unused-code-report.md"):
        """保存报告到文件"""
        report_path = self.project_root / output_file
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_report())
        print(f"✅ 报告已保存到: {report_path}")

    def run(self, output_file: str = None):
        """运行完整分析"""
        print("=" * 80)
        print("未使用代码分析工具")
        print("=" * 80)
        print()

        self.analyze_go_code()
        self.analyze_python_code()
        self.generate_summary()

        report = self.generate_report()

        if output_file:
            self.save_report(output_file)
        else:
            print(report)

        return self.results


if __name__ == '__main__':
    import sys

    output_file = sys.argv[1] if len(sys.argv) > 1 else None

    analyzer = UnusedCodeAnalyzer()
    results = analyzer.run(output_file)

    # 退出码：如果有未使用代码，返回 1（用于 CI）
    sys.exit(1 if results['summary']['total'] > 0 else 0)
