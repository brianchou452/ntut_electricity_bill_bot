"""
測試通知等級過濾功能

此腳本展示如何使用通知等級系統：
1. 設定不同的最小通知等級
2. 發送不同等級的通知
3. 驗證過濾功能是否正常運作
"""

import asyncio
import sys
from pathlib import Path

# 將專案根目錄加入 Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.notifier import NotificationManager, NotificationLevel  # noqa: E402


async def test_notification_levels():
    """測試不同通知等級的過濾功能"""

    print("=" * 60)
    print("通知等級系統測試")
    print("=" * 60)

    # 建立通知管理器
    manager = NotificationManager()

    # 測試場景 1: Discord 只接收 WARNING 以上的通知
    print("\\n[場景 1] Discord 設定最小等級為 WARNING")
    manager.add_discord_webhook(
        webhook_url="https://discord.com/api/webhooks/test",  # 測試用，不會實際發送
        min_level=NotificationLevel.WARNING,
    )

    # 測試場景 2: Telegram 只接收 ERROR 以上的通知
    print("[場景 2] Telegram 設定最小等級為 ERROR")
    manager.add_telegram_notifier(
        bot_token="test_token",  # 測試用，不會實際發送
        chat_id="test_chat_id",
        min_level=NotificationLevel.ERROR,
    )

    print("\\n" + "=" * 60)
    print("開始測試不同等級的通知...")
    print("=" * 60)

    # 測試不同等級的通知
    test_cases = [
        (NotificationLevel.DEBUG, "除錯訊息", "這是一個除錯訊息"),
        (NotificationLevel.INFO, "一般資訊", "這是一般資訊訊息"),
        (NotificationLevel.SUCCESS, "成功訊息", "操作成功完成"),
        (NotificationLevel.WARNING, "警告訊息", "這是警告訊息"),
        (NotificationLevel.ERROR, "錯誤訊息", "發生錯誤"),
        (NotificationLevel.CRITICAL, "嚴重錯誤", "發生嚴重錯誤"),
    ]

    for level, title, message in test_cases:
        print(f"\\n[測試] 發送 {level.name} 等級通知: {title}")
        print("  預期結果:")
        print("    - Discord (min_level=WARNING): ", end="")
        print("✅ 發送" if level >= NotificationLevel.WARNING else "❌ 跳過")
        print("    - Telegram (min_level=ERROR): ", end="")
        print("✅ 發送" if level >= NotificationLevel.ERROR else "❌ 跳過")

        await manager._send_to_all(
            title=title, message=message, records=None, status="info", level=level
        )

    print("\\n" + "=" * 60)
    print("測試完成！")
    print("=" * 60)

    # 輸出說明
    print("\\n【說明】")
    print("1. 等級順序: DEBUG < INFO < SUCCESS < WARNING < ERROR < CRITICAL")
    print("2. Discord 設定 min_level=WARNING，只會收到 WARNING/ERROR/CRITICAL")
    print("3. Telegram 設定 min_level=ERROR，只會收到 ERROR/CRITICAL")
    print("4. 查看日誌可以確認哪些通知被過濾掉")


async def test_level_conversion():
    """測試等級轉換功能"""
    print("\\n" + "=" * 60)
    print("等級轉換測試")
    print("=" * 60)

    # 測試字串轉換
    test_strings = ["debug", "INFO", "Warning", "ERROR", "critical", "unknown"]

    for s in test_strings:
        level = NotificationLevel.from_string(s)
        print(f"字串 '{s}' -> {level.name} ({level.value})")


if __name__ == "__main__":
    print("\\n🚀 開始測試通知等級系統\\n")

    # 執行測試
    asyncio.run(test_notification_levels())
    asyncio.run(test_level_conversion())

    print("\\n✅ 所有測試執行完畢！\\n")
