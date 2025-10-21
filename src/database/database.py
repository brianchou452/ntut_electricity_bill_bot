"""
Database operations using aiosqlite
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

from src.utils.logger import app_logger
from src.database.models import CrawlerLog, ElectricityRecord


class Database:
    def __init__(self, db_path: str = "data/electricity_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)

    async def init_database(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS electricity_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    balance REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS crawler_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    records_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    duration_seconds REAL
                )
            """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_electricity_created
                ON electricity_records(created_at)
            """
            )

            await db.commit()
            app_logger.info("資料庫初始化完成")

    async def insert_electricity_record(self, record: ElectricityRecord) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO electricity_records
                    (balance, created_at)
                    VALUES (?, ?)
                """,
                    (
                        record.balance,
                        record.created_at or datetime.now(),
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            app_logger.error(f"插入電費記錄失敗: {e}")
            return False

    async def insert_crawler_log(self, log: CrawlerLog) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO crawler_logs
                    (timestamp, status, records_count, error_message, duration_seconds)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        log.timestamp,
                        log.status,
                        log.records_count,
                        log.error_message,
                        log.duration_seconds,
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            app_logger.error(f"插入爬蟲日誌失敗: {e}")
            return False

    async def get_latest_records(self, limit: int = 10) -> List[ElectricityRecord]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT * FROM electricity_records
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [ElectricityRecord(**dict(row)) for row in rows]
        except Exception as e:
            app_logger.error(f"查詢最新記錄失敗: {e}")
            return []

    async def get_records_by_date_range(
        self, start_date: str, end_date: str
    ) -> List[ElectricityRecord]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT * FROM electricity_records
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """,
                    (start_date, end_date),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [ElectricityRecord(**dict(row)) for row in rows]
        except Exception as e:
            app_logger.error(f"查詢日期範圍記錄失敗: {e}")
            return []

    async def get_latest_balance(self) -> Optional[float]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    SELECT balance FROM electricity_records
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                ) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else None
        except Exception as e:
            app_logger.error(f"查詢最新餘額失敗: {e}")
            return None

    async def get_yesterday_records(
        self, target_date: Optional[str] = None
    ) -> List[ElectricityRecord]:
        """取得昨日的所有記錄"""
        try:
            if target_date is None:
                from datetime import datetime, timedelta

                yesterday = datetime.now() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")

            start_datetime = f"{target_date} 00:00:00"
            end_datetime = f"{target_date} 23:59:59"

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT * FROM electricity_records
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at ASC
                """,
                    (start_datetime, end_datetime),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [ElectricityRecord(**dict(row)) for row in rows]
        except Exception as e:
            app_logger.error(f"查詢昨日記錄失敗: {e}")
            return []

    async def get_daily_usage_summary(self, target_date: Optional[str] = None) -> dict:
        """取得每日用電摘要"""
        records = await self.get_yesterday_records(target_date)

        if len(records) < 2:
            return {
                "date": target_date,
                "total_usage": 0.0,
                "start_balance": None,
                "end_balance": None,
                "hourly_usage": [],
            }

        # 計算總用電量 (起始餘額 - 結束餘額)
        start_balance = records[0].balance
        end_balance = records[-1].balance
        total_usage = start_balance - end_balance

        # 計算每小時用電量
        hourly_usage = []
        for i in range(1, len(records)):
            prev_record = records[i - 1]
            curr_record = records[i]
            usage = prev_record.balance - curr_record.balance

            hourly_usage.append(
                {
                    "time": curr_record.created_at.strftime("%H:%M")
                    if curr_record.created_at
                    else "Unknown",
                    "usage": max(0, usage),  # 確保用電量不為負數
                    "balance": curr_record.balance,
                }
            )

        return {
            "date": target_date,
            "total_usage": max(0, total_usage),
            "start_balance": start_balance,
            "end_balance": end_balance,
            "hourly_usage": hourly_usage,
        }
