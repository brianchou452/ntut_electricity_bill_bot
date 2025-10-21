"""
通知等級定義

類似 Python logging 的等級系統，用於控制通知的發送
"""

from enum import IntEnum


class NotificationLevel(IntEnum):
    """通知等級枚舉"""

    DEBUG = 10  # 除錯訊息
    INFO = 20  # 一般資訊
    SUCCESS = 25  # 成功訊息
    WARNING = 30  # 警告訊息
    ERROR = 40  # 錯誤訊息
    CRITICAL = 50  # 嚴重錯誤

    @classmethod
    def from_string(cls, level_str: str) -> "NotificationLevel":
        """從字串轉換為等級"""
        level_map = {
            "debug": cls.DEBUG,
            "info": cls.INFO,
            "success": cls.SUCCESS,
            "warning": cls.WARNING,
            "error": cls.ERROR,
            "critical": cls.CRITICAL,
        }
        return level_map.get(level_str.lower(), cls.INFO)


# 等級名稱對應（用於顯示）
LEVEL_NAMES = {
    NotificationLevel.DEBUG: "DEBUG",
    NotificationLevel.INFO: "INFO",
    NotificationLevel.SUCCESS: "SUCCESS",
    NotificationLevel.WARNING: "WARNING",
    NotificationLevel.ERROR: "ERROR",
    NotificationLevel.CRITICAL: "CRITICAL",
}
