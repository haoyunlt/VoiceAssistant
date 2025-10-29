#!/usr/bin/env bash
#
# Agent Engine 优化 - 批量创建 GitHub Issues
#
# 使用方式:
#   ./create-agent-issues.sh [--dry-run] [--iteration N]
#
# 示例:
#   ./create-agent-issues.sh --dry-run              # 预览但不创建
#   ./create-agent-issues.sh --iteration 1          # 只创建迭代 1 的 Issues
#   ./create-agent-issues.sh                        # 创建所有 Issues

set -euo pipefail

# 配置
REPO="${GITHUB_REPO:-your-org/voicehelper}"  # 从环境变量读取或使用默认值
DRY_RUN=false
ITERATION=""

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --iteration)
      ITERATION="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--iteration N] [--repo OWNER/REPO]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# 检查 gh CLI
if ! command -v gh &> /dev/null; then
    echo "Error: gh CLI not found. Please install it:"
    echo "  macOS: brew install gh"
    echo "  Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    exit 1
fi

# 检查认证
if ! gh auth status &> /dev/null; then
    echo "Error: gh CLI not authenticated. Please run:"
    echo "  gh auth login"
    exit 1
fi

echo "======================================"
echo "Agent Engine Issues Creator"
echo "======================================"
echo "Repository: $REPO"
echo "Dry Run: $DRY_RUN"
echo "Iteration Filter: ${ITERATION:-all}"
echo "======================================"
echo

# 定义 Issues（格式: title|labels|body|iteration）
declare -a issues=(
  # 迭代 1
  "feat(observability): implement agent execution tracing|enhancement,area/observability,stage/iteration-1|Implement complete agent execution tracing system. See docs/roadmap/agent-issues-template.md Issue #1 for details.|1"

  "feat(eval): build agent evaluation framework|enhancement,area/testing,stage/iteration-1|Build automated evaluation framework with benchmark datasets. See docs/roadmap/agent-issues-template.md Issue #2 for details.|1"

  "feat(cost): implement granular cost tracking and budget control|enhancement,area/cost,stage/iteration-1|Implement request-level token metering, budget alerts, and fallback strategies. See docs/roadmap/agent-issues-template.md Issue #3 for details.|1"

  "feat(dashboard): create agent performance dashboards|enhancement,area/observability,stage/iteration-1|Create 3 Grafana dashboards for agent performance, cost, and tracing. See docs/roadmap/agent-issues-template.md Issue #4 for details.|1"

  # 迭代 2
  "feat(self-rag): implement retrieval quality assessment|enhancement,area/rag,stage/iteration-2|Implement retrieval quality critic and query rewriting. See docs/roadmap/agent-issues-template.md Issue #5 for details.|2"

  "feat(self-rag): adaptive retrieval strategy|enhancement,area/rag,stage/iteration-2|Implement adaptive retrieval strategy based on query type. See docs/roadmap/agent-issues-template.md Issue #6 for details.|2"

  "feat(memory): memory compression and intelligent forgetting|enhancement,area/memory,stage/iteration-2|Implement memory compression and intelligent forgetting mechanisms. See docs/roadmap/agent-issues-template.md Issue #7 for details.|2"

  "feat(context): context window management|enhancement,area/memory,stage/iteration-2|Implement MCP-style context window management with priority-based truncation.|2"

  # 迭代 3
  "feat(multi-agent): implement debate mode|enhancement,area/multi-agent,stage/iteration-3|Implement debate mode for multi-agent collaboration. See docs/roadmap/agent-issues-template.md Issue #8 for details.|3"

  "feat(multi-agent): voting and consensus mechanism|enhancement,area/multi-agent,stage/iteration-3|Implement voting and consensus mechanism for multi-agent decision making.|3"

  "feat(multi-agent): message bus and shared blackboard|enhancement,area/multi-agent,stage/iteration-3|Implement Redis-based message bus and shared blackboard. See docs/roadmap/agent-issues-template.md Issue #9 for details.|3"

  "feat(multi-agent): agent registry and discovery|enhancement,area/multi-agent,stage/iteration-3|Implement agent registry and capability-based discovery.|3"

  # 迭代 4
  "feat(hitl): implement human-in-the-loop mechanism|enhancement,area/hitl,stage/iteration-4|Implement human inquiry and approval workflow. See docs/roadmap/agent-issues-template.md Issue #10 for details.|4"

  "feat(tools): enhance tool marketplace|enhancement,area/tools,stage/iteration-4|Enhance tool marketplace with semantic search, versioning, and dependency management. See docs/roadmap/agent-issues-template.md Issue #11 for details.|4"

  "feat(tools): tool chain orchestration|enhancement,area/tools,stage/iteration-4|Implement declarative tool chain orchestration.|4"

  "feat(executor): implement tree of thoughts executor|enhancement,area/executor,stage/iteration-4|Implement Tree of Thoughts executor. See docs/roadmap/agent-issues-template.md Issue #12 for details.|4"

  "feat(executor): self-discover executor|enhancement,area/executor,stage/iteration-4|Implement Self-Discover executor for dynamic reasoning structure selection.|4"

  "feat(core): checkpoint and resume|enhancement,area/core,stage/iteration-4|Implement checkpoint and resume mechanism for long-running tasks.|4"
)

# 创建 Issue 函数
create_issue() {
  local title="$1"
  local labels="$2"
  local body="$3"
  local iteration="$4"

  # 过滤迭代
  if [[ -n "$ITERATION" && "$iteration" != "$ITERATION" ]]; then
    return
  fi

  echo "----------------------------------------"
  echo "Title: $title"
  echo "Labels: $labels"
  echo "Iteration: $iteration"
  echo

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would create issue"
    echo
    return
  fi

  # 创建 Issue
  if gh issue create \
      --repo "$REPO" \
      --title "$title" \
      --label "$labels" \
      --body "$body" &> /dev/null; then
    echo "✅ Created successfully"
  else
    echo "❌ Failed to create"
  fi
  echo
}

# 计数器
total=0
filtered=0

# 遍历创建
for issue in "${issues[@]}"; do
  IFS='|' read -r title labels body iteration <<< "$issue"

  total=$((total + 1))

  # 过滤迭代
  if [[ -n "$ITERATION" && "$iteration" != "$ITERATION" ]]; then
    continue
  fi

  filtered=$((filtered + 1))
  create_issue "$title" "$labels" "$body" "$iteration"

  # 避免 API 限流
  sleep 0.5
done

echo "======================================"
echo "Summary"
echo "======================================"
echo "Total issues: $total"
echo "Filtered issues: $filtered"
if [[ "$DRY_RUN" == "true" ]]; then
  echo "Mode: DRY RUN (no issues created)"
else
  echo "Mode: LIVE (issues created)"
fi
echo "======================================"

if [[ "$DRY_RUN" == "true" ]]; then
  echo
  echo "To create issues for real, run:"
  echo "  $0 --repo $REPO"
fi
