# 算法服务虚拟环境设置指南

## 已创建的虚拟环境

所有算法服务均已创建 Python 3.11.14 虚拟环境：

- ✅ agent-engine
- ✅ indexing-service
- ✅ knowledge-service
- ✅ model-adapter
- ✅ multimodal-engine
- ✅ rag-engine
- ✅ retrieval-service
- ✅ vector-store-adapter
- ✅ voice-engine

## 使用方法

### 激活虚拟环境

进入任意服务目录并激活虚拟环境：

```bash
# 示例：激活 agent-engine 虚拟环境
cd algo/agent-engine
source venv/bin/activate
```

### 验证 Python 版本

```bash
python --version
# 输出: Python 3.11.14
```

### 安装依赖

虚拟环境已创建，但依赖尚未安装。根据需要安装：

```bash
# 在激活的虚拟环境中
pip install --upgrade pip
pip install -r requirements.txt
```

### 退出虚拟环境

```bash
deactivate
```

## 批量设置脚本

### 方法 1：使用单个服务脚本

每个服务都有独立的设置脚本：

```bash
cd algo/<service-name>
./setup-venv.sh
```

### 方法 2：使用统一设置脚本

为所有服务创建虚拟环境并安装依赖：

```bash
cd algo
./setup-all-venvs.sh
```

### 方法 3：手动创建

```bash
cd algo/<service-name>
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

## pip 镜像配置

项目已配置国内镜像源（清华/阿里云/中科大）以加速依赖安装。

配置文件：`algo/pip.conf`

使用镜像安装：
```bash
export PIP_CONFIG_FILE=/Users/lintao/important/ai-customer/VoiceHelper/algo/pip.conf
pip install -r requirements.txt
```

## 服务目录结构

```
algo/
├── agent-engine/          # Agent 引擎
│   ├── venv/             # Python 3.11 虚拟环境
│   ├── requirements.txt
│   ├── setup-venv.sh
│   └── main.py
├── indexing-service/      # 索引服务
│   ├── venv/
│   └── ...
├── knowledge-service/     # 知识服务
│   ├── venv/
│   └── ...
├── model-adapter/         # 模型适配器
│   ├── venv/
│   └── ...
├── multimodal-engine/     # 多模态引擎
│   ├── venv/
│   └── ...
├── rag-engine/           # RAG 引擎
│   ├── venv/
│   └── ...
├── retrieval-service/    # 检索服务
│   ├── venv/
│   └── ...
├── vector-store-adapter/ # 向量存储适配器
│   ├── venv/
│   └── ...
└── voice-engine/         # 语音引擎
    ├── venv/
    └── ...
```

## 常见问题

### Q: 为什么选择 Python 3.11？
A: Python 3.11 提供了显著的性能改进（比 3.10 快 10-60%）和更好的错误信息。

### Q: 虚拟环境位置在哪里？
A: 每个服务目录下的 `venv/` 文件夹。

### Q: 如何升级虚拟环境？
A: 删除 `venv` 文件夹并重新运行 `./setup-venv.sh`。

### Q: 依赖安装失败怎么办？
A:
1. 检查 Python 版本：`python --version`
2. 升级 pip：`pip install --upgrade pip`
3. 清理缓存：`pip cache purge`
4. 使用国内镜像：`export PIP_CONFIG_FILE=...`
5. 查看详细错误：`pip install -r requirements.txt -v`

### Q: 如何在 IDE 中使用虚拟环境？
A: 在 VS Code/PyCharm/Cursor 中，选择项目解释器为：
```
/Users/lintao/important/ai-customer/VoiceHelper/algo/<service>/venv/bin/python
```

## 下一步

1. 根据需要为各服务安装依赖
2. 配置环境变量（`.env` 文件）
3. 运行服务测试
4. 启动开发服务器

更多信息请参考各服务的 README.md 文件。
