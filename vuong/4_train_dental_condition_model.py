"""
Huan luyen 2 model cua he thong: detector (YOLOv8, 4 lop co bbox that) va
classifier toan anh (6 lop). Chay:

    python 4_train_dental_condition_model.py --stage all
    python 4_train_dental_condition_model.py --stage detector
    python 4_train_dental_condition_model.py --stage classifier

Truoc khi chay, phai build manifest/dataset.yaml mot lan:
    python 1_dental_preprocess.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from importlib import import_module

import cv2
import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support, accuracy_score
from torch.utils.data import Dataset, DataLoader

_prep = import_module("1_dental_preprocess")
_model_def = import_module("3_dental_condition_model")

ARTIFACTS_DIR = _prep.ARTIFACTS_DIR
MANIFEST_DIR = _prep.MANIFEST_DIR
CLASSIFIER_CLASSES = _prep.CLASSIFIER_CLASSES
DETECTOR_CLASSES = _prep.DETECTOR_CLASSES
normalize_color = _prep.normalize_color
load_image = _prep.load_image


# --------------------------------------------------------------------------
# Detector
# --------------------------------------------------------------------------


def train_detector(
    dataset_yaml: Path = ARTIFACTS_DIR / "dataset.yaml",
    epochs: int = 60,
    imgsz: int = 640,
    batch: int = 16,
    conf_threshold: float = 0.35,
    patience: int = 15,
) -> None:
    """epochs=60 la SO EPOCH TOI DA. patience=15: ultralytics se dung train som
    neu val mAP khong cai thien sau 15 epoch lien tiep (lan train truoc mAP50
    da bao hoa quanh epoch 46/60 trong khi train_loss van giam - dau hieu
    overfit - patience giup tranh train du thua vao dieu do)."""
    if not dataset_yaml.exists():
        raise FileNotFoundError(f"Khong thay {dataset_yaml}. Chay 1_dental_preprocess.py truoc.")

    model = _model_def.create_yolo_detector("yolov8n.pt")
    run_dir = ARTIFACTS_DIR / "detector_runs"
    model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        patience=patience,
        project=str(run_dir.parent),
        name=run_dir.name,
        exist_ok=True,
    )
    val_metrics = model.val(data=str(dataset_yaml), project=str(run_dir.parent), name=run_dir.name, exist_ok=True)

    best_weights = run_dir / "weights" / "best.pt"
    metrics_report = {
        "precision": float(val_metrics.box.mp),
        "recall": float(val_metrics.box.mr),
        "mAP50": float(val_metrics.box.map50),
        "mAP50-95": float(val_metrics.box.map),
        "classes": DETECTOR_CLASSES,
    }
    (ARTIFACTS_DIR / "detector_metrics.json").write_text(
        json.dumps(metrics_report, indent=2), encoding="utf-8"
    )
    print(f"[detector] best weights: {best_weights}")
    print(f"[detector] metrics: {metrics_report}")

    _update_inference_config(detector_weights=str(best_weights), detector_conf_threshold=conf_threshold)


# --------------------------------------------------------------------------
# Classifier
# --------------------------------------------------------------------------


class ClassifierDataset(Dataset):
    def __init__(self, csv_path: Path, transform):
        self.transform = transform
        self.rows: list[tuple[str, int]] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.rows.append((row["filepath"], int(row["label_id"])))

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        filepath, label_id = self.rows[idx]
        image_bgr = load_image(filepath)
        image_bgr = normalize_color(image_bgr)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        tensor = self.transform(image_rgb)
        return tensor, label_id


def train_classifier(
    manifest_dir: Path = MANIFEST_DIR,
    epochs: int = 60,
    batch_size: int = 32,
    lr: float = 1e-4,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    patience: int = 10,
) -> None:
    """epochs=60 la SO EPOCH TOI DA (giong detector). patience=10: dung train
    som neu val macro_f1 khong cai thien sau tung nay epoch lien tiep. Lich su
    tung epoch duoc luu vao classifier_train_history.csv de kiem tra sau nay
    xem model da bao hoa (nhu detector) hay chua train du."""
    train_csv = manifest_dir / "train.csv"
    val_csv = manifest_dir / "val.csv"
    if not train_csv.exists() or not val_csv.exists():
        raise FileNotFoundError(f"Khong thay manifest trong {manifest_dir}. Chay 1_dental_preprocess.py truoc.")

    train_ds = ClassifierDataset(train_csv, _model_def.get_train_transforms())
    val_ds = ClassifierDataset(val_csv, _model_def.get_eval_transforms())

    # num_workers=0 (cu) doc + tien xu ly anh (normalize_color: can bang trang +
    # CLAHE bang OpenCV) tuan tu tren 1 luong duy nhat -> GPU phai cho, moi epoch
    # cham gap ~8 lan so voi detector (ultralytics tu dung 8 worker song song).
    # Dung nhieu worker de nap/tien xu ly anh song song, khong chan GPU.
    num_workers = min(8, os.cpu_count() or 4)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, persistent_workers=num_workers > 0,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True, persistent_workers=num_workers > 0,
    )

    device_t = torch.device(device)
    model = _model_def.build_classifier().to(device_t)

    label_ids = [label_id for _, label_id in train_ds.rows]
    class_weights = _model_def.compute_class_weights(label_ids).to(device_t)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_f1 = -1.0
    epochs_without_improvement = 0
    best_path = ARTIFACTS_DIR / "classifier_best.pt"
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    history: list[dict] = []

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device_t), labels.to(device_t)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)
        scheduler.step()
        train_loss = running_loss / len(train_ds)

        val_metrics = _evaluate_classifier(model, val_loader, device_t)
        print(
            f"[classifier] epoch {epoch}/{epochs} - train_loss={train_loss:.4f} "
            f"val_acc={val_metrics['accuracy']:.4f} val_macro_f1={val_metrics['macro_f1']:.4f}"
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_metrics["macro_f1"],
            }
        )

        if val_metrics["macro_f1"] > best_f1:
            best_f1 = val_metrics["macro_f1"]
            epochs_without_improvement = 0
            torch.save(model.state_dict(), best_path)
            (ARTIFACTS_DIR / "classifier_metrics.json").write_text(
                json.dumps(val_metrics, indent=2), encoding="utf-8"
            )
            print(f"[classifier] -> checkpoint moi tot nhat (macro_f1={best_f1:.4f}) luu tai {best_path}")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"[classifier] early stopping tai epoch {epoch} (khong cai thien sau {patience} epoch)")
                break

    with (ARTIFACTS_DIR / "classifier_train_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "train_loss", "val_accuracy", "val_macro_f1"])
        writer.writeheader()
        writer.writerows(history)

    _update_inference_config(classifier_checkpoint=str(best_path))


@torch.no_grad()
def _evaluate_classifier(model, loader: DataLoader, device: torch.device) -> dict:
    model.eval()
    all_preds, all_labels = [], []
    for images, labels in loader:
        images = images.to(device)
        logits = model(images)
        preds = logits.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds.tolist())
        all_labels.extend(labels.numpy().tolist())

    accuracy = accuracy_score(all_labels, all_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, labels=list(range(len(CLASSIFIER_CLASSES))), zero_division=0
    )
    per_class = {
        CLASSIFIER_CLASSES[i]: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i])}
        for i in range(len(CLASSIFIER_CLASSES))
    }
    return {
        "accuracy": float(accuracy),
        "macro_f1": float(np.mean(f1)),
        "per_class": per_class,
    }


# --------------------------------------------------------------------------
# Config chung cho inference (2_detect_dental_conditions.py doc lai file nay)
# --------------------------------------------------------------------------


def _update_inference_config(**kwargs) -> None:
    config_path = ARTIFACTS_DIR / "inference_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config.update(kwargs)
    config.setdefault("detector_conf_threshold", 0.35)
    config.setdefault("classifier_conf_threshold", 0.50)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["detector", "classifier", "all"], default="all")
    parser.add_argument("--epochs-detector", type=int, default=60)
    parser.add_argument("--epochs-classifier", type=int, default=60)
    parser.add_argument("--patience-detector", type=int, default=15)
    parser.add_argument("--patience-classifier", type=int, default=10)
    args = parser.parse_args()

    if args.stage in ("detector", "all"):
        train_detector(epochs=args.epochs_detector, patience=args.patience_detector)
    if args.stage in ("classifier", "all"):
        train_classifier(epochs=args.epochs_classifier, patience=args.patience_classifier)
