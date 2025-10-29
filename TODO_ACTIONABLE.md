# VoiceHelper 可执行任务清单

> 生成时间：2025-10-29
> 优先级：P0（紧急）> P1（重要）> P2（增强）

---

## 🔴 P0 紧急任务（必须完成，阻塞发布）

### 1. Go 服务单元测试补充 ⚠️ 严重

**问题**：所有 Go 服务（7个）都没有测试文件，生产风险极高。

#### 1.1 Identity Service 测试（优先）
- [ ] `internal/domain/user_test.go` - 用户实体测试
- [ ] `internal/domain/password_test.go` - 密码验证测试
- [ ] `internal/biz/auth_usecase_test.go` - 认证用例测试
- [ ] `internal/biz/user_usecase_test.go` - 用户用例测试
- [ ] `internal/data/user_repo_test.go` - 用户仓储测试
- [ ] `internal/data/token_blacklist_test.go` - Token 黑名单测试
- [ ] **目标覆盖率**：>60%
- [ ] **预计工时**：3-4 天

#### 1.2 Model Router 测试（优先）
- [ ] `internal/domain/ab_testing_test.go` - A/B 测试领域测试
- [ ] `internal/application/ab_testing_service_v2_test.go` - A/B 测试服务测试
- [ ] `internal/application/routing_service_test.go` - 路由服务测试
- [ ] `internal/data/ab_test_repo_test.go` - 仓储测试
- [ ] `internal/infrastructure/ab_test_cache_test.go` - 缓存测试
- [ ] **目标覆盖率**：>60%
- [ ] **预计工时**：3-4 天

#### 1.3 其他 Go 服务测试
- [ ] **Notification Service** - 核心用例测试（2天）
- [ ] **Conversation Service** - 会话管理测试（2天）
- [ ] **AI Orchestrator** - 编排逻辑测试（2天）
- [ ] **Knowledge Service** - 知识库管理测试（1天）
- [ ] **Analytics Service** - 报表逻辑测试（1天）
- [ ] **目标覆盖率**：>50%
- [ ] **总预计工时**：2周

**验收标准**：
```bash
# 所有服务通过测试
cd cmd/identity-service && go test ./... -v
cd cmd/model-router && go test ./... -v
# ...其他服务

# 覆盖率检查
go test ./... -coverprofile=coverage.out
go tool cover -func=coverage.out | grep total | awk '{print $3}'
# 应输出 >50%
```

---

### 2. Web 前端核心功能开发

**问题**：Web 仅有 Next.js 骨架，无法交付完整产品。

#### 2.1 实时对话界面（核心）
- [ ] `app/chat/page.tsx` - 对话页面主组件
- [ ] `components/chat/MessageList.tsx` - 消息列表组件
- [ ] `components/chat/MessageInput.tsx` - 输入框组件
- [ ] `components/chat/VoiceButton.tsx` - 语音按钮组件
- [ ] `lib/websocket.ts` - WebSocket 客户端封装
- [ ] `hooks/useChat.ts` - 对话 Hook
- [ ] **预计工时**：4-5 天

#### 2.2 WebSocket 集成
- [ ] `lib/api/websocket-client.ts` - WebSocket 连接管理
- [ ] `lib/api/message-handler.ts` - 消息处理逻辑
- [ ] `hooks/useWebSocket.ts` - WebSocket Hook
- [ ] 连接状态管理（连接中/已连接/断开）
- [ ] 自动重连机制
- [ ] 消息队列管理（离线消息）
- [ ] **预计工时**：2-3 天

#### 2.3 语音输入支持
- [ ] `lib/voice/recorder.ts` - 录音器封装
- [ ] `lib/voice/audio-processor.ts` - 音频处理
- [ ] `components/voice/VoiceRecorder.tsx` - 录音组件
- [ ] `hooks/useVoiceRecording.ts` - 录音 Hook
- [ ] 与 Voice Engine API 集成
- [ ] VAD 静音检测前端实现
- [ ] **预计工时**：2-3 天

#### 2.4 历史记录查看
- [ ] `app/history/page.tsx` - 历史记录页面
- [ ] `components/history/ConversationList.tsx` - 对话列表
- [ ] `components/history/ConversationDetail.tsx` - 对话详情
- [ ] `lib/api/conversation-api.ts` - 对话 API 客户端
- [ ] 分页加载
- [ ] 搜索与过滤
- [ ] **预计工时**：2-3 天

#### 2.5 状态管理
- [ ] `store/chat-store.ts` - Zustand 对话状态
- [ ] `store/user-store.ts` - 用户状态
- [ ] `store/settings-store.ts` - 设置状态
- [ ] **预计工时**：1-2 天

**总预计工时**：2-3周

