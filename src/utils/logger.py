"""
Logger configuration using loguru
"""
from pathlib import Path
from loguru import logger
import sys
from typing import Any, Dict


class Logger:
    def __init__(self):
        self._setup_logger()

    def _setup_logger(self) -> None:
        logger.remove()
        
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        
        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            encoding="utf-8"
        )
        
        logger.add(
            log_dir / "error_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            encoding="utf-8"
        )

    def get_logger(self, name: str = None):
        if name:
            return logger.bind(name=name)
        return logger


log_manager = Logger()
app_logger = log_manager.get_logger("ntut_bot")