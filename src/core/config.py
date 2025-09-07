from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    local_database_url: str = Field(..., env="LOCAL_DATABASE_URL")
    nominatim_url: str = Field(..., env="NOMINATIM_URL")
    overpass_url: str = Field(..., env="OVERPASS_URL")

    class Config:
        env_file = ".env"

settings = Settings()
