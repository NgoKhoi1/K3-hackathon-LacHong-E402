"""
Chuan bi du lieu + tien xu ly anh mau cho he thong sang loc rang mieng.

Du lieu tho tren may (da khao sat thuc te) gom 2 nhom rat khac nhau:

1) Tap co bounding box THAT (YOLO format), 4 lop:
   Caries_Gingivitus_ToothDiscoloration_Ulcer-yolo_annotated-Dataset/.../Data/
     images/train, images/val
     labels/train, labels/val   (moi dong: "<class_id> cx cy w h", class_id 0-3)
   File labels/train/labels.txt va labels/val/labels.txt CHI LA chu giai ten lop
   (1-indexed: 1=caries,2=ulcer,3=tooth discoloration,4=gingivitis), KHONG PHAI
   annotation cua anh -> phai loai file nay khi doc nhan.
   Vi data.yaml goc co bug (nc: 1 nhung names co 4 phan tu), script nay sinh lai
   1 dataset.yaml dung, KHONG sua truc tiep file goc.

2) Cac thu muc chi co anh phan loai theo lop (KHONG co bbox):
   Calculus/Calculus/                                    -> Calculus
   hypodontia/hypodontia/                                -> Hypodontia
   Data caries/.../caries orignal data set/done/          -> Caries (goc)
   Data caries/.../caries augmented data set/preview/     -> Caries (augmented)
   Gingivitis/Gingivitis/                                 -> Gingivitis
   Mouth Ulcer/.../ulcer original dataset/.../             -> Ulcers (goc)
   Mouth Ulcer/.../Mouth_Ulcer_augmented_DataSet/preview/ -> Ulcers (augmented)
   Tooth Discoloration/.../tooth discoloration original.../-> Tooth Discoloration (goc)
   Tooth Discoloration/.../Tooth_discoloration_augmented.../preview/ -> Tooth Discoloration (augmented)

   Calculus va Hypodontia KHONG co anh augmented rieng va KHONG co bbox o bat ky
   dau -> kien truc he thong dung classifier toan-anh (6 lop) de gan co/khong cho
   2 lop nay, thay vi ep bbox gia. Xem 3_dental_condition_model.py.

File nay co 2 nhom chuc nang:
  A. Xay dung manifest dataset (train/val/test) cho classifier + sinh dataset.yaml
     cho detector -> dung boi 4_train_dental_condition_model.py
  B. Tien xu ly anh mau dung chung cho ca luc train va luc suy luan (inference)
     -> dung boi 2_detect_dental_conditions.py va 5_chatbot_dental_agent.py
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
import yaml

# --------------------------------------------------------------------------
# Duong dan goc + danh sach lop
# --------------------------------------------------------------------------

BASE_DIR = Path(r"C:\lab-hackathon")
DATASET_DIR = BASE_DIR / "dataset"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
MANIFEST_DIR = ARTIFACTS_DIR / "manifests"

# Thu tu lop cua detector PHAI khop voi labels.txt / data.yaml goc (0-indexed)
DETECTOR_CLASSES = ["Caries", "Ulcers", "Tooth Discoloration", "Gingivitis"]

# Toan bo 6 lop cua bai toan, dung cho classifier toan anh
CLASSIFIER_CLASSES = [
    "Caries",
    "Calculus",
    "Gingivitis",
    "Tooth Discoloration",
    "Ulcers",
    "Hypodontia",
]

# Cau truc dataset/ (da don dep, phang, khong con thu muc long trung ten):
#   dataset/Calculus/*.jpg
#   dataset/Gingivitis/*.jpg
#   dataset/Hypodontia/*.jpg
#   dataset/Caries/{original,augmented}/*.jpg
#   dataset/Ulcers/{original,augmented}/*.jpg
#   dataset/Tooth Discoloration/{original,augmented}/*.jpg
#   dataset/yolo_bbox/{images,labels}/{train,val}
_YOLO_ROOT = DATASET_DIR / "yolo_bbox"
YOLO_IMAGES = {"train": _YOLO_ROOT / "images" / "train", "val": _YOLO_ROOT / "images" / "val"}
YOLO_LABELS = {"train": _YOLO_ROOT / "labels" / "train", "val": _YOLO_ROOT / "labels" / "val"}

# (thu_muc_anh, ten_lop, is_augmented)
CLASSIFICATION_SOURCES: list[tuple[Path, str, bool]] = [
    (DATASET_DIR / "Calculus", "Calculus", False),
    (DATASET_DIR / "Hypodontia", "Hypodontia", False),
    (DATASET_DIR / "Gingivitis", "Gingivitis", False),
    (DATASET_DIR / "Caries" / "original", "Caries", False),
    (DATASET_DIR / "Caries" / "augmented", "Caries", True),
    (DATASET_DIR / "Ulcers" / "original", "Ulcers", False),
    (DATASET_DIR / "Ulcers" / "augmented", "Ulcers", True),
    (DATASET_DIR / "Tooth Discoloration" / "original", "Tooth Discoloration", False),
    (DATASET_DIR / "Tooth Discoloration" / "augmented", "Tooth Discoloration", True),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

# --------------------------------------------------------------------------
# A. Xay dung manifest dataset
# --------------------------------------------------------------------------


class ImageRecord(NamedTuple):
    path: Path
    label: str
    is_augmented: bool
    split_hint: str | None  # "train"/"val" neu anh nay den tu tap YOLO (giu nguyen split goc)


def _label_from_yolo_file(label_path: Path) -> str | None:
    """Tra ve lop chiem da so trong 1 file annotation YOLO, hoac None neu rong."""
    counts: dict[int, int] = {}
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        class_id = int(line.split()[0])
        counts[class_id] = counts.get(class_id, 0) + 1
    if not counts:
        return None
    dominant_id = max(counts, key=counts.get)
    return DETECTOR_CLASSES[dominant_id]


def collect_yolo_records() -> list[ImageRecord]:
    """Anh tu tap co bbox cung duoc dua vao du lieu train classifier (nhan = lop
    chiem da so trong anh), giu nguyen split train/val goc de khong bi leak giua
    detector va classifier."""
    records: list[ImageRecord] = []
    for split, img_dir in YOLO_IMAGES.items():
        label_dir = YOLO_LABELS[split]
        for img_path in sorted(img_dir.iterdir()):
            if img_path.suffix not in IMAGE_EXTS:
                continue
            label_path = label_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue  # khong co annotation -> khong du tin cay de gan nhan classifier
            label = _label_from_yolo_file(label_path)
            if label is None:
                continue  # anh nen/khong co ton thuong -> bo qua khoi classifier
            records.append(ImageRecord(img_path, label, False, split))
    return records


def collect_classification_records() -> list[ImageRecord]:
    records: list[ImageRecord] = []
    for folder, label, is_augmented in CLASSIFICATION_SOURCES:
        if not folder.exists():
            continue
        for img_path in sorted(folder.iterdir()):
            if img_path.suffix in IMAGE_EXTS:
                records.append(ImageRecord(img_path, label, is_augmented, None))
    return records


AUGMENT_CAP_MULTIPLIER = 4
# Vai lop (Caries/Ulcers/Tooth Discoloration) chi co 183-265 anh GOC that su,
# duoc augment len ~10x de "trong" du so luong nhu cac lop khac (1251-2349 anh
# goc that). Neu dung het augmented, model gan nhu hoc thuoc vai tram anh goc
# qua cac ban xoay/lat/chinh sang - overfit ro rang (da xac nhan: lop it anh
# goc nhat - Tooth Discoloration 183 anh - cung la lop precision thap nhat khi
# train, 0.49). Gioi han so ban augmented giu lai toi da = AUGMENT_CAP_MULTIPLIER
# x so anh goc cua chinh lop do, thay vi dung toan bo, de giam trung lap.


def stratified_split(
    records: list[ImageRecord],
    val_ratio: float = 0.15,
    test_ratio: float = 0.10,
    seed: int = 42,
    augment_cap_multiplier: int = AUGMENT_CAP_MULTIPLIER,
) -> dict[str, list[ImageRecord]]:
    """Chia train/val/test theo tung lop. De tranh data leakage giua anh goc va
    anh augmented cua chinh no, CHI anh khong-augmented moi duoc dua vao val/test;
    anh augmented luon o lai trong train (nhung bi gioi han so luong - xem
    AUGMENT_CAP_MULTIPLIER). Anh da co split_hint (tu tap YOLO) giu nguyen split do."""
    rng = random.Random(seed)
    by_label: dict[str, list[ImageRecord]] = {}
    for r in records:
        by_label.setdefault(r.label, []).append(r)

    splits: dict[str, list[ImageRecord]] = {"train": [], "val": [], "test": []}
    for label, items in by_label.items():
        fixed = [r for r in items if r.split_hint is not None]
        for r in fixed:
            splits[r.split_hint].append(r)

        free = [r for r in items if r.split_hint is None]
        eligible = [r for r in free if not r.is_augmented]
        augmented = [r for r in free if r.is_augmented]
        rng.shuffle(eligible)
        rng.shuffle(augmented)

        cap = augment_cap_multiplier * len(eligible)
        if len(augmented) > cap:
            print(f"[manifest] {label}: gioi han augmented {len(augmented)} -> {cap} anh (cap {augment_cap_multiplier}x so voi {len(eligible)} anh goc)")
            augmented = augmented[:cap]

        n_val = int(len(eligible) * val_ratio)
        n_test = int(len(eligible) * test_ratio)
        val_part = eligible[:n_val]
        test_part = eligible[n_val : n_val + n_test]
        train_part = eligible[n_val + n_test :] + augmented

        splits["val"].extend(val_part)
        splits["test"].extend(test_part)
        splits["train"].extend(train_part)

    for part in splits.values():
        rng.shuffle(part)
    return splits


def write_classifier_manifest(splits: dict[str, list[ImageRecord]], out_dir: Path = MANIFEST_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    label_map = {label: idx for idx, label in enumerate(CLASSIFIER_CLASSES)}
    (out_dir / "label_map.json").write_text(json.dumps(label_map, ensure_ascii=False, indent=2), encoding="utf-8")

    for split_name, items in splits.items():
        csv_path = out_dir / f"{split_name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filepath", "label", "label_id", "is_augmented"])
            for r in items:
                writer.writerow([str(r.path), r.label, label_map[r.label], int(r.is_augmented)])
        print(f"[manifest] {split_name}: {len(items)} anh -> {csv_path}")


# Lop qua it box luc train so voi Caries (108 vs 1221) - ultralytics KHONG ho
# tro truyen trong so loss theo tung lop truc tiep qua model.train(...), nen
# cach thay the tuong duong la OVERSAMPLE: lap lai anh co chua lop hiem trong
# danh sach train de model nhin thay no thuong xuyen hon moi epoch.
OVERSAMPLE_CLASSES = ["Ulcers"]
OVERSAMPLE_MULTIPLIER = 4


def _label_file_has_any_class(label_path: Path, target_class_ids: set[int]) -> bool:
    if not label_path.exists():
        return False
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and int(line.split()[0]) in target_class_ids:
            return True
    return False


def build_yolo_train_list(out_path: Path = ARTIFACTS_DIR / "train_images_oversampled.txt") -> Path:
    """Sinh file .txt liet ke duong dan anh train cho YOLO, trong do anh chua
    lop trong OVERSAMPLE_CLASSES duoc lap lai OVERSAMPLE_MULTIPLIER lan. Ultralytics
    cho phep train: tro toi 1 file .txt thay vi thu muc, va doc lap lai duong dan
    ma khong can nhan ban file that tren o dia."""
    target_ids = {DETECTOR_CLASSES.index(c) for c in OVERSAMPLE_CLASSES}
    img_dir = YOLO_IMAGES["train"]
    label_dir = YOLO_LABELS["train"]

    lines: list[str] = []
    n_images = 0
    n_oversampled = 0
    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix not in IMAGE_EXTS:
            continue
        n_images += 1
        label_path = label_dir / f"{img_path.stem}.txt"
        if _label_file_has_any_class(label_path, target_ids):
            n_oversampled += 1
            lines.extend([str(img_path)] * OVERSAMPLE_MULTIPLIER)
        else:
            lines.append(str(img_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"[oversample] {n_images} anh goc, {n_oversampled} anh co lop {OVERSAMPLE_CLASSES} "
        f"duoc lap {OVERSAMPLE_MULTIPLIER}x -> tong {len(lines)} dong trong {out_path}"
    )
    return out_path


def build_yolo_dataset_yaml(out_path: Path = ARTIFACTS_DIR / "dataset.yaml") -> Path:
    """Sinh lai file cau hinh YOLO dung (data.yaml goc bi bug nc=1 trong khi co
    4 lop). Khong ghi de len file goc. train: tro toi danh sach anh da oversample
    (xem build_yolo_train_list), val: giu nguyen thu muc goc (KHONG oversample
    tap val - se lam sai lech metric danh gia)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    train_list_path = build_yolo_train_list()
    config = {
        "path": str(_YOLO_ROOT),
        "train": str(train_list_path),
        "val": str(YOLO_IMAGES["val"]),
        "nc": len(DETECTOR_CLASSES),
        "names": DETECTOR_CLASSES,
    }
    out_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[dataset.yaml] da sinh: {out_path}")
    return out_path


