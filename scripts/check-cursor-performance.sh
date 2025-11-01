#!/usr/bin/env bash
# ==============================================================================
# Cursor Performance Check Script
# 快速检查 Cursor 性能相关指标
# ==============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Cursor Performance Check                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}\n"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ==============================================================================
# 1. Check Cache Sizes
# ==============================================================================
echo -e "${CYAN}[1/5] Checking cache sizes...${NC}"

check_cache() {
  local path=$1
  local name=$2
  if [ -d "$path" ]; then
    size=$(du -sh "$path" 2>/dev/null | awk '{print $1}')
    count=$(find "$path" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo -e "  ${name}: ${YELLOW}${size}${NC} (${count} files)"

    # Warning if too large
    size_bytes=$(du -s "$path" 2>/dev/null | awk '{print $1}')
    if [ "$size_bytes" -gt 100000 ]; then  # > ~100MB
      echo -e "    ${RED}⚠️  Large cache detected! Consider running: ./scripts/optimize-cursor.sh${NC}"
    fi
  else
    echo -e "  ${name}: ${GREEN}✓ Clean${NC}"
  fi
}

# Python caches
pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
pyc_count=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
if [ "$pycache_count" -gt 0 ] || [ "$pyc_count" -gt 0 ]; then
  echo -e "  Python cache: ${YELLOW}$pycache_count dirs, $pyc_count files${NC}"
  if [ "$pycache_count" -gt 100 ]; then
    echo -e "    ${RED}⚠️  Run: find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null${NC}"
  fi
else
  echo -e "  Python cache: ${GREEN}✓ Clean${NC}"
fi

# Node.js caches
node_modules_count=$(find . -type d -name "node_modules" 2>/dev/null | wc -l | tr -d ' ')
if [ "$node_modules_count" -gt 0 ]; then
  node_modules_size=$(find . -type d -name "node_modules" -prune -exec du -sh {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
  echo -e "  node_modules: ${YELLOW}$node_modules_count dirs${NC}"
else
  echo -e "  node_modules: ${GREEN}✓ Clean or ignored${NC}"
fi

# Go caches
if command -v go &> /dev/null; then
  go_cache_size=$(du -sh ~/Library/Caches/go-build 2>/dev/null | awk '{print $1}' || echo "0")
  echo -e "  Go build cache: ${YELLOW}${go_cache_size}${NC}"
fi

echo ""

# ==============================================================================
# 2. Check Cursor Process
# ==============================================================================
echo -e "${CYAN}[2/5] Checking Cursor processes...${NC}"

if pgrep -f "Cursor" > /dev/null; then
  cursor_count=$(pgrep -f "Cursor" | wc -l | tr -d ' ')
  echo -e "  ${GREEN}Cursor is running${NC} (${cursor_count} processes)"

  # CPU usage
  cpu_usage=$(ps aux | grep -i "[C]ursor" | awk '{sum+=$3} END {print sum}')
  if (( $(echo "$cpu_usage > 50" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  CPU usage: ${RED}${cpu_usage}%${NC} (High!)"
  elif (( $(echo "$cpu_usage > 20" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  CPU usage: ${YELLOW}${cpu_usage}%${NC}"
  else
    echo -e "  CPU usage: ${GREEN}${cpu_usage}%${NC}"
  fi

  # Memory usage
  mem_usage=$(ps aux | grep -i "[C]ursor" | awk '{sum+=$6} END {print sum/1024}')
  if (( $(echo "$mem_usage > 4096" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  Memory usage: ${RED}~${mem_usage} MB${NC} (High!)"
  elif (( $(echo "$mem_usage > 2048" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  Memory usage: ${YELLOW}~${mem_usage} MB${NC}"
  else
    echo -e "  Memory usage: ${GREEN}~${mem_usage} MB${NC}"
  fi
else
  echo -e "  ${YELLOW}Cursor is not running${NC}"
fi

echo ""

# ==============================================================================
# 3. Check Project Size
# ==============================================================================
echo -e "${CYAN}[3/5] Checking project size...${NC}"

# Total size
total_size=$(du -sh . 2>/dev/null | awk '{print $1}')
echo -e "  Total size: ${YELLOW}${total_size}${NC}"

# File counts
go_count=$(find . -name "*.go" 2>/dev/null | wc -l | tr -d ' ')
py_count=$(find . -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
ts_count=$(find . -name "*.ts" -o -name "*.tsx" 2>/dev/null | wc -l | tr -d ' ')

echo -e "  Go files: ${GREEN}${go_count}${NC}"
echo -e "  Python files: ${GREEN}${py_count}${NC}"
echo -e "  TypeScript files: ${GREEN}${ts_count}${NC}"

if [ "$py_count" -gt 1000 ]; then
  echo -e "    ${YELLOW}ℹ️  Large Python project detected. Ensure 'diagnosticMode: openFilesOnly' is set.${NC}"
fi

echo ""

# ==============================================================================
# 4. Check Large Files
# ==============================================================================
echo -e "${CYAN}[4/5] Checking large files (> 10MB)...${NC}"

large_files=$(find . -type f -size +10M 2>/dev/null | wc -l | tr -d ' ')
if [ "$large_files" -gt 0 ]; then
  echo -e "  Found ${YELLOW}${large_files}${NC} large files:"
  find . -type f -size +10M -exec ls -lh {} \; 2>/dev/null | awk '{print "    " $9 " (" $5 ")"}' | head -5
  if [ "$large_files" -gt 5 ]; then
    echo -e "    ${YELLOW}... and $(($large_files - 5)) more${NC}"
  fi
  echo -e "    ${YELLOW}ℹ️  Consider adding these to .cursorignore if not needed${NC}"
else
  echo -e "  ${GREEN}✓ No large files found${NC}"
fi

echo ""

# ==============================================================================
# 5. Check Configuration
# ==============================================================================
echo -e "${CYAN}[5/5] Checking configuration files...${NC}"

check_config() {
  local file=$1
  local name=$2
  if [ -f "$file" ]; then
    lines=$(wc -l < "$file" | tr -d ' ')
    echo -e "  ${name}: ${GREEN}✓ Exists${NC} (${lines} lines)"
  else
    echo -e "  ${name}: ${RED}✗ Missing${NC}"
  fi
}

check_config ".cursorignore" ".cursorignore"
check_config ".vscode/settings.json" ".vscode/settings.json"
check_config "scripts/optimize-cursor.sh" "Optimization script"

# Check key settings
if [ -f ".vscode/settings.json" ]; then
  if grep -q '"openFilesOnly"' .vscode/settings.json 2>/dev/null; then
    echo -e "  Python analysis mode: ${GREEN}✓ openFilesOnly${NC} (Optimized)"
  else
    echo -e "  Python analysis mode: ${YELLOW}⚠️  Not set to openFilesOnly${NC}"
  fi

  if grep -q '"workbench.editor.limit.enabled": true' .vscode/settings.json 2>/dev/null; then
    limit=$(grep "workbench.editor.limit.value" .vscode/settings.json | grep -o '[0-9]\+')
    echo -e "  Editor limit: ${GREEN}✓ Enabled${NC} (max ${limit} editors)"
  else
    echo -e "  Editor limit: ${YELLOW}⚠️  Not enabled${NC}"
  fi
fi

echo ""

# ==============================================================================
# Summary & Recommendations
# ==============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Recommendations                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}\n"

# Collect issues
issues=0

# Check if caches are large
if [ "$pycache_count" -gt 100 ]; then
  echo -e "${YELLOW}• Clean Python caches: ./scripts/optimize-cursor.sh${NC}"
  ((issues++))
fi

# Check if Cursor is using too much CPU
if pgrep -f "Cursor" > /dev/null; then
  cpu_usage=$(ps aux | grep -i "[C]ursor" | awk '{sum+=$3} END {print sum}')
  if (( $(echo "$cpu_usage > 50" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "${YELLOW}• High CPU usage detected. Try restarting Cursor (Cmd+Q)${NC}"
    ((issues++))
  fi
fi

# Check if config files exist
if [ ! -f ".cursorignore" ]; then
  echo -e "${RED}• Create .cursorignore file to exclude unnecessary files${NC}"
  ((issues++))
fi

# Summary
if [ "$issues" -eq 0 ]; then
  echo -e "${GREEN}✨ All checks passed! Your Cursor is well optimized.${NC}\n"
else
  echo -e "${YELLOW}⚠️  Found ${issues} optimization opportunity(ies).${NC}\n"
fi

echo -e "${CYAN}Quick Commands:${NC}"
echo -e "  ${GREEN}./scripts/optimize-cursor.sh${NC}           - Clean all caches"
echo -e "  ${GREEN}Cmd + Q${NC}                                 - Restart Cursor"
echo -e "  ${GREEN}Cmd + Shift + P > 'Reload Window'${NC}      - Reload window"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo -e "  ${GREEN}CURSOR_PERFORMANCE_OPTIMIZATION.md${NC}     - Full optimization guide"
echo -e "  ${GREEN}.vscode/PERFORMANCE_QUICK_REFERENCE.md${NC} - Quick reference"
echo ""

echo -e "${GREEN}✓ Performance check complete!${NC}\n"
