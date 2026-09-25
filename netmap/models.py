from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class HostCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    ip_address: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None
    grouping: Optional[str] = None
    description: Optional[str] = ""
    is_active: bool = True

class HostUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = Field(None, min_length=1, max_length=255)
    location: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    grouping: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    aggregation_mode: str = Field("any", pattern="^(any|all)$")
    description: Optional[str] = ""

class GroupUpdate(BaseModel):
    aggregation_mode: Optional[str] = Field(None, pattern="^(any|all)$")
    description: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4)
    role: str = Field("operator", pattern="^(admin|operator)$")

class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|operator)$")

class SettingsUpdate(BaseModel):
    server_host: Optional[str] = None
    server_port: Optional[int] = Field(None, ge=1, le=65535)
    interval_seconds: Optional[int] = Field(None, ge=5, le=86400)
    ping_threads: Optional[int] = Field(None, ge=1, le=500)
    ping_timeout: Optional[int] = Field(None, ge=1, le=30)
    ping_count: Optional[int] = Field(None, ge=1, le=10)
    retention_hours: Optional[int] = Field(None, ge=24, le=8760)
