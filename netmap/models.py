"""
NetMap - Network Tree Status Monitor (Data Models & Schemas)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

from typing import Optional
from pydantic import BaseModel, Field

class HostCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    ip_address: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None
    grouping: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field("", max_length=1000)
    is_active: bool = True

class HostUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = Field(None, min_length=1, max_length=255)
    location: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    grouping: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    aggregation_mode: str = Field("any", pattern="^(any|all)$")
    description: Optional[str] = Field("", max_length=1000)

class GroupUpdate(BaseModel):
    aggregation_mode: Optional[str] = Field(None, pattern="^(any|all)$")
    description: Optional[str] = Field(None, max_length=1000)

class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)
    role: str = Field("operator", pattern="^(admin|operator)$")

class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=4, max_length=128)
    role: Optional[str] = Field(None, pattern="^(admin|operator)$")

class SettingsUpdate(BaseModel):
    server_host: Optional[str] = Field(None, max_length=255)
    server_port: Optional[int] = Field(None, ge=1, le=65535)
    url_prefix: Optional[str] = Field(None, max_length=255)
    interval_seconds: Optional[int] = Field(None, ge=5, le=86400)
    ping_threads: Optional[int] = Field(None, ge=1, le=500)
    ping_timeout: Optional[int] = Field(None, ge=1, le=30)
    ping_count: Optional[int] = Field(None, ge=1, le=10)
    retention_hours: Optional[int] = Field(None, ge=24, le=8760)
    speedtest_enabled: Optional[bool] = None
    speedtest_server_url: Optional[str] = Field(None, max_length=500)
    speedtest_duration_seconds: Optional[int] = Field(None, ge=3, le=30)
    speedtest_visitor_cooldown_hours: Optional[int] = Field(None, ge=0, le=72)

class SpeedtestResultCreate(BaseModel):
    ping_ms: Optional[float] = Field(None, ge=0.0, le=60000.0)
    jitter_ms: Optional[float] = Field(None, ge=0.0, le=60000.0)
    download_max_mbps: Optional[float] = Field(None, ge=0.0, le=1000000.0)
    download_avg_mbps: Optional[float] = Field(None, ge=0.0, le=1000000.0)
    upload_max_mbps: Optional[float] = Field(None, ge=0.0, le=1000000.0)
    upload_avg_mbps: Optional[float] = Field(None, ge=0.0, le=1000000.0)

