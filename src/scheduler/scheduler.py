"""
Task scheduler using APScheduler
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.crawler.ntut_crawler import CrawlerService
from src.database.database import Database
from src.database.models import CrawlerLog
from src.notifier.webhook import NotificationManager
from src.utils.chart_generator import ChartGenerator
from src.utils.logger import app_logger
from src.utils.settings import settings


class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.database = Database(settings.db_path)
        self.crawler_service = CrawlerService(
            {"username": settings.ntut_username, "password": settings.ntut_password}
        )
        self.crawler_service.set_database(self.database)  # 設定資料庫實例
        self.notification_manager = NotificationManager()
        self.chart_generator = ChartGenerator()
        self.is_running = False

        self._setup_scheduler()
        self._setup_notifications()

    def _setup_scheduler(self):
        executors = {"default": AsyncIOExecutor()}
        self.scheduler.configure(executors=executors)

        try:
            # 爬取任務
            trigger = CronTrigger.from_crontab(settings.cron_schedule)
            self.scheduler.add_job(
                func=self.run_crawl_task,
                trigger=trigger,
                id="electricity_crawl_task",
                name="電費爬取任務",
                replace_existing=True,
                max_instances=1,
            )
            app_logger.info(f"已設定定時任務，執行週期: {settings.cron_schedule}")

            # 每日匯總任務 - 在通知起始時間執行
            from datetime import time

            start_time = time.fromisoformat(settings.notification_start_time)
            daily_trigger = CronTrigger(
                hour=start_time.hour, minute=start_time.minute, second=0
            )
            self.scheduler.add_job(
                func=self.run_daily_summary_task,
                trigger=daily_trigger,
                id="daily_summary_task",
                name="每日用電摘要任務",
                replace_existing=True,
                max_instances=1,
            )
            app_logger.info(
                f"已設定每日摘要任務，執行時間: {settings.notification_start_time}"
            )

        except ValueError as e:
            app_logger.error(f"無效的 cron 表達式或時間設定: {e}")
            raise

    def _setup_notifications(self):
        if settings.discord_webhook_url:
            self.notification_manager.add_discord_webhook(settings.discord_webhook_url)

        if settings.telegram_bot_token and settings.telegram_chat_id:
            self.notification_manager.add_telegram_notifier(
                settings.telegram_bot_token, settings.telegram_chat_id
            )

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

            if settings.run_on_startup:
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

    async def run_daily_summary_task(self):
        """執行每日用電摘要任務"""
        task_start_time = datetime.now()
        app_logger.info("開始執行每日用電摘要任務")

        try:
            # 計算昨日日期
            yesterday = datetime.now() - timedelta(days=1)
            target_date = yesterday.strftime("%Y-%m-%d")

            # 取得每日摘要資料
            daily_summary = await self.database.get_daily_usage_summary(target_date)

            if not daily_summary or daily_summary.get("total_usage", 0) <= 0:
                app_logger.info(f"昨日 ({target_date}) 無用電資料或用電量為零")
                # 仍然發送通知，告知無用電記錄
                await self.notification_manager.send_daily_summary_notification(
                    daily_summary or {"date": target_date, "total_usage": 0}, None
                )
                return

            # 生成圖表
            chart_path = None
            try:
                chart_path = await self.chart_generator.generate_daily_usage_chart(
                    daily_summary
                )
            except Exception as e:
                app_logger.error(f"圖表生成失敗: {e}")

            # 發送通知
            await self.notification_manager.send_daily_summary_notification(
                daily_summary, chart_path
            )

            # 清理 1 天前的舊圖表檔案
            self.chart_generator.cleanup_old_charts(days_old=1)

            duration = (datetime.now() - task_start_time).total_seconds()
            app_logger.info(f"每日摘要任務完成，耗時 {duration:.2f} 秒")

        except Exception as e:
            app_logger.error(f"每日摘要任務執行異常: {e}")

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

    async def run_manual_daily_summary(self, target_date: Optional[str] = None) -> Dict:
        """手動觸發每日摘要任務"""
        app_logger.info("手動觸發每日摘要任務")
        start_time = datetime.now()

        try:
            if target_date is None:
                from datetime import timedelta

                yesterday = datetime.now() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")

            # 取得每日摘要資料
            daily_summary = await self.database.get_daily_usage_summary(target_date)

            # 生成圖表
            chart_path = None
            if daily_summary and daily_summary.get("total_usage", 0) > 0:
                chart_path = await self.chart_generator.generate_daily_usage_chart(
                    daily_summary
                )

            # 發送通知
            await self.notification_manager.send_daily_summary_notification(
                daily_summary or {"date": target_date, "total_usage": 0}, chart_path
            )

            return {
                "status": "success",
                "target_date": target_date,
                "chart_generated": chart_path is not None,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

        except Exception as e:
            app_logger.error(f"手動每日摘要任務失敗: {e}")
            return {
                "status": "error",
                "error_message": str(e),
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.scheduler: Optional[TaskScheduler] = None
            self._initialized = True

    async def start(self):
        if not self.scheduler:
            self.scheduler = TaskScheduler()
        await self.scheduler.start()

    async def stop(self):
        if self.scheduler:
            await self.scheduler.stop()

    async def run_manual_crawl(self) -> Dict:
        if not self.scheduler:
            return {"status": "error", "error_message": "調度器未初始化"}
        return await self.scheduler.run_manual_crawl()

    async def run_manual_daily_summary(self, target_date: Optional[str] = None) -> Dict:
        if not self.scheduler:
            return {"status": "error", "error_message": "調度器未初始化"}
        return await self.scheduler.run_manual_daily_summary(target_date)

    def get_status(self) -> Dict:
        if not self.scheduler:
            return {"status": "not_initialized"}
        return self.scheduler.get_scheduler_status()
