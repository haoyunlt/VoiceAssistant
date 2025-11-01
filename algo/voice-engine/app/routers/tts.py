"""
TTS (Text-to-Speech) endpoints
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.voice import TTSRequest, TTSResponse
from app.services.multi_vendor_adapter import get_multi_vendor_adapter
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])

# 全局服务实例
tts_service = TTSService()


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(request: TTSRequest):
    """
    文本转语音（批量模式）

    - **text**: 待合成文本
    - **voice**: 音色（可选）
    - **rate**: 语速（可选，如 +10%）
    - **pitch**: 音调（可选，如 +5Hz）
    - **format**: 音频格式（mp3, wav, opus）
    - **cache_key**: 缓存键（可选）
    """
    try:
        logger.info(f"TTS request: text length={len(request.text)}, voice={request.voice}")
        response = await tts_service.synthesize(request)
        logger.info(f"TTS completed: duration={response.duration_ms}ms, cached={response.cached}")
        return response
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}") from e


@router.post("/synthesize/stream")
async def synthesize_stream(request: TTSRequest):
    """
    流式文本转语音

    - **text**: 待合成文本
    - **voice**: 音色（可选）
    - **rate**: 语速（可选）
    - **pitch**: 音调（可选）

    返回音频流
    """
    try:
        logger.info(f"TTS stream request: text length={len(request.text)}")

        # 生成音频流
        audio_stream = await tts_service.synthesize_stream(request)

        return StreamingResponse(
            audio_stream,
            media_type=f"audio/{request.format}",
            headers={
                "Content-Disposition": f'attachment; filename="speech.{request.format}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    except Exception as e:
        logger.error(f"TTS stream synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS stream synthesis failed: {str(e)}") from e


@router.get("/voices")
async def list_voices():
    """
    列出可用的音色

    返回支持的音色列表
    """
    try:
        voices = await tts_service.list_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Failed to list voices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}") from e


@router.get("/cache/stats")
async def get_cache_stats():
    """
    获取缓存统计信息

    返回缓存的统计数据，包括：
    - total_entries: 总缓存条目数
    - total_size_mb: 总缓存大小（MB）
    - total_hits: 总命中次数
    - hit_rate: 命中率
    - avg_audio_size_kb: 平均音频大小（KB）
    """
    try:
        stats = tts_service.get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}") from e


@router.post("/cache/clear")
async def clear_cache():
    """
    清空缓存

    清空所有 TTS 缓存数据
    """
    try:
        tts_service.clear_cache()
        logger.info("TTS cache cleared")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}") from e


@router.get("/cache/health")
async def check_cache_health():
    """
    检查缓存健康状态

    返回缓存后端的健康状态
    """
    try:
        health = tts_service.health_check()
        return health
    except Exception as e:
        logger.error(f"Cache health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}") from e


# ===== Multi-Vendor Endpoints =====


class MultiVendorTTSRequest(BaseModel):
    """多厂商 TTS 请求"""

    text: str
    voice: str | None = None
    rate: str = "0%"
    pitch: str = "0%"
    use_cache: bool = True
    vendor_preference: Literal["azure", "edge"] | None = None


@router.post("/synthesize/multi-vendor", summary="多厂商 TTS 合成（自动降级）")
async def synthesize_multi_vendor(request: MultiVendorTTSRequest):
    """
    多厂商 TTS 合成（支持自动降级）

    降级策略：
    1. 如果 vendor_preference 为 "azure" 且 Azure 可用 -> Azure
    2. 否则 -> Edge TTS

    Args:
        - **text**: 待合成文本
        - **voice**: 语音名称（None 时使用默认）
        - **rate**: 语速（-50% ~ +100%）
        - **pitch**: 音调（-50% ~ +50%）
        - **use_cache**: 是否使用缓存
        - **vendor_preference**: 首选厂商（azure | edge | None）

    Returns:
        音频流（audio/mpeg 或 audio/wav）
    """
    try:
        import io

        # 获取适配器
        adapter = get_multi_vendor_adapter()

        # 如果指定了厂商偏好，临时修改适配器配置
        if request.vendor_preference:
            original_preference = adapter.preferred_tts
            adapter.preferred_tts = request.vendor_preference

            audio_data, vendor = await adapter.synthesize(
                text=request.text,
                voice=request.voice,
                rate=request.rate,
                pitch=request.pitch,
                use_cache=request.use_cache,
            )

            # 恢复原始配置
            adapter.preferred_tts = original_preference
        else:
            audio_data, vendor = await adapter.synthesize(
                text=request.text,
                voice=request.voice,
                rate=request.rate,
                pitch=request.pitch,
                use_cache=request.use_cache,
            )

        logger.info(
            f"Multi-vendor TTS completed: vendor={vendor}, audio_size={len(audio_data)} bytes"
        )

        # 返回音频流
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "X-Vendor": vendor,
                "X-Audio-Size": str(len(audio_data)),
            },
        )

    except Exception as e:
        logger.error(f"Multi-vendor TTS failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-vendor TTS failed: {str(e)}") from e


@router.get("/voices/list", summary="列出所有可用语音")
async def list_all_voices(
    vendor: Literal["azure", "edge", "all"] = Query("all", description="厂商筛选"),
):
    """
    列出所有可用的语音

    Args:
        vendor: 厂商筛选（azure | edge | all）

    Returns:
        语音列表
    """
    try:
        adapter = get_multi_vendor_adapter()
        voices = adapter.list_voices(vendor=vendor)

        return {
            "vendor_filter": vendor,
            "voices": voices,
            "count": len(voices),
        }

    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/vendors/status", summary="获取所有 TTS 厂商状态")
async def get_vendors_status_tts():
    """
    获取所有 TTS 厂商的状态

    Returns:
        状态字典
    """
    try:
        adapter = get_multi_vendor_adapter()
        status = adapter.get_status()

        # 仅返回 TTS 相关状态
        return {
            "preferred_tts": status["preferred_tts"],
            "services": {
                "azure": status["services"].get("azure", {}),
                "edge_tts": status["services"].get("edge_tts", {}),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get vendors status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
