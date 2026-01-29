from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Billing Slip Automation"
    debug: bool = True
    database_url: str = "sqlite:///./billing.db"

    class Config:
        env_file = ".env"


settings = Settings()
