"""YOLOv8n plant disease detector for the Raspberry Pi.

Two backends:
  tflite    tflite-runtime on the Pi's CPU
  openvino  OpenVINO IR on the Intel Movidius Neural Compute Stick ("MYRIAD")

YOLOv8 exports give a (1, 4 + num_classes, N) output with boxes as cx, cy, w, h.
TFLite exports use coordinates normalised to 0-1, OpenVINO uses pixels; both are
handled. Letterboxing and NMS are done here in numpy.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    label: str


def nms(boxes, scores, iou_thr):
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        w = np.clip(np.minimum(x2[i], x2[order[1:]]) - np.maximum(x1[i], x1[order[1:]]), 0, None)
        h = np.clip(np.minimum(y2[i], y2[order[1:]]) - np.maximum(y1[i], y1[order[1:]]), 0, None)
        iou = w * h / (areas[i] + areas[order[1:]] - w * h + 1e-9)
        order = order[1:][iou < iou_thr]
    return keep


def letterbox(img, size):
    h, w = img.shape[:2]
    r = size / max(h, w)
    nw, nh = round(w * r), round(h * r)
    canvas = np.full((size, size, 3), 114, np.uint8)
    dx, dy = (size - nw) // 2, (size - nh) // 2
    canvas[dy:dy + nh, dx:dx + nw] = cv2.resize(img, (nw, nh))
    return canvas, r, dx, dy


def postprocess(pred, names, size, r, dx, dy, conf_thr, iou_thr, frame_shape):
    """pred: (4 + nc, N) raw YOLOv8 output for one image."""
    pred = pred.T
    if pred[:, :4].max() <= 2.0:          # normalised coordinates (TFLite export)
        pred[:, :4] *= size
    scores = pred[:, 4:]
    cls = scores.argmax(1)
    conf = scores[np.arange(len(cls)), cls]
    keep = conf >= conf_thr
    if not keep.any():
        return []
    b, cls, conf = pred[keep, :4], cls[keep], conf[keep]
    boxes = np.stack([b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2,
                      b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2], axis=1)
    boxes[:, [0, 2]] = ((boxes[:, [0, 2]] - dx) / r).clip(0, frame_shape[1])
    boxes[:, [1, 3]] = ((boxes[:, [1, 3]] - dy) / r).clip(0, frame_shape[0])
    idx = nms(boxes + cls[:, None] * 10000.0, conf, iou_thr)
    return [Detection(*boxes[i].tolist(), float(conf[i]), names[int(cls[i])]) for i in idx]


class DiseaseDetector:
    def __init__(self, model_path, names, backend="tflite", size=640, conf=0.5, iou=0.5, threads=4):
        self.names, self.size, self.conf, self.iou = list(names), size, conf, iou
        if backend == "tflite":
            from tflite_runtime.interpreter import Interpreter

            self.interp = Interpreter(model_path=str(model_path), num_threads=threads)
            self.interp.allocate_tensors()
            self._in = self.interp.get_input_details()[0]
            self._out = self.interp.get_output_details()[0]
            self._run = self._run_tflite
        elif backend == "openvino":
            from openvino.runtime import Core

            core = Core()
            self.compiled = core.compile_model(core.read_model(str(model_path)), "MYRIAD")
            self._run = self._run_openvino
        else:
            raise ValueError(f"unknown backend {backend}")

    def _run_tflite(self, x):
        x = x.transpose(0, 2, 3, 1) if self._in["shape"][-1] == 3 else x   # TFLite wants NHWC
        self.interp.set_tensor(self._in["index"], x)
        self.interp.invoke()
        return self.interp.get_tensor(self._out["index"])[0]

    def _run_openvino(self, x):
        return self.compiled([x])[self.compiled.output(0)][0]

    def detect(self, frame_bgr):
        img, r, dx, dy = letterbox(frame_bgr, self.size)
        x = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        return postprocess(self._run(x), self.names, self.size, r, dx, dy, self.conf, self.iou, frame_bgr.shape)