**验收标准**：
- ✅ 用户可输入文字并实时获得回复
- ✅ WebSocket 连接稳定，断线自动重连
- ✅ 语音录制并发送到后端
- ✅ 可查看历史对话记录
- ✅ 界面响应式，支持移动端

---

### 3. Knowledge Service 架构决策

**问题**：Python 版本（95%完成）与 Go 版本（70%完成）职责重叠。

#### 3.1 职责分析（1天）
- [ ] 列出两个版本的功能清单
- [ ] 分析重叠功能（实体提取/图谱管理/检索）
- [ ] 评估性能差异（Python 灵活 vs Go 高性能）
- [ ] 调研团队技术栈偏好

#### 3.2 架构方案选择（1天）
**方案 A：保留 Python 版本，Go 作为协调层**
- ✅ Python Knowledge Service：AI 能力（实体提取/GraphRAG/检索）
- ✅ Go Knowledge Service：业务逻辑（知识库 CRUD/权限/版本控制）
- ✅ Go 调用 Python gRPC 接口

**方案 B：保留 Go 版本，迁移 Python 功能**
- ⚠️ 需将 GraphRAG/LLM 调用迁移到 Go
- ⚠️ 工作量大（2-3周）
- ⚠️ 可能损失 Python AI 生态优势

**方案 C：合并为单一 Python 服务**
- ⚠️ 放弃 Go 高性能优势
- ⚠️ CRUD 性能可能下降

**建议**：采用方案 A（职责分离）

#### 3.3 实施重构（3-5天）
- [ ] 明确接口边界
- [ ] 更新 API 文档
- [ ] 调整 K8s 部署配置
- [ ] 更新 README 说明
- [ ] 添加集成测试

**总预计工时**：1周

---

## 🟡 P1 重要任务（影响用户体验）

### 4. Admin 平台 MVP

**目标**：完成基础管理功能，支持运营人员使用。

#### 4.1 用户管理（3天）
- [ ] `platforms/admin/app/users/page.tsx` - 用户列表
- [ ] `platforms/admin/app/users/[id]/page.tsx` - 用户详情
- [ ] `platforms/admin/components/users/UserTable.tsx` - 用户表格
- [ ] `platforms/admin/components/users/UserForm.tsx` - 用户表单
- [ ] API 集成（Identity Service）
- [ ] 搜索/过滤/分页

#### 4.2 租户管理（2天）
- [ ] `platforms/admin/app/tenants/page.tsx` - 租户列表
- [ ] `platforms/admin/app/tenants/[id]/page.tsx` - 租户详情
- [ ] 租户创建/编辑/禁用
- [ ] 配额管理界面

#### 4.3 知识库管理（3天）
- [ ] `platforms/admin/app/knowledge/page.tsx` - 知识库列表
- [ ] `platforms/admin/app/knowledge/[id]/page.tsx` - 知识库详情
- [ ] 文档上传与管理
- [ ] 索引状态查看
- [ ] 向量数据统计

#### 4.4 系统配置（2天）
- [ ] `platforms/admin/app/settings/page.tsx` - 系统配置
- [ ] 模型配置（Model Router）
- [ ] 限流配置
- [ ] 告警配置

**总预计工时**：2周

---

### 5. Identity Service 高级功能

#### 5.1 OAuth 集成（4-5天）
- [ ] `internal/biz/oauth_usecase.go` - OAuth 用例完善
- [ ] **Google OAuth**
  - [ ] 配置 Google Cloud Console
  - [ ] 实现 OAuth 2.0 流程
  - [ ] 用户信息映射
- [ ] **GitHub OAuth**
  - [ ] 配置 GitHub OAuth App
  - [ ] 实现授权流程
  - [ ] 用户绑定逻辑
- [ ] **微信 OAuth**（可选）
  - [ ] 配置微信开放平台
  - [ ] 实现微信登录
- [ ] 统一 OAuth 回调处理
- [ ] 测试（单元测试 + 集成测试）

#### 5.2 密码重置（2天）
- [ ] `internal/biz/password_reset_usecase.go`
- [ ] 发送重置邮件（集成 Notification Service）
- [ ] 重置 Token 管理（Redis，TTL=30min）
- [ ] 密码重置接口（验证 Token + 更新密码）
- [ ] 测试

#### 5.3 双因素认证（3天）
- [ ] `internal/domain/totp.go` - TOTP 实现
- [ ] 启用 2FA 接口（生成密钥 + 二维码）
- [ ] 验证 2FA 接口（验证 TOTP 码）
- [ ] 登录流程改造（支持 2FA 验证）
- [ ] 备用码生成
- [ ] 测试

**总预计工时**：2周

---

### 6. 监控仪表盘补全

