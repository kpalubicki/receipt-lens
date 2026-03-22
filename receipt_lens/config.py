from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    vision_model: str = "llava:7b"
    max_image_size_mb: int = 10
    app_port: int = 8001

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
