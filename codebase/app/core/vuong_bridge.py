"""Cầu nối sang pipeline thật trong vuong/ (ngoài repo codebase/, phát triển
riêng, không sửa trực tiếp ở đây). Các file vuong/*.py có tên bắt đầu bằng số
(1_dental_preprocess.py...) nên phải nạp qua importlib.import_module, không
dùng cú pháp `import` thường được — và để import_module tìm thấy chúng,
vuong/ phải có mặt trong sys.path.

Chỉ gọi từ các Real*Service trong app/services/ — không import ở module-level
chỗ khác, để lỗi thiếu requirements-model.txt chỉ lộ ra khi thật sự cần model.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from types import ModuleType

from app.core.config import settings


@dataclass(frozen=True)
class VuongModules:
    prep: ModuleType  # 1_dental_preprocess
    detect: ModuleType  # 2_detect_dental_conditions
    chatbot: ModuleType  # 5_chatbot_dental_agent


@lru_cache
def load_vuong_modules() -> VuongModules:
    if settings.vuong_dir not in sys.path:
        sys.path.insert(0, settings.vuong_dir)
    try:
        prep = import_module("1_dental_preprocess")
        detect = import_module("2_detect_dental_conditions")
        chatbot = import_module("5_chatbot_dental_agent")
    except ImportError as exc:
        raise RuntimeError(
            f"Không import được pipeline thật từ vuong_dir='{settings.vuong_dir}'. "
            "Kiểm tra đường dẫn DENTAL_VUONG_DIR và đã cài đủ "
            "requirements-model.txt (torch, torchvision, ultralytics, opencv-python, "
            "PyYAML, openai, python-dotenv) chưa."
        ) from exc
    return VuongModules(prep=prep, detect=detect, chatbot=chatbot)
