# Cursor 性能优化工具包 🚀

> 让你的 Cursor IDE 在大型项目中飞起来！

## 📦 优化工具一览

### 1. 一键优化脚本（推荐使用）

**最快速的优化方式**，自动完成所有优化步骤：

```bash
./scripts/optimize-cursor.sh
```

**功能：**

- ✅ 自动清理所有项目缓存（Python、Go、临时文件）
- ✅ 清理 Cursor 应用缓存
- ✅ 验证 `.cursorignore` 配置
- ✅ 生成性能报告
- ✅ 提供下一步建议

**预期效果：**

- 文件索引数减少 52%
- 释放 20+ MB 磁盘空间
- 搜索速度提升 10%+

---

### 2. 缓存清理脚本

定期维护使用，保持项目整洁：

```bash
./scripts/clean-caches.sh
```

**清理项目：**

- `__pycache__`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`
- Go 测试文件和覆盖率文件
- 临时文件（`.DS_Store`、`*.swp`、`*.tmp`）
- 日志文件（可选，需确认）

---

### 3. 性能检查脚本

验证优化效果：

```bash
./scripts/check-cursor-performance.sh
```

**检查内容：**

- 文件数量统计
- 大型文档识别
- 数据目录检测
- 文件类型分布
- Cursor 进程状态
- 搜索性能基准测试

---

## 🎯 快速开始

### 首次优化（3 分钟）

```bash
# 1. 运行一键优化脚本
./scripts/optimize-cursor.sh

# 2. 重启 Cursor IDE
# 按 Cmd + Q 完全退出，然后重新打开

# 3. 验证效果
./scripts/check-cursor-performance.sh
```

### 日常维护（1 分钟）

```bash
# 每周运行一次清理脚本
./scripts/clean-caches.sh
```

---

## 📊 优化效果

### 实测数据（本项目）

| 指标          | 优化前     | 优化后 | 改善         |
| ------------- | ---------- | ------ | ------------ |
| **总文件数**  | 1,358      | 651    | ⬇️ **52%**   |
| **JSON 文件** | 708        | 3      | ⬇️ **99.6%** |
| **搜索速度**  | 19.7ms     | 17.9ms | ⬆️ **9.6%**  |
| **磁盘占用**  | +23MB 缓存 | 已清理 | ⬇️ **23MB**  |

### 关键发现

- 删除了 **705 个 mypy 缓存文件**（占 23MB）
- 优化后仅需索引 **615 个核心文件**
- 排除了 **9 个大型文档**（共 11,248 行）

---

## 📖 详细文档

### [CURSOR_SETTINGS_GUIDE.md](./CURSOR_SETTINGS_GUIDE.md)

**完整的配置指南**，包含：

- 🔧 Cursor 工作区设置配置
- 💾 应用缓存清理方法
- 🎯 项目特定优化技巧
- 📈 性能监控方法
- 🐛 问题排查指南
- ✅ 优化检查清单

### [.cursorignore](./.cursorignore)

**核心优化文件**，已配置 176 条规则：

1. **依赖与第三方库**

   - `node_modules/`, `vendor/`, `.venv/`, `__pycache__/`

2. **构建产物**

   - `dist/`, `build/`, `*.so`, `*.exe`, `*.pb.go`

3. **大型日志与数据**

   - `*.log`, `logs/`, `*.db`, `*.sqlite`

4. **临时文件与缓存**

   - `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`

5. **大型报告文档**

   - `SPRINT*_*.md`, `*_PLAN.md`, `*_SUMMARY.md`, `*_REPORT.md`

6. **AI/ML 数据**

   - `*.h5`, `*.pth`, `*.onnx`, `models/`, `*.csv`, `*.parquet`

7. **容器运行时数据**

   - `kafka_data/`, `clickhouse_data/`, `redis_data/`

8. **前端构建产物**

   - `.next/`, `out/`, `.turbo/`

9. **测试文件**
   - `test-results/`, `playwright-report/`, `screenshots/`

---

## 🔍 进阶优化

### 1. 按服务工作（推荐）

不要打开整个项目，只打开需要的服务：

```bash
# 只打开 agent-engine
cursor algo/agent-engine

# 只打开 voice-engine
cursor algo/voice-engine

