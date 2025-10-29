#!/usr/bin/env python3
"""
从 retrieval-optimization-tasks.md 创建 GitHub Issues

用途:
1. 解析任务清单Markdown
2. 为每个Task创建GitHub Issue
3. 设置labels, milestones, assignees

使用:
    python scripts/create_roadmap_issues.py \
        --tasks docs/roadmap/retrieval-optimization-tasks.md \
        --project "Retrieval Optimization" \
        --dry-run

依赖:
    pip install PyGithub markdown
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    from github import Github
except ImportError:
    print("Error: PyGithub not installed. Run: pip install PyGithub")
    sys.exit(1)


class Task:
    """任务数据类"""

    def __init__(
        self,
        id: str,
        title: str,
        phase: str,
        sprint: str,
        effort_days: int,
        description: str,
        files: List[str],
        dependencies: List[str],
        acceptance: List[str],
    ):
        self.id = id
        self.title = title
        self.phase = phase
        self.sprint = sprint
        self.effort_days = effort_days
        self.description = description
        self.files = files
        self.dependencies = dependencies
        self.acceptance = acceptance

    def to_github_issue(self) -> Dict:
        """转换为GitHub Issue格式"""
        body = f"""## 描述
{self.description}

## 核心文件
{chr(10).join(f"- `{f}`" for f in self.files)}

## 依赖
{self._format_dependencies()}

## 验收标准
{chr(10).join(f"- [ ] {a}" for a in self.acceptance)}

## 元信息
- **Phase**: {self.phase}
- **Sprint**: {self.sprint}
- **工作量**: {self.effort_days} 天
- **任务ID**: {self.id}

