from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hotel Costa Azul API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    auth_secret: str = ""
    checkin_data_key: str = ""
    hotel_timezone: str = ""
    database_url: str = "postgresql+psycopg://hotel_user:hotel_password@localhost:5432/hotel_costa_azul"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
