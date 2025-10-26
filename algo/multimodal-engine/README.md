# Multimodal Engine

多模态引擎服务 - 提供 OCR（光学字符识别）和视觉理解功能。

## 🎯 核心功能

- **OCR（光学字符识别）**: 基于 PaddleOCR 的高精度文字识别
- **Vision Understanding（视觉理解）**: 基于 Vision LLM 的图像理解
- **图像综合分析**: 物体检测、场景识别、颜色提取
- **多语言支持**: 支持中文、英文等多种语言
- **多格式支持**: JPG、PNG、PDF 等常见格式

## 📋 技术栈

- **框架**: FastAPI 0.110+
- **OCR**: PaddleOCR 2.7+
- **Vision LLM**: GPT-4V, Claude-3 Vision (通过 Model Adapter)
- **图像处理**: Pillow, OpenCV
- **Python**: 3.11+

## 🚀 快速开始

### 本地开发

```bash
# 安装系统依赖（Ubuntu/Debian）
sudo apt-get install libgl1-mesa-glx libglib2.0-0

# 安装 Python 依赖
make install

# 配置环境变量
export OCR_PROVIDER=paddleocr
export VISION_PROVIDER=gpt4v
export MODEL_ADAPTER_ENDPOINT=http://localhost:8006

# 运行服务
make run
```

服务将在 `http://localhost:8005` 启动。

### Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
make docker-run

# 查看日志
make logs
```

## 📡 API 端点

### 1. OCR（文字识别）

#### 批量识别

```bash
POST /api/v1/ocr/recognize
```

**请求示例**:

```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "languages": ["ch", "en"],
  "detect_orientation": true,
  "confidence_threshold": 0.5
}
```

**响应示例**:

```json
{
  "text_blocks": [
    {
      "text": "您好，世界",
      "confidence": 0.95,
      "bbox": [
        [10, 20],
        [100, 20],
        [100, 50],
        [10, 50]
      ],
      "language": "zh"
    }
  ],
  "full_text": "您好，世界",
  "language": "zh",
  "processing_time_ms": 250
}
```

#### 文件上传识别

```bash
POST /api/v1/ocr/recognize/upload
```

**请求**:

```bash
curl -X POST "http://localhost:8005/api/v1/ocr/recognize/upload" \
  -F "file=@document.jpg" \
  -F "languages=ch,en" \
  -F "confidence_threshold=0.5"
```

### 2. Vision Understanding（视觉理解）

#### 图像理解

```bash
POST /api/v1/vision/understand
```

**请求示例**:

```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "prompt": "这张图片中有什么？",
  "model": "gpt-4-vision-preview",
  "max_tokens": 1000,
  "detail": "auto"
}
```

**响应示例**:

```json
{
  "answer": "这张图片展示了一个现代化的办公室场景，有多台电脑和工作人员...",
  "model": "gpt-4-vision-preview",
  "tokens_used": 350,
  "processing_time_ms": 2500
}
```

#### 文件上传理解

```bash
POST /api/v1/vision/understand/upload
```

**请求**:

```bash
curl -X POST "http://localhost:8005/api/v1/vision/understand/upload" \
  -F "file=@photo.jpg" \
  -F "prompt=描述这张照片的内容"
```

### 3. 图像综合分析

#### 综合分析

```bash
POST /api/v1/analysis/image
```

**请求示例**:

```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "tasks": ["description", "objects", "scene", "colors", "text"]
}
```

**响应示例**:

```json
{
  "description": "一张展示城市街景的照片，有建筑物和行人",
  "objects": [
    { "name": "建筑物", "confidence": 0.95 },
    { "name": "行人", "confidence": 0.88 }
  ],
  "scene": "城市街道",
  "colors": ["#3a5f8d", "#8b9dc3", "#f0f0f0"],
  "text": "Street View Cafe",
  "metadata": {
    "width": 1920,
    "height": 1080,
    "format": "JPEG",
    "size_bytes": 524288
  },
  "processing_time_ms": 3500
}
```

## 配置说明

| 配置项                     | 说明               | 默认值                    |
| -------------------------- | ------------------ | ------------------------- |
| `OCR_PROVIDER`             | OCR 提供商         | paddleocr                 |
| `OCR_LANGUAGES`            | 支持的语言         | ch,en                     |
| `OCR_USE_GPU`              | 是否使用 GPU       | false                     |
| `OCR_CONFIDENCE_THRESHOLD` | 置信度阈值         | 0.5                       |
| `VISION_PROVIDER`          | Vision 提供商      | gpt4v                     |
| `VISION_MODEL`             | Vision 模型        | gpt-4-vision-preview      |
| `MODEL_ADAPTER_ENDPOINT`   | Model Adapter 地址 | http://model-adapter:8006 |
| `MAX_IMAGE_SIZE`           | 最大图像尺寸       | 4096                      |

## 架构设计

### OCR 处理流程

```
Image Input
    |
    v
