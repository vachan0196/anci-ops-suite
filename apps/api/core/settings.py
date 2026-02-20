from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Anci Ops Suite API"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
