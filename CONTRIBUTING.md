# 贡献指南

感谢您对 VoiceHelper 项目的兴趣！本文档将帮助您了解如何为项目做出贡献。

---

## 📋 目录

1. [行为准则](#行为准则)
2. [如何贡献](#如何贡献)
3. [开发流程](#开发流程)
4. [代码规范](#代码规范)
5. [提交规范](#提交规范)
6. [Pull Request 流程](#pull-request-流程)
7. [测试要求](#测试要求)

---

## 行为准则

我们致力于为所有贡献者提供一个友好、安全和包容的环境。请遵循以下准则：

- 尊重他人观点和经验
- 接受建设性的批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

---

## 如何贡献

### 报告 Bug

如果您发现了 Bug，请：

1. 搜索 [Issues](https://github.com/yourusername/VoiceAssistant/issues) 确认是否已有人报告
2. 如果没有，创建新 Issue，包含以下信息：
   - Bug 描述
   - 复现步骤
   - 预期行为
   - 实际行为
   - 环境信息（OS、Go/Python 版本等）
   - 相关日志和截图

### 提出新功能

如果您有新功能建议，请：

1. 先在 [Discussions](https://github.com/yourusername/VoiceAssistant/discussions) 讨论
2. 说明功能的用途和价值
3. 如果获得认可，创建 Feature Request Issue

### 贡献代码

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 开发流程

### 1. 设置开发环境

#### 前置要求
```bash
# Go
go version  # >= 1.21

# Python
python --version  # >= 3.11

# Docker
docker --version  # >= 24.0
```

#### 启动本地环境
```bash
# 1. Clone 项目
git clone https://github.com/yourusername/VoiceAssistant.git
cd VoiceAssistant

# 2. 启动基础设施
docker-compose up -d

# 3. 初始化数据库
make db-migrate

# 4. 启动服务
make dev
```

### 2. 分支策略

```
main (protected)
  ├── develop (默认分支)
  │   ├── feature/xxx
  │   ├── bugfix/xxx
  │   └── refactor/xxx
  └── release/v1.0.0
```

- `main`: 生产环境代码，仅接受来自 `develop` 或 `hotfix` 的合并
- `develop`: 开发分支，功能完成后合并到此分支
- `feature/*`: 新功能开发
- `bugfix/*`: Bug 修复
- `hotfix/*`: 紧急修复
- `release/*`: 发布准备

### 3. 本地开发

#### Go 服务
```bash
# 1. 进入服务目录
cd cmd/identity-service

# 2. 安装依赖
go mod download

# 3. 运行服务
go run main.go wire.go

# 4. 运行测试
go test ./... -v -cover
```

#### Python 服务
```bash
# 1. 进入服务目录
cd algo/indexing-service

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行服务
python main.py

# 5. 运行测试
pytest
```

---

## 代码规范

### Go 代码规范

#### 1. 格式化
```bash
# 使用 gofmt
go fmt ./...

# 使用 goimports
goimports -w .
```

#### 2. Linting
```bash
# 使用 golangci-lint
golangci-lint run
```

#### 3. 命名规范
- **包名**: 小写，单数，简短
  ```go
  package biz  // ✅
  package bizlogic  // ❌
  ```
- **变量**: 驼峰命名，首字母大写表示导出
  ```go
  var userID string  // ✅ 私有
  var UserID string  // ✅ 导出
  var user_id string // ❌
  ```
- **接口**: 以 `er` 结尾
  ```go
  type Reader interface {}  // ✅
  type IReader interface {} // ❌
  ```

#### 4. 注释
```go
// GetUser 获取用户信息
// 
// 参数:
//   - id: 用户ID
//
// 返回:
//   - *User: 用户对象
//   - error: 错误信息
func GetUser(id string) (*User, error) {
    // ...
}
```

### Python 代码规范

#### 1. 格式化
```bash
# 使用 black
black .

# 使用 isort
isort .
```

#### 2. Linting
```bash
# 使用 ruff
ruff check .

# 使用 mypy (类型检查)
mypy .
```

#### 3. 命名规范
- **模块名**: 小写，下划线分隔
  ```python
  document_parser.py  # ✅
  documentParser.py   # ❌
  ```
- **类名**: 驼峰命名
  ```python
  class UserService:  # ✅
  class user_service: # ❌
  ```
- **函数/变量**: 小写，下划线分隔
  ```python
  def get_user_by_id():  # ✅
  def getUserById():     # ❌
  ```

#### 4. 类型注解
```python
from typing import List, Optional

def get_user(user_id: str) -> Optional[User]:
    """获取用户信息
    
    Args:
        user_id: 用户ID
        
    Returns:
        User 对象，不存在返回 None
    """
    pass
```

---

## 提交规范

### Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建过程或辅助工具变动

### Scope 范围
- `identity`: Identity Service
- `conversation`: Conversation Service
- `knowledge`: Knowledge Service
- `indexing`: Indexing Service
- `retrieval`: Retrieval Service
- `agent`: Agent Engine
- `rag`: RAG Engine
- `router`: Model Router
- `adapter`: Model Adapter
- `notification`: Notification Service
- `analytics`: Analytics Service

### 示例

```bash
# 新功能
feat(identity): 新增 OAuth2 登录支持

实现了 Google、GitHub OAuth2 登录功能
- 添加 OAuth2 配置
- 实现回调处理
- 更新前端登录页面

Closes #123

# Bug 修复
fix(conversation): 修复上下文丢失问题

修复了长时间会话导致上下文丢失的 Bug
- 增加上下文持久化
- 优化 Redis 缓存策略

Fixes #456

# 文档更新
docs: 更新部署文档

# 重构
refactor(knowledge): 重构文档上传逻辑
```

---

## Pull Request 流程

### 1. PR 准备清单

在提交 PR 之前，请确保：

- [ ] 代码已通过 Lint 检查
- [ ] 所有测试通过
- [ ] 新功能有对应的单元测试
- [ ] 覆盖率 ≥ 70%
- [ ] API 文档已更新
- [ ] CHANGELOG 已更新
- [ ] Commit 消息符合规范

### 2. PR 模板

```markdown
## 变更说明
<!-- 描述本次变更的动机和内容 -->

## 变更类型
- [ ] 新功能
- [ ] Bug 修复
- [ ] 重构
- [ ] 文档更新
- [ ] 性能优化

## 影响范围
<!-- 哪些服务/模块受影响 -->

## 测试证据
<!-- 截图、日志、指标 -->

## 性能影响
<!-- P95 延迟、QPS、资源消耗 -->

## 检查清单
- [ ] 代码已通过 lint
- [ ] 单元测试已通过（覆盖率 ≥ 70%）
- [ ] 集成测试已通过
- [ ] API 文档已更新
- [ ] CHANGELOG 已更新
```

### 3. Code Review 流程

1. 提交 PR 后，自动触发 CI 检查
2. 至少 1 个 Maintainer 审核
3. 解决所有 Review 意见
4. CI 全部通过
5. Maintainer 合并

---

## 测试要求

### 单元测试

#### Go 测试
```go
func TestGetUser(t *testing.T) {
    // Arrange
    repo := &mockUserRepo{}
    uc := NewUserUsecase(repo)
    
    // Act
    user, err := uc.GetUser(context.Background(), "user_123")
    
    // Assert
    assert.NoError(t, err)
    assert.Equal(t, "user_123", user.ID)
}
```

#### Python 测试
```python
def test_get_user():
    # Arrange
    repo = MockUserRepo()
    service = UserService(repo)
    
    # Act
    user = service.get_user("user_123")
    
    # Assert
    assert user.id == "user_123"
```

### 集成测试

```bash
# 启动测试环境
make test-env-up

# 运行集成测试
make integration-test

# 清理测试环境
make test-env-down
```

### 测试覆盖率要求

- **核心业务逻辑**: ≥ 80%
- **Domain 层**: ≥ 80%
- **Application 层**: ≥ 70%
- **Data 层**: ≥ 60%
- **整体覆盖率**: ≥ 70%

---

## 常见问题

### Q: 如何添加新的依赖？

**Go**:
```bash
go get github.com/example/package@v1.2.3
go mod tidy
```

**Python**:
```bash
pip install package==1.2.3
pip freeze > requirements.txt
```

### Q: 如何调试服务？

**Go (使用 Delve)**:
```bash
dlv debug cmd/identity-service/main.go
```

**Python**:
```python
import pdb; pdb.set_trace()
```

### Q: 如何查看日志？

```bash
# 本地开发
tail -f logs/identity-service.log

# Kubernetes
kubectl logs -f deployment/identity-service -n voicehelper-prod
```

---

## 获取帮助

- **文档**: https://docs.voicehelper.ai
- **Discussions**: https://github.com/yourusername/VoiceAssistant/discussions
- **Issue 追踪**: https://github.com/yourusername/VoiceAssistant/issues
- **Slack**: #voicehelper-dev

---

## 许可证

通过贡献代码，您同意您的贡献将按照 MIT 许可证授权。

---

**感谢您的贡献！** 🎉
