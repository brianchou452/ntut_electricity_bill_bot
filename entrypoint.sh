#!/bin/bash

set -e

echo "啟動 NTUT 電費爬蟲機器人..."
echo "使用者: $(whoami)"
echo "模式: ${BOT_MODE:-scheduler}"

# 根據 BOT_MODE 環境變數決定啟動模式
case "${BOT_MODE:-scheduler}" in
  api)
    echo "啟動 API 模式..."
    exec uvicorn api:app --host 0.0.0.0 --port 8000
    ;;
  scheduler)
    echo "啟動排程器模式..."
    exec python main.py
    ;;
  *)
    echo "錯誤: 未知的 BOT_MODE: ${BOT_MODE}"
    echo "支援的模式: api, scheduler"
    exit 1
    ;;
esac
