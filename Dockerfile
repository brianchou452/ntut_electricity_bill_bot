# 使用 Playwright 官方 Python image
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XVFB_WHD=1920x1080x24

# 複製 pyproject.toml 檔案
COPY pyproject.toml poetry.lock* ./

# 安裝必要的系統套件、中文字體和 Poetry
RUN apt-get update && \
    apt-get install -y fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei x11-utils xvfb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# 複製專案檔案
COPY . .

# 複製並設定啟動腳本權限
COPY entrypoint.sh /entrypoint.sh

# 建立必要的目錄和設定權限
RUN mkdir -p /app/data /app/logs && \
    chmod +x /entrypoint.sh && \
    chmod +x /app/main.py && \
    chown -R pwuser:pwuser /app /entrypoint.sh && \
    mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

USER pwuser

# 健康檢查
HEALTHCHECK --interval=5m --timeout=30s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; from src.scheduler.scheduler import SchedulerManager; sm = SchedulerManager(); print('healthy' if sm.get_status().get('is_running', False) else exit(1))" || exit 1

# 暴露埠號 (如果需要的話)
# EXPOSE 8000

# 使用啟動腳本
ENTRYPOINT ["/entrypoint.sh"]