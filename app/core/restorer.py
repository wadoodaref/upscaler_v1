"""Optional face restoration module using GFPGAN ONNX."""

from __future__ import annotations

import logging
from pathlib import Path
import cv2
import numpy as np

log = logging.getLogger(__name__)


class FaceRestorer:
    def __init__(self, models_dir: Path, providers: list[str]) -> None:
        self.models_dir = models_dir
        self.providers = providers
        self.session = None
        self._model_path = self._find_model()

    def _find_model(self) -> Path | None:
        candidates = [
            self.models_dir / "gfpgan_1.4.onnx",
            self.models_dir.parent.parent / "face_swap_v1" / "models" / "gfpgan_1.4.onnx",
            self.models_dir.parent.parent / "face_swap_v2" / "models" / "gfpgan_1.4.onnx",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None

    @property
    def is_available(self) -> bool:
        return self._model_path is not None

    def _ensure_session(self) -> None:
        if self.session is not None:
            return
        if not self._model_path:
            raise FileNotFoundError("GFPGAN model not found. Place gfpgan_1.4.onnx in models directory.")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(self._model_path), sess_options=opts, providers=self.providers)
        log.info("Loaded GFPGAN face restorer with provider: %s", self.session.get_providers()[0])

    def restore_face_crop(self, face_512: np.ndarray) -> np.ndarray:
        """Inference on a 512x512 BGR face chip."""
        self._ensure_session()
        # Preprocessing: BGR -> RGB, normalize to [-1, 1], transpose to NCHW
        rgb = cv2.cvtColor(face_512, cv2.COLOR_BGR2RGB)
        tensor = (rgb.astype(np.float32) / 127.5) - 1.0
        tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]

        input_name = self.session.get_inputs()[0].name
        out = self.session.run(None, {input_name: tensor})[0][0]

        # Postprocessing: CHW -> HWC, [-1, 1] -> [0, 255], RGB -> BGR
        out = np.clip(np.transpose(out, (1, 2, 0)), -1, 1)
        out = ((out + 1.0) * 127.5).astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    def enhance_image_faces(self, image: np.ndarray, blend: float = 0.8) -> np.ndarray:
        """Simple face detection and enhancement using OpenCV Haar cascade or fallback."""
        if not self.is_available:
            return image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(64, 64))

        if len(faces) == 0:
            return image

        res = image.copy()
        for (x, y, w, h) in faces:
            # Expand bounding box slightly for natural hair/chin restoration
            pad_x = int(w * 0.15)
            pad_y = int(h * 0.15)
            x0 = max(0, x - pad_x)
            y0 = max(0, y - pad_y)
            x1 = min(image.shape[1], x + w + pad_x)
            y1 = min(image.shape[0], y + h + pad_y)

            crop = image[y0:y1, x0:x1]
            orig_h, orig_w = crop.shape[:2]

            resized = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_LANCZOS4)
            restored = self.restore_face_crop(resized)
            restored_orig_size = cv2.resize(restored, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

            # Smooth border blending
            if blend < 1.0:
                blended = cv2.addWeighted(restored_orig_size, blend, crop, 1.0 - blend, 0)
            else:
                blended = restored_orig_size
            res[y0:y1, x0:x1] = blended

        return res
