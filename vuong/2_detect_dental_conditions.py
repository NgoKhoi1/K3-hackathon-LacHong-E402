"""
Suy luan (inference): chay detector + classifier tren 1 anh mau va hop nhat
ket qua thanh danh sach "vision findings" de chatbot dung.

- Detector (bbox that): Caries, Ulcers, Tooth Discoloration, Gingivitis.
- Classifier (toan anh, khong bbox): ca 6 lop, kem Calculus va Hypodontia.

Voi 4 lop co ca detector lan classifier, detector duoc uu tien (co vi tri cu
the); classifier dung de: (a) bo sung khi detector khong bat duoc gi nhung
van co dau hieu toan anh, (b) tang/giam do tin cay cheo kiem.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from importlib import import_module

_prep = import_module("1_dental_preprocess")
_model_def = import_module("3_dental_condition_model")

CLASSIFIER_CLASSES = _prep.CLASSIFIER_CLASSES
DETECTOR_CLASSES = _prep.DETECTOR_CLASSES
ARTIFACTS_DIR = _prep.ARTIFACTS_DIR
preprocess_for_inference = _prep.preprocess_for_inference
check_image_quality = _prep.check_image_quality
load_image = _prep.load_image

DETECTOR_ONLY_FALLBACK_CLASSES = [c for c in CLASSIFIER_CLASSES if c not in DETECTOR_CLASSES]  # Calculus, Hypodontia

DEFAULT_DETECTOR_CONF_TH = 0.35
DEFAULT_CLASSIFIER_CONF_TH = 0.50


@dataclass
class Detection:
    label: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass
class ClassificationScore:
    label: str
    confidence: float


@dataclass
class ConditionFinding:
    label: str
    present: bool
    confidence: float
    bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    source: str = ""  # "detector" | "classifier" | "detector+classifier"


@dataclass
class VisionFindings:
    detections: list[Detection]
    classification_scores: list[ClassificationScore]
    conditions: dict[str, ConditionFinding]  # keyed by label, ca 6 lop luon co mat

    def flagged(self) -> list[ConditionFinding]:
        return sorted((c for c in self.conditions.values() if c.present), key=lambda c: -c.confidence)


class DentalDetector:
    """Wrapper cho model YOLOv8 da train (xem 4_train_dental_condition_model.py)."""

    def __init__(self, weights_path: str | Path, conf_threshold: float = DEFAULT_DETECTOR_CONF_TH):
        from ultralytics import YOLO

        self.model = YOLO(str(weights_path))
        self.conf_threshold = conf_threshold

    def predict(self, image_bgr: np.ndarray) -> list[Detection]:
        results = self.model.predict(source=image_bgr, conf=self.conf_threshold, verbose=False)
        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                label = DETECTOR_CLASSES[class_id]
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                detections.append(Detection(label, confidence, (x1, y1, x2, y2)))
        return detections


class DentalClassifier:
    """Wrapper cho classifier toan anh 6 lop (xem 4_train_dental_condition_model.py)."""

    def __init__(self, checkpoint_path: str | Path, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = _model_def.build_classifier(pretrained=False)
        state_dict = torch.load(str(checkpoint_path), map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def predict(self, classifier_input_rgb: np.ndarray) -> list[ClassificationScore]:
        tensor = torch.from_numpy(classifier_input_rgb).permute(2, 0, 1).unsqueeze(0)
        mean = torch.tensor(_model_def._IMAGENET_MEAN).view(1, 3, 1, 1)
        std = torch.tensor(_model_def._IMAGENET_STD).view(1, 3, 1, 1)
        tensor = (tensor - mean) / std
        tensor = tensor.to(self.device)

        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        scores = [ClassificationScore(CLASSIFIER_CLASSES[i], float(p)) for i, p in enumerate(probs)]
        return sorted(scores, key=lambda s: -s.confidence)


def merge_findings(
    detections: list[Detection],
    classification_scores: list[ClassificationScore],
    detector_conf_th: float = DEFAULT_DETECTOR_CONF_TH,
    classifier_conf_th: float = DEFAULT_CLASSIFIER_CONF_TH,
) -> VisionFindings:
    class_scores = {s.label: s.confidence for s in classification_scores}
    conditions: dict[str, ConditionFinding] = {label: ConditionFinding(label, False, 0.0) for label in CLASSIFIER_CLASSES}

    dets_by_label: dict[str, list[Detection]] = {}
    for d in detections:
        dets_by_label.setdefault(d.label, []).append(d)

    for label in CLASSIFIER_CLASSES:
        label_dets = dets_by_label.get(label, [])
        classifier_conf = class_scores.get(label, 0.0)

        if label_dets:
            det_conf = max(d.confidence for d in label_dets)
            has_classifier_support = classifier_conf >= classifier_conf_th
            conditions[label] = ConditionFinding(
                label=label,
                present=True,
                confidence=det_conf,
                bboxes=[d.bbox_xyxy for d in label_dets],
                source="detector+classifier" if has_classifier_support else "detector",
            )
        elif label in DETECTOR_CLASSES:
            # co the detector, khong bat duoc bbox nhung classifier van nghi ngo toan anh
            if classifier_conf >= classifier_conf_th:
                conditions[label] = ConditionFinding(
                    label=label, present=True, confidence=classifier_conf, bboxes=[], source="classifier"
                )
        else:
            # Calculus / Hypodontia: khong co detector, chi dua vao classifier
            if classifier_conf >= classifier_conf_th:
                conditions[label] = ConditionFinding(
                    label=label, present=True, confidence=classifier_conf, bboxes=[], source="classifier"
                )

    return VisionFindings(detections=detections, classification_scores=classification_scores, conditions=conditions)


_HUMAN_TEMPLATES = {
    "Caries": "vung rang co dau hieu sau rang / ton thuong men-nga rang",
    "Calculus": "mang bam cao rang (vang/nau, thuong bam o vien nuou)",
    "Gingivitis": "vung nuou co dau hieu viem (do, sung)",
    "Tooth Discoloration": "rang co dau hieu doi mau / nhiem mau",
    "Ulcers": "vung nghi loet mieng (vet trang/do)",
    "Hypodontia": "dau hieu thieu rang / khoang mat rang bat thuong",
}


def to_human_findings(findings: VisionFindings) -> list[str]:
    """Dien giai ket qua model thanh cau tieng Viet than thien, dung lam du lieu
    nen (grounding) cho buoc sinh phan hoi tu nhien trong chatbot - KHONG tu
    y sinh them thong tin ngoai nhung gi model da phat hien."""
    sentences = []
    for c in findings.flagged():
        desc = _HUMAN_TEMPLATES.get(c.label, c.label)
        location = " (da xac dinh duoc vi tri tren anh)" if c.bboxes else " (chua xac dinh chinh xac vi tri)"
        sentences.append(f"He thong phat hien {desc}, do tin cay {c.confidence:.0%}{location}.")
    if not sentences:
        sentences.append("He thong khong phat hien dau hieu bat thuong ro ret trong 6 nhom da khao sat.")
    return sentences


def load_config(config_path: Path = ARTIFACTS_DIR / "inference_config.json") -> dict:
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {
        "detector_weights": str(ARTIFACTS_DIR / "detector_runs" / "weights" / "best.pt"),
        "classifier_checkpoint": str(ARTIFACTS_DIR / "classifier_best.pt"),
        "detector_conf_threshold": DEFAULT_DETECTOR_CONF_TH,
        "classifier_conf_threshold": DEFAULT_CLASSIFIER_CONF_TH,
    }


def _run_pipeline_with_models(
    image_path: str | Path, detector: "DentalDetector", classifier: "DentalClassifier", config: dict
) -> VisionFindings:
    image = load_image(image_path)
    quality = check_image_quality(image)
    if not quality.is_acceptable:
        raise ValueError("Anh khong dat chat luong toi thieu: " + " ".join(quality.issues))

    processed = preprocess_for_inference(image)
    detections = detector.predict(processed["detector_input_bgr"])
    classification_scores = classifier.predict(processed["classifier_input_rgb"])

    return merge_findings(
        detections,
        classification_scores,
        detector_conf_th=config.get("detector_conf_threshold", DEFAULT_DETECTOR_CONF_TH),
        classifier_conf_th=config.get("classifier_conf_threshold", DEFAULT_CLASSIFIER_CONF_TH),
    )


def run_full_pipeline(image_path: str | Path, config: Optional[dict] = None) -> VisionFindings:
    """Suy luan tren 1 anh don le (tu load model moi lan goi - tien cho 1 lan chay,
    KHONG dung cho batch vi rat lang phi thoi gian load lai model)."""
    config = config or load_config()
    detector = DentalDetector(config["detector_weights"], config.get("detector_conf_threshold", DEFAULT_DETECTOR_CONF_TH))
    classifier = DentalClassifier(config["classifier_checkpoint"])
    return _run_pipeline_with_models(image_path, detector, classifier, config)


def collect_labeled_images(root: Path) -> list[tuple[Path, Optional[str]]]:
    """Quet 1 file anh hoac 1 thu muc (de quy). Nhan ky vong cua moi anh = ten
    thu muc cha gan nhat, NEU ten do khop (khong phan biet hoa/thuong) voi 1 trong
    6 lop; nguoc lai la None (khong danh gia dung/sai, chi in ket qua)."""
    label_lookup = {c.lower(): c for c in CLASSIFIER_CLASSES}
    root = Path(root)

    if root.is_file():
        expected = label_lookup.get(root.parent.name.lower())
        return [(root, expected)]

    items: list[tuple[Path, Optional[str]]] = []
    for img_path in sorted(root.rglob("*")):
        if img_path.suffix in _prep.IMAGE_EXTS:
            expected = label_lookup.get(img_path.parent.name.lower())
            items.append((img_path, expected))
    return items


def run_batch(root: str | Path, config: Optional[dict] = None) -> None:
    config = config or load_config()
    detector = DentalDetector(config["detector_weights"], config.get("detector_conf_threshold", DEFAULT_DETECTOR_CONF_TH))
    classifier = DentalClassifier(config["classifier_checkpoint"])

    items = collect_labeled_images(Path(root))
    if not items:
        print(f"Khong tim thay anh nao trong: {root}")
        return

    # dem theo lop: [so_anh, so_dung_top1, so_co_trong_flagged]
    per_class_stats: dict[str, list[int]] = {c: [0, 0, 0] for c in CLASSIFIER_CLASSES}
    n_error = 0

    for img_path, expected in items:
        try:
            findings = _run_pipeline_with_models(img_path, detector, classifier, config)
        except Exception as exc:  # anh loi/khong dat chat luong - bao cao roi bo qua, khong dung ca batch
            n_error += 1
            print(f"[LOI] {img_path}: {exc}")
            continue

        flagged = findings.flagged()
        flagged_labels = [c.label for c in flagged]
        top1 = flagged_labels[0] if flagged else None
        detected_str = ", ".join(f"{c.label}:{c.confidence:.0%}" for c in flagged) or "(khong phat hien gi)"

        match_str = ""
        if expected:
            per_class_stats[expected][0] += 1
            if top1 == expected:
                per_class_stats[expected][1] += 1
            if expected in flagged_labels:
                per_class_stats[expected][2] += 1
            match_str = " | OK" if top1 == expected else (" | dung-nhung-khong-top1" if expected in flagged_labels else " | SAI")

        print(f"{img_path.name:30s} | ky_vong={expected or '?':22s} | phat_hien: {detected_str}{match_str}")

    print("\n--- Tong ket ---")
    total, total_top1, total_any = 0, 0, 0
    for label, (n, n_top1, n_any) in per_class_stats.items():
        if n == 0:
            continue
        total += n
        total_top1 += n_top1
        total_any += n_any
        print(f"{label:22s} n={n:4d}  top1_accuracy={n_top1/n:.0%}  co_trong_ket_qua={n_any/n:.0%}")
    if total:
        print(f"\nTONG: {total} anh co nhan | top1_accuracy={total_top1/total:.0%} | co_trong_ket_qua={total_any/total:.0%}")
    if n_error:
        print(f"({n_error} anh loi/khong dat chat luong, da bo qua)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Dung mot anh:  python 2_detect_dental_conditions.py <duong_dan_anh>")
        print("Dung ca folder: python 2_detect_dental_conditions.py <duong_dan_thu_muc>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_dir():
        run_batch(target)
    else:
        findings = run_full_pipeline(target)
        for line in to_human_findings(findings):
            print(line)
