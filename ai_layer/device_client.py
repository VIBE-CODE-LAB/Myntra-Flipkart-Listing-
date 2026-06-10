"""
Device Client Library
Handles device-side operations for connecting to and communicating with the server
Used by remote devices to register, send heartbeats, and check for termination
"""

import requests
import yaml
import time
import threading
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict
from urllib.parse import urljoin

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class DeviceClient:
    """
    Client library for remote devices to communicate with the server
    
    Features:
    - Device registration and token management
    - Periodic heartbeat sending
    - Termination status checking
    - Auto-reconnection on failures
    """

    # Configuration paths
    CONFIG_DIR = Path(__file__).parent.parent / "config"
    DEVICE_CONFIG_FILE = CONFIG_DIR / "device_config.yaml"
    DEVICE_INFO_FILE = CONFIG_DIR / ".device_info"

    def __init__(self, server_url: Optional[str] = None, auto_register: bool = True):
        """
        Initialize device client
        
        Args:
            server_url: Server URL (e.g., http://192.168.1.100:5000)
            auto_register: Auto-register if not already registered
        """
        self.device_id = None
        self.api_token = None
        self.device_name = None
        self.is_master = False
        self.is_terminated = False
        self.server_url = server_url or os.getenv("DEVICE_SERVER_URL", "http://localhost:5001")
        self._heartbeat_thread = None
        self._heartbeat_running = False
        self._connection_loss_count = 0
        self._max_connection_losses = 3

        # Load saved device info if exists
        self._load_device_info()

        # Auto-register if needed
        if auto_register and not self.is_registered():
            logger.info("[CLIENT] Device not registered, attempting registration...")
            self.register_device()

    def register_device(self, device_name: str = "My Device", os_type: str = "windows") -> bool:
        """
        Register device with server
        
        Args:
            device_name: User-friendly device name
            os_type: Operating system type (windows/macos/linux)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = urljoin(self.server_url, "/api/auth/register-device")
            
            payload = {
                "device_name": device_name,
                "os_type": os_type
            }
            
            logger.info(f"[CLIENT] Registering device: {device_name}")
            response = requests.post(
                endpoint,
                json=payload,
                headers={
                    "x-registration-token": os.getenv("REGISTRATION_TOKEN", "")
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"[CLIENT] Registration failed: {response.text}")
                return False
            
            data = response.json()
            
            # Save device info
            self.device_id = data["device_id"]
            self.api_token = data["api_token"]
            self.device_name = data["device_name"]
            self.is_master = data["is_master"]
            
            self._save_device_info()
            
            logger.info(f"[CLIENT] ✓ Device registered: {self.device_id}")
            logger.info(f"[CLIENT] ✓ Server: {self.server_url}")
            logger.info(f"[CLIENT] ✓ Master device: {self.is_master}")
            
            return True
        
        except Exception as e:
            logger.error(f"[CLIENT] Registration error: {e}")
            return False

    def is_registered(self) -> bool:
        """Check if device is already registered"""
        return self.device_id is not None and self.api_token is not None

    def send_heartbeat(self) -> bool:
        """
        Send heartbeat to server
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_registered():
            return False
        
        try:
            endpoint = urljoin(self.server_url, f"/api/devices/{self.device_id}/heartbeat")
            
            payload = {
                "device_id": self.device_id,
                "api_token": self.api_token,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            headers = {
                "X-Device-ID": self.device_id
            }
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                self._connection_loss_count = 0
                return True
            else:
                logger.warning(f"[CLIENT] Heartbeat failed: {response.status_code}")
                self._connection_loss_count += 1
                return False
        
        except Exception as e:
            logger.warning(f"[CLIENT] Heartbeat error: {e}")
            self._connection_loss_count += 1
            return False

    def check_termination_status(self) -> bool:
        """
        Check if device has been terminated
        
        Returns:
            True if terminated, False otherwise
        """
        if not self.is_registered():
            return False
        
        try:
            endpoint = urljoin(self.server_url, "/api/control/status")
            
            params = {
                "device_id": self.device_id,
                "api_token": self.api_token
            }
            
            headers = {
                "X-Device-ID": self.device_id,
                "api_token": self.api_token
            }
            
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                is_terminated = data.get("is_terminated", False)
                
                if is_terminated and not self.is_terminated:
                    logger.warning("[CLIENT] ⚠️ DEVICE HAS BEEN TERMINATED BY MAIN SYSTEM")
                    self.is_terminated = True
                    self._save_device_info()
                
                return is_terminated
            
            return False
        
        except Exception as e:
            logger.warning(f"[CLIENT] Status check error: {e}")
            return False

    def start_heartbeat_loop(self, interval: int = 30):
        """
        Start background heartbeat thread
        
        Args:
            interval: Heartbeat interval in seconds
        """
        if self._heartbeat_running:
            logger.warning("[CLIENT] Heartbeat loop already running")
            return
        
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(interval,),
            daemon=True
        )
        self._heartbeat_thread.start()
        logger.info(f"[CLIENT] ✓ Heartbeat loop started (interval: {interval}s)")

    def stop_heartbeat_loop(self):
        """Stop background heartbeat thread"""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("[CLIENT] ✓ Heartbeat loop stopped")

    def _heartbeat_loop(self, interval: int):
        """Internal heartbeat loop"""
        while self._heartbeat_running:
            try:
                # Send heartbeat
                self.send_heartbeat()
                
                # Check termination status
                if self.check_termination_status():
                    logger.error("[CLIENT] Termination signal received, stopping...")
                    self._heartbeat_running = False
                    break
                
                # Sleep
                time.sleep(interval)
            
            except Exception as e:
                logger.error(f"[CLIENT] Heartbeat loop error: {e}")
                time.sleep(interval)

    def get_server_status(self) -> Optional[dict]:
        """
        Get server health status
        
        Returns:
            Server status dict or None if error
        """
        try:
            endpoint = urljoin(self.server_url, "/health")
            response = requests.get(endpoint, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            
            return None
        
        except Exception as e:
            logger.warning(f"[CLIENT] Server status check failed: {e}")
            return None

    def disconnect(self):
        """Disconnect from server"""
        self.stop_heartbeat_loop()
        logger.info("[CLIENT] Disconnected from server")

    def _load_device_info(self):
        """Load device info from config file"""
        try:
            if self.DEVICE_INFO_FILE.exists():
                with open(self.DEVICE_INFO_FILE, 'r') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self.device_id = data.get("device_id")
                        self.api_token = data.get("api_token")
                        self.device_name = data.get("device_name")
                        self.is_master = data.get("is_master", False)
                        self.is_terminated = data.get("is_terminated", False)
                        
                        if self.device_id:
                            logger.info(f"[CLIENT] Loaded device info: {self.device_id}")
        
        except Exception as e:
            logger.warning(f"[CLIENT] Failed to load device info: {e}")

    def _save_device_info(self):
        """Save device info to config file"""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            data = {
                "device_id": self.device_id,
                "api_token": self.api_token,
                "device_name": self.device_name,
                "is_master": self.is_master,
                "is_terminated": self.is_terminated,
                "saved_at": datetime.utcnow().isoformat()
            }
            
            with open(self.DEVICE_INFO_FILE, 'w') as f:
                yaml.dump(data, f)
            
            logger.debug("[CLIENT] Device info saved")
        
        except Exception as e:
            logger.error(f"[CLIENT] Failed to save device info: {e}")

    def get_device_info(self) -> dict:
        """Get current device information"""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "is_master": self.is_master,
            "is_registered": self.is_registered(),
            "is_terminated": self.is_terminated,
            "server_url": self.server_url,
            "connection_losses": self._connection_loss_count
        }

    def __repr__(self) -> str:
        return (
            f"DeviceClient(device_id={self.device_id}, "
            f"device_name={self.device_name}, "
            f"is_registered={self.is_registered()})"
        )


# ================ HELPER FUNCTIONS ================

def create_client(server_url: str, device_name: str = "My Device") -> DeviceClient:
    """
    Create and register a new device client
    
    Args:
        server_url: Server URL
        device_name: Device name
        
    Returns:
        Initialized DeviceClient instance
    """
    client = DeviceClient(server_url=server_url, auto_register=False)
    client.register_device(device_name)
    return client


def get_or_create_client(server_url: str) -> DeviceClient:
    """
    Get existing client or create new one
    
    Args:
        server_url: Server URL
        
    Returns:
        DeviceClient instance
    """
    client = DeviceClient(server_url=server_url, auto_register=True)
    return client
