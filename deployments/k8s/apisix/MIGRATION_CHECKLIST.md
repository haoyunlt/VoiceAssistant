# Istio → APISIX 迁移检查清单

## 迁移前准备 (Day -1)

### 环境检查
- [ ] 确认 Kubernetes 集群版本 ≥ 1.23
- [ ] 验证 etcd 服务可用性
- [ ] 确认 Redis 集群正常（限流缓存）
- [ ] 验证 TLS 证书有效期
- [ ] 确认监控系统正常（Prometheus/Grafana）

### 备份
- [ ] 备份 Istio 配置（Gateway/VirtualService/DestinationRule）
- [ ] 备份 Istio 安全策略（PeerAuthentication/AuthorizationPolicy）
- [ ] 备份当前服务配置（Services/Deployments）
- [ ] 备份监控配置（Telemetry/ServiceMonitor）
- [ ] 导出当前监控基线数据

### 配置准备
- [ ] 准备 APISIX Secrets（admin-key, jwt-secret）
- [ ] 准备 TLS 证书 Secret
- [ ] 配置 DNS TTL（降低到 60s）
- [ ] 准备回滚脚本

### 团队准备
- [ ] 召开迁移 Kickoff 会议
- [ ] 通知业务方维护窗口
- [ ] 准备应急联系方式
- [ ] 准备战情室（Slack/钉钉）

---

## 迁移执行 (Day 0)

### 阶段 1: 部署 APISIX (2 小时)

#### 1.1 部署核心组件
```bash
./scripts/migrate-istio-to-apisix.sh apply
```

- [ ] 创建 apisix namespace
- [ ] 部署 APISIX Deployment (3 副本)
- [ ] 创建 APISIX Services (Gateway + Admin)
- [ ] 配置 ServiceAccount 和 RBAC
- [ ] 部署 HPA 和 PDB

**验证**:
```bash
kubectl get pods -n apisix
kubectl get svc -n apisix
```

#### 1.2 配置路由和上游
- [ ] 应用 Routes ConfigMap
- [ ] 应用 Upstreams ConfigMap
- [ ] 验证路由规则加载

**验证**:
```bash
# 通过 Admin API 检查
kubectl port-forward -n apisix svc/apisix-admin 9180:9180
curl http://localhost:9180/apisix/admin/routes \
  -H "X-API-KEY: <admin-key>"
```

#### 1.3 配置安全策略
- [ ] 应用 SSL/TLS 配置
- [ ] 配置 JWT 认证
- [ ] 配置 mTLS 上游
- [ ] 配置 RBAC 规则
- [ ] 配置 WAF 规则
- [ ] 配置 PII 脱敏

**验证**:
```bash
# JWT 测试
curl -i https://api.voiceassistant.com/api/v1/ai/chat  # 应返回 401
curl -i -H "Authorization: Bearer <valid-jwt>" \
  https://api.voiceassistant.com/api/v1/ai/chat  # 应返回 200 或业务状态码
```

#### 1.4 配置可观测性
- [ ] 应用 OpenTelemetry 配置
- [ ] 应用 Prometheus ServiceMonitor
- [ ] 应用 PrometheusRule 告警规则
- [ ] 导入 Grafana Dashboard
- [ ] 配置 Kafka 日志收集

**验证**:
```bash
# 检查 Prometheus 指标
kubectl port-forward -n apisix svc/apisix-admin 9091:9091
curl http://localhost:9091/apisix/prometheus/metrics | grep apisix_

# 检查 Grafana
# 访问 Grafana，确认 APISIX Dashboard 显示正常
```

### 阶段 2: 内部验证 (1 小时)

#### 2.1 功能测试
- [ ] 健康检查: `GET /health`
- [ ] API 路由: `GET /api/v1/conversations`
- [ ] WebSocket: `ws://ws.voiceassistant.com/ws/voice`
- [ ] gRPC: `grpc.voiceassistant.com:443`
- [ ] JWT 认证: 有效/无效 token
- [ ] 限流: 超出 rate limit 应返回 429
- [ ] CORS: OPTIONS preflight

#### 2.2 性能测试
- [ ] 运行负载测试（k6/JMeter）
- [ ] 验证 P95 延迟 < 200ms
- [ ] 验证 QPS ≥ 1000
- [ ] 验证错误率 < 0.1%

