from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dental Diagnosis Agent API"
    api_v1_prefix: str = "/api/v1"

    max_image_size_mb: float = 8.0
    allowed_image_formats: tuple[str, ...] = ("jpeg", "jpg", "png")

    # False khi model YOLO/LLM thật đã được tích hợp.
    use_mock_models: bool = True

    yolo_model_path: str | None = None  # đường dẫn tới file .pt
    yolo_confidence_threshold: float = 0.5

    cors_allow_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DENTAL_")


settings = Settings()
