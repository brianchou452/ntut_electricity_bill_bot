"""
Webhook notification service
"""

from datetime import datetime
from typing import Dict, List, Optional
import zoneinfo

import aiohttp

from ..database.models import ElectricityRecord
from ..utils.logger import app_logger
from ..utils.settings import settings


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


class DiscordNotifier(WebhookNotifier):
    async def _create_payload(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]],
        status: str,
    ) -> Dict[str, object]:
        color_map = {
            "success": 0x00FF00,  # 綠色
            "error": 0xFF0000,  # 紅色
            "warning": 0xFFAA00,  # 橘色
            "info": 0x0099FF,  # 藍色
        }

        # 使用 settings 中的時區設定
        local_tz = zoneinfo.ZoneInfo(settings.tz)
        now_local = datetime.now(local_tz)
        
        embed = {
            "title": title,
            "description": message,
            "color": color_map.get(status, 0x0099FF),
            "timestamp": now_local.isoformat(),
            "footer": {"text": "NTUT電費帳單機器人"},
        }

        if records:
            if len(records) <= 5:
                fields = []
                for i, record in enumerate(records, 1):
                    created_time = self._format_record_time(record.created_at, local_tz)
                    fields.append(
                        {
                            "name": f"記錄 #{i}",
                            "value": f"餘額: ${record.balance:.2f} NTD\n時間: {created_time}",
                            "inline": True,
                        }
                    )
                embed["fields"] = fields
            else:
                embed["fields"] = [
                    {
                        "name": "統計資訊",
                        "value": f"共 {len(records)} 筆記錄\n最新餘額: ${records[0].balance:.2f} NTD",
                        "inline": False,
                    }
                ]

        return {"embeds": [embed]}

    def _format_record_time(self, created_at: Optional[datetime], target_tz) -> str:
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


class NotificationManager:
    def __init__(self):
        self.notifiers: List[WebhookNotifier] = []

    def add_discord_webhook(self, webhook_url: str) -> None:
        if webhook_url:
            self.notifiers.append(DiscordNotifier(webhook_url))
            app_logger.info("已添加 Discord webhook 通知")

    async def send_crawl_success_notification(
        self, records: List[ElectricityRecord], duration: float
    ) -> None:
        title = "🟢 電費爬取成功"
        message = f"成功爬取 {len(records)} 筆電費記錄，耗時 {duration:.2f} 秒"

        await self._send_to_all(title, message, records, "success")

    async def send_crawl_error_notification(
        self, error_message: str, duration: float
    ) -> None:
        title = "🔴 電費爬取失敗"
        message = f"爬取過程發生錯誤：{error_message}\n耗時 {duration:.2f} 秒"

        await self._send_to_all(title, message, None, "error")

    async def send_partial_success_notification(
        self, records_count: int, duration: float
    ) -> None:
        title = "🟡 電費爬取部分成功"
        message = f"爬取到 {records_count} 筆記錄，但可能有遺漏\n耗時 {duration:.2f} 秒"

        await self._send_to_all(title, message, None, "warning")

    async def send_startup_notification(self) -> None:
        title = "🚀 機器人啟動"
        message = "NTUT電費帳單機器人已成功啟動，開始執行定時爬取任務"

        await self._send_to_all(title, message, None, "info")

    async def send_balance_notification(self, balance_text: str, balance_number: float) -> None:
        title = "💰 購電餘額查詢成功"
        message = f"目前購電餘額：{balance_text}\n餘額數值：{balance_number:.2f} NTD"

        await self._send_to_all(title, message, None, "success")

    async def _send_to_all(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]],
        status: str,
    ) -> None:
        if not self.notifiers:
            app_logger.info(f"無可用的通知服務，跳過發送: {title}")
            return

        for notifier in self.notifiers:
            try:
                await notifier.send_notification(title, message, records, status)
            except Exception as e:
                app_logger.error(f"通知發送失敗: {e}")
