"""
Base webhook notification service
"""

from typing import Dict, List, Optional, Union

import aiohttp

from src.database.models import ElectricityRecord
from src.utils.logger import app_logger

from .levels import NotificationLevel, LEVEL_NAMES


class WebhookNotifier:
    def __init__(
        self,
        webhook_url: str,
        timeout: int = 30,
        min_level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.min_level = NotificationLevel(min_level)

    async def send_notification(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]] = None,
        level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ) -> bool:
        if not self.webhook_url:
            app_logger.warning("Webhook URL 未設定，跳過通知發送")
            return False

        # 檢查通知等級是否符合最小等級要求
        notification_level = NotificationLevel(level)
        if notification_level < self.min_level:
            app_logger.debug(
                f"通知等級 {LEVEL_NAMES[notification_level]} < "
                f"最小等級 {LEVEL_NAMES[self.min_level]}，跳過發送: {title}"
            )
            return False

        try:
            payload = await self._create_payload(title, message, records, level)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status in (200, 204):
                        app_logger.info(f"Webhook 通知發送成功: {title}")
                        return True
                    else:
                        app_logger.error(
                            f"Webhook 通知發送失敗，狀態碼: {response.status}"
                        )
                        return False

        except aiohttp.ClientError as e:
            app_logger.error(f"Webhook 通知網路錯誤: {e}")
            return False
        except Exception as e:
            app_logger.error(f"Webhook 通知發送失敗: {e}")
            return False

    async def _create_payload(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]],
        level: Union[NotificationLevel, int],
    ) -> Dict[str, object]:
        from datetime import datetime
        from typing import Any

        timestamp = datetime.now().isoformat()

        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "title": title,
            "message": message,
            "level": LEVEL_NAMES[NotificationLevel(level)],
            "bot_name": "NTUT電費帳單機器人",
        }

        if records:
            payload["data"] = {
                "records_count": len(records),
                "records": [
                    self._format_record(record) for record in records[:10]
                ],  # 限制顯示前10筆
            }

            if len(records) > 10:
                payload["data"]["has_more"] = True
                payload["data"]["total_records"] = len(records)

        return payload

    def _format_record(self, record: ElectricityRecord) -> Dict:
        return {
            "balance": record.balance,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
