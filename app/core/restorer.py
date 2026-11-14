"""Optional face restoration: SCRFD face detection + GFPGAN v1.4, both ONNX.

Faces are found with det_10g.onnx (SCRFD, pure NumPy decode), aligned to the
FFHQ-512 five-point template GFPGAN was trained on, restored, and blended back
with a feathered mask. The detector and alignment are ported from this
machine's face_swap_v2 engine (engine/detector.py, engine/align.py).

OpenCV's Haar cascade is deliberately not used: cv2 5.x no longer ships
CascadeClassifier in the main module, and an unaligned square crop gives
GFPGAN a face it was never trained on.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

GFPGAN_FILE = "gfpgan_1.4.onnx"
DETECTOR_FILE = "det_10g.onnx"

# FFHQ 512 template used by GFPGAN (eyes, nose, mouth corners).
FFHQ_512 = np.array(
    [[192.98138, 239.94708], [318.90277, 240.1936], [256.63416, 314.01935],
     [201.26117, 371.41043], [313.08905, 371.15118]], dtype=np.float32)

_STRIDES = [8, 16, 32]


def _nms(dets: np.ndarray, iou_thr: float) -> list[int]:
    x1, y1, x2, y2 = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = dets[:, 4].argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= iou_thr]
    return keep


class FaceDetector:
    """SCRFD-10GF. Returns (bbox[4], kps[5,2], score) per face, largest first."""

    def __init__(self, model_path: Path, size: int = 640) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # The detector is tiny; CPU avoids DirectML's dynamic-shape quirks.
        self.session = ort.InferenceSession(str(model_path), sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.size = size
        self._centers: dict = {}

    def _grid(self, side: int, stride: int, anchors: int) -> np.ndarray:
        key = (side, stride, anchors)
        c = self._centers.get(key)
        if c is None:
            c = np.stack(np.mgrid[:side, :side][::-1], axis=-1).astype(np.float32)
            c = (c * stride).reshape(-1, 2)
            if anchors > 1:
                c = np.stack([c] * anchors, axis=1).reshape(-1, 2)
            self._centers[key] = c
        return c

    def detect(self, img_bgr: np.ndarray, thresh: float = 0.5) -> list:
        h, w = img_bgr.shape[:2]
        scale = min(1.0, self.size / w, self.size / h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA) if scale != 1.0 else img_bgr
        canvas = np.zeros((self.size, self.size, 3), dtype=np.uint8)
        canvas[:nh, :nw] = resized

        rgb = canvas[:, :, ::-1].astype(np.float32)
        blob = ((rgb - 127.5) / 128.0).transpose(2, 0, 1)[None]
        outs = self.session.run(None, {self.input_name: np.ascontiguousarray(blob)})

        fmc = len(outs) // 3            # scores, boxes, keypoints per stride
        rows = []
        for idx, stride in enumerate(_STRIDES[:fmc]):
            scores = outs[idx].reshape(-1)
            side = self.size // stride
            anchors = max(1, scores.shape[0] // (side * side))
            centers = self._grid(side, stride, anchors)
            pos = np.where(scores >= thresh)[0]
            if pos.size == 0:
                continue
            d = outs[idx + fmc].reshape(-1, 4)[pos] * stride
            k = outs[idx + fmc * 2].reshape(-1, 10)[pos] * stride
            c = centers[pos]
            boxes = np.stack([c[:, 0] - d[:, 0], c[:, 1] - d[:, 1],
                              c[:, 0] + d[:, 2], c[:, 1] + d[:, 3]], axis=-1)
            kps = k.reshape(-1, 5, 2) + c[:, None, :]
            rows.append(np.concatenate([boxes / scale, scores[pos, None],
                                        kps.reshape(-1, 10) / scale], axis=1))
        if not rows:
            return []
        dets = np.concatenate(rows).astype(np.float32)
        faces = [(dets[i, :4], dets[i, 5:].reshape(5, 2), float(dets[i, 4]))
                 for i in _nms(dets[:, :5], 0.4)]
        faces.sort(key=lambda f: (f[0][2] - f[0][0]) * (f[0][3] - f[0][1]), reverse=True)
        return faces


def _paste_back(target: np.ndarray, crop: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Blend the restored 512 crop back with an eroded, blurred mask."""
    h, w = target.shape[:2]
    size = crop.shape[0]
    inv = cv2.invertAffineTransform(M)
    # Work only inside the face's bounding box: the image is already upscaled
    # and a full-frame float composite per face would be slow and RAM-hungry.
    corners = cv2.transform(np.array([[[0, 0], [size, 0], [size, size], [0, size]]], np.float32), inv)[0]
    x0, y0 = np.floor(corners.min(axis=0)).astype(int)
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return target
    local = inv.copy()
    local[:, 2] -= (x0, y0)
    bw, bh = x1 - x0, y1 - y0

    fake = cv2.warpAffine(crop, local, (bw, bh), flags=cv2.INTER_LINEAR).astype(np.float32)
    mask = cv2.warpAffine(np.full((size, size), 255, np.uint8), local, (bw, bh))
    mask[mask > 20] = 255
    face_px = int(np.sqrt(max(1, int((mask == 255).sum()))))
    k = max(face_px // 10, 10)
    mask = cv2.erode(mask, np.ones((k, k), np.uint8))
    k = max(face_px // 20, 5)
    m = (cv2.GaussianBlur(mask, (2 * k + 1, 2 * k + 1), 0).astype(np.float32) / 255.0)[..., None]

    region = target[y0:y1, x0:x1].astype(np.float32)
    target[y0:y1, x0:x1] = np.clip(m * fake + (1.0 - m) * region, 0, 255).astype(np.uint8)
    return target


class FaceRestorer:
    MAX_FACES = 20

    def __init__(self, models_dir: Path, providers: list[str]) -> None:
        self.models_dir = models_dir
        self.providers = providers
        self.session = None
        self.detector: FaceDetector | None = None
        self._model_path = self._find(GFPGAN_FILE)
        self._detector_path = self._find(DETECTOR_FILE)

    def _find(self, name: str) -> Path | None:
        # models/ first; the sibling face-swap projects are a dev-machine
        # convenience only and are never present next to a portable build.
        projects = self.models_dir.parent.parent
        for c in (self.models_dir / name,
                  projects / "face_swap_v2" / "models" / name,
                  projects / "face_swap_v1" / "models" / name):
            if c.is_file():
                return c
        return None

    @property
    def is_available(self) -> bool:
        return self._model_path is not None and self._detector_path is not None

    @property
    def missing(self) -> list[str]:
        return [n for n, p in ((GFPGAN_FILE, self._model_path), (DETECTOR_FILE, self._detector_path)) if p is None]

    def _ensure_session(self) -> None:
        if self.session is not None:
            return
        if not self._model_path:
            raise FileNotFoundError(f"GFPGAN model not found. Place {GFPGAN_FILE} in the models folder.")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(self._model_path), sess_options=opts, providers=self.providers)
        log.info("Loaded GFPGAN face restorer with provider: %s", self.session.get_providers()[0])

    def restore_face_crop(self, face_512: np.ndarray) -> np.ndarray:
        """Inference on an FFHQ-aligned 512x512 BGR face."""
        self._ensure_session()
        rgb = cv2.cvtColor(face_512, cv2.COLOR_BGR2RGB)
        tensor = (rgb.astype(np.float32) / 127.5) - 1.0
        tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]

        input_name = self.session.get_inputs()[0].name
        out = self.session.run(None, {input_name: tensor})[0][0]

        out = np.clip(np.transpose(out, (1, 2, 0)), -1, 1)
        out = ((out + 1.0) * 127.5).round().astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    def detect_faces(self, image: np.ndarray) -> list:
        if self.detector is None:
            if not self._detector_path:
                raise FileNotFoundError(f"Face detector not found. Place {DETECTOR_FILE} in the models folder.")
            self.detector = FaceDetector(self._detector_path)
        return self.detector.detect(image)

    def enhance_image_faces(self, image: np.ndarray, blend: float = 0.8) -> np.ndarray:
        """Restore every detected face in ``image`` (BGR). Returns a new image."""
        if not self.is_available:
            return image

        faces = self.detect_faces(image)[: self.MAX_FACES]
        log.info("Face restoration: %d face(s) found", len(faces))
        if not faces:
            return image

        res = image.copy()
        for _bbox, kps, _score in faces:
            M, _ = cv2.estimateAffinePartial2D(kps.astype(np.float32), FFHQ_512, method=cv2.LMEDS)
            if M is None:
                continue
            aligned = cv2.warpAffine(image, M, (512, 512), flags=cv2.INTER_AREA, borderValue=0.0)
            restored = self.restore_face_crop(aligned)
            if blend < 1.0:
                restored = cv2.addWeighted(restored, blend, aligned, 1.0 - blend, 0)
            res = _paste_back(res, restored, M)
        return res
