from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    vision_model: str = "llava:7b"
    max_image_size_mb: int = 10
    max_batch_files: int = 10
    app_port: int = 8001
    history_db: str = "./data/history.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