def build_all_manifests() -> None:
    records = collect_yolo_records() + collect_classification_records()
    print(f"[manifest] tong so anh thu thap duoc: {len(records)}")
    for label in CLASSIFIER_CLASSES:
        n = sum(1 for r in records if r.label == label)
        print(f"  - {label}: {n} anh")
    splits = stratified_split(records)
    write_classifier_manifest(splits)
    build_yolo_dataset_yaml()


# --------------------------------------------------------------------------
# B. Tien xu ly anh mau (dung chung train/inference)
# --------------------------------------------------------------------------

CLASSIFIER_IMG_SIZE = 240  # do phan giai chuan cua EfficientNet-B1 (xem 3_dental_condition_model.py)

BLUR_REF_LONG_SIDE = 800         # kich thuoc chuan hoa truoc khi do blur (xem compute_blur_score)
BLUR_VAR_THRESHOLD = 8.0         # phuong sai Laplacian (tren anh da chuan hoa kich thuoc) duoi nguong nay = anh mo
BRIGHTNESS_MIN = 40.0            # do sang trung binh (0-255) qua toi
BRIGHTNESS_MAX = 235.0           # qua sang / chay sang
ORAL_HUE_MIN_RATIO = 0.12        # ty le pixel co mau "khoang mieng" toi thieu


