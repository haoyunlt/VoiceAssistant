# Voice Engine - Azure Speech 集成指南

> **功能状态**: ✅ 已实现
> **实现日期**: 2025-10-27
> **Sprint**: Sprint 2
> **版本**: v1.0.0

---

## 📖 概述

Voice Engine 现已集成 **Azure Cognitive Services Speech SDK**，提供：

- **Azure ASR** (Automatic Speech Recognition) - 高质量语音识别
- **Azure TTS** (Text-to-Speech) - Neural 语音合成
- **多厂商自动降级** - Azure ↔ Edge TTS / Faster-Whisper

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/voice-engine
pip install -r requirements.txt
```

### 2. 配置 Azure 密钥

```bash
# 设置环境变量
export AZURE_SPEECH_KEY="your_azure_speech_key"
export AZURE_SPEECH_REGION="eastasia"  # 或其他区域

# 或者在 .env 文件中配置
echo "AZURE_SPEECH_KEY=your_key" >> .env
echo "AZURE_SPEECH_REGION=eastasia" >> .env
```

**获取 Azure Speech 密钥**:

1. 登录 [Azure Portal](https://portal.azure.com)
2. 创建 "Speech Services" 资源
3. 在 "Keys and Endpoint" 页面获取密钥和区域

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

### 4. 测试 API

访问 [http://localhost:8004/docs](http://localhost:8004/docs) 查看 API 文档。

---

## 🎯 功能特性

### ✅ Azure ASR (语音识别)

**特性**:

- ✅ 高准确率（Azure Neural 模型）
- ✅ 多语言支持（zh-CN, en-US, ja-JP, etc.）
- ✅ 置信度评分
- ✅ 自动降级到 Faster-Whisper

**支持的语言**:

- 中文: zh-CN
- 英文: en-US
- 日文: ja-JP
- 韩文: ko-KR
- 西班牙文: es-ES
- 法文: fr-FR
- 德文: de-DE
- 俄文: ru-RU
- [更多...](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)

### ✅ Azure TTS (语音合成)

**特性**:

- ✅ Neural 语音（自然流畅）
- ✅ SSML 支持（语速、音调调整）
- ✅ 多语音选择（30+ 中文语音）
- ✅ 自动降级到 Edge TTS

**中文 Neural 语音**:
| 语音名称 | 性别 | 描述 |
| --- | --- | --- |
| zh-CN-XiaoxiaoNeural | 女 | 晓晓（温暖友好） |
| zh-CN-YunxiNeural | 男 | 云希（自然稳重） |
| zh-CN-YunyangNeural | 男 | 云扬（新闻播报） |
| zh-CN-XiaoyiNeural | 女 | 晓伊（温柔体贴） |
| zh-CN-YunjianNeural | 男 | 云健（运动解说） |
| zh-CN-XiaochenNeural | 女 | 晓辰（活泼可爱） |
| zh-CN-XiaohanNeural | 女 | 晓涵（亲切自然） |
| zh-CN-XiaomengNeural | 女 | 晓梦（甜美温柔） |
| zh-CN-XiaomoNeural | 女 | 晓墨（知性优雅） |
| zh-CN-XiaoqiuNeural | 女 | 晓秋（成熟稳重） |

### ✅ 多厂商自动降级

**降级策略**:

**ASR 降级链**:

```
1. Azure Speech ASR (首选，如果配置)
   ↓ (失败或未配置)
2. Faster-Whisper (本地，免费)
```

**TTS 降级链**:

```
1. Azure Speech TTS (首选，如果配置)
   ↓ (失败或未配置)
