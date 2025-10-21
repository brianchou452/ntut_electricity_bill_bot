"""
Base webhook notification service
"""

from typing import Dict, List, Optional

import aiohttp

from src.database.models import ElectricityRecord
from src.utils.logger import app_logger


class WebhookNotifier:
    def __init__(self, webhook_url: str, timeout: int = 30):
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send_notification(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]] = None,
        status: str = "info",
    ) -> bool:
        if not self.webhook_url:
            app_logger.warning("Webhook URL 未設定，跳過通知發送")
            return False

        try:
            payload = await self._create_payload(title, message, records, status)

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
        status: str,
    ) -> Dict[str, object]:
        from datetime import datetime

        timestamp = datetime.now().isoformat()

        payload = {
            "timestamp": timestamp,
            "title": title,
            "message": message,
            "status": status,
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
