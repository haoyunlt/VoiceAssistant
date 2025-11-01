"""
Voice processing data models
"""

from pydantic import BaseModel, Field


class ASRRequest(BaseModel):
    """ASR 识别请求"""

    audio_url: str | None = Field(None, description="音频文件 URL")
    audio_base64: str | None = Field(None, description="音频文件 Base64 编码")
    language: str | None = Field(None, description="语言代码（如 zh, en）")
    enable_vad: bool = Field(True, description="是否启用 VAD")
    task: str = Field("transcribe", description="任务类型：transcribe（转录）或 translate（翻译）")


class ASRResponse(BaseModel):
    """ASR 识别响应"""

    text: str = Field(..., description="识别文本")
    language: str = Field(..., description="检测到的语言")
    confidence: float | None = Field(None, description="置信度 (0-1)")
    segments: list[dict] | None = Field(None, description="分段信息（时间戳、文本）")
    duration_ms: float = Field(..., description="音频时长（毫秒）")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")


class StreamASRRequest(BaseModel):
    """流式 ASR 识别请求"""

    session_id: str = Field(..., description="会话 ID")
    language: str | None = Field(None, description="语言代码")
    enable_vad: bool = Field(True, description="是否启用 VAD")


class TTSRequest(BaseModel):
    """TTS 合成请求"""

    text: str = Field(..., description="待合成文本")
    voice: str | None = Field(None, description="音色")
    rate: str | None = Field(None, description="语速（如 +10%）")
    pitch: str | None = Field(None, description="音调（如 +5Hz）")
    format: str = Field("mp3", description="音频格式：mp3, wav, opus")
    cache_key: str | None = Field(None, description="缓存键（用于相同文本复用）")


class TTSResponse(BaseModel):
    """TTS 合成响应"""

    audio_url: str | None = Field(None, description="音频文件 URL")
    audio_base64: str | None = Field(None, description="音频文件 Base64 编码")
    duration_ms: float = Field(..., description="音频时长（毫秒）")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")
    cached: bool = Field(False, description="是否来自缓存")


class VoiceSegment(BaseModel):
    """语音片段"""

    start_ms: float = Field(..., description="开始时间（毫秒）")
    end_ms: float = Field(..., description="结束时间（毫秒）")
    is_speech: bool = Field(..., description="是否为语音")
    confidence: float | None = Field(None, description="置信度")


class VADRequest(BaseModel):
    """VAD 检测请求"""

    audio_url: str | None = Field(None, description="音频文件 URL")
    audio_base64: str | None = Field(None, description="音频文件 Base64 编码")
    threshold: float | None = Field(None, description="阈值 (0-1)")


class VADResponse(BaseModel):
    """VAD 检测响应"""

    segments: list[VoiceSegment] = Field(..., description="语音片段列表")
    total_speech_duration_ms: float = Field(..., description="总语音时长（毫秒）")
    total_duration_ms: float = Field(..., description="总时长（毫秒）")
    speech_ratio: float = Field(..., description="语音占比 (0-1)")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")
