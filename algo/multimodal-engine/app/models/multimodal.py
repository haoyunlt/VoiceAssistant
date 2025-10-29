"""
Multimodal processing data models
"""

from typing import Any

from pydantic import BaseModel, Field


class OCRTextBlock(BaseModel):
    """OCR 文本块"""

    text: str = Field(..., description="识别的文本")
    confidence: float = Field(..., description="置信度 (0-1)")
    bbox: list[list[int]] = Field(..., description="边界框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]")
    language: str | None = Field(None, description="语言")


class OCRRequest(BaseModel):
    """OCR 识别请求"""

    image_url: str | None = Field(None, description="图像 URL")
    image_base64: str | None = Field(None, description="图像 Base64 编码")
    languages: list[str] | None = Field(None, description="语言列表（如 ['ch', 'en']）")
    detect_orientation: bool = Field(True, description="是否检测文字方向")
    confidence_threshold: float | None = Field(None, description="置信度阈值")


class OCRResponse(BaseModel):
    """OCR 识别响应"""

    text_blocks: list[OCRTextBlock] = Field(..., description="文本块列表")
    full_text: str = Field(..., description="完整文本")
    language: str = Field(..., description="主要语言")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")


class VisionRequest(BaseModel):
    """视觉理解请求"""

    image_url: str | None = Field(None, description="图像 URL")
    image_base64: str | None = Field(None, description="图像 Base64 编码")
    prompt: str = Field(..., description="问题或指令")
    model: str | None = Field(None, description="模型名称")
    max_tokens: int | None = Field(None, description="最大 Token 数")
    detail: str = Field("auto", description="图像细节级别：auto, low, high")


class VisionResponse(BaseModel):
    """视觉理解响应"""

    answer: str = Field(..., description="回答")
    model: str = Field(..., description="使用的模型")
    tokens_used: int | None = Field(None, description="使用的 Token 数")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")


class ImageAnalysisRequest(BaseModel):
    """图像分析请求"""

    image_url: str | None = Field(None, description="图像 URL")
    image_base64: str | None = Field(None, description="图像 Base64 编码")
    tasks: list[str] = Field(
        default_factory=lambda: ["description"],
        description="分析任务列表：description, objects, scene, colors, text",
    )


class ImageAnalysisResponse(BaseModel):
    """图像分析响应"""

    description: str | None = Field(None, description="图像描述")
    objects: list[dict[str, Any]] | None = Field(None, description="检测到的物体")
    scene: str | None = Field(None, description="场景类型")
    colors: list[str] | None = Field(None, description="主要颜色")
    text: str | None = Field(None, description="图像中的文本（OCR）")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据（尺寸、格式等）")
    processing_time_ms: float = Field(..., description="处理时间（毫秒）")
