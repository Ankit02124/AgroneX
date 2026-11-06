"""
Hybrid transfer learning for the AgroneX disease detector (YOLOv8n).

The custom drone dataset has only 445 images, so the model is trained in steps:

  stage 1  COCO        start from Ultralytics' yolov8n.pt (nothing to run)
  stage 2  PlantDoc    learn what diseased leaves look like (close-up field photos)
  stage 3  drone set   adapt to the drone's view, scale and lighting (healthy / disease)

    python training/train.py --stage plantdoc --data data/plantdoc.yaml
    python training/train.py --stage drone --data data/drone.yaml \
        --weights runs/detect/plantdoc/weights/best.pt

Stage 3 uses a 10x lower learning rate so it refines the PlantDoc features
instead of overwriting them.
"""

import argparse

from ultralytics import YOLO

STAGES = {
    "plantdoc": dict(epochs=100, lr0=0.01, weights="yolov8n.pt"),
    "drone": dict(epochs=100, lr0=0.001, weights=None),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=STAGES, required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--weights", help="starting weights (stage 3: best.pt from stage 2)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--epochs", type=int)
    args = ap.parse_args()

    stage = STAGES[args.stage]
    weights = args.weights or stage["weights"]
    if weights is None:
        ap.error("--weights is required for the drone stage")

    YOLO(weights).train(
        data=args.data,
        epochs=args.epochs or stage["epochs"],
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=stage["lr0"],
        cos_lr=True,
        patience=20,
        name=args.stage,
        # drone images: any rotation is valid from above, and light changes a lot
        degrees=15.0,
        flipud=0.5,
        fliplr=0.5,
        hsv_v=0.5,
        mosaic=1.0,
    )


if __name__ == "__main__":
    main()
