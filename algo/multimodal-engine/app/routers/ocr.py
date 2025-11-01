"""
OCR (Optical Character Recognition) endpoints
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.multimodal import OCRRequest, OCRResponse
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"])

# 全局服务实例
ocr_service = OCRService()


@router.post("/recognize", response_model=OCRResponse)
async def recognize_text(request: OCRRequest):
    """
    OCR 文字识别

    - **image_url**: 图像 URL
    - **image_base64**: 图像 Base64 编码
    - **languages**: 语言列表
    - **detect_orientation**: 是否检测文字方向
    - **confidence_threshold**: 置信度阈值
    """
    try:
        logger.info(f"OCR request: languages={request.languages}")
        response = await ocr_service.recognize(request)
        logger.info(f"OCR completed: found {len(response.text_blocks)} text blocks")
        return response
    except Exception as e:
        logger.error(f"OCR recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR recognition failed: {str(e)}") from e


@router.post("/recognize/upload", response_model=OCRResponse)
async def recognize_upload(
    file: UploadFile = File(...),
    languages: str = None,
    detect_orientation: bool = True,
    confidence_threshold: float = None,
):
    """
    OCR 文字识别（文件上传）

    - **file**: 图像文件
    - **languages**: 语言列表（逗号分隔，如 'ch,en'）
    - **detect_orientation**: 是否检测文字方向
    - **confidence_threshold**: 置信度阈值
    """
    try:
        logger.info(f"OCR upload request: filename={file.filename}")

        # 读取文件内容
        image_data = await file.read()

        # 识别
        language_list = languages.split(",") if languages else None
        response = await ocr_service.recognize_from_bytes(
            image_data=image_data,
            languages=language_list,
            detect_orientation=detect_orientation,
            confidence_threshold=confidence_threshold,
        )

        logger.info(f"OCR completed: found {len(response.text_blocks)} text blocks")
        return response

    except Exception as e:
        logger.error(f"OCR recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR recognition failed: {str(e)}") from e
