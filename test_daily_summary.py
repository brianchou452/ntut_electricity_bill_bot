#!/usr/bin/env python3
"""
每日用電摘要功能測試

此腳本用於測試新增的每日用電摘要和圖表生成功能
包含假資料生成、資料庫操作、圖表生成和通知發送等功能
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 加入專案根目錄到 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.database import Database
from src.database.models import ElectricityRecord
from src.notifier.webhook import NotificationManager
from src.scheduler.scheduler import TaskScheduler
from src.utils.chart_generator import ChartGenerator
from src.utils.logger import app_logger


class TestDataGenerator:
    """測試資料生成器"""

    def __init__(self):
        self.database = Database("data/test_electricity_bot.db")

    async def init_test_database(self):
        """初始化測試資料庫"""
        await self.database.init_database()
        app_logger.info("測試資料庫初始化完成")

    async def clear_test_data(self):
        """清空測試資料"""
        import aiosqlite

        try:
            async with aiosqlite.connect(self.database.db_path) as db:
                await db.execute("DELETE FROM electricity_records")
                await db.execute("DELETE FROM crawler_logs")
                await db.commit()
            app_logger.info("測試資料已清空")
        except Exception as e:
            app_logger.error(f"清空測試資料失敗: {e}")

    async def generate_daily_fake_data(
        self, target_date: str, start_balance: float = 500.0
    ):
        """
        生成指定日期的假資料

        Args:
            target_date: 目標日期 (YYYY-MM-DD)
            start_balance: 起始餘額
        """
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")

            # 生成一天24小時的假資料（每小時一筆）
            current_balance = start_balance
            records = []

            for hour in range(24):
                # 模擬每小時用電 1-5 元的消費
                hourly_usage = random.uniform(1.0, 5.0)
                current_balance -= hourly_usage

                # 確保餘額不會變成負數
                current_balance = max(0, current_balance)

                # 創建該小時的記錄
                record_time = date_obj + timedelta(hours=hour)

                record = ElectricityRecord(
                    balance=round(current_balance, 2), created_at=record_time
                )

                # 插入到資料庫
                await self.database.insert_electricity_record(record)
                records.append(record)

            app_logger.info(f"已生成 {target_date} 的 {len(records)} 筆假資料")
            app_logger.info(
                f"起始餘額: ${start_balance:.2f}, 結束餘額: ${current_balance:.2f}"
            )
            app_logger.info(f"總用電金額: ${start_balance - current_balance:.2f}")

            return records

        except Exception as e:
            app_logger.error(f"生成假資料失敗: {e}")
            return []

    async def generate_multiple_days_data(self, days: int = 7):
        """生成多天的假資料"""
        base_date = datetime.now() - timedelta(days=days)
        start_balance = 500.0

        for i in range(days):
            target_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            # 每天起始餘額稍微不同
            daily_start = start_balance - (i * 50)  # 每天遞減 50 元
            await self.generate_daily_fake_data(target_date, max(100, daily_start))


class DailySummaryTester:
    """每日摘要功能測試器"""

    def __init__(self, webhook_url: str = ""):
        self.database = Database("data/test_electricity_bot.db")
        self.chart_generator = ChartGenerator()
        self.notification_manager = NotificationManager()
        self.data_generator = TestDataGenerator()

        # 如果提供了 webhook URL，就配置通知服務
        if webhook_url:
            self.notification_manager.add_discord_webhook(webhook_url)
            app_logger.info(f"已配置 Discord webhook 用於測試")

    async def test_database_queries(self, target_date: str = None):
        """測試資料庫查詢功能"""
        if target_date is None:
            yesterday = datetime.now() - timedelta(days=1)
            target_date = yesterday.strftime("%Y-%m-%d")

        app_logger.info(f"=== 測試資料庫查詢功能 ({target_date}) ===")

        # 測試取得昨日記錄
        records = await self.database.get_yesterday_records(target_date)
        app_logger.info(f"查詢到 {len(records)} 筆記錄")

        if records:
            app_logger.info(
                f"第一筆記錄: {records[0].created_at} - ${records[0].balance}"
            )
            app_logger.info(
                f"最後一筆記錄: {records[-1].created_at} - ${records[-1].balance}"
            )

        # 測試每日摘要
        summary = await self.database.get_daily_usage_summary(target_date)
        app_logger.info(f"每日摘要: {summary}")

        return summary

    async def test_chart_generation(self, daily_summary: dict):
        """測試圖表生成功能"""
        app_logger.info("=== 測試圖表生成功能 ===")

        if not daily_summary or daily_summary.get("total_usage", 0) <= 0:
            app_logger.warning("沒有有效的摘要資料，跳過圖表生成測試")
            return None

        try:
            chart_path = await self.chart_generator.generate_daily_usage_chart(
                daily_summary
            )

            if chart_path and Path(chart_path).exists():
                app_logger.info(f"圖表生成成功: {chart_path}")
                file_size = Path(chart_path).stat().st_size
                app_logger.info(f"圖表檔案大小: {file_size} bytes")
                return chart_path
            else:
                app_logger.error("圖表生成失敗")
                return None

        except Exception as e:
            app_logger.error(f"圖表生成異常: {e}")
            return None

    async def test_notification_system(
        self, daily_summary: dict, chart_path: str = None
    ):
        """測試通知系統（不實際發送，只測試邏輯）"""
        app_logger.info("=== 測試通知系統 ===")

        # 檢查是否有配置的通知服務
        if not self.notification_manager.notifiers:
            app_logger.info("未配置通知服務，模擬通知發送")

        try:
            # 實際發送通知
            app_logger.info("準備發送每日摘要通知...")
            app_logger.info(f"摘要資料: {daily_summary}")
            app_logger.info(f"圖表路徑: {chart_path}")

            # 實際發送通知
            await self.notification_manager.send_daily_summary_notification(daily_summary, chart_path)

            app_logger.info("通知系統測試完成")

        except Exception as e:
            app_logger.error(f"通知系統測試失敗: {e}")

    async def test_scheduler_integration(self, target_date: str = None):
        """測試調度器整合功能"""
        app_logger.info("=== 測試調度器整合功能 ===")

        # 創建測試調度器（不啟動實際調度）
        test_config = {
            "db_path": "data/test_electricity_bot.db",
            "discord_webhook": "",  # 空字串避免實際發送
        }

        try:
            scheduler = TaskScheduler(test_config)

            # 測試手動觸發每日摘要任務
            result = await scheduler.run_manual_daily_summary(target_date)
            app_logger.info(f"手動觸發結果: {result}")

            return result

        except Exception as e:
            app_logger.error(f"調度器測試失敗: {e}")
            return None

    async def run_full_test(self, target_date: str = None, send_notification: bool = False):
        """運行完整測試"""
        app_logger.info("🚀 開始每日摘要功能完整測試")

        try:
            # 1. 初始化測試環境
            await self.data_generator.init_test_database()

            # 2. 生成測試資料
            if target_date is None:
                yesterday = datetime.now() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")

            app_logger.info(f"生成測試日期: {target_date}")
            await self.data_generator.generate_daily_fake_data(target_date)

            # 3. 測試資料庫查詢
            daily_summary = await self.test_database_queries(target_date)

            # 4. 測試圖表生成
            chart_path = await self.test_chart_generation(daily_summary)

            # 5. 測試通知系統
            if send_notification:
                await self.test_notification_system(daily_summary, chart_path)
            else:
                app_logger.info("跳過通知發送測試 (使用 --send-notification 啟用)")

            # 6. 測試調度器整合
            await self.test_scheduler_integration(target_date)

            app_logger.info("✅ 所有測試完成！")

        except Exception as e:
            app_logger.error(f"❌ 測試過程中發生錯誤: {e}")


async def main():
    """主函式"""
    import argparse

    parser = argparse.ArgumentParser(description="每日用電摘要功能測試")
    parser.add_argument("--date", help="測試日期 (YYYY-MM-DD)")
    parser.add_argument("--clear", action="store_true", help="清空測試資料")
    parser.add_argument(
        "--generate-days", type=int, default=1, help="生成幾天的測試資料"
    )
    parser.add_argument("--full-test", action="store_true", help="運行完整測試")
    parser.add_argument("--webhook-url", help="Discord webhook URL（用於實際發送通知）")
    parser.add_argument("--send-notification", action="store_true", help="實際發送通知到 Discord")

    args = parser.parse_args()

    tester = DailySummaryTester(args.webhook_url or "")

    try:
        if args.clear:
            app_logger.info("清空測試資料...")
            await tester.data_generator.clear_test_data()
            return

        if args.full_test:
            await tester.run_full_test(args.date, args.send_notification)
        elif args.generate_days > 1:
            app_logger.info(f"生成 {args.generate_days} 天的測試資料...")
            await tester.data_generator.init_test_database()
            await tester.data_generator.generate_multiple_days_data(args.generate_days)
        else:
            # 單獨測試功能
            await tester.data_generator.init_test_database()

            target_date = args.date
            if not target_date:
                yesterday = datetime.now() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")

            # 生成測試資料
            await tester.data_generator.generate_daily_fake_data(target_date)

            # 測試查詢
            summary = await tester.test_database_queries(target_date)

            # 測試圖表
            chart_path = None
            if summary:
                chart_path = await tester.test_chart_generation(summary)

            # 測試通知（如果啟用）
            if args.send_notification and summary:
                await tester.test_notification_system(summary, chart_path)

    except KeyboardInterrupt:
        app_logger.info("測試被用戶中斷")
    except Exception as e:
        app_logger.error(f"測試失敗: {e}")


if __name__ == "__main__":
    print("=== NTUT 電費機器人 - 每日摘要功能測試 ===")
    print("使用方法:")
    print("  python test_daily_summary.py --full-test                                    # 運行完整測試（不發送通知）")
    print("  python test_daily_summary.py --full-test --send-notification --webhook-url <URL>  # 運行完整測試並發送通知")
    print("  python test_daily_summary.py --date 2025-01-14 --send-notification --webhook-url <URL>  # 測試指定日期並發送通知")
    print("  python test_daily_summary.py --generate-days 7                             # 生成7天測試資料")
    print("  python test_daily_summary.py --clear                                       # 清空測試資料")
    print()
    print("注意：")
    print("  - 使用 --send-notification 需要同時提供 --webhook-url")
    print("  - webhook URL 應該是完整的 Discord webhook 網址")
    print()

    asyncio.run(main())
