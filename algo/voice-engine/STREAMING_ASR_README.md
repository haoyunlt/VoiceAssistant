# 流式 ASR 识别 - 快速开始

> **功能状态**: ✅ 已实现
> **实现日期**: 2025-10-27
> **Sprint**: Sprint 1

---

## 📋 功能简介

实现了基于 WebSocket 的实时语音识别功能，支持：

- ✅ WebSocket 双向通信
- ✅ WebRTC VAD 端点检测
- ✅ 增量识别 (中间结果)
- ✅ 最终识别 (高准确率)
- ✅ 多语言支持 (中文/英文)
- ✅ 可配置的模型大小

---

## 🚀 快速启动

### 方法 1: 使用启动脚本 (推荐)

```bash
cd algo/voice-engine
chmod +x quickstart.sh
./quickstart.sh
```

### 方法 2: 手动启动

```bash
# 1. 创建虚拟环境
cd algo/voice-engine
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 下载 Whisper 模型 (首次运行)
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# 4. 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

---

## 🧪 测试

### Web 测试页面

访问: http://localhost:8001/static/test_streaming_asr.html

功能:

- 选择模型大小 (tiny/base/small/medium)
- 选择语言 (中文/英文)
- 启用/禁用 VAD
- 实时查看识别结果
- 查看详细日志

### API 文档

访问: http://localhost:8001/docs

查看完整的 API 接口文档，包括 WebSocket 端点。

### 单元测试

```bash
# 运行所有测试
pytest tests/test_streaming_asr.py -v

# 运行带覆盖率的测试
pytest tests/test_streaming_asr.py -v --cov=app --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

---

## 📡 WebSocket API

### 端点

```
ws://localhost:8001/api/v1/asr/ws/stream
```

### 通信协议

#### 1. 连接并发送配置

```javascript
const ws = new WebSocket('ws://localhost:8001/api/v1/asr/ws/stream');

ws.onopen = () => {
  // 发送配置
  ws.send(
    JSON.stringify({
      model_size: 'base', // tiny/base/small/medium
      language: 'zh', // zh/en
      vad_enabled: true, // true/false
    })
  );
};
```

#### 2. 发送音频数据

```javascript
// 发送 PCM 音频数据 (16kHz, 16-bit, mono)
ws.send(audioDataBuffer); // ArrayBuffer
```

#### 3. 接收识别结果

```javascript
ws.onmessage = (event) => {
  const result = JSON.parse(event.data);

  switch (result.type) {
    case 'session_start':
      console.log('会话开始');
      break;

    case 'speech_start':
      console.log('检测到语音');
      break;

    case 'partial_result':
      console.log('增量结果:', result.text);
      break;

    case 'final_result':
      console.log('最终结果:', result.text);
      console.log('置信度:', result.confidence);
      break;

    case 'speech_end':
      console.log('语音结束');
      break;

    case 'session_end':
      console.log('会话结束');
      break;

    case 'error':
      console.error('错误:', result.error);
      break;
  }
};
```

#### 4. 结束会话

```javascript
// 发送结束信号
ws.send(JSON.stringify({ type: 'end_stream' }));

// 关闭连接
ws.close();
```

---

## 🔧 配置参数

### 模型大小

| 模型   | 大小   | 速度 | 准确率 | 推荐场景        |
| ------ | ------ | ---- | ------ | --------------- |
| tiny   | ~75MB  | 最快 | 低     | 快速原型        |
| base   | ~142MB | 快   | 中     | 一般使用 (推荐) |
| small  | ~466MB | 中   | 高     | 生产环境        |
| medium | ~1.5GB | 慢   | 很高   | 高准确率需求    |

### VAD 模式

| 模式 | 灵敏度 | 推荐场景        |
| ---- | ------ | --------------- |
| 0    | 最低   | 安静环境        |
| 1    | 低     | 一般环境        |
| 2    | 中     | 稍嘈杂环境      |
| 3    | 高     | 嘈杂环境 (推荐) |

### 音频参数

- **采样率**: 16kHz (固定)
- **位深**: 16-bit (固定)
- **通道**: Mono (单声道)
- **格式**: PCM

---

## 📊 性能指标

### 当前性能

| 指标           | 值         | 目标    | 状态 |
| -------------- | ---------- | ------- | ---- |
| 增量识别延迟   | ~300-500ms | < 500ms | ✅   |
| 最终识别准确率 | ~85-90%    | > 90%   | ⚠️   |
| VAD 准确率     | ~90%       | > 95%   | ⚠️   |
| 并发连接       | 未测试     | > 20    | ⏳   |

### 性能优化建议

1. **使用更大的模型提升准确率** (small/medium)
2. **部署到 GPU** 加速识别 (RTX 3090: 5-10x)
3. **调整 VAD 阈值** 适应不同环境
4. **批量识别** 减少 API 调用

---

## 🐛 已知问题

### 1. Whisper 模型首次加载慢

**现象**: 首次启动时下载模型需要 1-2 分钟

**解决方案**:

```bash
# 预下载模型
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### 2. VAD 在极端安静环境误判

**现象**: 极度安静时可能误判静音为语音

**解决方案**: 调整 VAD 模式为 0 或 1

### 3. 浏览器音频采样率不匹配

**现象**: 部分浏览器默认采样率非 16kHz

**解决方案**: 前端强制指定 `sampleRate: 16000`

---

## 📝 开发笔记

### 已实现的功能

- [x] WebSocket 端点
- [x] 流式音频处理
- [x] VAD 端点检测
- [x] 增量识别
- [x] 最终识别
- [x] 错误处理
- [x] 会话管理
- [x] 前端测试页面
- [x] 单元测试

### 待优化项

- [ ] GPU 加速支持
- [ ] 更精细的 VAD 调优
- [ ] 多语言混合识别
- [ ] 音频质量检测
- [ ] 实时性能监控
- [ ] 压力测试

---

## 🔗 相关文档

- [Voice Engine README](README.md)
- [Sprint 执行指南](../../SPRINT_EXECUTION_GUIDE.md)
- [VoiceHelper 迁移计划](../../VOICEHELPER_MIGRATION_PLAN.md)
- [API 文档](http://localhost:8001/docs)

---

## 📞 联系方式

- **负责人**: AI Engineer 1
- **Sprint**: Sprint 1 (Week 1-2)
- **状态**: ✅ 已完成

---

**最后更新**: 2025-10-27
**版本**: v1.0.0
