from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# codebase/app/core/config.py -> ../../.. = thư mục gốc chứa cả codebase/ và vuong/
_DEFAULT_VUONG_DIR = str(Path(__file__).resolve().parents[3] / "vuong")


class Settings(BaseSettings):
    app_name: str = "Dental Diagnosis Agent API"
    api_v1_prefix: str = "/api/v1"

    max_image_size_mb: float = 8.0
    allowed_image_formats: tuple[str, ...] = ("jpeg", "jpg", "png")

    # Thư mục chứa pipeline thật (vuong/) — modules được import động qua
    # importlib (tên file có số ở đầu nên không import kiểu thường được).
    vuong_dir: str = _DEFAULT_VUONG_DIR
    detector_conf_threshold: float = 0.35
    classifier_conf_threshold: float = 0.5
    inference_device: str = "cpu"  # "cuda" nếu máy có GPU và đã cài torch bản GPU

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    cors_allow_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DENTAL_")


settings = Settings()
