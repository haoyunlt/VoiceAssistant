"""
Image analysis endpoints (综合分析)
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.multimodal import ImageAnalysisRequest, ImageAnalysisResponse
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["Analysis"])

# 全局服务实例
analysis_service = AnalysisService()


@router.post("/image", response_model=ImageAnalysisResponse)
async def analyze_image(request: ImageAnalysisRequest):
    """
    图像综合分析

    - **image_url**: 图像 URL
    - **image_base64**: 图像 Base64 编码
    - **tasks**: 分析任务列表（description, objects, scene, colors, text）
    """
    try:
        logger.info(f"Image analysis request: tasks={request.tasks}")
        response = await analysis_service.analyze(request)
        logger.info("Image analysis completed")
        return response
    except Exception as e:
        logger.error(f"Image analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")


@router.post("/image/upload", response_model=ImageAnalysisResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    tasks: str = "description",
):
    """
    图像综合分析（文件上传）

    - **file**: 图像文件
    - **tasks**: 分析任务列表（逗号分隔，如 'description,text,scene'）
    """
    try:
        logger.info(f"Image analysis upload request: filename={file.filename}, tasks={tasks}")

        # 读取文件内容
        image_data = await file.read()

        # 分析
        task_list = [t.strip() for t in tasks.split(",")]
        response = await analysis_service.analyze_from_bytes(
            image_data=image_data,
            tasks=task_list,
        )

        logger.info("Image analysis completed")
        return response

    except Exception as e:
        logger.error(f"Image analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")
