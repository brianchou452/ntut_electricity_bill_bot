"""
Database models for electricity bill data
"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ElectricityRecord(BaseModel):
    id: Optional[int] = None
    balance: float = Field(..., description="剩餘電費")
    created_at: Optional[datetime] = Field(default_factory=datetime.now, description="記錄建立時間")
    
    class Config:
        from_attributes = True


class CrawlerLog(BaseModel):
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now, description="執行時間")
    status: str = Field(..., description="執行狀態: success, error, partial")
    records_count: int = Field(default=0, description="爬取到的記錄數")
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        from_attributes = True