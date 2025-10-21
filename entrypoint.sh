#!/bin/bash

set -e

echo "啟動 NTUT 電費爬蟲機器人..."
echo "使用者: $(whoami)"

exec python main.py
