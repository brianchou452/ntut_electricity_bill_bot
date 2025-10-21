"""
Notification manager for coordinating multiple notification services
"""

import zoneinfo
from datetime import time, datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.database.models import ElectricityRecord
from src.utils.logger import app_logger
from src.utils.settings import settings

from .base import WebhookNotifier
from .discord import DiscordNotifier
from .telegram import TelegramNotifier
from .levels import NotificationLevel


class NotificationManager:
    def __init__(self) -> None:
        self.notifiers: List[WebhookNotifier] = []

    def add_discord_webhook(
        self,
        webhook_url: str,
        min_level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ) -> None:
        if webhook_url:
            self.notifiers.append(DiscordNotifier(webhook_url, min_level=min_level))
            app_logger.info(f"已添加 Discord webhook 通知（最小等級：{min_level}）")

    def add_telegram_notifier(
        self,
        bot_token: str,
        chat_id: str,
        min_level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ) -> None:
        if bot_token and chat_id:
            self.notifiers.append(
                TelegramNotifier(bot_token, chat_id, min_level=min_level)
            )
            app_logger.info(f"已添加 Telegram 通知（最小等級：{min_level}）")

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
        message = f"爬取過程發生錯誤：{error_message}\\n耗時 {duration:.2f} 秒"

        await self._send_to_all(title, message, None, NotificationLevel.ERROR)

    async def send_partial_success_notification(
        self, records_count: int, duration: float
    ) -> None:
        title = "🟡 電費爬取部分成功"
        message = (
            f"爬取到 {records_count} 筆記錄，但可能有遺漏\\n耗時 {duration:.2f} 秒"
        )

        await self._send_to_all(title, message, None, NotificationLevel.WARNING)

    async def send_startup_notification(self) -> None:
        title = "🚀 機器人啟動"
        message = "NTUT電費帳單機器人已成功啟動，開始執行定時爬取任務"

        await self._send_to_all(title, message, None, NotificationLevel.INFO)

    async def send_daily_summary_notification(
        self, daily_summary: Dict, chart_path: Optional[str] = None
    ) -> None:
        """發送每日用電摘要通知"""
        date = daily_summary.get("date", "未知日期")
        total_usage = daily_summary.get("total_usage", 0)
        start_balance = daily_summary.get("start_balance", 0)
        end_balance = daily_summary.get("end_balance", 0)
        hourly_count = len(daily_summary.get("hourly_usage", []))

        title = "📊 每日用電摘要報告"

        if total_usage > 0:
            message = f"""📅 日期：{date}
💰 總用電金額：${total_usage:.2f} NTD
🔋 起始餘額：${start_balance:.2f} NTD
🔋 結束餘額：${end_balance:.2f} NTD
📈 記錄筆數：{hourly_count} 筆

{"📊 圖表已生成，請查看附檔" if chart_path else ""}"""
        else:
            message = f"""📅 日期：{date}
ℹ️ 今日無用電記錄或用電量為零

可能原因：
• 資料收集不足（少於2筆記錄）
• 系統維護期間
• 用電量極少"""

        # 發送文字通知
        await self._send_to_all(title, message, None, NotificationLevel.INFO)

        # 如果有圖表，發送圖表
        if chart_path and Path(chart_path).exists():
            await self._send_chart_to_all(chart_path, f"{date} 用電圖表")

    async def _send_chart_to_all(self, chart_path: str, description: str) -> None:
        """發送圖表到所有通知服務"""
        if not self.notifiers:
            app_logger.info(f"無可用的通知服務，跳過圖表發送: {description}")
            return

        for notifier in self.notifiers:
            try:
                if isinstance(notifier, (DiscordNotifier, TelegramNotifier)):
                    await notifier.send_chart_notification(chart_path, description)
            except Exception as e:
                app_logger.error(f"圖表發送失敗: {e}")

    async def send_balance_notification(self, balance_number: float) -> None:
        title = "💰 購電餘額查詢成功"
        message = f"餘額數值：{balance_number:.2f} NTD"

        # 檢查是否在通知時間範圍內
        if not self._is_within_notification_time():
            app_logger.info(f"成功通知已忽略（超出通知時間範圍）: {title} - {message}")
            return

        # 檢查餘額是否小於門檻值，只有低餘額才發送通知
        if balance_number >= settings.notification_balance_threshold:
            app_logger.info(
                f"成功通知已忽略（餘額 {balance_number:.2f} >= {settings.notification_balance_threshold}）: {title} - {message}"
            )
            return

        await self._send_to_all(title, message, None, NotificationLevel.SUCCESS)

    async def _send_to_all(
        self,
        title: str,
        message: str,
        records: Optional[List[ElectricityRecord]],
        level: Union[NotificationLevel, int] = NotificationLevel.INFO,
    ) -> None:
        if not self.notifiers:
            app_logger.info(f"無可用的通知服務，跳過發送: {title}")
            return

        for notifier in self.notifiers:
            try:
                await notifier.send_notification(title, message, records, level)
            except Exception as e:
                app_logger.error(f"通知發送失敗: {e}")
