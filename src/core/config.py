from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_neon_url: str = Field(..., env="DATABASE_NEON_URL")
    database_local_url: str = Field(..., env="DATABASE_LOCAL_URL")
    nominatim_url: str = Field(..., env="NOMINATIM_URL")
    overpass_url: str = Field(..., env="OVERPASS_URL")
    debug: bool = False
    timeout: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()
