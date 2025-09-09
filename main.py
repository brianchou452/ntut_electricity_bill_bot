"""
NTUT Electricity Bill Bot - Main Entry Point
北科電費帳單機器人 - 主程式進入點
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Dict

from src.scheduler.scheduler import SchedulerManager
from src.utils.logger import app_logger
from src.utils.settings import settings


class ElectricityBillBot:
    def __init__(self):
        self.scheduler_manager = SchedulerManager()
        self.running = False

    async def start(self):
        """啟動機器人"""
        if self.running:
            app_logger.warning("機器人已經在運行中")
            return

        try:
            app_logger.info("正在啟動 NTUT 電費帳單機器人...")
            app_logger.info(f"調度週期: {settings.cron_schedule}")
            app_logger.info(f"資料庫路徑: {settings.db_path}")

            # 確保必要目錄存在
            Path("data").mkdir(exist_ok=True)
            Path("logs").mkdir(exist_ok=True)

            # 轉換設定為字典格式供調度器使用
            config = {
                "username": settings.ntut_username,
                "password": settings.ntut_password,
                "db_path": settings.db_path,
                "cron_schedule": settings.cron_schedule,
                "run_on_startup": settings.run_on_startup,
                "discord_webhook": settings.discord_webhook_url,
                "timezone": settings.tz,
            }

            await self.scheduler_manager.start(config)
            self.running = True

            app_logger.info("🚀 NTUT 電費帳單機器人啟動成功!")

        except Exception as e:
            app_logger.error(f"機器人啟動失敗: {e}")
            raise

    async def stop(self):
        """停止機器人"""
        if not self.running:
            return

        app_logger.info("正在停止 NTUT 電費帳單機器人...")

        try:
            await self.scheduler_manager.stop()
            self.running = False
            app_logger.info("✅ NTUT 電費帳單機器人已停止")

        except Exception as e:
            app_logger.error(f"停止機器人時發生錯誤: {e}")

    async def manual_crawl(self) -> Dict:
        """手動執行爬取任務"""
        app_logger.info("執行手動爬取任務")
        result = await self.scheduler_manager.run_manual_crawl()
        return result

    def get_status(self) -> Dict:
        """取得機器人狀態"""
        scheduler_status = self.scheduler_manager.get_status()
        return {
            "bot_running": self.running,
            "scheduler": scheduler_status,
            "config": {
                "cron_schedule": settings.cron_schedule,
                "db_path": settings.db_path,
                "has_discord_webhook": bool(settings.discord_webhook_url),
            },
        }


async def main():
    """主函式"""
    bot = ElectricityBillBot()

    def signal_handler(sig, frame):
        """處理中斷信號"""
        app_logger.info(f"收到信號 {sig}，準備關閉程式...")
        task = asyncio.create_task(bot.stop())
        task.add_done_callback(lambda t: None)

    # 註冊信號處理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.start()

        # 保持程式運行
        while bot.running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        app_logger.info("收到鍵盤中斷，正在關閉...")
    except Exception as e:
        app_logger.error(f"程式運行時發生未預期的錯誤: {e}")
    finally:
        await bot.stop()


def run_manual_task():
    """執行單次手動任務的命令行介面"""

    async def manual_task():
        bot = ElectricityBillBot()
        try:
            # 初始化但不啟動調度器
            config = {
                "username": settings.ntut_username,
                "password": settings.ntut_password,
                "db_path": settings.db_path,
                "cron_schedule": settings.cron_schedule,
                "run_on_startup": False,  # 手動模式不自動執行
                "discord_webhook": settings.discord_webhook_url,
                "timezone": settings.tz,
            }
            await bot.scheduler_manager.start(config)
            result = await bot.manual_crawl()

            app_logger.info("手動任務執行結果:")
            app_logger.info(f"狀態: {result['status']}")
            app_logger.info(f"記錄數: {result['records_count']}")
            app_logger.info(f"執行時間: {result['duration_seconds']:.2f} 秒")

            if result.get("error_message"):
                app_logger.error(f"錯誤訊息: {result['error_message']}")

        except Exception as e:
            app_logger.error(f"手動任務執行失敗: {e}")
        finally:
            await bot.stop()

    asyncio.run(manual_task())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        app_logger.info("執行手動任務模式")
        run_manual_task()
    else:
        app_logger.info("執行定時任務模式")
        asyncio.run(main())
