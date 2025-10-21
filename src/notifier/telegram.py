"""
Telegram notification service
"""

import zoneinfo
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp

from src.database.models import ElectricityRecord
from src.utils.logger import app_logger
from src.utils.settings import settings

from .base import WebhookNotifier
from .levels import NotificationLevel


class TelegramNotifier(WebhookNotifier):
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout: int = 30,
        min_level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ):
        # Telegram Bot API endpoint
        super().__init__(
            webhook_url=f"https://api.telegram.org/bot{bot_token}/sendMessage",
            timeout=timeout,
            min_level=min_level,
        )
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.send_photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    async def _create_payload(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]],
        level: Union[NotificationLevel, int],
    ) -> Dict[str, object]:
        # 根據通知等級決定 emoji
        notification_level = NotificationLevel(level)
        level_emoji = {
            NotificationLevel.DEBUG: "🔍",
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "🟡",
            NotificationLevel.ERROR: "🔴",
            NotificationLevel.CRITICAL: "🚨",
        }

        # 使用 settings 中的時區設定
        local_tz = zoneinfo.ZoneInfo(settings.tz)
        now_local = datetime.now(local_tz)

        # 組合訊息文字
        text_parts = [
            f"{level_emoji.get(notification_level, 'ℹ️')} **{title}**",
            "",
            message,
        ]

        if records:
            # 永遠只有一個記錄，簡化處理
            record = records[0]
            created_time = self._format_record_time(record.created_at, local_tz)
            text_parts.extend(
                [
                    "",
                    "**餘額資訊**",
                    f"餘額: ${record.balance:.2f} NTD",
                    f"時間: {created_time}",
                ]
            )

        text_parts.extend(
            ["", f"_{now_local.strftime('%Y-%m-%d %H:%M:%S')}_", "_NTUT電費帳單機器人_"]
        )
        return {
            "chat_id": self.chat_id,
            "text": "\\n".join(text_parts),
            "parse_mode": "Markdown",
        }

    def _format_record_time(
        self, created_at: Optional[datetime], target_tz: zoneinfo.ZoneInfo
    ) -> str:
        """格式化記錄時間到指定時區"""
        if not created_at:
            return "未知時間"

        # 處理無時區資訊的情況，假設是 UTC
        if created_at.tzinfo is None:
            from datetime import timezone

            utc_time = created_at.replace(tzinfo=timezone.utc)
            local_time = utc_time.astimezone(target_tz)
        else:
            # 有時區資訊，直接轉換
            local_time = created_at.astimezone(target_tz)

        return local_time.strftime("%Y-%m-%d %H:%M:%S")

    async def send_chart_notification(self, chart_path: str, description: str) -> bool:
        """發送圖表通知到 Telegram"""
        if not self.bot_token or not self.chat_id:
            app_logger.warning("Telegram bot token 或 chat ID 未設定，跳過圖表發送")
            return False

        try:
            # 使用 multipart/form-data 發送照片
            with open(chart_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", self.chat_id)
                data.add_field("caption", description)
                data.add_field("photo", f, filename=Path(chart_path).name)

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.send_photo_url,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        if response.status == 200:
                            app_logger.info(f"Telegram 圖表發送成功: {description}")
                            return True
                        else:
                            response_text = await response.text()
                            app_logger.error(
                                f"Telegram 圖表發送失敗，狀態碼: {response.status}, "
                                f"回應: {response_text}"
                            )
                            return False

        except FileNotFoundError:
            app_logger.error(f"圖表檔案不存在: {chart_path}")
            return False
        except Exception as e:
            app_logger.error(f"Telegram 圖表發送發生錯誤: {e}")
            return False
