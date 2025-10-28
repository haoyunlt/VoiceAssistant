# Istio Gateway 迁移变更日志

## v3.0 - APISIX → Istio Gateway 迁移 (2025-10-28)

### 🎯 迁移目标

从 APISIX 集中式网关迁移到 Istio Service Mesh 架构，获得:
- ✅ 服务间全链路追踪
- ✅ 服务级流量控制
- ✅ 零信任安全架构（mTLS + 细粒度授权）
- ✅ 云原生标准（Kubernetes 原生）

### 📦 新增文件

#### 核心配置
- `gateway.yaml` - Istio Gateway 配置
  - HTTP/HTTPS/gRPC/WebSocket 支持
  - TLS 1.2/1.3 配置
  - 多域名支持

- `virtual-service.yaml` - 路由规则
  - 15+ 服务路由配置
  - 超时和重试策略
  - CORS 配置

- `destination-rule.yaml` - 流量策略
  - 15+ 服务流量策略
  - 负载均衡（ROUND_ROBIN/LEAST_REQUEST/Consistent Hash）
  - 连接池配置
  - 熔断策略

#### 安全配置
- `security.yaml` - 全面的安全策略
  - PeerAuthentication（mTLS STRICT 模式）
  - RequestAuthentication（JWT 验证）
  - AuthorizationPolicy（24+ 授权策略）
    - 默认拒绝策略
    - 服务间授权
    - 基于 JWT Claims 的授权
    - 租户隔离
    - IP 黑白名单
    - 审计日志策略

#### 可观测性
- `telemetry.yaml` - 完整的可观测性配置
  - OpenTelemetry 追踪（3 种采样率策略）
  - Prometheus 指标（Request/Duration/Size/gRPC）
  - 访问日志（JSON 格式 + 自定义标签）
  - ServiceMonitor 配置
  - PrometheusRule 告警规则（15+ 告警）

#### 高级功能
- `envoy-filter.yaml` - EnvoyFilter 配置
  - 全局限流（IP + Redis 分布式）
  - 安全响应头
  - 请求ID追踪
  - CORS 全局策略
  - 请求体大小限制
  - 连接管理
  - WebSocket 支持
  - gzip 压缩
  - 结构化日志

#### 文档与工具
- `README.md` - 快速开始指南
- `MIGRATION_GUIDE.md` - 完整迁移文档（40+ 页）
  - 迁移流程
  - 配置映射
  - 金丝雀切换
  - 监控指标
  - 故障排查
- `../../../scripts/migrate-apisix-to-istio.sh` - 迁移脚本
  - 自动化安装
  - 金丝雀切换
  - 验证和回滚

### 🔄 配置映射

| APISIX 功能 | Istio 对应 | 文件 |
|-------------|-----------|------|
| APISIX Gateway | Istio Gateway | `gateway.yaml` |
| Route | VirtualService | `virtual-service.yaml` |
| Upstream | DestinationRule | `destination-rule.yaml` |
| limit-req 插件 | EnvoyFilter (rate limit) | `envoy-filter.yaml` |
| jwt-auth 插件 | RequestAuthentication | `security.yaml` |
| cors 插件 | VirtualService.corsPolicy | `virtual-service.yaml` |
| prometheus 插件 | Telemetry (metrics) | `telemetry.yaml` |
| opentelemetry 插件 | Telemetry (tracing) | `telemetry.yaml` |
| mTLS Upstream | PeerAuthentication | `security.yaml` |
| RBAC | AuthorizationPolicy | `security.yaml` |

### 📊 服务覆盖

配置覆盖以下服务:

**Go Services (gRPC)**:
- identity-service
- conversation-service
- knowledge-service
- ai-orchestrator
- model-router
- analytics-service
- notification-service

**Python Services (FastAPI/HTTP)**:
- agent-engine
- rag-engine
- retrieval-service
- voice-engine
- multimodal-engine
- indexing-service
- model-adapter
- vector-store-adapter

**总计**: 15+ 服务完整配置

### 🚀 主要特性

#### 1. 流量管理
- ✅ HTTP/HTTPS 路由（15+ 路由规则）
- ✅ gRPC 路由（5+ gRPC 服务）
- ✅ WebSocket 支持（语音流式传输）
- ✅ 超时和重试策略
- ✅ 负载均衡（3 种策略）
- ✅ 连接池优化
- ✅ 熔断保护

#### 2. 安全
- ✅ mTLS 服务间加密（STRICT 模式）
- ✅ JWT 认证（多 Issuer 支持）
- ✅ 细粒度授权（24+ 授权策略）
  - 基于 Namespace
  - 基于 ServiceAccount
  - 基于 JWT Claims（tenant_id, user_id, role）
- ✅ 默认拒绝 + 显式授权
- ✅ 租户隔离
- ✅ IP 黑白名单
- ✅ 审计日志

#### 3. 可观测性
- ✅ OpenTelemetry 全链路追踪
  - 全局 10% 采样率
  - AI 服务 50% 采样率
  - WebSocket 100% 采样率
- ✅ Prometheus 指标
  - Request Count/Duration/Size
  - gRPC 指标
  - TCP 连接指标
  - 自定义标签（15+ 标签）
- ✅ JSON 访问日志
- ✅ 15+ Prometheus 告警规则
- ✅ Grafana Dashboard 支持

