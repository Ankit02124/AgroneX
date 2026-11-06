"""
Export the trained detector for the Raspberry Pi.

    python training/export.py --weights runs/detect/drone/weights/best.pt --format tflite
    python training/export.py --weights runs/detect/drone/weights/best.pt --format openvino

tflite    float32 by default, --int8 for a smaller and faster model on the Pi CPU
          (needs --data so Ultralytics can calibrate on real images)
openvino  FP16 IR for the Intel Movidius Neural Compute Stick (MYRIAD plugin)

Copy the result to companion/models/ and set model.path / model.backend in
companion/config.yaml.
"""

import argparse

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--format", choices=["tflite", "openvino"], default="tflite")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--int8", action="store_true")
    ap.add_argument("--data", help="dataset yaml, needed for --int8 calibration")
    args = ap.parse_args()

    kwargs = dict(format=args.format, imgsz=args.imgsz)
    if args.format == "openvino":
        kwargs["half"] = True
    if args.int8:
        kwargs.update(int8=True, data=args.data)
    print("exported:", YOLO(args.weights).export(**kwargs))


if __name__ == "__main__":
    main()
