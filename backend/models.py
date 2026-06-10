"""
Pydantic models for device management
Defines request/response data structures
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DeviceStatus(str, Enum):
    """Device status enum"""
    ONLINE = "online"
    OFFLINE = "offline"
    TERMINATED = "terminated"


class DeviceType(str, Enum):
    """Operating system types"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


# ================ REQUEST MODELS ================

class DeviceRegisterRequest(BaseModel):
    """Request to register a new device"""
    device_name: str = Field(..., min_length=1, max_length=100, description="User-friendly device name")
    os_type: str = Field(..., description="Operating system type (windows/macos/linux)")


class DeviceHeartbeatRequest(BaseModel):
    """Heartbeat request from remote device"""
    device_id: str
    api_token: str
    timestamp: Optional[datetime] = None


class DeviceTerminateRequest(BaseModel):
    """Request to terminate a device"""
    device_id: str
    api_token: str = Field(..., description="Master token to authorize termination")


class TerminateAllRequest(BaseModel):
    """Request to terminate all remote devices"""
    api_token: str = Field(..., description="Master token to authorize termination")


class DeviceStatusCheckRequest(BaseModel):
    """Request to check control status"""
    device_id: str
    api_token: str


# ================ RESPONSE MODELS ================

class DeviceRegisterResponse(BaseModel):
    """Response after device registration"""
    device_id: str
    api_token: str
    device_name: str
    server_url: str
    is_master: bool
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "dev_550e8400e29b41d4a716446655440000",
                "api_token": "token_abc123xyz",
                "device_name": "My Laptop",
                "server_url": "http://192.168.1.100:5000",
                "is_master": False,
                "created_at": "2026-02-03T10:30:00"
            }
        }


class DeviceInfo(BaseModel):
    """Public device information returned to the dashboard."""
    device_id: str
    device_name: str
    os_type: str
    status: DeviceStatus
    ip_address: Optional[str] = None
    last_connected: Optional[datetime] = None
    is_master: bool
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "dev_550e8400e29b41d4a716446655440000",
                "device_name": "Main System",
                "os_type": "windows",
                "status": "online",
                "ip_address": "192.168.1.100",
                "last_connected": "2026-02-03T10:30:00",
                "is_master": True,
                "created_at": "2026-02-03T10:00:00"
            }
        }


class DeviceListResponse(BaseModel):
    """List of all devices"""
    total_devices: int
    online_count: int
    offline_count: int
    devices: List[DeviceInfo]


class HeartbeatResponse(BaseModel):
    """Response to heartbeat"""
    acknowledged: bool
    status: str
    server_time: datetime


class TerminationResponse(BaseModel):
    """Response to termination request"""
    success: bool
    message: str
    terminated_at: Optional[datetime] = None


class ControlStatusResponse(BaseModel):
    """Response with control status"""
    device_id: str
    status: str  # "active" or "terminated"
    is_terminated: bool
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "dev_550e8400e29b41d4a716446655440000",
                "status": "active",
                "is_terminated": False,
                "message": "Device is active and connected"
            }
        }


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid token",
                "detail": "The provided API token is not valid",
                "timestamp": "2026-02-03T10:30:00"
            }
        }


# ================ DATABASE MODELS ================

class Device(BaseModel):
    """Device data model (for DB storage)"""
    device_id: str
    device_name: str
    os_type: str
    api_token: str
    ip_address: Optional[str] = None
    status: DeviceStatus = DeviceStatus.ONLINE
    is_master: bool = False
    is_terminated: bool = False
    last_connected: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "dev_550e8400e29b41d4a716446655440000",
                "device_name": "Laptop Pro",
                "os_type": "windows",
                "api_token": "token_secret_abc123",
                "ip_address": "192.168.1.50",
                "status": "online",
                "is_master": False,
                "is_terminated": False,
                "last_connected": "2026-02-03T10:30:00",
                "created_at": "2026-02-03T10:00:00",
                "updated_at": "2026-02-03T10:30:00"
            }
        }