#### 2.3 监控验证
- [ ] Prometheus 指标正常采集
- [ ] Grafana Dashboard 显示正常
- [ ] OpenTelemetry Traces 正常上报
- [ ] Kafka 日志正常收集
- [ ] 告警规则配置正确

---

## 流量切换 (Day 1-7)

### Day 1: 10% 流量

#### 切换前
- [ ] 确认 APISIX 健康检查通过
- [ ] 确认监控正常
- [ ] 通知业务方

#### 执行切换
- [ ] 更新 DNS 权重: 10% → APISIX, 90% → Istio
  ```bash
  # 示例：AWS Route53 权重路由
  # APISIX: Weight 10
  # Istio:  Weight 90
  ```

#### 监控（持续 24 小时）
- [ ] 每小时检查错误率
- [ ] 每小时检查 P95 延迟
- [ ] 每小时检查可用性
- [ ] 检查告警是否触发

#### Go/No-Go 决策点
- [ ] 错误率 < 1% ✓
- [ ] P95 延迟增幅 < 50% ✓
- [ ] 可用性 ≥ 99% ✓
- [ ] 无 P0/P1 故障 ✓

---

### Day 2: 25% 流量

#### 切换前
- [ ] 回顾 Day 1 监控数据
- [ ] 确认无遗留问题

#### 执行切换
- [ ] 更新 DNS 权重: 25% → APISIX, 75% → Istio

#### 监控（持续 24 小时）
- [ ] 每 4 小时检查关键指标
- [ ] 检查告警是否触发

#### Go/No-Go 决策点
- [ ] 同 Day 1 标准

---

### Day 3-4: 50% 流量

#### 切换前
- [ ] 回顾 Day 2 监控数据
- [ ] 确认容量充足（APISIX 副本数）

#### 执行切换
- [ ] 更新 DNS 权重: 50% → APISIX, 50% → Istio

#### 监控（持续 48 小时）
- [ ] 每 4 小时检查关键指标
- [ ] 观察 HPA 扩缩容行为
- [ ] 验证限流和熔断正常

#### Go/No-Go 决策点
- [ ] 同 Day 1 标准

---

### Day 5-6: 75% 流量

#### 切换前
- [ ] 回顾 Day 3-4 监控数据

#### 执行切换
- [ ] 更新 DNS 权重: 75% → APISIX, 25% → Istio

#### 监控（持续 24 小时）
- [ ] 每 4 小时检查关键指标

#### Go/No-Go 决策点
- [ ] 同 Day 1 标准

---

### Day 7: 100% 流量

#### 切换前
- [ ] 回顾 Day 5-6 监控数据
- [ ] 最终 Go/No-Go 评审会议
- [ ] 确认回滚预案就绪

#### 执行切换
- [ ] 更新 DNS 权重: 100% → APISIX, 0% → Istio
- [ ] 确认 DNS 传播完成（dig/nslookup）

#### 监控（持续 72 小时）
- [ ] 每 2 小时检查关键指标（前 24h）
- [ ] 每 4 小时检查关键指标（后 48h）

---

## 稳定运行期 (Day 8-14)

### 持续监控
- [ ] 每日检查 SLO 达成情况
- [ ] 每日检查告警情况
- [ ] 每日检查成本变化
- [ ] 收集用户反馈

### 优化调整
- [ ] 根据监控数据调整 HPA 参数
- [ ] 优化限流阈值
- [ ] 优化连接池配置
- [ ] 优化缓存策略

### Istio 保留
- [ ] 保持 Istio 控制平面运行（备用）
- [ ] 保持 Istio 配置备份
- [ ] 不删除 Istio CRD

---

## 清理 Istio (Day 15+)

### 准备
- [ ] 确认 APISIX 稳定运行 ≥ 2 周
- [ ] 确认无计划的回滚需求
- [ ] 通知团队准备清理

### 执行清理
```bash
./scripts/migrate-istio-to-apisix.sh cleanup
```

#### 阶段 1: 删除 Istio 配置
- [ ] 删除 Gateway
- [ ] 删除 VirtualService
- [ ] 删除 DestinationRule
- [ ] 删除 PeerAuthentication
- [ ] 删除 AuthorizationPolicy
- [ ] 删除 RequestAuthentication
- [ ] 删除 Telemetry

