from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "life_recorder"
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    S3_BUCKET: str | None = None
    MAPBOX_TOKEN: str | None = None
    OSRM_BASE_URL: str | None = None
    OPENAI_API_KEY: str | None = None
    ENV: str = "dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
