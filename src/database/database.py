"""
Database operations using aiosqlite
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

from ..utils.logger import app_logger
from .models import CrawlerLog, ElectricityRecord


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
