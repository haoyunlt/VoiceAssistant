# Voice Engine

语音引擎服务 - 提供 ASR（自动语音识别）、TTS（文本转语音）、VAD（语音活动检测）功能。

## 🎯 核心功能

- **ASR (自动语音识别)**: 基于 Whisper 的高精度语音识别
- **TTS (文本转语音)**: 基于 Edge TTS 的自然语音合成
- **VAD (语音活动检测)**: 基于 Silero VAD 的实时语音检测
- **多语言支持**: 支持中文、英文等多种语言
- **流式处理**: 支持流式 ASR 和 TTS
- **智能缓存**: TTS 结果缓存，提升响应速度

## 📋 技术栈

- **框架**: FastAPI 0.110+
- **ASR**: Faster-Whisper (OpenAI Whisper)
- **TTS**: Edge TTS (Microsoft Edge)
- **VAD**: Silero VAD (PyTorch)
- **音频处理**: pydub, numpy
- **Python**: 3.11+

## 🚀 快速开始

### 本地开发

```bash
# 安装系统依赖（Ubuntu/Debian）
sudo apt-get install ffmpeg libsndfile1

# 安装 Python 依赖
make install

# 配置环境变量
export ASR_PROVIDER=whisper
export WHISPER_MODEL=base
export TTS_PROVIDER=edge

# 运行服务
make run
```

服务将在 `http://localhost:8004` 启动。

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

### 1. ASR（语音识别）

#### 批量识别

```bash
POST /api/v1/asr/recognize
```

**请求示例**:

```json
{
  "audio_base64": "UklGRiQAAABXQVZFZm10...",
  "language": "zh",
  "enable_vad": true,
  "task": "transcribe"
}
```

**响应示例**:

```json
{
  "text": "你好，世界",
  "language": "zh",
  "confidence": 0.95,
  "segments": [
    {
      "start": 0.0,
      "end": 1.5,
      "text": "你好，世界"
    }
  ],
  "duration_ms": 1500,
  "processing_time_ms": 350
}
```

#### 文件上传识别

```bash
POST /api/v1/asr/recognize/upload
```

**请求**:

```bash
curl -X POST "http://localhost:8004/api/v1/asr/recognize/upload" \
  -F "file=@audio.wav" \
  -F "language=zh" \
  -F "enable_vad=true"
```

### 2. TTS（文本转语音）

#### 批量合成

```bash
POST /api/v1/tts/synthesize
```

**请求示例**:

```json
{
  "text": "你好，欢迎使用语音助手",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+0%",
  "pitch": "+0Hz",
  "format": "mp3"
}
```

**响应示例**:

```json
{
  "audio_base64": "SUQzBAAAAAAAI1RTU0UAAAA...",
  "duration_ms": 2500,
  "processing_time_ms": 450,
  "cached": false
}
```

#### 流式合成

```bash
POST /api/v1/tts/synthesize/stream
```

返回音频流，可直接播放。

#### 列出音色

```bash
GET /api/v1/tts/voices
```

**响应示例**:

```json
{
  "voices": [
    {
      "name": "zh-CN-XiaoxiaoNeural",
      "gender": "Female",
      "language": "zh-CN",
      "description": "晓晓（女声，活泼）"
    },
    {
      "name": "zh-CN-YunxiNeural",
      "gender": "Male",
      "language": "zh-CN",
      "description": "云希（男声，自然）"
    }
  ]
}
```

### 3. VAD（语音活动检测）

#### 检测语音活动

```bash
POST /api/v1/vad/detect
```

**请求示例**:

```json
{
  "audio_base64": "UklGRiQAAABXQVZFZm10...",
  "threshold": 0.3
}
```

**响应示例**:

```json
{
  "segments": [
    {
      "start_ms": 100,
      "end_ms": 1500,
      "is_speech": true,
      "confidence": null
    },
    {
      "start_ms": 2000,
      "end_ms": 3500,
      "is_speech": true,
      "confidence": null
    }
  ],
  "total_speech_duration_ms": 2900,
  "total_duration_ms": 5000,
  "speech_ratio": 0.58,
  "processing_time_ms": 150
}
```

#### 文件上传检测

```bash
POST /api/v1/vad/detect/upload
```

## 配置说明