2. Edge TTS (免费)
```

**优点**:

- ✅ 高可用性（多重备份）
- ✅ 成本优化（优先使用免费服务）
- ✅ 透明降级（自动切换，无需手动干预）

---

## 🌐 API 端点

### ASR 多厂商识别

**POST** `/api/v1/asr/recognize/multi-vendor`

**请求**:

```json
{
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAA...",
  "language": "zh",
  "model_size": "base",
  "vendor_preference": "azure" // "azure" | "faster-whisper" | null
}
```

**响应**:

```json
{
  "text": "你好世界",
  "confidence": 0.95,
  "language": "zh-CN",
  "vendor": "azure" // 实际使用的厂商
}
```

### TTS 多厂商合成

**POST** `/api/v1/tts/synthesize/multi-vendor`

**请求**:

```json
{
  "text": "你好，欢迎使用语音助手",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+10%",
  "pitch": "+5%",
  "use_cache": true,
  "vendor_preference": "azure" // "azure" | "edge" | null
}
```

**响应**: 音频流（audio/mpeg）

**响应头**:

```
X-Vendor: azure
X-Audio-Size: 123456
```

### 列出所有可用语音

**GET** `/api/v1/tts/voices/list?vendor=all`

**查询参数**:

- `vendor`: 厂商筛选（`azure` | `edge` | `all`）

**响应**:

```json
{
  "vendor_filter": "all",
  "voices": [
    {
      "name": "zh-CN-XiaoxiaoNeural",
      "gender": "Female",
      "language": "zh-CN",
      "description": "晓晓（女声，温暖友好）",
      "vendor": "azure"
    }
    // ...
  ],
  "count": 24
}
```

### 获取厂商状态

**GET** `/api/v1/asr/vendors/status`

**响应**:

```json
{
  "preferred_asr": "faster-whisper",
  "services": {
    "azure": {
      "healthy": false,
      "error": "Azure not configured or failed to initialize"
    },
    "faster_whisper": {
      "healthy": true,
      "note": "Faster-Whisper is always available (local)"
    }
  }
}
```

**GET** `/api/v1/tts/vendors/status`

**响应**:

```json
{
  "preferred_tts": "edge",
  "services": {
    "azure": {
      "healthy": false,
      "error": "Azure not configured or failed to initialize"
    },
    "edge_tts": {
      "healthy": true,
      "note": "Edge TTS is always available (free)"
    }
  }
}
```

---

## ⚙️ 配置

### 环境变量

| 变量                  | 必需 | 默认值           | 描述                  |
| --------------------- | ---- | ---------------- | --------------------- |
| `AZURE_SPEECH_KEY`    | 否   | `""`             | Azure Speech 订阅密钥 |
| `AZURE_SPEECH_REGION` | 否   | `eastasia`       | Azure 区域            |
| `PREFERRED_ASR`       | 否   | `faster-whisper` | 首选 ASR 服务         |
| `PREFERRED_TTS`       | 否   | `edge`           | 首选 TTS 服务         |

### 配置示例

**.env 文件**:

```bash
# Azure Speech 配置（可选）
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=eastasia

# 多厂商首选项
PREFERRED_ASR=azure         # 优先使用 Azure ASR
PREFERRED_TTS=azure         # 优先使用 Azure TTS
```

**Python 代码**:

```python
from app.services.multi_vendor_adapter import MultiVendorSpeechAdapter

# 初始化适配器
adapter = MultiVendorSpeechAdapter(
    preferred_asr="azure",
    preferred_tts="azure",
    azure_key="your_key",
    azure_region="eastasia"
)

# ASR 识别（自动降级）
result = await adapter.recognize(
    audio_data=audio_bytes,
    language="zh",
    model_size="base"
)
print(f"识别结果: {result['text']}, 厂商: {result['vendor']}")

# TTS 合成（自动降级）
audio_data, vendor = await adapter.synthesize(
    text="你好世界",
    voice="zh-CN-XiaoxiaoNeural"
)
print(f"合成完成: {len(audio_data)} bytes, 厂商: {vendor}")
```

---

## 📊 性能对比

### ASR 性能

| 厂商           | 平均延迟    | 准确率     | 成本     | 备注           |
| -------------- | ----------- | ---------- | -------- | -------------- |
| **Azure ASR**  | ~300-500ms  | **95-98%** | **付费** | 高质量，多语言 |
| Faster-Whisper | ~500-1000ms | 85-90%     | 免费     | 本地，稳定     |

### TTS 性能

| 厂商          | 平均延迟    | 音质     | 成本     | 备注                  |
| ------------- | ----------- | -------- | -------- | --------------------- |
| **Azure TTS** | ~500-800ms  | **优秀** | **付费** | Neural 语音，自然流畅 |
| Edge TTS      | ~800-1200ms | 良好     | 免费     | 音质略差，但可用      |

### 成本分析

**Azure Speech 定价** (截至 2025-10):

- **ASR**: ¥7.5/小时音频（标准），¥14.5/小时（神经网络）
- **TTS**: ¥100/百万字符（Neural）

**推荐策略**:

- **开发/测试**: 使用免费服务（Edge TTS + Faster-Whisper）
- **生产环境**: 根据质量需求选择 Azure 或混合模式

---

## 🔧 故障排查

### 问题 1: Azure SDK 安装失败

**原因**: Azure SDK 依赖较多，可能安装失败

**解决**:

```bash
# 单独安装 Azure SDK
pip install azure-cognitiveservices-speech==1.38.0

