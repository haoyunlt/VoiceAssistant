"""
情感识别服务

使用MFCC特征 + 机器学习模型进行语音情感分类
"""

import logging
import os

import librosa
import numpy as np

logger = logging.getLogger(__name__)


class EmotionRecognitionService:
    """语音情感识别服务"""

    # 支持的情感类别
    EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"]

    def __init__(
        self,
        model_path: str | None = None,
        sample_rate: int = 16000,
        use_pretrained: bool = True,
    ):
        """
        初始化情感识别服务

        Args:
            model_path: 模型路径（如果为None，将加载预训练模型）
            sample_rate: 音频采样率
            use_pretrained: 是否使用预训练模型
        """
        self.sample_rate = sample_rate
        self.model = None
        self.scaler = None
        self.use_pretrained = use_pretrained

        if use_pretrained:
            self._load_pretrained_model(model_path)
        else:
            logger.info("情感识别服务初始化（无模型加载）")

    def _load_pretrained_model(self, model_path: str | None):
        """加载预训练模型"""
        try:
            import joblib
            from sklearn.ensemble import RandomForestClassifier

            if model_path and os.path.exists(model_path):
                # 加载用户自定义模型
                self.model = joblib.load(model_path)
                scaler_path = model_path.replace(".pkl", "_scaler.pkl")
                if os.path.exists(scaler_path):
                    self.scaler = joblib.load(scaler_path)
                logger.info(f"加载情感识别模型: {model_path}")
            else:
                # 使用默认模型（简单随机森林分类器）
                # 实际生产中应该使用训练好的模型
                self.model = RandomForestClassifier(n_estimators=100, random_state=42)
                logger.info("使用默认随机森林模型（未训练）")

        except ImportError as e:
            logger.warning(f"无法加载scikit-learn: {e}")
            self.model = None

    def extract_features(
        self, audio_data: np.ndarray, sample_rate: int = None
    ) -> np.ndarray:
        """
        提取音频特征

        Args:
            audio_data: 音频数据（numpy数组）
            sample_rate: 采样率

        Returns:
            特征向量
        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        features = []

        # 1. MFCC特征（梅尔频率倒谱系数）
        mfccs = librosa.feature.mfcc(
            y=audio_data, sr=sample_rate, n_mfcc=40, n_fft=2048, hop_length=512
        )
        mfccs_mean = np.mean(mfccs, axis=1)
        mfccs_std = np.std(mfccs, axis=1)
        features.extend(mfccs_mean)
        features.extend(mfccs_std)

        # 2. 色度特征（Chroma）
        chroma = librosa.feature.chroma_stft(
            y=audio_data, sr=sample_rate, n_fft=2048, hop_length=512
        )
        chroma_mean = np.mean(chroma, axis=1)
        chroma_std = np.std(chroma, axis=1)
        features.extend(chroma_mean)
        features.extend(chroma_std)

        # 3. 梅尔频谱（Mel Spectrogram）
        mel = librosa.feature.melspectrogram(
            y=audio_data, sr=sample_rate, n_fft=2048, hop_length=512
        )
        mel_mean = np.mean(mel, axis=1)
        mel_std = np.std(mel, axis=1)
        features.extend(mel_mean)
        features.extend(mel_std)

        # 4. 零交叉率（Zero Crossing Rate）
        zcr = librosa.feature.zero_crossing_rate(y=audio_data, hop_length=512)
        zcr_mean = np.mean(zcr)
        zcr_std = np.std(zcr)
        features.extend([zcr_mean, zcr_std])

        # 5. 谱质心（Spectral Centroid）
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=sample_rate, n_fft=2048, hop_length=512
        )
        sc_mean = np.mean(spectral_centroid)
        sc_std = np.std(spectral_centroid)
        features.extend([sc_mean, sc_std])

        # 6. 谱滚降（Spectral Rolloff）
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio_data, sr=sample_rate, n_fft=2048, hop_length=512
        )
        sr_mean = np.mean(spectral_rolloff)
        sr_std = np.std(spectral_rolloff)
        features.extend([sr_mean, sr_std])

        # 7. 能量
        rms = librosa.feature.rms(y=audio_data, hop_length=512)
        rms_mean = np.mean(rms)
        rms_std = np.std(rms)
        features.extend([rms_mean, rms_std])

        return np.array(features)

    def recognize(
        self, audio_data: bytes, sample_rate: int | None = None
    ) -> dict:
        """
        识别音频中的情感

        Args:
            audio_data: 音频数据（字节流）
            sample_rate: 采样率

        Returns:
            Dict包含：
            - emotion: 主要情感
            - confidence: 置信度
            - probabilities: 各情感的概率分布
            - features: 提取的特征信息
        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        try:
            # 转换音频数据
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_array = audio_array / 32768.0  # 归一化到[-1, 1]

            # 提取特征
            features = self.extract_features(audio_array, sample_rate)

            # 如果有模型，使用模型预测
            if self.model is not None and hasattr(self.model, "predict_proba"):
                # 归一化特征
                if self.scaler:
                    features = self.scaler.transform(features.reshape(1, -1))
                else:
                    features = features.reshape(1, -1)

                # 预测
                probabilities = self.model.predict_proba(features)[0]
                emotion_idx = np.argmax(probabilities)
                emotion = self.EMOTIONS[emotion_idx]
                confidence = probabilities[emotion_idx]

                probs_dict = {
                    self.EMOTIONS[i]: float(prob)
                    for i, prob in enumerate(probabilities)
                }
            else:
                # 使用基于规则的简单分类（启发式）
                emotion, confidence, probs_dict = self._rule_based_classification(
                    features
                )

            # 分析特征统计
            feature_stats = self._analyze_features(features)

            return {
                "emotion": emotion,
                "confidence": float(confidence),
                "probabilities": probs_dict,
                "features": feature_stats,
            }

        except Exception as e:
            logger.error(f"情感识别失败: {e}", exc_info=True)
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "probabilities": {},
                "features": {},
                "error": str(e),
            }

    def _rule_based_classification(
        self, features: np.ndarray
    ) -> tuple[str, float, dict[str, float]]:
        """
        基于规则的简单情感分类（无需训练模型）

        根据声学特征的统计值进行启发式分类
        """
        # 提取关键特征（简化版）
        # 假设features的前80个是MFCC的mean和std
        features[:40]
        mfcc_std = features[40:80]

        # 能量（最后两个特征）
        energy_mean = features[-2] if len(features) > 2 else 0
        energy_std = features[-1] if len(features) > 1 else 0

        # 简单规则（仅供演示，实际应该使用训练好的模型）
        emotion_scores = {
            "neutral": 0.5,  # 默认中性
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "fearful": 0.0,
            "disgusted": 0.0,
            "surprised": 0.0,
        }

        # 规则1：高能量 + 高变化 → 愤怒/惊讶
        if energy_mean > 0.05 and energy_std > 0.02:
            emotion_scores["angry"] += 0.3
            emotion_scores["surprised"] += 0.2

        # 规则2：低能量 + 低变化 → 悲伤
        if energy_mean < 0.02:
            emotion_scores["sad"] += 0.4

        # 规则3：中等能量 + 中等变化 → 快乐
        if 0.02 <= energy_mean <= 0.05:
            emotion_scores["happy"] += 0.3

        # 规则4：MFCC变化大 → 情绪激动
        if np.mean(mfcc_std) > 10:
            emotion_scores["angry"] += 0.2
            emotion_scores["fearful"] += 0.1

        # 归一化分数
        total = sum(emotion_scores.values())
        if total > 0:
            probs = {k: v / total for k, v in emotion_scores.items()}
        else:
            probs = {k: 1 / len(emotion_scores) for k in emotion_scores}

        # 选择最高分情感
        emotion = max(probs, key=probs.get)
        confidence = probs[emotion]

        return emotion, confidence, probs

    def _analyze_features(self, features: np.ndarray) -> dict:
        """分析特征统计信息"""
        return {
            "feature_count": len(features),
            "mean": float(np.mean(features)),
            "std": float(np.std(features)),
            "min": float(np.min(features)),
            "max": float(np.max(features)),
        }

    def recognize_from_file(self, audio_path: str) -> dict:
        """
        从文件识别情感

        Args:
            audio_path: 音频文件路径

        Returns:
            识别结果
        """
        try:
            # 加载音频文件
            audio_array, sr = librosa.load(audio_path, sr=self.sample_rate)

            # 转换为字节流
            audio_int16 = (audio_array * 32768).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            return self.recognize(audio_bytes, sr)

        except Exception as e:
            logger.error(f"从文件识别情感失败: {e}", exc_info=True)
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "probabilities": {},
                "features": {},
                "error": str(e),
            }

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        model_save_path: str | None = None,
    ):
        """
        训练情感识别模型

        Args:
            X_train: 训练特征
            y_train: 训练标签
            model_save_path: 模型保存路径
        """
        try:
            import joblib
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler

            # 特征标准化
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)

            # 训练模型
            self.model = RandomForestClassifier(
                n_estimators=200, max_depth=20, random_state=42, n_jobs=-1
            )
            self.model.fit(X_train_scaled, y_train)

            logger.info(f"模型训练完成，准确率: {self.model.score(X_train_scaled, y_train):.3f}")

            # 保存模型
            if model_save_path:
                joblib.dump(self.model, model_save_path)
                scaler_path = model_save_path.replace(".pkl", "_scaler.pkl")
                joblib.dump(self.scaler, scaler_path)
                logger.info(f"模型已保存到: {model_save_path}")

        except Exception as e:
            logger.error(f"训练模型失败: {e}", exc_info=True)
            raise


# 全局单例（线程安全版本）
import threading

_emotion_service: EmotionRecognitionService | None = None
_emotion_service_lock = threading.Lock()


def get_emotion_service() -> EmotionRecognitionService:
    """
    获取情感识别服务单例（线程安全）

    使用双重检查锁定模式确保线程安全的单例初始化
    """
    global _emotion_service

    # 第一次检查（无锁，快速路径）
    if _emotion_service is not None:
        return _emotion_service

    # 第二次检查（加锁）
    with _emotion_service_lock:
        if _emotion_service is None:
            _emotion_service = EmotionRecognitionService(use_pretrained=True)
            logger.info("EmotionRecognitionService singleton initialized")
        return _emotion_service
