"""
NTUT electricity billing system crawler using Playwright
"""

import random
from datetime import datetime
from typing import Any, Dict, Optional

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..database.models import ElectricityRecord
from ..utils.logger import app_logger

# 常數定義
BROWSER_NOT_INITIALIZED = "瀏覽器未初始化"
BALANCE_SELECTOR_TEXT = "text=購電餘額"


class NTUTCrawler:
    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> "NTUTCrawler":
        try:
            self.playwright = await async_playwright().start()

            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--lang=zh-TW",
                ],
                env={"TZ": "Asia/Taipei"},
            )

            # 建立新頁面並設定時區和語言
            self.page = await self.browser.new_page(
                locale="zh-TW", timezone_id="Asia/Taipei"
            )

            await self.page.set_viewport_size({"width": 1280, "height": 720})
            await self.page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )

            app_logger.info("瀏覽器啟動成功")
            return self

        except Exception as e:
            app_logger.error(f"瀏覽器啟動失敗: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, "playwright"):
                await self.playwright.stop()
            app_logger.info("瀏覽器關閉成功")
        except Exception as e:
            app_logger.error(f"瀏覽器關閉失敗: {e}")

    async def get_balance(self) -> str:
        """取得購電餘額"""
        if not self.page:
            app_logger.error(BROWSER_NOT_INITIALIZED)
            return BROWSER_NOT_INITIALIZED

        try:
            # 使用 xpath 取得購電餘額
            try:
                balance_element = await self.page.locator(
                    '//*[@id="main"]/div[4]/div[1]/div[2]/div/div[2]/ul/li[3]/span[2]'
                ).text_content()
                if balance_element:
                    balance_text = balance_element.strip()
                    app_logger.info(f"購電餘額: {balance_text}")
                    return balance_text
            except Exception as e:
                app_logger.warning(f"使用 xpath 取得餘額失敗: {e}")

            # 備用方法：尋找包含 "購電餘額" 的元素並提取後方文字
            try:
                # 取得包含購電餘額的完整文字
                full_text = await self.page.locator(
                    BALANCE_SELECTOR_TEXT
                ).text_content()
                if full_text and ":" in full_text:
                    # 提取冒號後的文字
                    balance_part = full_text.split(":", 1)[1].strip()
                    app_logger.info(f"購電餘額: {balance_part}")
                    return balance_part

                # 如果沒有冒號，嘗試尋找相鄰元素
                balance_container = self.page.locator(BALANCE_SELECTOR_TEXT).locator(
                    ".."
                )
                container_text = await balance_container.text_content()
                if container_text:
                    # 移除 "購電餘額" 文字，取得剩餘部分
                    balance_text = container_text.replace("購電餘額", "").strip()
                    if balance_text.startswith(":"):
                        balance_text = balance_text[1:].strip()
                    app_logger.info(f"購電餘額: {balance_text}")
                    return balance_text

            except Exception as e:
                app_logger.warning(f"備用方法取得餘額失敗: {e}")

            return "無法取得餘額"

        except Exception as e:
            app_logger.error(f"取得餘額時發生錯誤: {e}")
            return f"取得餘額失敗: {str(e)}"

    def extract_balance_number(self, balance_text: str) -> float:
        """從餘額文字中提取浮點數"""
        try:
            import re

            # 尋找數字（包含小數點）
            numbers = re.findall(r"\d+\.?\d*", balance_text)
            if numbers:
                return float(numbers[0])
            return 0.0
        except (ValueError, IndexError):
            app_logger.warning(f"無法從 '{balance_text}' 提取數字")
            return 0.0

    async def login(self) -> bool:
        if not self.page:
            app_logger.error(BROWSER_NOT_INITIALIZED)
            return False

        try:
            app_logger.info("開始登入流程")

            # 前往主頁面
            await self.page.goto("https://www.aotech.tw/ntut/index.php", timeout=30000)
            app_logger.info("已載入主頁面")

            # 點擊學生登入連結
            await self.page.get_by_role("link", name="學生登入").click()
            app_logger.info("已點擊學生登入連結")

            # 填寫帳號
            await self.page.get_by_role("textbox", name="帳號").click()
            await self.page.get_by_role("textbox", name="帳號").fill(self.username)
            app_logger.info(f"已填入帳號: {self.username}")

            # 填寫密碼
            await self.page.get_by_role("textbox", name="密碼").click()
            await self.page.get_by_role("textbox", name="密碼").fill(self.password)
            app_logger.info("已填入密碼")

            await self.page.wait_for_timeout(
                random.randint(3000, 7000)
            )  # 等待 3 到 7 秒以防止過快點擊

            # 點擊登入按鈕
            await self.page.get_by_role("button", name="登入").click()
            app_logger.info("已點擊登入按鈕")

            # 等待登入成功的指標 - 購電餘額文字出現
            try:
                await self.page.wait_for_selector(BALANCE_SELECTOR_TEXT, timeout=10000)
                app_logger.info("登入成功 - 已偵測到購電餘額")
                return True

            except PlaywrightTimeoutError:
                # 如果沒有找到餘額，嘗試尋找其他登入成功的指標
                app_logger.warning("未找到購電餘額，嘗試尋找其他登入指標")

                # 檢查是否有錯誤訊息
                error_elements = await self.page.query_selector_all(
                    '.error, .alert-danger, [class*="error"]'
                )
                if error_elements:
                    error_text = await error_elements[0].text_content()
                    app_logger.error(f"登入錯誤: {error_text}")
                    return False

                # 檢查頁面 URL 是否變化
                current_url = self.page.url
                if "login" not in current_url.lower():
                    app_logger.info("登入可能成功 - 頁面已跳轉")
                    return True
                else:
                    app_logger.error("登入失敗 - 仍在登入頁面")
                    return False

        except PlaywrightTimeoutError:
            app_logger.error("登入過程超時")
            await self.take_screenshot("login_timeout.png")
            return False
        except Exception as e:
            app_logger.error(f"登入失敗: {e}")
            return False

    def create_balance_record(self, balance: float) -> ElectricityRecord:
        """建立餘額記錄"""
        return ElectricityRecord(balance=balance)

    def _safe_float(self, value: str) -> float:
        """安全轉換字串為浮點數"""
        try:
            # 移除非數字字元（保留小數點和負號）
            import re

            cleaned = re.sub(r"[^\d.-]", "", str(value))
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0

    async def take_screenshot(self, filename: Optional[str] = None) -> str:
        if not self.page:
            app_logger.warning(BROWSER_NOT_INITIALIZED)
            return ""

        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            screenshot_path = f"logs/{filename}"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            app_logger.info(f"螢幕截圖已儲存: {screenshot_path}")
            return screenshot_path

        except Exception as e:
            app_logger.error(f"截圖失敗: {e}")
            return ""


class CrawlerService:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.crawler = NTUTCrawler(
            username=config.get("username", ""), password=config.get("password", "")
        )

    def set_database(self, database):
        """設定資料庫實例"""
        self.database = database

    async def run_crawl_task(self) -> Dict[str, Any]:
        start_time = datetime.now()
        result = {
            "status": "error",
            "records_count": 0,
            "error_message": None,
            "duration_seconds": 0.0,
            "records": [],
        }

        try:
            async with self.crawler:
                login_success = await self.crawler.login()
                if not login_success:
                    result["error_message"] = "登入失敗"
                    return result

                # 登入成功後取得餘額
                balance_text = await self.crawler.get_balance()
                balance_number = self.crawler.extract_balance_number(balance_text)
                app_logger.info(
                    f"登入成功，餘額: {balance_text} (數值: {balance_number})"
                )

                # 將餘額資訊存入結果中
                result["balance_text"] = balance_text
                result["balance_number"] = balance_number

                # 建立並儲存餘額記錄到資料庫
                if balance_number > 0 and hasattr(self, "database"):
                    balance_record = self.crawler.create_balance_record(balance_number)
                    success = await self.database.insert_electricity_record(
                        balance_record
                    )
                    if success:
                        app_logger.info(f"餘額記錄已存入資料庫: {balance_number}")
                        result["status"] = "success"
                        result["records_count"] = 1
                        result["records"] = [balance_record]
                    else:
                        app_logger.error("餘額記錄存入資料庫失敗")
                        result["status"] = "partial"
                        result["error_message"] = "餘額記錄存入資料庫失敗"
                else:
                    result["status"] = "partial"
                    result["error_message"] = "未取得有效餘額或資料庫未設定"
                    app_logger.warning("未取得有效餘額或資料庫未設定")

        except Exception as e:
            result["error_message"] = str(e)
            app_logger.error(f"爬蟲任務執行失敗: {e}")

            if self.crawler.page:
                await self.crawler.take_screenshot("error_debug.png")

        finally:
            end_time = datetime.now()
            result["duration_seconds"] = (end_time - start_time).total_seconds()

        return result
