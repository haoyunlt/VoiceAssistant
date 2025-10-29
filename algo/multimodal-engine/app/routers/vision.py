"""
Vision understanding endpoints (using Vision LLMs)
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.multimodal import VisionRequest, VisionResponse
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/vision", tags=["Vision"])

# 全局服务实例
vision_service = VisionService()


@router.post("/understand", response_model=VisionResponse)
async def understand_image(request: VisionRequest):
    """
    视觉理解（使用 Vision LLM）

    - **image_url**: 图像 URL
    - **image_base64**: 图像 Base64 编码
    - **prompt**: 问题或指令
    - **model**: 模型名称（可选）
    - **max_tokens**: 最大 Token 数（可选）
    - **detail**: 图像细节级别（auto, low, high）
    """
    try:
        logger.info(f"Vision request: prompt={request.prompt[:50]}...")
        response = await vision_service.understand(request)
        logger.info(f"Vision completed: answer length={len(response.answer)}")
        return response
    except Exception as e:
        logger.error(f"Vision understanding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Vision understanding failed: {str(e)}")


@router.post("/understand/upload", response_model=VisionResponse)
async def understand_upload(
    file: UploadFile = File(...),
    prompt: str = "请描述这张图片",
    model: str = None,
    max_tokens: int = None,
):
    """
    视觉理解（文件上传）

    - **file**: 图像文件
    - **prompt**: 问题或指令
    - **model**: 模型名称（可选）
    - **max_tokens**: 最大 Token 数（可选）
    """
    try:
        logger.info(f"Vision upload request: filename={file.filename}, prompt={prompt[:50]}...")

        # 读取文件内容
        image_data = await file.read()

        # 理解
        response = await vision_service.understand_from_bytes(
            image_data=image_data,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )

        logger.info(f"Vision completed: answer length={len(response.answer)}")
        return response

    except Exception as e:
        logger.error(f"Vision understanding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Vision understanding failed: {str(e)}")