#### 4. 性能优化
- ✅ 连接池配置（HTTP/1.1 + HTTP/2）
- ✅ 熔断策略
- ✅ 请求重试
- ✅ gzip 压缩
- ✅ HPA 自动扩缩容
  - Gateway: 3-10 副本
  - Istiod: 2-5 副本

#### 5. 高级功能
- ✅ 全局限流（IP + Redis 分布式）
- ✅ 安全响应头（HSTS, CSP, X-Frame-Options）
- ✅ 请求ID追踪
- ✅ CORS 全局策略
- ✅ 请求体大小限制（100MB）
- ✅ WebSocket 升级支持
- ✅ 结构化日志（JSON 格式）

### 📈 资源对比

| 组件 | APISIX | Istio | 变化 |
|------|--------|-------|------|
| Gateway | 3 Pods × 512MB = 1.5GB | 3-10 Pods × 1GB = 3-10GB | +1.5-8.5GB |
| Control Plane | - | 2-5 Pods × 2GB = 4-10GB | +4-10GB |
| Sidecar | - | 50 services × 2 replicas × 128MB = ~13GB | +13GB |
| **总计** | ~1.5GB | ~20-30GB | **+18.5-28.5GB** |

**权衡**:
- 💰 成本增加: 约 15-20GB 内存
- 📊 收益: 服务间全链路追踪、服务级流量控制、零信任安全

### 🔧 迁移工具

#### 迁移脚本
`scripts/migrate-apisix-to-istio.sh` 支持以下命令:
- `plan` - 显示迁移计划
- `preflight` - 预检查环境
- `install-istio` - 安装 Istio
- `apply` - 部署配置
- `verify` - 验证健康
- `canary` - 金丝雀切换（10% → 25% → 50% → 75% → 100%）
- `rollback` - 回滚到 APISIX
- `cleanup` - 清理 APISIX

#### 金丝雀切换
- ✅ 5 个阶段渐进式流量切换
- ✅ 每个阶段观察期（30分钟 - 1小时）
- ✅ 实时监控指标（错误率/延迟/吞吐量）
- ✅ 一键回滚

### 📚 文档完善度

- ✅ 快速开始指南（README.md）
- ✅ 完整迁移文档（MIGRATION_GUIDE.md）
  - 40+ 页详细文档
  - 配置映射表
  - 金丝雀切换指南
  - 监控指标查询
  - 故障排查手册
- ✅ 架构文档更新（docs/arch/overview.md）
- ✅ 命令行工具（migrate-apisix-to-istio.sh）

### ⚠️ 注意事项

#### 资源要求
- 确保集群有足够内存（约增加 20-30GB）
- 建议使用 HPA 自动扩缩容

#### 迁移风险
- Sidecar 注入需要重启所有 Pod
- 流量切换期间需要监控错误率
- 准备回滚方案（保留 APISIX 环境）

#### 兼容性
- Kubernetes v1.26+
- Istio v1.20.1+
- 现有服务需要支持 mTLS（大部分 Go/Python 服务已支持）

### 🎓 学习资源

- [Istio 官方文档](https://istio.io/latest/docs/)
- [Envoy Proxy 文档](https://www.envoyproxy.io/docs/)
- [Istio 性能与可扩展性](https://istio.io/latest/docs/ops/deployment/performance-and-scalability/)
- [Istio 最佳实践](https://istio.io/latest/docs/ops/best-practices/)

### ✅ 验收标准

- [ ] 所有配置文件通过 `istioctl analyze`
- [ ] Gateway LoadBalancer 可访问
- [ ] 所有服务路由正常工作
- [ ] mTLS 覆盖率 100%
- [ ] JWT 认证正常工作
- [ ] 限流功能正常
- [ ] Prometheus 指标正常采集
- [ ] OpenTelemetry 追踪正常
- [ ] 访问日志正常输出
- [ ] 错误率 < 1%
- [ ] P95 延迟 < 2s
- [ ] 可用性 > 99.9%

### 📞 支持

- **Slack**: #istio-migration
- **Wiki**: https://wiki.voiceassistant.com/istio
- **Grafana**: https://grafana.voiceassistant.com/d/istio-gateway
- **Prometheus**: https://prometheus.voiceassistant.com

---

## 下一步

1. ✅ 完成配置文件创建
2. ✅ 创建迁移脚本
3. ✅ 编写完整文档
4. ⏭️ 执行预检查: `./scripts/migrate-apisix-to-istio.sh preflight`
5. ⏭️ 安装 Istio: `./scripts/migrate-apisix-to-istio.sh install-istio`
6. ⏭️ 部署配置: `./scripts/migrate-apisix-to-istio.sh apply`
7. ⏭️ 验证安装: `./scripts/migrate-apisix-to-istio.sh verify`
8. ⏭️ 金丝雀切换: `./scripts/migrate-apisix-to-istio.sh canary`
9. ⏭️ 稳定观察 2周+
10. ⏭️ 清理 APISIX: `./scripts/migrate-apisix-to-istio.sh cleanup`

---

**项目状态**: ✅ 配置完成，准备迁移
**预计迁移时间**: 2周+（包含观察期）
**风险级别**: 中等（已准备回滚方案）
