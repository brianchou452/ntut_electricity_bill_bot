"""
Settings configuration using Pydantic Settings
"""

from pydantic_settings import BaseSettings


class BotSettings(BaseSettings):
    # 必要配置
    ntut_username: str
    ntut_password: str

    # 調度配置
    cron_schedule: str = "0 */1 * * *"  # 每小時執行一次
    run_on_startup: bool = True
    tz: str = "Asia/Taipei"

    # 資料庫配置
    db_path: str = "data/electricity_bot.db"

    # Discord 通知配置
    discord_webhook_url: str = ""

    # 通知時間範圍配置
    notification_start_time: str = "06:00"  # 開始發送成功通知的時間 (HH:MM)
    notification_end_time: str = "23:00"  # 停止發送成功通知的時間 (HH:MM)
    notification_balance_threshold: float = 100.0  # 餘額低於此數值才發送通知

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# 全域設定實例
settings = BotSettings(
    ntut_username="",
    ntut_password=""
)