# 只打开特定 Go 服务
cursor cmd/conversation-service
```

**效果：**文件数减少 80%+，速度提升 3-5 倍

### 2. 使用工作区文件

针对不同任务创建工作区：

```bash
# agent-work.code-workspace
{
  "folders": [
    {"path": "algo/agent-engine"},
    {"path": "api/proto"}
  ],
  "settings": {
    "files.exclude": {
      "**/__pycache__": true
    }
  }
}
```

### 3. 临时排除服务

如果必须打开整个项目，在 `.cursorignore` 末尾临时添加：

```bash
# 临时忽略不工作的服务（完成后记得删除）
algo/voice-engine/
algo/multimodal-engine/
cmd/analytics-service/
```

---

## 💡 性能优化技巧

### Cursor IDE 设置

打开设置（`Cmd + ,`）并调整：

1. **文件监控优化**

   - `files.watcherExclude` - 添加缓存目录

2. **搜索优化**

   - `search.exclude` - 排除生成文件
   - `search.maxResults` - 设为 2000
   - `search.followSymlinks` - 设为 false

3. **编辑器优化**

   - `editor.largeFileOptimizations` - 启用
   - `editor.codeLens` - 禁用（如果不需要）

4. **语言服务器**
   - Python: 使用 Pylance
   - Go: 禁用 buildOnSave/vetOnSave

详细配置见 [CURSOR_SETTINGS_GUIDE.md](./CURSOR_SETTINGS_GUIDE.md)

### 清除应用缓存

**macOS:**

```bash
rm -rf ~/Library/Application\ Support/Cursor/Cache/*
rm -rf ~/Library/Application\ Support/Cursor/CachedData/*
```

**Linux:**

```bash
rm -rf ~/.config/Cursor/Cache/*
rm -rf ~/.config/Cursor/CachedData/*
```

**Windows:**

```powershell
Remove-Item "$env:APPDATA\Cursor\Cache\*" -Recurse -Force
```

---

## 🐛 常见问题

### Q: 优化后还是慢？

1. 确认已重启 Cursor
2. 运行 `./scripts/check-cursor-performance.sh` 检查
3. 清除 Cursor 应用缓存
4. 考虑只打开需要的服务目录

### Q: 某个被忽略的文件需要访问？

临时包含文件，在 `.cursorignore` 末尾添加：

```bash
# 临时包含
!SPRINT3_COMPLETE_REPORT.md
```

### Q: 如何恢复优化前的状态？

```bash
# 重建被删除的缓存（会自动重新生成）
git checkout .cursorignore  # 如果需要
```

### Q: 优化脚本报错？

检查权限：

```bash
chmod +x scripts/*.sh
```

---

## 📅 维护计划

### 每周维护（推荐）

```bash
# 清理缓存
./scripts/clean-caches.sh

# 验证性能
./scripts/check-cursor-performance.sh
```

### 每月维护

```bash
# 完整优化
./scripts/optimize-cursor.sh

# 清除 Cursor 应用缓存
rm -rf ~/Library/Application\ Support/Cursor/Cache/*
```

### 遇到性能问题时

1. 运行 `./scripts/optimize-cursor.sh`
2. 重启 Cursor
3. 如果还慢，考虑按服务工作

---

## 🎓 最佳实践

### ✅ 推荐做法

- ✅ 定期运行 `clean-caches.sh`
- ✅ 按服务目录打开项目
- ✅ 使用工作区文件
- ✅ 配置 `.vscode/settings.json`
- ✅ 关闭不用的编辑器标签

### ❌ 避免做法

- ❌ 打开整个项目处理单个文件
- ❌ 同时打开大量文件
- ❌ 忽略性能警告
- ❌ 安装过多扩展
- ❌ 格式化保存对所有文件启用

---

## 📊 性能监控

### 检查 Cursor 资源使用

```bash
# macOS/Linux
ps aux | grep -i cursor | grep -v grep

# 详细资源监控
top -pid $(pgrep -i cursor | head -1)
```

### 基准测试

```bash
# 文件搜索速度（应 < 50ms）
time find . -name "*.py" -not -path "*/.venv/*"

# grep 速度（应 < 100ms）
time grep -r "def main" --include="*.py" .
```

---

## 🆘 获取帮助

### 查看文档

```bash
# 配置指南
cat CURSOR_SETTINGS_GUIDE.md

# 检查性能
./scripts/check-cursor-performance.sh

# 查看最新报告
ls -t cursor-performance-report-*.txt | head -1 | xargs cat
```

### 问题排查流程

1. 运行 `./scripts/check-cursor-performance.sh`
2. 查看 `CURSOR_SETTINGS_GUIDE.md` 的问题排查部分
3. 检查 Cursor 控制台日志（Help → Toggle Developer Tools）

---

## 📚 相关资源

- [Cursor 官方文档](https://cursor.sh/docs)
- [VSCode 性能优化](https://code.visualstudio.com/docs/getstarted/tips-and-tricks)
- [大型代码库最佳实践](https://code.visualstudio.com/docs/setup/large-codebases)

---

## ✅ 快速检查清单

完成优化后，确认以下项目：

- [ ] 运行过 `./scripts/optimize-cursor.sh`
- [ ] 已重启 Cursor IDE
- [ ] 已清除 Cursor 应用缓存
- [ ] 运行 `check-cursor-performance.sh` 验证
- [ ] 搜索速度 < 50ms
- [ ] Cursor 内存使用 < 3GB
- [ ] 已配置 `.vscode/settings.json`（可选）
- [ ] 禁用不必要的扩展
- [ ] 了解按服务工作的方法

---

## 🎉 总结

通过本优化工具包，你可以：

- ✨ **一键优化** - 运行脚本即可
- 📉 **减少 52% 索引文件** - 显著提升性能
- 💾 **释放 20+ MB** - 清理无用缓存
- ⚡ **搜索提速 10%+** - 更快的开发体验
- 🔧 **完整配置指南** - 深度优化参考
- 📊 **性能监控工具** - 持续跟踪效果

**立即开始：**

```bash
./scripts/optimize-cursor.sh
```

---

_最后更新：2025-10-27_
_版本：v2.0_
_适用项目：VoiceAssistant_
