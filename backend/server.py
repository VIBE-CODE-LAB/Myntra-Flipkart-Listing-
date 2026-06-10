"""
FastAPI Backend Server
Handles device management, registration, and termination
"""

from fastapi import FastAPI, Depends, HTTPException, Header, status, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import asyncio
from typing import Optional
import socket
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.database import init_db, get_db, DeviceModel
from backend.models import (
    DeviceRegisterRequest, DeviceRegisterResponse,
    DeviceHeartbeatRequest, HeartbeatResponse,
    DeviceTerminateRequest, TerminationResponse,
    TerminateAllRequest,
    DeviceStatusCheckRequest, ControlStatusResponse,
    DeviceListResponse, DeviceInfo,
    ErrorResponse
)
from backend.auth import AuthManager, rate_limiter
from backend.device_manager import DeviceManager

# ================ SETUP ================

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Myntra Listing AI - Device Manager",
    description="Backend server for managing connected AI devices and Flipkart listing generation",
    version="1.0.0"
)

# Add CORS middleware
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
master_token = None
STARTUP_COMPLETE = False


# ================ STARTUP & SHUTDOWN ================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global master_token, STARTUP_COMPLETE
    
    print("\n" + "="*60)
    print("[SERVER] Starting Flipkart AI Device Manager Server")
    print("="*60)
    
    # Initialize database
    init_db()
    
    # Get or create master token
    loaded_token = AuthManager.load_master_token()
    if loaded_token:
        master_token = loaded_token
        print(f"[SERVER] ✓ Loaded existing master token")
    else:
        master_token = AuthManager.create_master_token()
        print(f"[SERVER] ✓ Created new master token")
    
    # Initialize master device if not exists
    db = next(get_db())
    try:
        from backend.database import DeviceRepository
        repo = DeviceRepository()
        master_device = repo.get_master_device(db)
        
        if not master_device:
            print("[SERVER] Registering master device...")
            manager = DeviceManager(db)
            device_id, api_token, _ = manager.register_device(
                device_name="Main System",
                os_type="windows",  # Auto-detect in production
                is_master=True
            )
            print(f"[SERVER] ✓ Master device registered: {device_id}")
        else:
            print(f"[SERVER] ✓ Master device already exists: {master_device.device_id}")
    finally:
        db.close()
    
    STARTUP_COMPLETE = True
    print("[SERVER] ✓ Server startup complete\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("\n[SERVER] Shutting down server...")
    rate_limiter.cleanup()
    print("[SERVER] ✓ Server shutdown complete\n")


# ================ DEPENDENCIES ================

def get_client_ip(request: Request) -> str:
    """Extract client IP address"""
    return request.client.host if request.client else "unknown"


def check_rate_limit(client_ip: str = Depends(get_client_ip)):
    """Rate limiting dependency"""
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests"
        )
    return client_ip


# ================ HEALTH CHECK ================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Flipkart AI Device Manager",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# ================ AUTHENTICATION ENDPOINTS ================

@app.post(
    "/api/auth/register-device",
    response_model=DeviceRegisterResponse,
    tags=["Authentication"],
    summary="Register a new device",
    responses={
        200: {"description": "Device registered successfully"},
        400: {"description": "Invalid request"},
        429: {"description": "Too many requests"}
    }
)
async def register_device(
    request: DeviceRegisterRequest,
    registration_token: Optional[str] = Header(None, alias="x-registration-token"),
    db: Session = Depends(get_db),
    client_ip: str = Depends(check_rate_limit)
):
    """
    Register a new device with the server
    
    This endpoint should be called on first startup of the application
    on a new machine.
    
    Args:
        request: Device registration request
        
    Returns:
        Device ID, API token, and server URL
    """
    try:
        expected_registration_token = os.getenv("REGISTRATION_TOKEN", "").strip()
        if expected_registration_token and not AuthManager.verify_token(
            registration_token or "", expected_registration_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid registration token",
            )

        manager = DeviceManager(db)
        
        # Determine if this is master device (only if no master exists yet)
        from backend.database import DeviceRepository
        repo = DeviceRepository()
        is_master = repo.get_master_device(db) is None
        
        device_id, api_token, server_url = manager.register_device(
            device_name=request.device_name,
            os_type=request.os_type,
            ip_address=client_ip,
            is_master=is_master
        )
        
        return DeviceRegisterResponse(
            device_id=device_id,
            api_token=api_token,
            device_name=request.device_name,
            server_url=server_url,
            is_master=is_master,
            created_at=datetime.utcnow()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@app.post(
    "/api/auth/verify-device",
    response_model=dict,
    tags=["Authentication"],
    summary="Verify device token"
)
async def verify_device(
    device_id: str,
    api_token: str,
    db: Session = Depends(get_db)
):
    """
    Verify if device token is valid
    
    Args:
        device_id: Device ID
        api_token: Device API token
        
    Returns:
        Verification result
    """
    manager = DeviceManager(db)
    is_valid, error = manager.verify_device_token(device_id, api_token)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )
    
    return {"valid": True, "message": "Token verified"}


# ================ DEVICE MANAGEMENT ENDPOINTS ================

