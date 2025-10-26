# 服务独立性配置指南

本文档说明了如何使用每个服务的独立配置文件。

## 目录

- [Go 服务](#go-服务)
- [Python 服务](#python-服务)
- [快速开始](#快速开始)
- [故障排除](#故障排除)

## Go 服务

每个 Go 服务现在都有以下独立文件：

- `go.mod` - Go 模块依赖
- `go.sum` - 依赖校验和
- `Makefile` - 构建和运行命令
- `Dockerfile` - Docker 镜像构建
- `docker-compose.yml` - 完整的服务栈

### Go 服务列表

1. **identity-service** (端口: 9000/8000)
2. **conversation-service** (端口: 9001/8001)
3. **knowledge-service** (端口: 9002/8002)
4. **ai-orchestrator** (端口: 9003/8003)
5. **model-router** (端口: 9004/8004)
6. **notification-service** (端口: 9005/8005)
7. **analytics-service** (端口: 9006/8006)

### Go 服务使用方法

```bash
# 进入服务目录
cd cmd/identity-service

# 安装依赖
make deps

# 运行测试
make test

# 本地构建
make build

# 本地运行
make run

# 构建 Docker 镜像
make docker-build

# 使用 docker-compose 启动完整服务栈
make docker-compose-up

# 查看日志
make docker-compose-logs

# 停止服务
make docker-compose-down
```

### Go 服务 Makefile 命令

- `make build` - 构建二进制文件
- `make run` - 运行服务
- `make test` - 运行测试
- `make lint` - 代码检查
- `make clean` - 清理构建文件
- `make docker-build` - 构建 Docker 镜像
- `make docker-compose-up` - 启动服务栈
- `make docker-compose-down` - 停止服务栈
- `make deps` - 安装依赖
- `make dev` - 开发模式（热更新）

## Python 服务

每个 Python 服务现在都有以下独立文件：

- `requirements.txt` - Python 依赖
- `.python-version` - Python 版本（3.11）
- `setup-venv.sh` - 虚拟环境设置脚本
- `Dockerfile` - Docker 镜像构建
- `docker-compose.yml` - 完整的服务栈

### Python 服务列表

1. **agent-engine** (端口: 8010)
2. **indexing-service** (端口: 8011)
3. **retrieval-service** (端口: 8012)
4. **model-adapter** (端口: 8013)
5. **rag-engine** (端口: 8014)
6. **voice-engine** (端口: 8015)
7. **multimodal-engine** (端口: 8016)

### Python 服务使用方法

```bash
# 进入服务目录
cd algo/agent-engine

# 设置虚拟环境（首次运行）
chmod +x setup-venv.sh
./setup-venv.sh

# 激活虚拟环境
source venv/bin/activate

# 安装/更新依赖
pip install -r requirements.txt

# 运行服务
uvicorn main:app --host 0.0.0.0 --port 8010 --reload

# 使用 docker-compose 启动完整服务栈
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 退出虚拟环境
deactivate
```

### Python 虚拟环境管理

每个服务都使用 Python 3.11。确保您已安装 Python 3.11：

```bash
# macOS (使用 Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt-get install python3.11 python3.11-venv

# 验证安装
python3.11 --version
```

## 快速开始

### 1. 启动单个 Go 服务

```bash
cd cmd/identity-service
make docker-compose-up
```

这将启动 identity-service 及其所有依赖（PostgreSQL, Redis, Vault）。

### 2. 启动单个 Python 服务

```bash
cd algo/agent-engine
docker-compose up -d
```

这将启动 agent-engine 及其所有依赖（Redis）。

### 3. 本地开发（Go）

```bash
cd cmd/identity-service

# 安装依赖
make deps

# 运行服务（开发模式）
make dev
```

### 4. 本地开发（Python）

```bash
cd algo/agent-engine

# 设置虚拟环境
./setup-venv.sh

# 激活虚拟环境
source venv/bin/activate

# 运行服务（开发模式，带热更新）
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
```

## 环境变量

每个服务的 `docker-compose.yml` 包含了必要的环境变量。对于本地开发，您可以创建 `.env` 文件：

### Go 服务 .env 示例

```env
ENV=development
LOG_LEVEL=info
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=voicehelper
POSTGRES_PASSWORD=voicehelper123
POSTGRES_DB=voicehelper
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Python 服务 .env 示例

```env
ENV=development
LOG_LEVEL=info
REDIS_HOST=localhost
REDIS_PORT=6379
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## 端口分配

### Go 服务端口

| 服务                 | gRPC 端口 | HTTP 端口 |
| -------------------- | --------- | --------- |
| identity-service     | 9000      | 8000      |
| conversation-service | 9001      | 8001      |
| knowledge-service    | 9002      | 8002      |
| ai-orchestrator      | 9003      | 8003      |
| model-router         | 9004      | 8004      |
| notification-service | 9005      | 8005      |
| analytics-service    | 9006      | 8006      |

### Python 服务端口

| 服务              | HTTP 端口 |
| ----------------- | --------- |
| agent-engine      | 8010      |
| indexing-service  | 8011      |
| retrieval-service | 8012      |
| model-adapter     | 8013      |
| rag-engine        | 8014      |
| voice-engine      | 8015      |
| multimodal-engine | 8016      |

### 基础设施端口

| 服务       | 端口        | 说明             |
| ---------- | ----------- | ---------------- |
| PostgreSQL | 5432-5438   | 每个服务独立实例 |
| Redis      | 6379-6395   | 每个服务独立实例 |
| Kafka      | 9092-9096   | 消息队列         |
| Milvus     | 19530-19531 | 向量数据库       |
| MinIO      | 9000-9007   | 对象存储         |
| ClickHouse | 8123, 9000  | 分析数据库       |

## 故障排除

### Go 服务问题

#### 1. 依赖下载失败

```bash
# 清理 mod cache
go clean -modcache

# 重新下载依赖
make deps
```

#### 2. 构建失败

```bash
# 检查 Go 版本
go version  # 应该是 1.22+

# 清理并重新构建
make clean
make build
```

#### 3. Wire 生成失败

```bash
# 安装 wire
go install github.com/google/wire/cmd/wire@latest

# 生成代码
make wire
```

### Python 服务问题

#### 1. 虚拟环境创建失败

```bash
# 确保安装了 Python 3.11
python3.11 --version

# 手动创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. 依赖安装失败

```bash
# 升级 pip
pip install --upgrade pip

# 清理 pip cache
pip cache purge

# 重新安装
pip install -r requirements.txt
```

#### 3. 端口冲突

如果端口被占用，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - '8010:8010' # 改为 "8017:8010"
```

### Docker 问题

#### 1. 容器无法启动

```bash
# 查看日志
docker-compose logs -f

# 检查容器状态
docker ps -a

# 重新构建镜像
docker-compose build --no-cache
```

#### 2. 网络问题

```bash
# 重新创建网络
docker network prune
docker-compose down
docker-compose up -d
```

#### 3. 卷问题

```bash
# 清理卷
docker-compose down -v
docker-compose up -d
```

## 最佳实践

### 1. 开发环境

- 使用虚拟环境隔离 Python 依赖
- 使用 `make dev` 启用 Go 服务热更新
- 使用 `--reload` 参数启用 Python 服务热更新

### 2. 依赖管理

- 定期运行 `go mod tidy` 清理 Go 依赖
- 使用 `pip freeze > requirements.txt` 固定 Python 依赖版本

### 3. Docker 优化

- 使用多阶段构建减小镜像大小
- 利用 Docker 层缓存加速构建
- 定期清理未使用的镜像和容器

### 4. 日志管理

- 使用结构化日志
- 配置日志级别
- 定期清理日志文件

## 下一步

- 查看 [QUICKSTART.md](../QUICKSTART.md) 了解整体架构
- 查看 [docs/arch/microservice-architecture-v2.md](arch/microservice-architecture-v2.md) 了解服务架构
- 查看各服务的 README 了解具体实现

## 支持

如有问题，请：

1. 查看服务的 README 文档
2. 查看服务日志
3. 提交 Issue
4. 联系开发团队