@dataclass
class ImageQualityReport:
    is_acceptable: bool
    blur_score: float
    brightness: float
    oral_cavity_ratio: float
    issues: list[str] = field(default_factory=list)


def load_image(path: str | Path) -> np.ndarray:
    """Doc anh mau, tra ve BGR uint8 (dinh dang mac dinh cua OpenCV)."""
    path = str(path)
    data = np.fromfile(path, dtype=np.uint8)  # an toan voi duong dan Unicode/co dau tren Windows
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Khong doc duoc anh: {path}")
    return image


def compute_blur_score(image: np.ndarray) -> float:
    """Phuong sai Laplacian sau khi CHUAN HOA KICH THUOC ve BLUR_REF_LONG_SIDE.

    Neu do truc tiep tren anh o do phan giai goc, chi so nay bi lech rat nhieu
    theo kich thuoc anh (anh chup dien thoai/camera nha khoa hien dai thuong
    la anh rat lon -> phuong sai Laplacian tho tren toan anh bi "loang" ra va
    trong ve thap gia tao, du anh net that su). Chuan hoa ve cung 1 kich thuoc
    truoc khi do giup gia tri co the so sanh duoc giua cac nguon anh khac nhau.
    """
    h, w = image.shape[:2]
    scale = BLUR_REF_LONG_SIDE / max(h, w)
    if scale < 1.0:  # chi thu nho anh lon hon kich thuoc chuan, khong phong to anh nho
        resized = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = image
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_brightness(image: np.ndarray) -> float:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 2].mean())


