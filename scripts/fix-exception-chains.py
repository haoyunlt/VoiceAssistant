#!/usr/bin/env python3
"""
批量修复异常链缺失问题 (B904)
将 except Exception: raise XXX 改为 except Exception as err: raise XXX from err
"""

import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGO_DIR = PROJECT_ROOT / "algo"

print("🔧 批量修复异常链缺失问题...")

# 获取所有需要修复的文件
result = subprocess.run(
    [
        "/usr/local/bin/python3.11",
        "-m",
        "ruff",
        "check",
        str(ALGO_DIR),
        "--select",
        "B904",
        "--output-format=concise",
    ],
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    print("✅ 没有发现异常链缺失问题！")
    exit(0)

# 解析输出，获取文件和行号
errors = []
for line in result.stdout.strip().split("\n"):
    if not line:
        continue
    # 格式: algo/service/file.py:123:45: B904 ...
    match = re.match(r"^(.+?):(\d+):\d+:", line)
    if match:
        file_path = PROJECT_ROOT / match.group(1)
        line_num = int(match.group(2))
        errors.append((file_path, line_num))

print(f"发现 {len(errors)} 个异常链缺失问题")

# 按文件分组
files_to_fix = {}
for file_path, line_num in errors:
    if file_path not in files_to_fix:
        files_to_fix[file_path] = []
    files_to_fix[file_path].append(line_num)

# 逐文件修复
fixed_count = 0
for file_path, line_numbers in files_to_fix.items():
    print(f"\n处理文件: {file_path.relative_to(PROJECT_ROOT)}")

    content = file_path.read_text()
    lines = content.split("\n")

    # 从后向前处理，避免行号变化
    for line_num in sorted(line_numbers, reverse=True):
        idx = line_num - 1  # 转换为0索引

        if idx >= len(lines):
            continue

        line = lines[idx]

        # 检查是否是 raise 语句
        if "raise" not in line:
            continue

        # 向上查找对应的 except
        except_idx = None
        for i in range(idx - 1, max(0, idx - 10), -1):
            if "except" in lines[i]:
                except_idx = i
                break

        if except_idx is None:
            continue

        except_line = lines[except_idx]

        # 检查是否已经有 as xxx
        if " as " in except_line:
            # 已经有异常变量，只需要添加 from
            match = re.search(r"as\s+(\w+)", except_line)
            if match:
                var_name = match.group(1)
                if f"from {var_name}" not in line:
                    # 在 raise 语句末尾添加 from
                    lines[idx] = re.sub(r"(raise\s+.+?)(\s*)$", rf"\1 from {var_name}\2", line)
                    fixed_count += 1
        else:
            # 需要添加 as err 并修改 raise
            # 提取异常类型
            match = re.search(r"except\s+(\w+(?:\.\w+)*)", except_line)
            if match:
                # 添加 as err
                lines[except_idx] = except_line.replace(match.group(0), f"{match.group(0)} as err")
                # 在 raise 语句添加 from err
                if "from err" not in line and "from None" not in line:
                    lines[idx] = re.sub(r"(raise\s+.+?)(\s*)$", r"\1 from err\2", line)
                    fixed_count += 1

    # 写回文件
    file_path.write_text("\n".join(lines))
    print(f"  ✅ 修复了 {len([ln for ln in line_numbers if ln <= len(lines)])} 处")

print(f"\n✨ 总共修复了约 {fixed_count} 个异常链问题！")
print("\n建议运行以下命令验证：")
print("  /usr/local/bin/python3.11 -m ruff check algo/ --select B904")
