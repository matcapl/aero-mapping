from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_NEON_URL")
    local_database_url: str = Field(..., env="DATABASE_LOCAL_URL")
    nominatim_url: str = Field(..., env="NOMINATIM_URL")
    overpass_url: str = Field(..., env="OVERPASS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "forbid"

settings = Settings()