def compute_oral_cavity_ratio(image: np.ndarray) -> float:
    """Heuristic don gian (KHONG phai model): uoc luong ty le pixel mang sac
    hong/do/trang dac trung cua nieu mac mieng - rang - nuou, de loc so bo cac
    anh ro rang khong phai anh khoang mieng (vd anh phong canh, tai lieu)."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    # vung hue do/hong (nuou, moi, ton thuong) + vung do sang cao/bao hoa thap (rang trang)
    reddish = ((h < 15) | (h > 165)) & (s > 30) & (v > 40)
    whitish = (s < 60) & (v > 120)
    mask = reddish | whitish
    return float(mask.mean())


def check_image_quality(image: np.ndarray) -> ImageQualityReport:
    blur = compute_blur_score(image)
    brightness = compute_brightness(image)
    oral_ratio = compute_oral_cavity_ratio(image)

    issues: list[str] = []
    if blur < BLUR_VAR_THRESHOLD:
        issues.append("Anh bi mo, ban hay giu may on dinh va chup net hon.")
    if brightness < BRIGHTNESS_MIN:
        issues.append("Anh hoi thieu sang, ban hay chup o noi du anh sang hon.")
    elif brightness > BRIGHTNESS_MAX:
        issues.append("Anh bi chay sang/qua chan sang, ban hay giam anh sang hoac tranh flash truc tiep.")
    if oral_ratio < ORAL_HUE_MIN_RATIO:
        issues.append(
            "Anh chua thay ro vung rang/nuou/khoang mieng, ban hay chup gan hon va tap trung dung vung can xem."
        )

    return ImageQualityReport(
        is_acceptable=len(issues) == 0,
        blur_score=blur,
        brightness=brightness,
        oral_cavity_ratio=oral_ratio,
        issues=issues,
    )


def normalize_color(image: np.ndarray) -> np.ndarray:
    """Can bang trang (gray-world) + CLAHE tren kenh L (LAB) de giam lech mau/anh
    sang giua cac nguon anh khac nhau, van giu thong tin mau RGB (khong chuyen
    grayscale nhu quy trinh X-quang)."""
    # gray-world white balance
    b, g, r = cv2.split(image.astype(np.float32))
    mean_b, mean_g, mean_r = b.mean(), g.mean(), r.mean()
    mean_gray = (mean_b + mean_g + mean_r) / 3.0
    b *= mean_gray / (mean_b + 1e-6)
    g *= mean_gray / (mean_g + 1e-6)
    r *= mean_gray / (mean_r + 1e-6)
    balanced = cv2.merge([b, g, r])
    balanced = np.clip(balanced, 0, 255).astype(np.uint8)

    # CLAHE tren do sang (L), giu nguyen kenh mau (a, b)
    lab = cv2.cvtColor(balanced, cv2.COLOR_BGR2LAB)
    l, a, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b_channel])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def preprocess_for_inference(image: np.ndarray) -> dict:
    """Pipeline dung chung cho inference. QUAN TRONG: moi nhanh dau ra phai
    khop CHINH XAC voi nhung gi model tuong ung da thay LUC TRAIN, neu khong se
    gay lech train/inference nghiem trong - da xac nhan bang thuc nghiem: voi
    ban cu (denoise + letterbox-pad cho classifier, normalize_color+denoise cho
    detector), anh test bi doan sai (vd Gingivitis -> Hypodontia 23%) nhung doan
    dung voi confidence cao (90%+) khi dung dung preprocessing luc train. Chi tiet:

    - detector: ultralytics doc anh THO truc tiep tu dia luc train (khong qua
      normalize_color/denoise) -> phai dua anh THO vao luc inference.
    - classifier: luc train (xem ClassifierDataset trong
      4_train_dental_condition_model.py) dung normalize_color(image) roi
      transforms.Resize keo dan ve 224x224 (KHONG letterbox-pad, KHONG denoise)
      -> lam dung y het o day.
    """
    normalized = normalize_color(image)
    classifier_input = cv2.resize(
        normalized, (CLASSIFIER_IMG_SIZE, CLASSIFIER_IMG_SIZE), interpolation=cv2.INTER_LINEAR
    )
    classifier_input_rgb = cv2.cvtColor(classifier_input, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return {
        "detector_input_bgr": image,
        "classifier_input_rgb": classifier_input_rgb,
    }


if __name__ == "__main__":
    build_all_manifests()
