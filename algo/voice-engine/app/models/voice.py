"""
Voice processing data models
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ASRRequest(BaseModel):
    """ASR 识别请求"""

    audio_url: Optional[str] = Field(None, description="音频文件 URL")
    audio_base64: Optional[str] = Field(None, description="音频文件 Base64 编码")
    language: Optional[str] = Field(None, description="语言代码（如 zh, en）")
    enable_vad: bool = Field(True, description="是否启用 VAD")
    task: str = Field("transcribe", description="任务类型：transcribe（转录）或 translate（翻译）")


class ASRResponse(BaseModel):
    """ASR 识别响应"""

    text: str = Field(..., description="识别文本")
    language: str = Field(..., description="检测到的语言")
    confidence: Optional[float] = Field(None, description="置信度 (0-1)")
    segments: Optional[List[dict]] = Field(None, description="分段信息（时间戳、文本）")
    duration_ms: float = Field(..., description="音频时长（毫秒）")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")


class StreamASRRequest(BaseModel):
    """流式 ASR 识别请求"""

    session_id: str = Field(..., description="会话 ID")
    language: Optional[str] = Field(None, description="语言代码")
    enable_vad: bool = Field(True, description="是否启用 VAD")


class TTSRequest(BaseModel):
    """TTS 合成请求"""

    text: str = Field(..., description="待合成文本")
    voice: Optional[str] = Field(None, description="音色")
    rate: Optional[str] = Field(None, description="语速（如 +10%）")
    pitch: Optional[str] = Field(None, description="音调（如 +5Hz）")
    format: str = Field("mp3", description="音频格式：mp3, wav, opus")
    cache_key: Optional[str] = Field(None, description="缓存键（用于相同文本复用）")


class TTSResponse(BaseModel):
    """TTS 合成响应"""

    audio_url: Optional[str] = Field(None, description="音频文件 URL")
    audio_base64: Optional[str] = Field(None, description="音频文件 Base64 编码")
    duration_ms: float = Field(..., description="音频时长（毫秒）")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")
    cached: bool = Field(False, description="是否来自缓存")


class VoiceSegment(BaseModel):
    """语音片段"""

    start_ms: float = Field(..., description="开始时间（毫秒）")
    end_ms: float = Field(..., description="结束时间（毫秒）")
    is_speech: bool = Field(..., description="是否为语音")
    confidence: Optional[float] = Field(None, description="置信度")


class VADRequest(BaseModel):
    """VAD 检测请求"""

    audio_url: Optional[str] = Field(None, description="音频文件 URL")
    audio_base64: Optional[str] = Field(None, description="音频文件 Base64 编码")
    threshold: Optional[float] = Field(None, description="阈值 (0-1)")


class VADResponse(BaseModel):
    """VAD 检测响应"""

    segments: List[VoiceSegment] = Field(..., description="语音片段列表")
    total_speech_duration_ms: float = Field(..., description="总语音时长（毫秒）")
    total_duration_ms: float = Field(..., description="总时长（毫秒）")
    speech_ratio: float = Field(..., description="语音占比 (0-1)")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")
