"""
Task scheduler using APScheduler
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..crawler.ntut_crawler import CrawlerService
from ..database.database import Database
from ..database.models import CrawlerLog
from ..notifier.webhook import NotificationManager
from ..utils.logger import app_logger


class TaskScheduler:
    def __init__(self, config: Dict):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.database = Database(config.get("db_path", "data/electricity_bot.db"))
        self.crawler_service = CrawlerService(config)
        self.crawler_service.set_database(self.database)  # 設定資料庫實例
        self.notification_manager = NotificationManager()
        self.is_running = False

        self._setup_scheduler()
        self._setup_notifications()

    def _setup_scheduler(self):
        executors = {"default": AsyncIOExecutor()}
        self.scheduler.configure(executors=executors)

        cron_expression = self.config.get(
            "cron_schedule", "0 */1 * * *"
        )  # 每小時執行一次

        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            self.scheduler.add_job(
                func=self.run_crawl_task,
                trigger=trigger,
                id="electricity_crawl_task",
                name="電費爬取任務",
                replace_existing=True,
                max_instances=1,
            )
            app_logger.info(f"已設定定時任務，執行週期: {cron_expression}")

        except ValueError as e:
            app_logger.error(f"無效的 cron 表達式 '{cron_expression}': {e}")
            raise

    def _setup_notifications(self):
        discord_webhook = self.config.get("discord_webhook")

        if discord_webhook:
            self.notification_manager.add_discord_webhook(discord_webhook)

    async def start(self):
        if self.is_running:
            app_logger.warning("調度器已在運行中")
            return

        try:
            await self.database.init_database()

            self.scheduler.start()
            self.is_running = True

            app_logger.info("任務調度器啟動成功")
            await self.notification_manager.send_startup_notification()

            if self.config.get("run_on_startup", True):
                app_logger.info("啟動時執行一次爬取任務")
                self._startup_task = asyncio.create_task(self.run_crawl_task())

        except Exception as e:
            app_logger.error(f"調度器啟動失敗: {e}")
            raise

    async def stop(self):
        if not self.is_running:
            return

        self.scheduler.shutdown()
        self.is_running = False
        app_logger.info("任務調度器已停止")

    async def run_crawl_task(self):
        task_start_time = datetime.now()
        app_logger.info("開始執行爬取任務")

        try:
            result = await self.crawler_service.run_crawl_task()

            await self._process_crawl_result(result)

        except Exception as e:
            app_logger.error(f"爬取任務執行異常: {e}")

            log_entry = CrawlerLog(
                status="error",
                error_message=str(e),
                duration_seconds=(datetime.now() - task_start_time).total_seconds(),
            )
            await self.database.insert_crawler_log(log_entry)
            await self.notification_manager.send_crawl_error_notification(
                str(e), float(log_entry.duration_seconds or 0.0)
            )

    async def _process_crawl_result(self, result: Dict):
        duration = result["duration_seconds"]

        log_entry = CrawlerLog(
            status=result["status"],
            records_count=result["records_count"],
            error_message=result["error_message"],
            duration_seconds=duration,
        )

        await self.database.insert_crawler_log(log_entry)

        if result["status"] == "success":
            app_logger.info("爬取任務成功完成，餘額已儲存")
            # 發送合併的成功通知（包含餘額資訊）
            balance_record = result["records"][0]  # 只有一個記錄
            await self.notification_manager.send_balance_notification(
                balance_record.balance
            )

        elif result["status"] == "partial":
            await self.notification_manager.send_partial_success_notification(
                result["records_count"], duration
            )

        elif result["status"] == "error":
            await self.notification_manager.send_crawl_error_notification(
                result["error_message"], duration
            )

    async def run_manual_crawl(self) -> Dict:
        app_logger.info("手動觸發爬取任務")
        start_time = datetime.now()

        try:
            result = await self.crawler_service.run_crawl_task()
            await self._process_crawl_result(result)
            return result

        except Exception as e:
            app_logger.error(f"手動爬取任務失敗: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "records_count": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

    def get_next_run_time(self) -> Optional[datetime]:
        jobs = self.scheduler.get_jobs()
        if jobs:
            return jobs[0].next_run_time
        return None

    def get_scheduler_status(self) -> Dict:
        return {
            "is_running": self.is_running,
            "next_run_time": self.get_next_run_time(),
            "jobs_count": len(self.scheduler.get_jobs()),
            "scheduler_state": self.scheduler.state,
        }


class SchedulerManager:
    _instance: Optional["SchedulerManager"] = None

    def __new__(cls, config: Optional[Dict] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict] = None):
        if not hasattr(self, "_initialized"):
            self.scheduler = TaskScheduler(config or {}) if config else None
            self._initialized = True

    async def start(self, config: Dict):
        if not self.scheduler:
            self.scheduler = TaskScheduler(config)
        await self.scheduler.start()

    async def stop(self):
        if self.scheduler:
            await self.scheduler.stop()

    async def run_manual_crawl(self) -> Dict:
        if not self.scheduler:
            return {"status": "error", "error_message": "調度器未初始化"}
        return await self.scheduler.run_manual_crawl()

    def get_status(self) -> Dict:
        if not self.scheduler:
            return {"status": "not_initialized"}
        return self.scheduler.get_scheduler_status()
