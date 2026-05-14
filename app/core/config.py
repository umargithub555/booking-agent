from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from fastapi_mail import ConnectionConfig
from pydantic import Field
import enum


class Settings(BaseSettings):
    APP_NAME: str = "Booking Agent"
    APP_DESCRIPTION: str = "API for Agentic Booking System"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal['development', 'production'] = 'development'

    SECRET_KEY:str
    ALGORITHM:str
    ACCESS_TOKEN_EXPIRE_TIME:int

    DATABASE_NAME: str = Field(..., alias='DATABASE_NAME')
    DATABASE_URL: str = Field(..., alias='DATABASE_URL')


    mail_username: str = Field(..., alias="MAIL_USERNAME")
    mail_password: str = Field(..., alias="MAIL_PASSWORD")
    mail_from: str = Field(..., alias="MAIL_FROM")

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    This ensures that settings are loaded only once,
    improving performance.
    """
    return Settings()



settings = get_settings()



conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)