---
_由 create_roadmap_issues.py 自动生成_
"""

        return {
            "title": self.title,
            "body": body,
            "labels": self._generate_labels(),
        }

    def _format_dependencies(self) -> str:
        """格式化依赖"""
        if not self.dependencies or self.dependencies == ["无"]:
            return "无"
        return "\n".join(f"- {d}" for d in self.dependencies)

    def _generate_labels(self) -> List[str]:
        """生成labels"""
        labels = []

        # Phase label
        labels.append(f"phase/{self.phase.lower()}")

        # Type label
        if "优化" in self.title or "增强" in self.title:
            labels.append("type/enhancement")
        elif "新建" in self.description or "实现" in self.title:
            labels.append("type/feature")
        elif "重构" in self.title:
            labels.append("type/refactor")
        else:
            labels.append("type/feature")

        # Area label
        if "检索" in self.title or "Retrieval" in self.title:
            labels.append("area/retrieval")
        elif "评测" in self.title or "Evaluation" in self.title:
            labels.append("area/eval")
        elif "缓存" in self.title or "Cache" in self.title:
            labels.append("area/cache")
        elif "重排" in self.title or "Rerank" in self.title:
            labels.append("area/rerank")

        return labels


def parse_tasks_markdown(md_path: Path) -> List[Task]:
    """解析任务清单Markdown"""
    print(f"解析任务清单: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    tasks = []

    # 正则匹配任务块
    # 例如: ### Task 1.1: Query Expansion & Rewriting
    task_pattern = re.compile(
        r"### (Task \d+\.\d+): (.+?)\n"
        r"- \*\*状态\*\*: (.+?)\n"
        r"- \*\*负责人\*\*: (.+?)\n"
        r"- \*\*Sprint\*\*: (.+?)\n"
        r"- \*\*工作量\*\*: (\d+) 天\n"
        r"- \*\*PR\*\*: (.+?)\n"
        r"- \*\*核心文件\*\*:\n((?:  - `.+?`\n)+)"
        r"- \*\*依赖\*\*: (.+?)\n"
        r"- \*\*验收\*\*:\n((?:  - \[ \] .+?\n)+)",
        re.MULTILINE | re.DOTALL,
    )

    matches = task_pattern.findall(content)

    for match in matches:
        task_id, title, status, assignee, sprint, effort, pr, files_block, deps, acceptance_block = match

        # 提取Phase
        phase = sprint.split()[0]  # "Sprint 1" -> "Sprint"
        if "1" in sprint or "2" in sprint or "3" in sprint:
            phase = "Phase 1"
        elif "4" in sprint or "5" in sprint or "6" in sprint:
            phase = "Phase 2"
        elif "7" in sprint or "8" in sprint:
            phase = "Phase 3"
        elif "9" in sprint or "10" in sprint or "11" in sprint or "12" in sprint:
            phase = "Phase 4"
        else:
            phase = "Phase 5"

        # 解析文件列表
        files = re.findall(r"`(.+?)`", files_block)

        # 解析验收标准
        acceptance = re.findall(r"- \[ \] (.+)", acceptance_block)

        task = Task(
            id=task_id,
            title=title,
            phase=phase,
            sprint=sprint.strip(),
            effort_days=int(effort),
            description=f"{title} (详见任务文档)",
            files=files,
            dependencies=[deps.strip()],
            acceptance=acceptance,
        )

        tasks.append(task)

    print(f"✓ 解析到 {len(tasks)} 个任务")
    return tasks


def create_issues(
    tasks: List[Task],
    repo_name: str,
    token: str,
    project_name: Optional[str] = None,
    dry_run: bool = False,
):
    """创建GitHub Issues"""

    if dry_run:
        print("\n🔍 Dry-run 模式: 仅预览，不实际创建Issues\n")
        for task in tasks:
            issue_data = task.to_github_issue()
            print(f"{'=' * 60}")
            print(f"Task: {task.id}")
            print(f"Title: {issue_data['title']}")
            print(f"Labels: {', '.join(issue_data['labels'])}")
            print(f"Body:\n{issue_data['body'][:200]}...")
            print()
        return

    # 连接GitHub
    print(f"\n📡 连接GitHub仓库: {repo_name}")
    gh = Github(token)
    repo = gh.get_repo(repo_name)

    created_count = 0
    skipped_count = 0

    for task in tasks:
        issue_data = task.to_github_issue()

        # 检查是否已存在
        existing = None
        for issue in repo.get_issues(state="all"):
            if task.id in issue.title or task.title in issue.title:
                existing = issue
                break

        if existing:
            print(f"⏭️  跳过 {task.id}: 已存在 #{existing.number}")
            skipped_count += 1
            continue

        # 创建Issue
        try:
            issue = repo.create_issue(
                title=f"[{task.id}] {issue_data['title']}",
                body=issue_data["body"],
                labels=issue_data["labels"],
            )
            print(f"✅ 创建 {task.id}: #{issue.number} - {issue_data['title']}")
            created_count += 1
        except Exception as e:
            print(f"❌ 创建失败 {task.id}: {e}")

    print(f"\n{'=' * 60}")
    print(f"✅ 创建: {created_count}")
    print(f"⏭️  跳过: {skipped_count}")
    print(f"📊 总计: {len(tasks)}")


def main():
    parser = argparse.ArgumentParser(description="从Markdown创建GitHub Issues")
    parser.add_argument("--tasks", default="docs/roadmap/retrieval-optimization-tasks.md", help="任务清单Markdown路径")
    parser.add_argument("--repo", default="your-org/voicehelper", help="GitHub仓库 (格式: owner/repo)")
    parser.add_argument("--token", help="GitHub Personal Access Token (或设置环境变量 GITHUB_TOKEN)")
    parser.add_argument("--project", help="GitHub Project名称（可选）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际创建")

    args = parser.parse_args()

    # 获取Token
    import os

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token and not args.dry_run:
        print("Error: 需要提供 --token 或设置环境变量 GITHUB_TOKEN")
        sys.exit(1)

    # 解析任务
    tasks_path = Path(args.tasks)
    if not tasks_path.exists():
        print(f"Error: 任务文件不存在: {tasks_path}")
        sys.exit(1)

    tasks = parse_tasks_markdown(tasks_path)

    # 创建Issues
    create_issues(
        tasks=tasks,
        repo_name=args.repo,
        token=token,
        project_name=args.project,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
