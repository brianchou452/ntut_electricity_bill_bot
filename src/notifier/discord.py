"""
Discord webhook notification service
"""

import zoneinfo
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

from src.database.models import ElectricityRecord
from src.utils.logger import app_logger
from src.utils.settings import settings

from .base import WebhookNotifier


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
                    "value": f"餘額: ${record.balance:.2f} NTD\\n時間: {created_time}",
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

    async def send_chart_notification(self, chart_path: str, description: str) -> bool:
        """發送圖表通知到 Discord"""
        if not self.webhook_url:
            app_logger.warning("Webhook URL 未設定，跳過圖表發送")
            return False

        try:
            # 使用 multipart/form-data 發送檔案
            with open(chart_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("file", f, filename=Path(chart_path).name)

                # 建立 embed 資料
                embed = {
                    "title": description,
                    "color": 0x00FF00,
                    "image": {"url": f"attachment://{Path(chart_path).name}"},
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "NTUT電費帳單機器人"},
                }

                data.add_field(
                    "payload_json",
                    aiohttp.JsonPayload({"embeds": [embed]}),
                    content_type="application/json",
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.webhook_url,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        if response.status in (200, 204):
                            app_logger.info(f"圖表發送成功: {description}")
                            return True
                        else:
                            app_logger.error(f"圖表發送失敗，狀態碼: {response.status}")
                            return False

        except FileNotFoundError:
            app_logger.error(f"圖表檔案不存在: {chart_path}")
            return False
        except Exception as e:
            app_logger.error(f"圖表發送發生錯誤: {e}")
            return False