# 如果失败，尝试升级 pip
pip install --upgrade pip
pip install azure-cognitiveservices-speech==1.38.0
```

### 问题 2: Azure API 返回 401 Unauthorized

**原因**: 密钥无效或未配置

**解决**:

1. 检查 `AZURE_SPEECH_KEY` 是否正确
2. 检查 `AZURE_SPEECH_REGION` 是否匹配（如 `eastasia`）
3. 验证密钥: [Azure Portal](https://portal.azure.com) → Speech Services → Keys and Endpoint

### 问题 3: Azure API 返回 429 Too Many Requests

**原因**: 超过 Azure 免费配额或速率限制

**解决**:

1. 等待一段时间后重试
2. 升级到付费套餐
3. 系统会自动降级到免费服务（Faster-Whisper / Edge TTS）

### 问题 4: 降级未生效

**原因**: 未正确捕获 Azure 错误

**解决**:

1. 查看日志: `logger.warning("Azure ASR failed: ..., falling back to Faster-Whisper")`
2. 确认 Faster-Whisper / Edge TTS 可用
3. 调用 `/api/v1/asr/vendors/status` 检查服务状态

### 问题 5: 音频识别为空

**原因**: 音频格式不正确

**解决**:

- 确保音频为 **16kHz, 16-bit, mono PCM** 格式
- Azure 支持多种格式，但建议使用 PCM

---

## 📚 最佳实践

### 1. 成本优化

**策略**:

```python
# 默认使用免费服务
adapter = MultiVendorSpeechAdapter(
    preferred_asr="faster-whisper",  # 免费
    preferred_tts="edge"              # 免费
)

# 仅在需要高质量时使用 Azure
result = await adapter.recognize(audio_data, language="zh")
if result["confidence"] < 0.7:
    # 置信度低，尝试 Azure
    adapter.preferred_asr = "azure"
    result = await adapter.recognize(audio_data, language="zh")
```

### 2. 高可用性

**策略**:

- ✅ 始终配置多个厂商
- ✅ 启用自动降级
- ✅ 监控厂商状态

```python
# 定期检查服务状态
status = adapter.get_status()
if not status["services"]["azure"]["healthy"]:
    logger.warning("Azure Speech is down, using fallback services")
```

### 3. 缓存优化

**策略**:

```python
# TTS 合成时启用缓存（默认启用）
audio_data, vendor = await adapter.synthesize(
    text="常用语句",
    use_cache=True  # 缓存命中时延迟 < 10ms
)
```

### 4. 语音选择

**策略**:

- 中文场景: `zh-CN-XiaoxiaoNeural`（温暖友好）
- 新闻播报: `zh-CN-YunyangNeural`（专业正式）
- 客服场景: `zh-CN-XiaoyiNeural`（温柔体贴）
- 运动解说: `zh-CN-YunjianNeural`（活力激情）

```python
# 根据场景选择语音
scenarios = {
    "customer_service": "zh-CN-XiaoyiNeural",
    "news": "zh-CN-YunyangNeural",
    "sports": "zh-CN-YunjianNeural",
    "default": "zh-CN-XiaoxiaoNeural"
}

voice = scenarios.get(scenario, scenarios["default"])
```

---

## 🧪 测试

### 单元测试

```bash
cd algo/voice-engine
pytest tests/test_azure_speech.py -v
```

### 手动测试

**测试 ASR**:

```bash
curl -X POST "http://localhost:8004/api/v1/asr/recognize/multi-vendor" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAA...",
    "language": "zh",
    "vendor_preference": "azure"
  }'
```

**测试 TTS**:

```bash
curl -X POST "http://localhost:8004/api/v1/tts/synthesize/multi-vendor" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，这是 Azure Speech 测试",
    "voice": "zh-CN-XiaoxiaoNeural",
    "vendor_preference": "azure"
  }' \
  --output test_azure.mp3
```

**查看厂商状态**:

```bash
# ASR 状态
curl "http://localhost:8004/api/v1/asr/vendors/status"

# TTS 状态
curl "http://localhost:8004/api/v1/tts/vendors/status"
```

---

## 📖 参考资源

- [Azure Speech SDK 文档](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/)
- [Azure Speech 定价](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/)
- [支持的语言](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)
- [Neural 语音列表](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt-tts)
- [SSML 参考](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup)

---

## 📞 支持

**负责人**: AI Engineer
**问题反馈**: #sprint2-azure-speech
**文档版本**: v1.0.0

---

**最后更新**: 2025-10-27
**状态**: ✅ 已完成
