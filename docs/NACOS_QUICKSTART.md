# Nacos 配置中心快速开始

## 5 分钟快速体验

### 步骤 1：启动 Nacos

```bash
# 使用 Docker 启动 Nacos
docker run -d \
  --name nacos \
  -p 8848:8848 \
  -e MODE=standalone \
  nacos/nacos-server:v2.3.0

# 等待 Nacos 启动（约 30 秒）
docker logs -f nacos
```

### 步骤 2：访问 Nacos 控制台

打开浏览器访问：http://localhost:8848/nacos

- **账号**：nacos
- **密码**：nacos

### 步骤 3：上传配置

```bash
# 自动上传所有服务配置
cd VoiceAssistant
./scripts/nacos-setup.sh

# 或手动在 Nacos 控制台创建配置：
# 1. 进入"配置管理" -> "配置列表"
# 2. 点击"+" 创建配置
# 3. Data ID: conversation-service.yaml
# 4. Group: VoiceAssistant
# 5. 配置格式: YAML
# 6. 复制 configs/conversation-service.yaml 的内容（去掉 nacos 块）
```

### 步骤 4：启动服务（Nacos 模式）

#### Go 服务示例

```bash
cd cmd/conversation-service

# 设置环境变量
export CONFIG_MODE=nacos
export NACOS_SERVER_ADDR=localhost
export NACOS_GROUP=VoiceAssistant

# 启动服务
go run main_new.go

# 日志输出：
# ✅ Loaded config from Nacos: VoiceAssistant/conversation-service.yaml (namespace: )
# 🔔 Watching config changes: VoiceAssistant/conversation-service.yaml
```

#### Python 服务示例

```bash
cd algo/agent-engine

# 安装依赖
pip install nacos-sdk-python PyYAML

# 设置环境变量
export CONFIG_MODE=nacos
export NACOS_SERVER_ADDR=localhost
export NACOS_GROUP=VoiceAssistant

# 启动服务
python main_with_nacos.py

# 日志输出：
# ✅ Loaded config from Nacos: VoiceAssistant/agent-engine.yaml (namespace: )
# 🔔 Watching config changes: VoiceAssistant/agent-engine.yaml
```

### 步骤 5：测试配置热更新

1. 在 Nacos 控制台修改配置
2. 观察服务日志：

```
🔄 Config changed: VoiceAssistant/conversation-service.yaml
✅ Config reloaded successfully
```

## 本地配置模式（无需 Nacos）

```bash
# 方式 1：不设置环境变量（默认本地模式）
go run main_new.go

# 方式 2：显式指定本地模式
export CONFIG_MODE=local
go run main_new.go

# 日志输出：
# ✅ Loaded config from local file: ./configs/conversation-service.yaml
```

## Docker Compose 体验

```bash
# 启动本地配置模式
docker-compose -f deployments/docker/docker-compose.nacos.yml --profile local up -d

# 启动 Nacos 配置中心模式
docker-compose -f deployments/docker/docker-compose.nacos.yml --profile nacos up -d

# 查看日志
docker-compose -f deployments/docker/docker-compose.nacos.yml logs -f conversation-service-nacos
```

## 常见问题

### Q: 如何在本地配置和 Nacos 之间切换？

A: 只需修改环境变量 `CONFIG_MODE`：

```bash
# 切换到本地模式
export CONFIG_MODE=local

# 切换到 Nacos 模式
export CONFIG_MODE=nacos
```

### Q: Nacos 不可用时会怎样？

A: Nacos 客户端有本地缓存，离线时会使用缓存的配置。如果首次启动且 Nacos 不可用，会报错并退出。

### Q: 如何验证服务使用的是哪种配置模式？

A: 查看服务启动日志：

```bash
# 本地模式
✅ Loaded config from local file: ./configs/service.yaml

# Nacos 模式
✅ Loaded config from Nacos: VoiceAssistant/service.yaml
```

### Q: 配置更新需要重启服务吗？

A:

- **本地模式**：需要重启
- **Nacos 模式**：不需要，配置会自动推送并重新加载

## 下一步

- 查看完整文档：`configs/README.md`
- 了解实现细节：`NACOS_INTEGRATION_SUMMARY.md`
- 多环境配置：使用 Namespace 隔离不同环境
- 生产部署：参考 Kubernetes 配置

## 技术支持

如有问题，请查看：

1. Nacos 官方文档：https://nacos.io/zh-cn/docs/quick-start.html
2. 故障排查：`configs/README.md` 中的"故障排查"章节
3. 示例代码：
   - Go: `cmd/conversation-service/main_new.go`
   - Python: `algo/agent-engine/main_with_nacos.py`