#### 阶段 2: 移除 Sidecar
- [ ] 移除 namespace istio-injection label
- [ ] 滚动重启所有 Pods
- [ ] 验证 Pods 无 istio-proxy 容器

#### 阶段 3: 卸载控制平面 (可选)
- [ ] 使用 istioctl uninstall
- [ ] 删除 istio-system namespace
- [ ] 删除 Istio CRD (谨慎操作)

---

## 回滚预案

### 触发条件
- [ ] 错误率 > 1%
- [ ] P95 延迟增加 > 50%
- [ ] 可用性 < 99%
- [ ] 出现 P0/P1 故障
- [ ] 业务方要求回滚

### 回滚步骤 (目标 RTO: 5 分钟)

#### 方案 1: DNS 快速回滚
```bash
# 1. 更新 DNS 指向 Istio Gateway (< 2 分钟)
# 2. 验证流量切回
# 3. 监控指标恢复
```

#### 方案 2: 使用脚本回滚
```bash
./scripts/migrate-istio-to-apisix.sh rollback
```

- [ ] 恢复 Istio 配置（从备份）
- [ ] 验证 Istio Gateway 正常
- [ ] 更新 DNS 或负载均衡器
- [ ] 监控流量切回
- [ ] 确认系统恢复正常

#### 回滚后行动
- [ ] 保留 APISIX 环境用于调查
- [ ] 根因分析（RCA）
- [ ] 修复问题
- [ ] 重新计划迁移

---

## 验收标准

### 功能验收
- [x] HTTP/HTTPS 路由正常
- [x] WebSocket 连接正常
- [x] gRPC 调用正常
- [x] JWT 认证正常
- [x] 限流功能正常
- [x] CORS 配置正常
- [x] mTLS 加密正常

### 性能验收
- [ ] API Gateway P95 延迟 < 200ms
- [ ] 端到端 QA P95 < 2.5s
- [ ] 可用性 ≥ 99.9%
- [ ] 错误率 < 0.1%
- [ ] 并发 RPS ≥ 1000

### 安全验收
- [ ] 未授权请求被拒绝（401）
- [ ] 跨租户访问被拒绝（403）
- [ ] SQL 注入被 WAF 拦截（403）
- [ ] XSS 攻击被 WAF 拦截（403）
- [ ] PII 数据已脱敏（日志检查）

### 可观测性验收
- [ ] Prometheus 指标正常采集
- [ ] OpenTelemetry Traces 正常
- [ ] Grafana Dashboard 正常
- [ ] 告警规则正常触发
- [ ] 日志正常收集到 Kafka

### 成本验收
- [ ] 内存使用减少 ≥ 70%（vs Istio Sidecar）
- [ ] Pod 数量减少（无 Sidecar）
- [ ] 无额外成本增加

---

## 签核

| 角色 | 姓名 | 签名 | 日期 |
|------|------|------|------|
| 平台负责人 | | | |
| 架构师 | | | |
| SRE Lead | | | |
| 业务负责人 | | | |

---

## 附录

### 联系方式
- **平台团队**: platform@voiceassistant.com
- **SRE 值班**: sre-oncall@voiceassistant.com
- **战情室**: Slack #apisix-migration

### 参考文档
- [APISIX 部署文档](./README.md)
- [迁移脚本](../../scripts/migrate-istio-to-apisix.sh)
- [架构概览](../../docs/arch/overview.md)
- [回滚手册](../../docs/runbook/index.md)

### 监控面板
- [Grafana APISIX Dashboard](https://grafana.voiceassistant.com/d/apisix-gateway)
- [Prometheus Alerts](https://prometheus.voiceassistant.com/alerts)
- [OpenTelemetry Traces](https://jaeger.voiceassistant.com)

### 关键指标查询

```promql
# 错误率
sum(rate(apisix_http_requests_total{status=~"5.."}[5m]))
/ sum(rate(apisix_http_requests_total[5m])) * 100

# P95 延迟
histogram_quantile(0.95,
  sum(rate(apisix_http_request_duration_seconds_bucket[5m])) by (le)
)

# 可用性
(sum(rate(apisix_http_requests_total[5m]))
 - sum(rate(apisix_http_requests_total{status=~"5.."}[5m])))
/ sum(rate(apisix_http_requests_total[5m])) * 100

# QPS
sum(rate(apisix_http_requests_total[1m]))
```
