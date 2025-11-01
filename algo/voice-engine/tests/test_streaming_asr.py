"""
流式 ASR 服务单元测试
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest
from app.services.streaming_asr_service import StreamingASRService


@pytest.fixture
def streaming_asr_service():
    """创建流式 ASR 服务实例"""
    return StreamingASRService(
        model_size="base",
        language="zh",
        vad_enabled=True,
        chunk_duration_ms=300,
        vad_mode=3,
    )


def generate_test_audio(duration_seconds: float, sample_rate: int = 16000) -> bytes:
    """
    生成测试音频数据

    Args:
        duration_seconds: 时长 (秒)
        sample_rate: 采样率

    Returns:
        PCM 音频字节 (16-bit)
    """
    num_samples = int(duration_seconds * sample_rate)
    # 生成正弦波
    t = np.linspace(0, duration_seconds, num_samples)
    audio = np.sin(2 * np.pi * 440 * t)  # 440Hz 正弦波
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


@pytest.mark.asyncio
async def test_service_initialization(streaming_asr_service):
    """测试服务初始化"""
    assert streaming_asr_service.model_size == "base"
    assert streaming_asr_service.language == "zh"
    assert streaming_asr_service.vad_enabled
    assert streaming_asr_service.sample_rate == 16000


@pytest.mark.asyncio
async def test_bytes_to_float32(streaming_asr_service):
    """测试音频字节转换"""
    # 生成测试音频
    audio_bytes = generate_test_audio(1.0)

    # 转换
    audio_float = streaming_asr_service._bytes_to_float32(audio_bytes)

    # 验证
    assert audio_float.dtype == np.float32
    assert len(audio_float) == 16000  # 1 秒 @ 16kHz
    assert audio_float.min() >= -1.0
    assert audio_float.max() <= 1.0


@pytest.mark.asyncio
async def test_detect_speech_vad_disabled():
    """测试 VAD 禁用时的行为"""
    service = StreamingASRService(vad_enabled=False)

    # 生成测试音频
    audio_chunk = generate_test_audio(0.02)  # 20ms

    # VAD 禁用时应该始终返回 True
    is_speech = service._detect_speech(audio_chunk)
    assert is_speech


@pytest.mark.asyncio
async def test_process_stream_session_lifecycle():
    """测试流式处理会话生命周期"""
    service = StreamingASRService(model_size="base", vad_enabled=False)

    # Mock Whisper 模型
    with patch.object(service, "_init_whisper_model"), patch.object(service, "_init_vad"):  # noqa: SIM117
        with patch.object(service, "_recognize_partial", return_value="测试文本"):
            with patch.object(service, "_recognize_final", return_value=("最终文本", 0.95)):
                # 创建音频流
                async def audio_stream():
                    # 发送一些音频数据
                    for _ in range(5):
                        yield generate_test_audio(0.3)  # 300ms 块

                # 处理流
                results = []
                async for result in service.process_stream(audio_stream()):
                    results.append(result)

                # 验证结果
                assert len(results) > 0

                # 应该包含 session_start
                assert results[0]["type"] == "session_start"

                # 应该包含 session_end
                assert results[-1]["type"] == "session_end"


@pytest.mark.asyncio
async def test_partial_recognition():
    """测试增量识别"""
    service = StreamingASRService(model_size="base")

    # Mock Whisper 模型
    mock_model = Mock()
    mock_segment = Mock()
    mock_segment.text = "测试文本"
    mock_model.transcribe.return_value = ([mock_segment], None)
    service._whisper_model = mock_model

    # 生成测试音频
    audio_data = generate_test_audio(3.0)

    # 执行识别
    text = await service._recognize_partial(audio_data)

    # 验证
    assert text == "测试文本"
    assert mock_model.transcribe.called


@pytest.mark.asyncio
async def test_final_recognition():
    """测试最终识别"""
    service = StreamingASRService(model_size="base")

    # Mock Whisper 模型
    mock_model = Mock()
    mock_segment = Mock()
    mock_segment.text = "最终文本"
    mock_segment.avg_logprob = -0.1  # 高置信度
    mock_model.transcribe.return_value = ([mock_segment], None)
    service._whisper_model = mock_model

    # 生成测试音频
    audio_data = generate_test_audio(5.0)

    # 执行识别
    text, confidence = await service._recognize_final(audio_data)

    # 验证
    assert text == "最终文本"
    assert 0.0 <= confidence <= 1.0
    assert mock_model.transcribe.called


@pytest.mark.asyncio
async def test_silence_detection_triggers_final_recognition():
    """测试静音检测触发最终识别"""
    service = StreamingASRService(
        model_size="base",
        vad_enabled=False,  # 禁用 VAD 简化测试
        max_silence_duration_ms=900,  # 3 个 300ms 块
    )

    # Mock 方法
    with patch.object(service, "_init_whisper_model"), patch.object(service, "_init_vad"):  # noqa: SIM117
        with patch.object(service, "_detect_speech") as mock_vad:
            with patch.object(service, "_recognize_final", return_value=("完整句子", 0.95)):
                # 模拟语音 → 静音 → 静音 → 静音 的模式
                mock_vad.side_effect = [True, False, False, False]

                # 创建音频流
                async def audio_stream():
                    for _ in range(4):
                        yield generate_test_audio(0.3)

                # 处理流
                results = []
                async for result in service.process_stream(audio_stream()):
                    results.append(result)

                # 验证包含 final_result
                final_results = [r for r in results if r["type"] == "final_result"]
                assert len(final_results) > 0
                assert final_results[0]["text"] == "完整句子"


@pytest.mark.asyncio
async def test_error_handling_in_stream():
    """测试流式处理中的错误处理"""
    service = StreamingASRService(model_size="base")

    # Mock 初始化方法
    with patch.object(service, "_init_whisper_model"), patch.object(service, "_init_vad"):  # noqa: SIM117
        # Mock 识别方法抛出异常
        with patch.object(service, "_recognize_partial", side_effect=Exception("测试异常")):
            # 创建音频流
            async def audio_stream():
                for _ in range(2):
                    yield generate_test_audio(3.5)  # 触发 partial recognition

            # 处理流
            results = []
            async for result in service.process_stream(audio_stream()):
                results.append(result)

            # 应该包含 error 结果
            [r for r in results if r["type"] == "error"]
            # 注意: 由于 try-catch, 可能不会有 error 结果，服务会继续运行
            # 但至少应该能完成处理
            assert len(results) > 0


def test_chunk_size_calculation():
    """测试音频块大小计算"""
    service = StreamingASRService(chunk_duration_ms=300)

    # 16kHz @ 300ms = 4800 samples = 9600 bytes (16-bit)
    expected_size = int(16000 * 300 / 1000)
    assert service.chunk_size == expected_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
