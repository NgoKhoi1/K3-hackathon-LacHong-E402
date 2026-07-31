"""
Dinh nghia model cho he thong sang loc rang mieng tu anh mau.

Kien truc hybrid (xem 1_dental_preprocess.py de biet ly do):
  - Detector (YOLOv8, ultralytics): dinh vi bbox cho 4 lop CO annotation that
    trong dataset - Caries, Ulcers, Tooth Discoloration, Gingivitis.
  - Classifier (CNN toan anh, 6 lop): gan nhan muc do "co/khong" cho ca 6 lop,
    bao gom Calculus va Hypodontia - 2 lop khong co bbox that trong dataset.
"""

from __future__ import annotations

import io
import math
import random
from typing import Sequence

import torch
import torch.nn as nn
import torchvision
from PIL import Image, ImageFilter
from torchvision import transforms

from importlib import import_module

_prep = import_module("1_dental_preprocess")
CLASSIFIER_CLASSES = _prep.CLASSIFIER_CLASSES
CLASSIFIER_IMG_SIZE = _prep.CLASSIFIER_IMG_SIZE
DETECTOR_CLASSES = _prep.DETECTOR_CLASSES


# --------------------------------------------------------------------------
# Detector (YOLOv8 qua ultralytics) - kien truc da co san, chi can khoi tao
# --------------------------------------------------------------------------


def create_yolo_detector(pretrained_weights: str = "yolov8n.pt"):
    """Tra ve model ultralytics YOLO, khoi tao tu weight pretrain COCO (yolov8n
    = ban nho nhat, phu hop demo/hackathon). So luong lop (nc) va ten lop duoc
    quyet dinh boi dataset.yaml luc train (xem build_yolo_dataset_yaml), khong
    can khai bao lai o day."""
    from ultralytics import YOLO

    return YOLO(pretrained_weights)


# --------------------------------------------------------------------------
# Classifier toan anh (6 lop)
# --------------------------------------------------------------------------


class DentalConditionClassifier(nn.Module):
    """EfficientNet-B1 (pretrain ImageNet) voi head thay bang softmax 6 lop.
    Anh dau vao 240x240 (do phan giai chuan cua B1, xem CLASSIFIER_IMG_SIZE
    trong 1_dental_preprocess.py) - nhinh hon B0 (224x224) nhung nhe hon nhieu
    so B3 (300x300, ~4.6x FLOPs B0, gay cham >8x va gan day VRAM 6GB khi thu).
    B1 chi ~1.8x FLOPs B0 - can bang tot hon giua dung luong model va toc do/
    rui ro overfit tren dataset ~8.300 anh train sau khi gioi han augment.

    Moi thu muc du lieu goc chi gan 1 nhan/anh (single-label theo lop), nen
    model dung softmax multi-class thay vi sigmoid multi-label - dung voi ban
    chat du lieu hien co. Luc suy luan, cac lop co xac suat cao thu 2 tro len
    van duoc bao cao nhu "kha nang lien quan" (xem 2_detect_dental_conditions.py),
    khong bi loai bo chi vi khong phai lop co xac suat cao nhat.
    """

    def __init__(self, num_classes: int = len(CLASSIFIER_CLASSES), pretrained: bool = True, dropout: float = 0.3):
        super().__init__()
        weights = torchvision.models.EfficientNet_B1_Weights.DEFAULT if pretrained else None
        backbone = torchvision.models.efficientnet_b1(weights=weights)
        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(p=dropout, inplace=True),
            nn.Linear(in_features, num_classes),
        )
        self.backbone = backbone

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)  # logits, ap dung softmax ben ngoai khi suy luan


def build_classifier(num_classes: int = len(CLASSIFIER_CLASSES), pretrained: bool = True) -> DentalConditionClassifier:
    return DentalConditionClassifier(num_classes=num_classes, pretrained=pretrained)


# --------------------------------------------------------------------------
# Augmentation / transform cho classifier
# --------------------------------------------------------------------------

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]