#### 6.1 RAG Engine Dashboard（2天）
- [ ] `deployments/grafana/dashboards/rag-performance.json`
  - 检索召回率
  - 答案准确率
  - E2E 延迟
  - 缓存命中率
- [ ] `deployments/grafana/dashboards/rag-cost.json`
  - Token 消耗统计
  - 成本分布（按租户）
  - 幻觉率趋势

#### 6.2 Voice Engine Dashboard（1天）
- [ ] `deployments/grafana/dashboards/voice-performance.json`
  - ASR 延迟
  - TTS 延迟
  - VAD 延迟
  - 缓存命中率

#### 6.3 Model Router Dashboard（1天）
- [ ] `deployments/grafana/dashboards/model-router.json`
  - 模型健康状态
  - 路由分布
  - A/B 测试效果对比
  - 成本统计

#### 6.4 系统级 Dashboard（2天）
- [ ] `deployments/grafana/dashboards/system-overview.json`
  - 所有服务健康状态
  - QPS 统计
  - 错误率
  - 资源使用
- [ ] 集成 Istio 官方仪表盘

**总预计工时**：1周

---

## 🟢 P2 增强任务（提升质量）

### 7. Python 服务测试补充

#### 7.1 Voice Engine 测试（3天）
- [ ] `tests/test_asr_service.py` - ASR 服务测试
- [ ] `tests/test_tts_service.py` - TTS 服务测试
- [ ] `tests/test_vad_service.py` - VAD 服务测试
- [ ] 集成测试（端到端）
- [ ] **目标覆盖率**：>60%

#### 7.2 Multimodal Engine 测试（2天）
- [ ] `tests/test_ocr_service.py` - OCR 服务测试
- [ ] `tests/test_vision_service.py` - Vision 服务测试
- [ ] `tests/test_analysis_service.py` - 分析服务测试
- [ ] **目标覆盖率**：>60%

#### 7.3 Vector Store Adapter 测试（2天）
- [ ] `tests/test_milvus_backend.py` - Milvus 后端测试
- [ ] `tests/test_pgvector_backend.py` - PgVector 后端测试
- [ ] `tests/test_connection_pool.py` - 连接池测试
- [ ] **目标覆盖率**：>60%

**总预计工时**：1周

---

### 8. 文档补全

#### 8.1 API 文档生成（2天）
- [ ] 使用 Swagger/OpenAPI 生成 API 文档
- [ ] 每个服务生成独立文档
- [ ] 部署到统一文档站点（如 GitBook/Docusaurus）

#### 8.2 部署文档完善（2天）
- [ ] `docs/deployment/prerequisites.md` - 前置条件
- [ ] `docs/deployment/installation.md` - 安装步骤
- [ ] `docs/deployment/configuration.md` - 配置说明
- [ ] `docs/deployment/troubleshooting.md` - 故障排查

#### 8.3 开发者指南（2天）
- [ ] `docs/development/setup.md` - 开发环境搭建
- [ ] `docs/development/coding-standards.md` - 编码规范
- [ ] `docs/development/testing.md` - 测试指南
- [ ] `docs/development/contributing.md` - 贡献指南

**总预计工时**：1周

---

### 9. 性能优化

#### 9.1 缓存策略优化（3天）
- [ ] Redis 缓存 Key 设计规范化
- [ ] 多级缓存（本地 + Redis）
- [ ] 缓存预热策略（热点数据）
- [ ] 缓存穿透/击穿/雪崩防护
- [ ] 性能测试验证

#### 9.2 数据库索引优化（2天）
- [ ] PostgreSQL 慢查询分析
- [ ] 为高频查询添加索引
- [ ] 复合索引优化
- [ ] 执行计划分析（EXPLAIN）
- [ ] 性能测试验证

#### 9.3 E2E 性能测试（3天）
- [ ] 使用 k6 编写性能测试脚本
- [ ] 对话流程压测（目标：1000 RPS）
- [ ] RAG 检索压测（目标：500 RPS）
- [ ] 语音处理压测（目标：200 RPS）
- [ ] 生成性能报告
- [ ] 性能瓶颈分析与优化

**总预计工时**：1-2周

---

## 📅 4周冲刺排期

### Week 1：紧急修复（P0.1 + P0.2 + P0.3）
| 工作日 | 任务 | 负责人 | 输出 |
|-------|------|--------|------|
| 周一-周三 | Identity Service 测试 | Go 后端 | 覆盖率 >60% |
| 周一-周三 | Model Router 测试 | Go 后端 | 覆盖率 >60% |
| 周一-周五 | Web 前端对话界面 | 前端 | 可演示原型 |
| 周四-周五 | Knowledge Service 架构分析 | 架构师 | 方案文档 |

**里程碑**：2个核心 Go 服务有测试，前端可演示。

---