@app.get(
    "/api/devices/list",
    response_model=DeviceListResponse,
    tags=["Devices"],
    summary="List all devices"
)
async def list_devices(
    api_token: str = Header(..., alias="api-token", description="Master API token"),
    db: Session = Depends(get_db)
):
    """
    Get list of all registered devices
    
    Requires master token authentication
    """
    manager = DeviceManager(db)
    
    # Verify master token
    is_valid, error = manager.verify_master_token(api_token)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": error or "Invalid master token"}
        )
    
    # Check and update offline devices
    manager.check_offline_devices()
    
    # Get stats
    stats = manager.get_device_stats()
    
    # Get all devices
    all_devices = manager.get_all_devices()
    
    device_infos = [
        DeviceInfo(
            device_id=d.device_id,
            device_name=d.device_name,
            os_type=d.os_type,
            status=d.status,
            ip_address=d.ip_address,
            last_connected=d.last_connected,
            is_master=d.is_master,
            created_at=d.created_at
        )
        for d in all_devices
    ]
    
    return DeviceListResponse(
        total_devices=stats["total_devices"],
        online_count=stats["online_count"],
        offline_count=stats["offline_count"],
        devices=device_infos
    )


@app.get(
    "/api/devices/{device_id}/status",
    response_model=dict,
    tags=["Devices"],
    summary="Get device status"
)
async def get_device_status(
    device_id: str,
    api_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get detailed status of a specific device
    
    Requires valid device or master token
    """
    manager = DeviceManager(db)
    device = manager.get_device_info(device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check auth
    is_valid, _ = manager.verify_device_token(device_id, api_token)
    if not is_valid:
        # Try master token
        is_valid, error = manager.verify_master_token(api_token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error
            )
    
    return {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "status": device.status,
        "is_online": device.status == "online",
        "is_terminated": device.is_terminated,
        "last_connected": device.last_connected,
        "ip_address": device.ip_address,
        "created_at": device.created_at
    }


@app.post(
    "/api/devices/{device_id}/heartbeat",
    response_model=HeartbeatResponse,
    tags=["Devices"],
    summary="Send heartbeat from device"
)
async def send_heartbeat(
    device_id: str,
    request: DeviceHeartbeatRequest,
    db: Session = Depends(get_db),
    x_forwarded_for: Optional[str] = Header(None)
):
    """
    Heartbeat endpoint for devices to send periodic pings
    
    Called every 30 seconds from remote devices to indicate they're still active
    """
    manager = DeviceManager(db)
    
    # Verify device
    is_valid, error = manager.verify_device_token(device_id, request.api_token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )
    
    # Get client IP
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None
    
    # Process heartbeat
    success, error = manager.process_heartbeat(device_id, client_ip)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return HeartbeatResponse(
        acknowledged=True,
        status="connected",
        server_time=datetime.utcnow()
    )


# ================ CONTROL ENDPOINTS ================

@app.get(
    "/api/control/status",
    response_model=ControlStatusResponse,
    tags=["Control"],
    summary="Check device termination status"
)
async def check_termination_status(
    device_id: str,
    api_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Check if device has been terminated by main system
    
    Remote devices call this periodically to check if they should stop
    """
    manager = DeviceManager(db)
    
    # Verify device
    is_valid, error = manager.verify_device_token(device_id, api_token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )
    
    # Check if terminated
    is_terminated = manager.check_device_terminated(device_id)
    
    return ControlStatusResponse(
        device_id=device_id,
        status="terminated" if is_terminated else "active",
        is_terminated=is_terminated,
        message="Device has been terminated" if is_terminated else "Device is active"
    )


@app.post(
    "/api/devices/terminate/{device_id}",
    response_model=TerminationResponse,
    tags=["Control"],
    summary="Terminate a specific device"
)
async def terminate_device(
    device_id: str,
    request: DeviceTerminateRequest,
    db: Session = Depends(get_db)
):
    """
    Terminate a specific remote device
    
    Requires master token authentication.
    The terminated device will receive the termination signal on next status check.
    """
    manager = DeviceManager(db)
    
    # Verify master token
    is_valid, error = manager.verify_master_token(request.api_token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )
    
    # Terminate device
    success, error = manager.terminate_device(device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return TerminationResponse(
        success=True,
        message=f"Device {device_id} has been terminated",
        terminated_at=datetime.utcnow()
    )


@app.post(
    "/api/devices/terminate-all",
    response_model=dict,
    tags=["Control"],
    summary="Terminate all remote devices"
)
async def terminate_all_devices(
    request: TerminateAllRequest,
    db: Session = Depends(get_db)
):
    """
    Terminate all remote (non-master) devices
    
    Requires master token authentication.
    All remote devices will be marked as terminated and will shut down
    on next status check.
    """
    manager = DeviceManager(db)
    
    # Verify master token
    is_valid, error = manager.verify_master_token(request.api_token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )
    
    # Terminate all remote devices
    count, error = manager.terminate_all_remote_devices()
    
    return {
        "success": True,
        "message": f"Terminated {count} remote devices",
        "devices_terminated": count,
        "terminated_at": datetime.utcnow()
    }


# ================ ERROR HANDLERS ================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "detail": None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Generic exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ================ ROOT ENDPOINT ================

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API info"""
    return {
        "service": "Flipkart AI Device Manager",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


# ================ MAIN ================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("BACKEND_PORT", "5001")),
        log_level="info"
    )
