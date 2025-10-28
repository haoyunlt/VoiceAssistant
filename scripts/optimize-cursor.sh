#!/usr/bin/env bash
# ==============================================================================
# Cursor IDE Performance Optimization Script
# 优化 Cursor 性能，清理缓存和索引
# ==============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Cursor IDE Performance Optimization Script      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}\n"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ==============================================================================
# 1. Clean Python Caches
# ==============================================================================
echo -e "${YELLOW}[1/7] Cleaning Python caches...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}✓ Python caches cleaned${NC}\n"

# ==============================================================================
# 2. Clean Node.js Caches
# ==============================================================================
echo -e "${YELLOW}[2/7] Cleaning Node.js caches...${NC}"
find . -type d -name "node_modules" -prune -exec du -sh {} \; 2>/dev/null | head -5 || true
find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".turbo" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".parcel-cache" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name ".eslintcache" -delete 2>/dev/null || true
find . -type f -name ".stylelintcache" -delete 2>/dev/null || true
find . -type f -name "tsconfig.tsbuildinfo" -delete 2>/dev/null || true
find . -type f -name "*.tsbuildinfo" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Node.js caches cleaned${NC}\n"

# ==============================================================================
# 3. Clean Go Caches
# ==============================================================================
echo -e "${YELLOW}[3/7] Cleaning Go caches...${NC}"
go clean -cache -testcache -modcache 2>/dev/null || true
rm -rf bin/* 2>/dev/null || true
echo -e "${GREEN}✓ Go caches cleaned${NC}\n"

# ==============================================================================
# 4. Clean Build Artifacts
# ==============================================================================
echo -e "${YELLOW}[4/7] Cleaning build artifacts...${NC}"
find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "coverage" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.log" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Build artifacts cleaned${NC}\n"

# ==============================================================================
# 5. Clean Temporary Files
# ==============================================================================
echo -e "${YELLOW}[5/7] Cleaning temporary files...${NC}"
find . -type d -name "tmp" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "temp" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.tmp" -delete 2>/dev/null || true
find . -type f -name "*.temp" -delete 2>/dev/null || true
find . -type f -name "*.bak" -delete 2>/dev/null || true
find . -type f -name ".DS_Store" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Temporary files cleaned${NC}\n"

# ==============================================================================
# 6. Clean VSCode/Cursor Caches
# ==============================================================================
echo -e "${YELLOW}[6/7] Cleaning VSCode/Cursor caches...${NC}"
rm -rf .vscode/.browse.* 2>/dev/null || true
rm -rf .vscode/ipch 2>/dev/null || true
rm -rf .history 2>/dev/null || true
echo -e "${GREEN}✓ VSCode/Cursor caches cleaned${NC}\n"

# ==============================================================================
# 7. Project Statistics
# ==============================================================================
echo -e "${YELLOW}[7/7] Gathering project statistics...${NC}\n"

echo -e "${BLUE}Project Statistics:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Total files
TOTAL_FILES=$(find . -type f | wc -l | tr -d ' ')
echo -e "Total files: ${GREEN}$TOTAL_FILES${NC}"

# Source files by language
GO_FILES=$(find . -name "*.go" | wc -l | tr -d ' ')
PY_FILES=$(find . -name "*.py" | wc -l | tr -d ' ')
TS_FILES=$(find . -name "*.ts" -o -name "*.tsx" | wc -l | tr -d ' ')
YAML_FILES=$(find . -name "*.yaml" -o -name "*.yml" | wc -l | tr -d ' ')

echo -e "Go files: ${GREEN}$GO_FILES${NC}"
echo -e "Python files: ${GREEN}$PY_FILES${NC}"
echo -e "TypeScript/TSX files: ${GREEN}$TS_FILES${NC}"
echo -e "YAML files: ${GREEN}$YAML_FILES${NC}"

# Lines of code
echo ""
echo -e "${BLUE}Lines of Code (approximate):${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v cloc &> /dev/null; then
    cloc --quiet --exclude-dir=node_modules,vendor,.venv,venv,dist,build .
else
    echo -e "${YELLOW}Install 'cloc' for detailed code statistics: brew install cloc${NC}"
    GO_LOC=$(find . -name "*.go" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
    PY_LOC=$(find . -name "*.py" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
    echo -e "Go: ~${GREEN}$GO_LOC${NC} lines"
    echo -e "Python: ~${GREEN}$PY_LOC${NC} lines"
fi

# Disk usage
echo ""
echo -e "${BLUE}Disk Usage:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
du -sh . 2>/dev/null | awk '{print "Project size: " $1}'

# Large directories
echo ""
echo -e "${BLUE}Top 5 Largest Directories:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
du -sh */ 2>/dev/null | sort -rh | head -5

# ==============================================================================
# Recommendations
# ==============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Performance Optimization Recommendations         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}\n"

echo -e "${GREEN}✓${NC} Caches cleaned successfully"
echo -e "${GREEN}✓${NC} .cursorignore configured to exclude:"
echo "    • Dependencies (node_modules, vendor, .venv)"
echo "    • Build artifacts (dist, build, *.pyc)"
echo "    • Data directories (*_data/)"
echo "    • Generated code (*.pb.go, *_pb2.py)"
echo "    • Detailed documentation (VoiceHelper-*.md)"
echo ""
echo -e "${YELLOW}Additional Tips:${NC}"
echo "  1. Restart Cursor IDE to apply all changes"
echo "  2. Use Cmd+Shift+P > 'Reload Window' to refresh"
echo "  3. Check .vscode/settings.json for performance tuning"
echo "  4. Run this script periodically: ./scripts/optimize-cursor.sh"
echo "  5. For large node_modules, consider: rm -rf platforms/*/node_modules"
echo ""
echo -e "${GREEN}✨ Optimization complete!${NC}\n"
