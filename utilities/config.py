"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # MongoDB Configuration
    mongodb_uri: str = "mongodb://localhost:27017/"
    mongodb_db_name: str = "books_crawler"

    # Crawler Configuration
    target_url: str = "https://books.toscrape.com"
    crawler_concurrent_requests: int = 10
    crawler_retry_attempts: int = 3
    crawler_retry_delay: int = 2
    crawler_timeout: int = 30

    # Scheduler Configuration
    scheduler_enabled: bool = True
    scheduler_cron_hour: int = 2
    scheduler_cron_minute: int = 0

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Books Crawler API"
    api_version: str = "1.0.0"

    # Security
    api_key: str = "dev-api-key-12345"
    secret_key: str = "dev-secret-key-67890"

    # Rate Limiting
    rate_limit_per_hour: int = 100

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/crawler.log"

    # Reports
    report_output_dir: str = "reports"
    report_format: str = "json"

    # Email Alerts (Optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_email: Optional[str] = None


# Singleton instance
settings = Settings()


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration loaded successfully:")
    print(f"MongoDB URI: {settings.mongodb_uri}")
    print(f"Target URL: {settings.target_url}")
    print(f"API Port: {settings.api_port}")