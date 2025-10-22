"""
NTUT Electricity Bill Bot - FastAPI REST API
北科電費帳單機器人 - REST API 介面
"""

from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.crawler.ntut_crawler import CrawlerService
from src.database.database import Database
from src.database.models import ElectricityRecord
from src.utils.logger import app_logger
from src.utils.settings import settings

# 常數定義
API_TITLE = "NTUT Electricity Bill API"

# 建立 FastAPI 應用
app = FastAPI(
    title=API_TITLE,
    description="北科電費查詢 API - 提供即時電費餘額查詢功能",
    version="1.0.0",
)


@app.get("/api/v1/health")
async def health_check() -> Dict[str, str]:
    """
    健康檢查端點

    Returns:
        Dict[str, str]: 健康狀態
    """
    return {"status": "ok", "service": API_TITLE}


@app.get("/api/v1/balance")
async def get_balance() -> JSONResponse:
    """
    抓取最新電費餘額

    這個端點會執行完整的爬蟲流程（登入 → 抓取餘額 → 存入資料庫）。
    由於爬蟲需要多步驟操作，可能需要 30-60 秒完成。

    Returns:
        JSONResponse: 包含餘額資料和執行狀態的 JSON 回應

    Raises:
        HTTPException: 當爬蟲執行失敗時

    Response Schema:
        - status (str): 執行狀態 - "success", "error", "partial"
        - records_count (int): 成功記錄數量
        - duration_seconds (float): 執行耗時（秒）
        - records (list): 餘額記錄列表
        - error_message (str, optional): 錯誤訊息（如果有錯誤）

    Example Response (Success):
        {
            "status": "success",
            "records_count": 1,
            "duration_seconds": 45.23,
            "records": [
                {
                    "balance": 1234.56,
                    "created_at": "2025-01-15T10:30:00"
                }
            ]
        }

    Example Response (Error):
        {
            "status": "error",
            "records_count": 0,
            "duration_seconds": 12.34,
            "error_message": "登入失敗",
            "records": []
        }
    """
    app_logger.info("收到 API 請求：查詢電費餘額")

    try:
        # 建立爬蟲服務
        crawler_config = {
            "username": settings.ntut_username,
            "password": settings.ntut_password,
        }
        crawler_service = CrawlerService(config=crawler_config)

        # 設定資料庫
        database = Database(db_path=settings.db_path)
        await database.init_database()
        crawler_service.set_database(database)

        # 執行爬取任務
        app_logger.info("開始執行爬蟲任務")
        result: Dict[str, Any] = await crawler_service.run_crawl_task()

        # 將 Pydantic 模型轉換為字典（以便 JSON 序列化）
        # mode='json' 會自動將 datetime 轉換為 ISO 8601 字串格式
        if result.get("records"):
            records_list: List[ElectricityRecord] = result["records"]
            result["records"] = [
                record.model_dump(mode="json") for record in records_list
            ]

        # 根據執行狀態回傳對應的 HTTP 狀態碼
        if result["status"] == "success":
            balance = result["records"][0]["balance"] if result["records"] else "N/A"
            app_logger.info(f"爬蟲任務成功完成，餘額: {balance}")
            return JSONResponse(status_code=200, content=result)

        elif result["status"] == "partial":
            # 部分成功（例如：抓到資料但存入資料庫失敗）
            app_logger.warning(f"爬蟲任務部分完成: {result.get('error_message', '')}")
            return JSONResponse(status_code=207, content=result)

        else:
            # 執行失敗
            error_msg = result.get("error_message", "未知錯誤")
            app_logger.error(f"爬蟲任務失敗: {error_msg}")
            return JSONResponse(status_code=500, content=result)

    except Exception as e:
        # 未預期的錯誤
        error_message = f"API 執行過程中發生未預期的錯誤: {str(e)}"
        app_logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/api/v1/status")
async def get_api_status() -> Dict[str, Any]:
    """
    取得 API 服務狀態和配置資訊

    Returns:
        Dict[str, Any]: API 狀態資訊
    """
    return {
        "service": API_TITLE,
        "status": "running",
        "config": {
            "database_path": settings.db_path,
            "has_credentials": bool(settings.ntut_username and settings.ntut_password),
        },
        "endpoints": {
            "health": "/api/v1/health",
            "balance": "/api/v1/balance",
            "status": "/api/v1/status",
            "docs": "/docs",
        },
    }


# 啟動提示
if __name__ == "__main__":
    import uvicorn

    app_logger.info("啟動 NTUT 電費 API 服務")
    app_logger.info("API 文件：http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