| 配置项                        | 说明               | 默认值               |
| ----------------------------- | ------------------ | -------------------- |
| `ASR_PROVIDER`                | ASR 提供商         | whisper              |
| `WHISPER_MODEL`               | Whisper 模型大小   | base                 |
| `WHISPER_DEVICE`              | 推理设备           | cpu                  |
| `TTS_PROVIDER`                | TTS 提供商         | edge                 |
| `TTS_VOICE`                   | 默认音色           | zh-CN-XiaoxiaoNeural |
| `VAD_ENABLED`                 | 是否启用 VAD       | true                 |
| `VAD_THRESHOLD`               | VAD 阈值           | 0.3                  |
| `VAD_MIN_SPEECH_DURATION_MS`  | 最小语音段（毫秒） | 500                  |
| `VAD_MIN_SILENCE_DURATION_MS` | 静音超时（毫秒）   | 2000                 |
| `AUDIO_SAMPLE_RATE`           | 采样率             | 16000                |
| `MAX_AUDIO_DURATION_SECONDS`  | 最大音频时长       | 300（5 分钟）        |

## 架构设计

### ASR 处理流程

```
Audio Input
    |
    v
VAD (optional) ──> 过滤静音
    |
    v
Whisper Model ──> 语音识别
    |
    v
Text + Segments
```

### TTS 处理流程

```
Text Input
    |
    v
Cache Check ──> 命中缓存 ──> 返回
    |
    | (未命中)
    v
Edge TTS ──> 语音合成
    |
    v
Cache Store ──> 返回
```

### VAD 处理流程

```
Audio Input
    |
    v
Audio Preprocessing ──> 16kHz, 单声道
    |
    v
Silero VAD Model ──> 检测语音活动
    |
    v
Speech Segments
```

## 模型说明

### Whisper 模型选择

| 模型     | 参数量 | 精度 | 速度 | 推荐场景   |
| -------- | ------ | ---- | ---- | ---------- |
| `tiny`   | 39M    | 低   | 快   | 实时应用   |
| `base`   | 74M    | 中   | 快   | 通用场景   |
| `small`  | 244M   | 高   | 中   | 高精度要求 |
| `medium` | 769M   | 高   | 慢   | 离线转录   |
| `large`  | 1550M  | 最高 | 最慢 | 专业级应用 |

### Edge TTS 音色

支持多种中英文音色，包括：

- **中文**: 晓晓、云希、云扬、晓伊、云健等
- **英文**: Aria, Guy, Jenny, Davis 等

## 性能优化

- **模型缓存**: Whisper 和 VAD 模型启动时加载
- **TTS 缓存**: 相同文本复用合成结果
- **流式处理**: ASR 和 TTS 支持流式，降低首字节延迟
- **并发处理**: FastAPI 异步处理，支持高并发

## 监控指标

- `asr_recognize_duration_seconds`: ASR 识别延迟
- `tts_synthesize_duration_seconds`: TTS 合成延迟
- `vad_detect_duration_seconds`: VAD 检测延迟
- `tts_cache_hit_rate`: TTS 缓存命中率

## 故障排查

### Whisper 模型加载失败

```bash
# 检查 PyTorch 安装
python -c "import torch; print(torch.__version__)"

# 检查 GPU 可用性（可选）
python -c "import torch; print(torch.cuda.is_available())"

# 手动下载模型
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### Edge TTS 连接失败

```bash
# 检查网络连接
curl -I https://speech.platform.bing.com

# 测试 Edge TTS
edge-tts --text "Hello" --write-media hello.mp3
```

### VAD 模型加载失败

```bash
# 检查 PyTorch Hub 缓存
ls ~/.cache/torch/hub/

# 手动下载模型
python -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad')"
```

### ffmpeg 缺失

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# 验证安装
ffmpeg -version
```

## 开发指南

### 添加新的 ASR Provider

1. 在 `app/services/asr_service.py` 添加新的识别方法
2. 更新 `ASR_PROVIDER` 配置选项
3. 实现对应的 API 集成

### 添加新的 TTS Provider

1. 在 `app/services/tts_service.py` 添加新的合成方法
2. 更新 `TTS_PROVIDER` 配置选项
3. 实现音色列表和流式支持

### 自定义 VAD 参数

```python
# 在 app/core/config.py 中修改默认值
VAD_THRESHOLD: float = 0.3
VAD_MIN_SPEECH_DURATION_MS: int = 500
VAD_MIN_SILENCE_DURATION_MS: int = 2000
```

## 📚 相关文档

- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)
- [Edge TTS](https://github.com/rany2/edge-tts)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [OpenAI Whisper](https://github.com/openai/whisper)

## 📝 License

MIT License
