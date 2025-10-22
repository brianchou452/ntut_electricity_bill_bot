# NTUT 電費帳單機器人

這是一個使用 Playwright 自動爬取北科電力系統資料的機器人，支援定時執行、資料儲存和 Webhook 通知。

## 功能特色

- 🤖 自動爬取電費帳單資料
- ⏰ 支援定時任務調度 (預設每小時執行)
- 🌐 REST API 即時查詢電費餘額
- 💾 SQLite 資料庫儲存
- 📡 Discord Webhook 通知
- 🐳 Docker 容器化部署
- 📝 完整的日誌記錄
- 🛡️ 錯誤處理和重試機制

## 快速開始

### 使用 Docker Compose (推薦)

1. 複製專案
```bash
git clone <repository-url>
cd ntut_electricity_bill_bot
```

2. 設定環境變數
```bash
cp .env.example .env
# 編輯 .env 檔案，填入必要的配置
# 重要: 設定 BOT_MODE=api (API 模式) 或 BOT_MODE=scheduler (排程器模式)
```

3. 啟動服務

**API 模式（預設）**：
```bash
# 使用預設配置啟動 API 服務
docker-compose up -d

# API 服務會在 http://localhost:8000 啟動
# 查看 API 文件：http://localhost:8000/docs
```

**排程器模式**：
```bash
# 設定 BOT_MODE=scheduler 啟動定時爬蟲
BOT_MODE=scheduler docker-compose up -d
```

**自訂埠號**：
```bash
# 在 .env 檔案中設定
API_PORT=9000

# 或使用環境變數
API_PORT=9000 docker-compose up -d
```

### 本地開發

1. 安裝 Python 3.11+
2. 安裝依賴
```bash
poetry install
# 或者
pip install -e .
```

3. 安裝 Playwright 瀏覽器
```bash
playwright install chromium
```

4. 執行程式
```bash
# 定時執行模式
python main.py

# 手動執行一次
python main.py manual

# REST API 模式
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## 配置說明

### 環境變數

| 變數名 | 必要 | 說明 | 預設值 |
|--------|------|------|--------|
| NTUT_USERNAME | ✓ | 學號 | - |
| NTUT_PASSWORD | ✓ | 密碼 | - |
| BOT_MODE | - | 啟動模式 (`api` 或 `scheduler`) | `api` |
| API_PORT | - | API 服務埠號 | `8000` |
| CRON_SCHEDULE | - | 定時執行週期 (cron 格式，僅 scheduler 模式) | `0 */1 * * *` |
| RUN_ON_STARTUP | - | 啟動時立即執行（僅 scheduler 模式） | `true` |
| DISCORD_WEBHOOK_URL | - | Discord 通知網址 | - |

### Cron 排程範例

```
0 */1 * * *    # 每小時執行
0 9 * * *      # 每天早上 9 點執行
0 9 * * 1      # 每週一早上 9 點執行
0 9 1 * *      # 每月 1 號早上 9 點執行
```

## 專案架構

```
ntut_electricity_bill_bot/
├── src/
│   ├── crawler/           # 爬蟲核心邏輯
│   ├── database/          # 資料庫操作
│   ├── notifier/          # 通知服務
│   ├── scheduler/         # 任務調度器
│   └── utils/            # 工具類別
├── data/                 # 資料庫檔案
├── logs/                # 日誌檔案
├── main.py              # 主程式進入點（排程器模式）
├── api.py               # REST API 進入點
├── Dockerfile           # Docker 映像檔設定
└── docker-compose.yml   # Docker Compose 配置
```

## 使用方式

### REST API 使用

#### 啟動 API 服務

```bash
# 開發模式（自動重新載入）
uvicorn api:app --reload

# 生產模式
uvicorn api:app --host 0.0.0.0 --port 8000
```

#### API 端點

**1. 查詢電費餘額**
```bash
GET /api/v1/balance
```

回應範例（成功）：
```json
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
```

回應範例（失敗）：
```json
{
  "status": "error",
  "records_count": 0,
  "duration_seconds": 12.34,
  "error_message": "登入失敗",
  "records": []
}
```

**2. 健康檢查**
```bash
GET /api/v1/health
```

回應範例：
```json
{
  "status": "ok",
  "service": "NTUT Electricity Bill API"
}
```

**3. API 狀態**
```bash
GET /api/v1/status
```

**4. API 文件**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### 使用範例

```bash
# 使用 curl
curl http://localhost:8000/api/v1/balance

# 使用 httpie
http GET http://localhost:8000/api/v1/balance

# 使用 Python requests
import requests
response = requests.get("http://localhost:8000/api/v1/balance")
data = response.json()
print(f"餘額: {data['records'][0]['balance']}")
```

### 查看日誌

```bash
# Docker 容器日誌
docker-compose logs -f ntut-electricity-bot

# 本地日誌檔案
tail -f logs/app_$(date +%Y-%m-%d).log
```

### 手動執行爬取

```bash
# Docker 環境
docker-compose exec ntut-electricity-bot python main.py manual

# 本地環境
python main.py manual
```

## 監控和維護

- 容器健康檢查：Docker Compose 包含健康檢查配置
- 日誌輪轉：自動按日期分割日誌檔案
- 錯誤通知：透過 Webhook 即時接收錯誤通知
- 資源限制：Docker 容器包含記憶體和 CPU 限制

## 故障排除

### 常見問題

1. **登入失敗**
   - 檢查 NTUT_LOGIN_URL、NTUT_USERNAME、NTUT_PASSWORD 是否正確
   - 確認網站結構是否有變更

2. **爬取失敗**
   - 檢查網站 HTML 結構是否變更
   - 查看截圖檔案 (logs/error_debug.png)

3. **通知未收到**
   - 確認 Webhook URL 正確
   - 檢查網路連線

### 日誌位置

- 應用程式日誌：`logs/app_YYYY-MM-DD.log`
- 錯誤日誌：`logs/error_YYYY-MM-DD.log`
- Docker 日誌：`docker-compose logs`

## 開發

### 程式碼規範

- 使用 async/await 語法處理非同步操作
- 使用 type hints 提升程式碼可讀性
- 遵循 PEP 8 編碼標準
- 使用 loguru 進行日誌記錄

### 測試

```bash
# 安裝開發依賴
pip install -e ".[dev]"

# 執行測試
pytest
```

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 授權

MIT License
