# 多阶段构建 - 优化版Dockerfile

# ===== 构建阶段 =====
FROM python:3.11-slim as builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
  gcc \
  g++ \
  && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements_updated.txt .

# 安装Python依赖到独立目录
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir --target=/build/deps -r requirements_updated.txt

# ===== 运行阶段 =====
FROM python:3.11-slim

# 创建非root用户
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

# 从构建阶段复制依赖
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/

# 复制应用代码
COPY --chown=appuser:appuser . .

# 暴露端口
EXPOSE 8005

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health').read()" || exit 1

# 切换到非root用户
USER appuser

# 启动命令
CMD ["python", "-m", "uvicorn", "main_refactored:app", "--host", "0.0.0.0", "--port", "8005"]