Image Preprocessing ──> 格式转换、尺寸调整
    |
    v
PaddleOCR ──> 文本检测 + 识别
    |
    v
Confidence Filtering ──> 过滤低置信度
    |
    v
Text Blocks + Full Text
```

### Vision Understanding 流程

```
Image Input
    |
    v
Image Encoding ──> Base64
    |
    v
Vision LLM ──> GPT-4V / Claude-3
    |          (via Model Adapter)
    v
Answer
```

### 综合分析流程

```
Image Input
    |
    ├─> OCR ──────────────> Text
    ├─> Vision LLM ───────> Description
    ├─> Vision LLM ───────> Objects
    ├─> Vision LLM ───────> Scene
    ├─> Color Extraction ─> Colors
    └─> Metadata ─────────> Size, Format
                |
                v
          Analysis Result
```

## 模型说明

### PaddleOCR

- **检测模型**: PP-OCRv4 (高精度)
- **识别模型**: PP-OCRv4 (支持中英文)
- **方向分类**: Mobile v2.0
- **优点**: 轻量级、高精度、免费

### Vision LLM 选择

| 模型            | 能力 | 速度 | 成本 | 推荐场景     |
| --------------- | ---- | ---- | ---- | ------------ |
| GPT-4 Vision    | 最强 | 慢   | 高   | 高精度要求   |
| Claude-3 Opus   | 很强 | 中   | 高   | 复杂场景理解 |
| Claude-3 Sonnet | 强   | 快   | 中   | 通用场景     |

## 性能优化

- **模型缓存**: PaddleOCR 模型启动时加载
- **图像预处理**: 自动调整尺寸，避免过大图像
- **批量处理**: 支持批量 OCR 识别（待实现）
- **异步处理**: FastAPI 异步，支持高并发

## 监控指标

- `ocr_recognize_duration_seconds`: OCR 识别延迟
- `vision_understand_duration_seconds`: 视觉理解延迟
- `image_analysis_duration_seconds`: 图像分析延迟
- `ocr_confidence_avg`: 平均识别置信度

## 故障排查

### PaddleOCR 模型加载失败

```bash
# 检查 PaddlePaddle 安装
python -c "import paddle; print(paddle.__version__)"

# 手动下载模型
python -c "from paddleocr import PaddleOCR; PaddleOCR()"

# 检查磁盘空间
df -h ~/.paddleocr/
```

### Vision LLM 调用失败

```bash
# 检查 Model Adapter 连接
curl http://localhost:8006/health

# 检查配置
echo $MODEL_ADAPTER_ENDPOINT
echo $VISION_MODEL
```

### 图像处理错误

```bash
# 检查图像格式
file image.jpg

# 检查 Pillow 安装
python -c "from PIL import Image; print(Image.__version__)"

# 检查 OpenCV 安装
python -c "import cv2; print(cv2.__version__)"
```

## 开发指南

### 添加新的 OCR Provider

1. 在 `app/services/ocr_service.py` 添加新的识别方法
2. 更新 `OCR_PROVIDER` 配置选项
3. 实现对应的 API 集成

### 添加新的分析任务

1. 在 `app/services/analysis_service.py` 添加新的分析方法
2. 在 `ImageAnalysisRequest.tasks` 添加新的任务类型
3. 更新文档

### 支持更多图像格式

```python
# 在 app/core/config.py 中添加
SUPPORTED_FORMATS: str = "jpg,jpeg,png,bmp,tiff,pdf,webp"
```

## 📚 相关文档

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [GPT-4 Vision](https://platform.openai.com/docs/guides/vision)
- [Claude-3 Vision](https://docs.anthropic.com/claude/docs/vision)
- [Pillow](https://pillow.readthedocs.io/)

## 📝 License

MIT License
