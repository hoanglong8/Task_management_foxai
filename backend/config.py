from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./tasks.db"

    # JWT
    jwt_secret_key: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10080  # 7 days

    # Admin seed account
    admin_email: str = "hoanglong208@gmail.com"
    admin_password: str = "change_me"
    admin_full_name: str = "Nguyễn Hoàng Long"

    # OpenAI
    openai_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""

    # Zalo
    zalo_app_id: str = ""
    zalo_app_secret: str = ""
    zalo_oa_access_token: str = ""
    zalo_webhook_secret: str = ""

    # Facebook
    facebook_page_access_token: str = ""
    facebook_verify_token: str = "foxai_verify_token"
    facebook_app_secret: str = ""

    # WhatsApp
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = "foxai_whatsapp_verify"

    # Misc
    tasks_file: str = "tasks.json"
    standup_dir: str = "./daily"
    reminder_hour: int = 9
    reminder_minute: int = 0
    timezone: str = "Asia/Ho_Chi_Minh"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
