"""
Webhook notification service
"""

from datetime import datetime, time
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
            # 永遠只有一個記錄，簡化處理
            record = records[0]
            created_time = self._format_record_time(record.created_at, local_tz)
            embed["fields"] = [
                {
                    "name": "餘額資訊",
                    "value": f"餘額: ${record.balance:.2f} NTD\n時間: {created_time}",
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

    def _is_within_notification_time(self) -> bool:
        """檢查當前時間是否在通知時間範圍內"""
        try:
            # 解析設定中的時間
            start_time = time.fromisoformat(settings.notification_start_time)
            end_time = time.fromisoformat(settings.notification_end_time)
            
            # 取得當前本地時間
            local_tz = zoneinfo.ZoneInfo(settings.tz)
            current_time = datetime.now(local_tz).time()
            
            # 處理跨日情況 (例如 23:00 到 06:00)
            if start_time <= end_time:
                # 正常情況：06:00 到 23:00
                return start_time <= current_time <= end_time
            else:
                # 跨日情況：23:00 到 06:00 (下一日)
                return current_time >= start_time or current_time <= end_time
                
        except ValueError as e:
            app_logger.error(f"通知時間設定格式錯誤: {e}")
            return True  # 設定有誤時預設允許發送


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

    async def send_balance_notification(self, balance_number: float) -> None:
        title = "💰 購電餘額查詢成功"
        message = f"餘額數值：{balance_number:.2f} NTD"

        # 檢查是否在通知時間範圍內
        if not self._is_within_notification_time():
            app_logger.info(f"成功通知已忽略（超出通知時間範圍）: {title} - {message}")
            return

        # 檢查餘額是否小於門檻值，只有低餘額才發送通知
        if balance_number >= settings.notification_balance_threshold:
            app_logger.info(f"成功通知已忽略（餘額 {balance_number:.2f} >= {settings.notification_balance_threshold}）: {title} - {message}")
            return

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