class _AddGaussianNoise:
    """Nhieu Gaussian nhe len tensor da chuan hoa [0,1], mo phong nhieu cam bien
    dien thoai. std nho de khong pha hong tin hieu mau (dac trung quan trong nhat
    cua bai toan nay)."""

    def __init__(self, std: float = 0.02):
        self.std = std

    def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
        noise = torch.randn_like(tensor) * self.std
        return torch.clamp(tensor + noise, 0.0, 1.0)


# --- Domain-randomization: 6 lop den tu 6 nguon anh rat khac nhau ve do phan
# giai/nen/do net. Model rat de "hoc thuoc" phong cach nguon anh thay vi dac
# trung lam sang that (da xac nhan qua thuc nghiem: anh that cua nguoi dung bi
# model doan sai nhieu du metric train cao). 3 transform duoi day gia lap bien
# thien thuong gap o ngoai doi (nen JPEG qua Zalo/Messenger, camera dien thoai
# do phan giai thap, tay run/mat net nhe) de giam phu thuoc vao style nguon.


class RandomJPEGCompression:
    """Gia lap anh da qua nhieu lan nen JPEG (gui qua mang xa hoi/chat app)."""

    def __init__(self, quality_range: tuple[int, int] = (30, 75), p: float = 0.35):
        self.quality_range = quality_range
        self.p = p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        quality = random.randint(*self.quality_range)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return Image.open(buffer).convert("RGB")


class RandomDownUpsample:
    """Thu nho anh xuong 1 ty le ngau nhien roi phong lai kich thuoc goc, gia
    lap anh chup tu camera/dien thoai do phan giai thap hon anh dataset."""

    def __init__(self, scale_range: tuple[float, float] = (0.35, 0.75), p: float = 0.35):
        self.scale_range = scale_range
        self.p = p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        w, h = img.size
        scale = random.uniform(*self.scale_range)
        small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        return small.resize((w, h), Image.BILINEAR)


class RandomSoftBlur:
    """Lam mem anh nhe (gaussian blur ban kinh nho), gia lap tay run/hoi mat net
    - KHONG dung blur manh vi anh van phai giu du chi tiet de nhan dang."""

    def __init__(self, radius_range: tuple[float, float] = (0.5, 2.0), p: float = 0.25):
        self.radius_range = radius_range
        self.p = p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        radius = random.uniform(*self.radius_range)
        return img.filter(ImageFilter.GaussianBlur(radius=radius))


def get_train_transforms(img_size: int = CLASSIFIER_IMG_SIZE) -> transforms.Compose:
    """Augmentation theo dung tinh than dataset: rotate nhe, flip ngang,
    brightness/contrast nhe, scale nhe, noise nhe - CONG THEM domain-randomization
    (JPEG/do phan giai/do net) de giam overfit vao phong cach tung nguon anh.
    Khong dung augmentation mau manh (vd hue-jitter lon) vi mau sac la tin hieu
    chan doan chinh (nuou do, mang bam vang/nau, rang doi mau...)."""
    return transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.RandomResizedCrop(img_size, scale=(0.9, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            RandomDownUpsample(),
            RandomSoftBlur(),
            RandomJPEGCompression(),
            transforms.ToTensor(),
            _AddGaussianNoise(std=0.02),
            transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ]
    )


def get_eval_transforms(img_size: int = CLASSIFIER_IMG_SIZE) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ]
    )


# --------------------------------------------------------------------------
# Xu ly mat can bang lop (Caries/Gingivitis chiem da so trong tap co bbox;
# Ulcers rat thua - 108 box train, 0 box val)
# --------------------------------------------------------------------------


def compute_class_weights(label_ids: Sequence[int], num_classes: int = len(CLASSIFIER_CLASSES)) -> torch.Tensor:
    """Trong so nghich dao tan suat lop, dung cho nn.CrossEntropyLoss(weight=...)."""
    counts = [0] * num_classes
    for label_id in label_ids:
        counts[label_id] += 1
    total = sum(counts)
    weights = [total / (num_classes * max(c, 1)) for c in counts]
    return torch.tensor(weights, dtype=torch.float32)
