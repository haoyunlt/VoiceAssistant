"""音频处理工具函数"""

import io

from pydub import AudioSegment


def extract_audio_segment(
    audio_data: bytes, start_ms: float, end_ms: float, format: str = "wav"
) -> bytes:
    """提取音频片段

    Args:
        audio_data: 原始音频数据
        start_ms: 开始时间（毫秒）
        end_ms: 结束时间（毫秒）
        format: 音频格式

    Returns:
        音频片段数据
    """
    # 加载音频
    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)

    # 提取片段
    segment = audio[start_ms:end_ms]

    # 导出为bytes
    output_buffer = io.BytesIO()
    segment.export(output_buffer, format=format)
    output_buffer.seek(0)

    return output_buffer.read()


def convert_audio_format(
    audio_data: bytes,
    from_format: str,
    to_format: str,
    sample_rate: int = None,
    channels: int = None,
) -> bytes:
    """转换音频格式

    Args:
        audio_data: 原始音频数据
        from_format: 源格式
        to_format: 目标格式
        sample_rate: 采样率（可选）
        channels: 声道数（可选）

    Returns:
        转换后的音频数据
    """
    # 加载音频
    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=from_format)

    # 设置采样率
    if sample_rate:
        audio = audio.set_frame_rate(sample_rate)

    # 设置声道数
    if channels:
        audio = audio.set_channels(channels)

    # 导出
    output_buffer = io.BytesIO()
    audio.export(output_buffer, format=to_format)
    output_buffer.seek(0)

    return output_buffer.read()


def get_audio_duration(audio_data: bytes, format: str = "wav") -> float:
    """获取音频时长（秒）

    Args:
        audio_data: 音频数据
        format: 音频格式

    Returns:
        时长（秒）
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)
    return len(audio) / 1000.0  # 毫秒转秒


def merge_audio_segments(segments: list[bytes], format: str = "wav") -> bytes:
    """合并多个音频片段

    Args:
        segments: 音频片段列表
        format: 音频格式

    Returns:
        合并后的音频数据
    """
    if not segments:
        return b""

    # 加载第一个片段
    merged = AudioSegment.from_file(io.BytesIO(segments[0]), format=format)

    # 合并其他片段
    for segment_data in segments[1:]:
        segment = AudioSegment.from_file(io.BytesIO(segment_data), format=format)
        merged += segment

    # 导出
    output_buffer = io.BytesIO()
    merged.export(output_buffer, format=format)
    output_buffer.seek(0)

    return output_buffer.read()


def normalize_audio(audio_data: bytes, target_dbfs: float = -20.0, format: str = "wav") -> bytes:
    """音频音量归一化

    Args:
        audio_data: 音频数据
        target_dbfs: 目标音量（dBFS）
        format: 音频格式

    Returns:
        归一化后的音频数据
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)

    # 计算增益
    change_in_dbfs = target_dbfs - audio.dBFS

    # 应用增益
    normalized_audio = audio.apply_gain(change_in_dbfs)

    # 导出
    output_buffer = io.BytesIO()
    normalized_audio.export(output_buffer, format=format)
    output_buffer.seek(0)

    return output_buffer.read()
