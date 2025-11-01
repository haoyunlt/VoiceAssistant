"""目标检测服务"""

import io

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger


class DetectedObject(BaseModel):
    """检测到的对象"""

    class_name: str
    confidence: float
    bbox: list[int]  # [x, y, width, height]
    center: list[int]  # [x, y]


class DetectionResult(BaseModel):
    """检测结果"""

    objects: list[DetectedObject]
    num_objects: int
    image_size: list[int]  # [width, height]
    processing_time_ms: float


class ObjectDetectionService:
    """目标检测服务（YOLO）"""

    def __init__(self):
        """初始化"""
        self.model = None
        self.class_names = []
        self.confidence_threshold = 0.5
        self.nms_threshold = 0.4
        self._load_model()

    def _load_model(self):
        """加载YOLO模型"""
        try:
            # 使用YOLOv8（通过ultralytics）
            try:
                from ultralytics import YOLO

                model_path = settings.get("YOLO_MODEL", "yolov8n.pt")
                self.model = YOLO(model_path)

                # 获取类别名称
                self.class_names = list(self.model.names.values())

                logger.info(f"YOLO model loaded: {model_path}")
            except ImportError:
                logger.warning("ultralytics not installed, trying OpenCV DNN")
                self._load_opencv_yolo()

        except Exception as e:
            logger.error(f"Failed to load object detection model: {e}")

    def _load_opencv_yolo(self):
        """使用OpenCV DNN加载YOLO"""
        try:
            # 下载YOLOv4-tiny模型文件
            model_cfg = settings.get("YOLO_CFG", "yolov4-tiny.cfg")
            model_weights = settings.get("YOLO_WEIGHTS", "yolov4-tiny.weights")

            self.model = cv2.dnn.readNetFromDarknet(model_cfg, model_weights)
            self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            # 加载COCO类别名称
            self.class_names = self._load_coco_names()

            logger.info("OpenCV YOLO model loaded")
        except Exception as e:
            logger.error(f"Failed to load OpenCV YOLO: {e}")

    def _load_coco_names(self) -> list[str]:
        """加载COCO数据集类别名称"""
        return [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ]

    async def detect_objects(
        self,
        image_data: bytes,
        confidence_threshold: float | None = None,
        nms_threshold: float | None = None,
    ) -> DetectionResult:
        """检测图像中的对象

        Args:
            image_data: 图像数据
            confidence_threshold: 置信度阈值
            nms_threshold: NMS阈值

        Returns:
            检测结果
        """
        if not self.model:
            raise RuntimeError("Object detection model not loaded")

        if confidence_threshold is None:
            confidence_threshold = self.confidence_threshold
        if nms_threshold is None:
            nms_threshold = self.nms_threshold

        import time

        start_time = time.time()

        try:
            # 加载图像
            image = Image.open(io.BytesIO(image_data))
            image_np = np.array(image.convert("RGB"))

            # 使用ultralytics YOLO
            if hasattr(self.model, "predict"):
                results = self.model.predict(
                    image_np, conf=confidence_threshold, iou=nms_threshold, verbose=False
                )[0]

                objects = []
                for box in results.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])

                    width = int(x2 - x1)
                    height = int(y2 - y1)
                    center_x = int(x1 + width / 2)
                    center_y = int(y1 + height / 2)

                    objects.append(
                        DetectedObject(
                            class_name=self.class_names[class_id],
                            confidence=confidence,
                            bbox=[int(x1), int(y1), width, height],
                            center=[center_x, center_y],
                        )
                    )
            else:
                # 使用OpenCV DNN
                objects = await self._detect_with_opencv(
                    image_np, confidence_threshold, nms_threshold
                )

            processing_time = (time.time() - start_time) * 1000

            return DetectionResult(
                objects=objects,
                num_objects=len(objects),
                image_size=[image.width, image.height],
                processing_time_ms=processing_time,
            )
        except Exception as e:
            logger.error(f"Object detection error: {e}")
            raise

    async def _detect_with_opencv(
        self, image: np.ndarray, confidence_threshold: float, nms_threshold: float
    ) -> list[DetectedObject]:
        """使用OpenCV DNN检测"""
        height, width = image.shape[:2]

        # 创建blob
        blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (416, 416), swapRB=True, crop=False)

        # 前向传播
        self.model.setInput(blob)
        layer_names = self.model.getLayerNames()
        output_layers = [layer_names[i - 1] for i in self.model.getUnconnectedOutLayers()]
        outputs = self.model.forward(output_layers)

        # 解析检测结果
        boxes = []
        confidences = []
        class_ids = []

        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence > confidence_threshold:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)

                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        # 非极大值抑制
        indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, nms_threshold)

        objects = []
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                objects.append(
                    DetectedObject(
                        class_name=self.class_names[class_ids[i]],
                        confidence=confidences[i],
                        bbox=[x, y, w, h],
                        center=[x + w // 2, y + h // 2],
                    )
                )

        return objects

    async def detect_and_annotate(
        self, image_data: bytes, confidence_threshold: float | None = None
    ) -> tuple[DetectionResult, bytes]:
        """检测并标注图像

        Args:
            image_data: 图像数据
            confidence_threshold: 置信度阈值

        Returns:
            (检测结果, 标注后的图像)
        """
        # 检测对象
        result = await self.detect_objects(image_data, confidence_threshold)

        # 加载图像
        image = Image.open(io.BytesIO(image_data))
        image_np = np.array(image.convert("RGB"))

        # 绘制边界框
        for obj in result.objects:
            x, y, w, h = obj.bbox

            # 绘制矩形
            cv2.rectangle(image_np, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # 绘制标签
            label = f"{obj.class_name}: {obj.confidence:.2f}"
            cv2.putText(image_np, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 转换回bytes
        annotated_image = Image.fromarray(image_np)
        output_buffer = io.BytesIO()
        annotated_image.save(output_buffer, format="JPEG")
        output_buffer.seek(0)

        return result, output_buffer.read()

    async def count_objects_by_class(self, detection_result: DetectionResult) -> dict[str, int]:
        """统计各类对象数量

        Args:
            detection_result: 检测结果

        Returns:
            类别计数字典
        """
        counts = {}
        for obj in detection_result.objects:
            counts[obj.class_name] = counts.get(obj.class_name, 0) + 1
        return counts
