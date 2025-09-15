# 每日用電摘要功能測試指南

本指南說明如何測試新增的每日用電摘要和圖表生成功能。

## 快速開始

### 1. 運行完整測試
```bash
poetry run python test_daily_summary.py --full-test
```
這會自動：
- 初始化測試資料庫
- 生成昨日的假資料（24小時每小時一筆記錄）
- 測試資料庫查詢功能
- 生成用電圖表
- 測試通知系統邏輯
- 測試調度器整合功能

### 2. 生成多天測試資料
```bash
# 生成過去7天的假資料
poetry run python test_daily_summary.py --generate-days 7
```

### 3. 測試指定日期
```bash
# 測試 2025-01-14 的資料
poetry run python test_daily_summary.py --date 2025-01-14
```

### 4. 清空測試資料
```bash
poetry run python test_daily_summary.py --clear
```

## 詳細功能說明

### 假資料生成器 (TestDataGenerator)

- **`generate_daily_fake_data(target_date, start_balance)`**
  - 為指定日期生成24小時的假資料
  - 每小時模擬用電 1-5 元
  - 起始餘額預設 500 元

- **`generate_multiple_days_data(days)`**
  - 生成多天的連續假資料
  - 每天起始餘額遞減，模擬真實使用情境

### 測試功能

#### 1. 資料庫查詢測試
- 測試 `get_yesterday_records()` 方法
- 測試 `get_daily_usage_summary()` 方法
- 驗證資料完整性和計算正確性

#### 2. 圖表生成測試
- 測試每日用電量折線圖生成
- 驗證圖表檔案是否正確生成
- 檢查檔案大小和格式

#### 3. 通知系統測試
- 測試通知邏輯（不實際發送）
- 驗證摘要資料格式
- 檢查圖表附件處理

#### 4. 調度器整合測試
- 測試 `run_manual_daily_summary()` 方法
- 驗證完整的工作流程

## 測試資料範例

### 生成的假資料格式
```json
{
  "date": "2025-01-14",
  "total_usage": 45.67,
  "start_balance": 500.00,
  "end_balance": 454.33,
  "hourly_usage": [
    {
      "time": "01:00",
      "usage": 2.34,
      "balance": 497.66
    },
    {
      "time": "02:00",
      "usage": 3.12,
      "balance": 494.54
    }
    // ... 更多小時資料
  ]
}
```

## 生成的檔案

### 測試資料庫
- `data/test_electricity_bot.db` - 測試專用 SQLite 資料庫

### 圖表檔案
- `data/charts/daily_usage_YYYY-MM-DD.png` - 每日用電圖表
- 包含兩個子圖：
  1. 每小時用電金額折線圖
  2. 餘額變化趨勢圖

### 日誌輸出
測試過程中會輸出詳細的日誌資訊，包括：
- 資料生成統計
- 查詢結果驗證
- 圖表生成狀態
- 通知系統測試結果

## 常見問題

### Q: 如何檢視生成的圖表？
A: 圖表會儲存在 `data/charts/` 目錄下，可以直接用圖片檢視器開啟。

### Q: 測試資料會影響正式環境嗎？
A: 不會，測試使用獨立的資料庫檔案 `test_electricity_bot.db`。

### Q: 如何測試真實的通知發送？
A: 在 `test_notification_system()` 方法中取消註解對應行：
```python
await self.notification_manager.send_daily_summary_notification(daily_summary, chart_path)
```

### Q: 可以自定義假資料的參數嗎？
A: 可以，在 `TestDataGenerator` 類別中修改：
- `hourly_usage` 的隨機範圍
- `start_balance` 起始餘額
- 資料點的數量和頻率

## 進階測試

### 1. 壓力測試
```bash
# 生成30天的大量資料
poetry run python test_daily_summary.py --generate-days 30
```

### 2. 邊界條件測試
- 零用電量的日期
- 餘額為零的情況
- 跨日期的資料查詢

### 3. 錯誤處理測試
- 資料庫連接失敗
- 圖表生成異常
- 檔案權限問題

## 整合到正式環境

測試完成後，確保：
1. 正式資料庫路徑正確
2. Discord webhook URL 已設定
3. 通知時間範圍符合需求
4. 圖表清理機制正常運作