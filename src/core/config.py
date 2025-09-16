from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_neon_url: str = Field(..., env="DATABASE_NEON_URL")
    database_local_url: str = Field(..., env="DATABASE_LOCAL_URL")
    nominatim_url: str = Field(..., env="NOMINATIM_URL")
    overpass_url: str = Field(..., env="OVERPASS_URL")
    debug: bool = False
    timeout: int = 30

    # Enrichment API keys
    companies_house_api_key: str = Field("", env="COMPANIES_HOUSE_API_KEY")
    openai_api_key: str = Field("", env="OPENAI_API_KEY") 
    serp_api_key: str = Field("", env="SERP_API_KEY")  # For Google search
    
    # Enrichment settings
    enable_website_scraping: bool = Field(True, env="ENABLE_WEBSITE_SCRAPING")
    enable_companies_house: bool = Field(True, env="ENABLE_COMPANIES_HOUSE")
    enable_linkedin_search: bool = Field(True, env="ENABLE_LINKEDIN_SEARCH")
    enrichment_timeout: int = Field(30, env="ENRICHMENT_TIMEOUT")
    
    # Keyword filtering
    facility_keywords: dict = Field(default_factory=dict, env="FACILITY_KEYWORDS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()
