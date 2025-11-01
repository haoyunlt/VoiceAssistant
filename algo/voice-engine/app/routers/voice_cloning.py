"""
Voice Cloning API Router - P2级功能
语音克隆服务API接口

功能：
1. 创建语音配置文件
2. 添加语音样本
3. 训练声纹模型
4. 使用声纹合成语音
5. 管理声纹配置
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.voice_cloning_service import VoiceCloningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice-cloning", tags=["Voice Cloning"])

# 全局服务实例（懒加载）
_voice_cloning_service = None


def get_service() -> VoiceCloningService:
    """获取语音克隆服务实例"""
    global _voice_cloning_service
    if _voice_cloning_service is None:
        logger.info("Initializing Voice Cloning Service...")
        _voice_cloning_service = VoiceCloningService()
    return _voice_cloning_service


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateProfileRequest(BaseModel):
    """创建配置文件请求"""

    user_id: str = Field(..., description="用户ID")
    profile_name: str = Field(..., description="配置文件名称")
    language: str = Field("zh-CN", description="语言代码")


class ProfileResponse(BaseModel):
    """配置文件响应"""

    success: bool
    profile_id: str | None = None
    profile: dict | None = None
    error: str | None = None


class AddSampleResponse(BaseModel):
    """添加样本响应"""

    success: bool
    sample_id: str | None = None
    sample_count: int | None = None
    can_train: bool | None = None
    recommended_samples: int | None = None
    error: str | None = None


class TrainProfileRequest(BaseModel):
    """训练配置文件请求"""

    profile_id: str = Field(..., description="配置文件ID")
    training_config: dict | None = Field(None, description="训练配置（可选）")


class TrainProfileResponse(BaseModel):
    """训练配置文件响应"""

    success: bool
    profile_id: str | None = None
    status: str | None = None
    message: str | None = None
    error: str | None = None


class SynthesizeRequest(BaseModel):
    """语音合成请求"""

    profile_id: str = Field(..., description="配置文件ID")
    text: str = Field(..., description="要合成的文本", min_length=1, max_length=500)
    output_format: str = Field("wav", description="输出格式（wav/mp3）")


class SynthesizeResponse(BaseModel):
    """语音合成响应"""

    success: bool
    audio_base64: str | None = None  # Base64编码的音频数据
    format: str | None = None
    text: str | None = None
    profile_id: str | None = None
    error: str | None = None


class ProfileListResponse(BaseModel):
    """配置文件列表响应"""

    success: bool
    profiles: list[dict] = []
    count: int = 0


class TrainingSuggestionsResponse(BaseModel):
    """训练建议响应"""

    success: bool
    profile_id: str | None = None
    can_train: bool | None = None
    suggestions: list[dict] = []
    error: str | None = None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/profiles", response_model=ProfileResponse)
async def create_profile(request: CreateProfileRequest):
    """
    创建语音配置文件

    开始一个新的语音克隆项目。需要先创建配置文件，然后添加语音样本。

    参数：
    - **user_id**: 用户ID
    - **profile_name**: 配置文件名称（唯一标识）
    - **language**: 语言代码（默认zh-CN）

    返回：
    - **profile_id**: 创建的配置文件ID
    - **profile**: 配置文件详细信息
    """
    try:
        service = get_service()
        result = await service.create_profile(
            user_id=request.user_id, profile_name=request.profile_name, language=request.language
        )

        logger.info(f"Profile created: {request.profile_name} for user {request.user_id}")

        return ProfileResponse(**result)

    except Exception as e:
        logger.error(f"Create profile failed: {e}", exc_info=True)
        return ProfileResponse(success=False, error=f"Failed to create profile: {str(e)}")


@router.post("/profiles/{profile_id}/samples", response_model=AddSampleResponse)
async def add_sample(
    profile_id: str,
    audio: UploadFile = File(..., description="音频文件（WAV格式，2-10秒）"),
    text: str = Form(..., description="对应的文本内容"),
):
    """
    添加语音样本

    为配置文件添加一个语音样本。建议收集50个样本以获得最佳效果。

    要求：
    - 音频格式：WAV，16kHz
    - 音频长度：2-10秒
    - 录音环境：安静，无背景噪音
    - 文本内容：与音频内容完全一致

    参数：
    - **profile_id**: 配置文件ID
    - **audio**: 音频文件
    - **text**: 对应文本

    返回：
    - **sample_id**: 样本ID
    - **sample_count**: 当前样本数量
    - **can_train**: 是否可以开始训练
    """
    try:
        service = get_service()

        # 读取音频数据
        audio_data = await audio.read()

        result = await service.add_sample(profile_id=profile_id, audio_data=audio_data, text=text)

        logger.info(
            f"Sample added to profile {profile_id}: {result.get('sample_count', 0)} total samples"
        )

        return AddSampleResponse(**result)

    except Exception as e:
        logger.error(f"Add sample failed: {e}", exc_info=True)
        return AddSampleResponse(success=False, error=f"Failed to add sample: {str(e)}")


@router.post("/profiles/{profile_id}/train", response_model=TrainProfileResponse)
async def train_profile(profile_id: str, training_config: dict | None = None):
    """
    训练语音配置文件

    使用收集的语音样本训练个性化TTS模型。

    要求：
    - 至少10个样本（推荐50个）
    - 样本质量良好
    - 样本多样性（不同情感、语速、音调）

    注意：
    - 训练过程可能需要数小时
    - 训练期间可以继续添加样本
    - 训练完成后才能使用该配置文件合成语音

    参数：
    - **profile_id**: 配置文件ID
    - **training_config**: 训练配置（可选）

    返回：
    - **status**: 训练状态（training/completed/failed）
    - **message**: 状态消息
    """
    try:
        service = get_service()

        result = await service.train_profile(profile_id=profile_id, training_config=training_config)

        logger.info(f"Training started for profile {profile_id}")

        return TrainProfileResponse(**result)

    except Exception as e:
        logger.error(f"Train profile failed: {e}", exc_info=True)
        return TrainProfileResponse(success=False, error=f"Failed to start training: {str(e)}")


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(request: SynthesizeRequest):
    """
    使用声纹合成语音

    使用训练好的个性化声纹模型合成语音。

    要求：
    - 配置文件状态必须为"completed"（训练完成）
    - 文本长度：1-500字符

    参数：
    - **profile_id**: 配置文件ID
    - **text**: 要合成的文本
    - **output_format**: 输出格式（默认wav）

    返回：
    - **audio_base64**: Base64编码的音频数据
    - **format**: 音频格式
    - **text**: 合成的文本
    """
    try:
        service = get_service()

        result = await service.synthesize(
            profile_id=request.profile_id, text=request.text, output_format=request.output_format
        )

        if result.get("success"):
            # 将音频数据转换为Base64
            import base64

            audio_base64 = base64.b64encode(result["audio_data"]).decode("utf-8")

            logger.info(
                f"Synthesized audio for profile {request.profile_id}: {len(request.text)} chars"
            )

            return SynthesizeResponse(
                success=True,
                audio_base64=audio_base64,
                format=result["format"],
                text=result["text"],
                profile_id=result["profile_id"],
            )
        else:
            return SynthesizeResponse(success=False, error=result.get("error", "Unknown error"))

    except Exception as e:
        logger.error(f"Synthesize failed: {e}", exc_info=True)
        return SynthesizeResponse(success=False, error=f"Synthesis failed: {str(e)}")


@router.get("/profiles/{profile_id}", response_model=dict)
async def get_profile(profile_id: str):
    """
    获取配置文件信息

    查询配置文件的详细信息，包括训练状态、样本数量等。

    参数：
    - **profile_id**: 配置文件ID

    返回：
    - 配置文件详细信息
    """
    try:
        service = get_service()
        profile = await service.get_profile(profile_id)

        if profile:
            return {"success": True, "profile": profile}
        else:
            raise HTTPException(status_code=404, detail="Profile not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}") from e


@router.get("/users/{user_id}/profiles", response_model=ProfileListResponse)
async def list_profiles(user_id: str):
    """
    列出用户的所有配置文件

    查询用户创建的所有语音配置文件。

    参数：
    - **user_id**: 用户ID

    返回：
    - **profiles**: 配置文件列表
    - **count**: 配置文件数量
    """
    try:
        service = get_service()
        profiles = await service.list_profiles(user_id)

        return ProfileListResponse(success=True, profiles=profiles, count=len(profiles))

    except Exception as e:
        logger.error(f"List profiles failed: {e}", exc_info=True)
        return ProfileListResponse(success=False, profiles=[], count=0)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """
    删除配置文件

    删除配置文件及其所有相关数据（样本、模型等）。

    警告：此操作不可恢复！

    参数：
    - **profile_id**: 配置文件ID

    返回：
    - 删除结果
    """
    try:
        service = get_service()
        result = await service.delete_profile(profile_id)

        if result.get("success"):
            logger.info(f"Profile deleted: {profile_id}")
            return result
        else:
            raise HTTPException(status_code=404, detail=result.get("error", "Profile not found"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete profile failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete profile: {str(e)}") from e


@router.get("/profiles/{profile_id}/suggestions", response_model=TrainingSuggestionsResponse)
async def get_training_suggestions(profile_id: str):
    """
    获取训练建议

    根据当前配置文件状态，提供训练建议和优化建议。

    参数：
    - **profile_id**: 配置文件ID

    返回：
    - **can_train**: 是否可以开始训练
    - **suggestions**: 建议列表
    """
    try:
        service = get_service()
        result = await service.get_training_suggestions(profile_id)

        return TrainingSuggestionsResponse(**result)

    except Exception as e:
        logger.error(f"Get suggestions failed: {e}", exc_info=True)
        return TrainingSuggestionsResponse(
            success=False, error=f"Failed to get suggestions: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    获取语音克隆服务统计信息

    返回：
    - 服务统计数据
    """
    service = get_service()

    total_profiles = len(service.profiles)
    training_profiles = sum(1 for p in service.profiles.values() if p.training_status == "training")
    completed_profiles = sum(
        1 for p in service.profiles.values() if p.training_status == "completed"
    )
    total_samples = sum(p.sample_count for p in service.profiles.values())

    return {
        "service": "Voice Cloning",
        "initialized": _voice_cloning_service is not None,
        "stats": {
            "total_profiles": total_profiles,
            "training_profiles": training_profiles,
            "completed_profiles": completed_profiles,
            "total_samples": total_samples,
            "min_sample_requirement": service.min_sample_count,
            "recommended_samples": service.recommended_sample_count,
        },
    }