### Week 2：核心补全（P0.1 续 + P0.2 续）
| 工作日 | 任务 | 负责人 | 输出 |
|-------|------|--------|------|
| 周一-周五 | 其他 5 个 Go 服务测试 | Go 后端 | 覆盖率 >50% |
| 周一-周三 | Web 前端 WebSocket 集成 | 前端 | 实时对话可用 |
| 周四-周五 | Web 前端语音输入 | 前端 | 语音输入可用 |
| 周一-周三 | Knowledge Service 重构 | Go+Python | 集成测试通过 |

**里程碑**：所有 Go 服务有测试，Web 核心功能完成。

---

### Week 3：体验增强（P1.1 + P1.2 + P1.3）
| 工作日 | 任务 | 负责人 | 输出 |
|-------|------|--------|------|
| 周一-周五 | Admin 平台 MVP | 前端 | 用户/租户管理可用 |
| 周一-周三 | Identity OAuth 集成 | Go 后端 | Google/GitHub 登录 |
| 周四-周五 | RAG Engine Dashboard | DevOps | Grafana 仪表盘 |
| 周一-周三 | Voice/Multimodal 测试 | Python 后端 | 覆盖率 >60% |

**里程碑**：Admin 平台可用，OAuth 登录可用，监控完善。

---

### Week 4：生产就绪（P1.3 续 + P2.3）
| 工作日 | 任务 | 负责人 | 输出 |
|-------|------|--------|------|
| 周一-周三 | 其他服务 Dashboard | DevOps | 全套监控仪表盘 |
| 周四-周五 | E2E 测试 | 全员 | 测试报告 |
| 周一-周三 | 性能压测 | DevOps | 性能报告 |
| 周四 | 安全加固 | 全员 | 安全检查清单 |
| 周五 | 文档完善 | 全员 | API 文档 + Runbook |

**里程碑**：生产就绪，可部署上线。

---

## ✅ 验收标准

### 功能验收
- [ ] 所有 Go 服务单元测试覆盖率 >50%
- [ ] Web 前端核心功能（对话/语音/历史）可用
- [ ] Admin 平台基础功能（用户/租户管理）可用
- [ ] Identity Service OAuth 登录可用
- [ ] 监控仪表盘覆盖 80%+ 服务

### 性能验收
- [ ] E2E QA 延迟 <2.5s
- [ ] API Gateway P95 <200ms
- [ ] 并发 RPS ≥1000
- [ ] 可用性 ≥99.9%（模拟测试）

### 质量验收
- [ ] 代码通过 Lint 检查
- [ ] 关键 API 有集成测试
- [ ] 文档完整（API + Runbook）
- [ ] 安全检查清单完成

### 生产验收
- [ ] K8s 部署成功（所有服务 Running）
- [ ] Istio Gateway 路由正常
- [ ] Prometheus 指标采集正常
- [ ] Grafana 仪表盘可访问
- [ ] 日志收集正常
- [ ] 告警规则配置正确

---

## 🛠️ 快速命令参考

### 测试
```bash
# Go 单元测试
cd cmd/identity-service && go test ./... -v -cover

# Python 单元测试
cd algo/agent-engine && pytest tests/ -v --cov=app

# 覆盖率报告
go test ./... -coverprofile=coverage.out
go tool cover -html=coverage.out -o coverage.html
```

### 部署
```bash
# 本地启动所有服务
docker-compose up -d

# K8s 部署
kubectl apply -f deployments/k8s/namespace.yaml
kubectl apply -f deployments/k8s/infrastructure/
kubectl apply -f deployments/k8s/services/

# 查看服务状态
kubectl get pods -n voiceassistant-prod
kubectl get svc -n voiceassistant-prod
```

### 监控
```bash
# 访问 Grafana
kubectl port-forward -n voiceassistant-infra svc/grafana 3000:3000
# 打开 http://localhost:3000

# 访问 Prometheus
kubectl port-forward -n voiceassistant-infra svc/prometheus 9090:9090
# 打开 http://localhost:9090

# 访问 Jaeger
kubectl port-forward -n voiceassistant-infra svc/jaeger 16686:16686
# 打开 http://localhost:16686
```

---

## 📊 进度追踪

建议使用 GitHub Projects 或 Jira 追踪进度：

```markdown
### Kanban 看板

| Backlog | In Progress | Code Review | Testing | Done |
|---------|-------------|-------------|---------|------|
| [ ] ... | [ ] ...     | [ ] ...     | [ ] ... | [x] ... |
```

### 每日站会议题
1. 昨天完成了什么？
2. 今天计划做什么？
3. 有什么阻塞？

### 每周回顾
1. 本周完成的任务
2. 本周遇到的问题
3. 下周重点任务
4. 风险与改进建议

