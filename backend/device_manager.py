"""
Device Manager
Manages device lifecycle and operations
"""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from backend.database import DeviceRepository, DeviceModel
from backend.auth import AuthManager


class DeviceManager:
    """Manages device registration, tracking, and termination"""

    # Device timeout in minutes (mark as offline if no heartbeat)
    DEVICE_TIMEOUT_MINUTES = 5
    
    def __init__(self, db: Session):
        """
        Initialize device manager
        
        Args:
            db: Database session
        """
        self.db = db
        self.repo = DeviceRepository()

    def register_device(
        self,
        device_name: str,
        os_type: str,
        ip_address: Optional[str] = None,
        is_master: bool = False
    ) -> Tuple[str, str, str]:
        """
        Register a new device
        
        Args:
            device_name: User-friendly device name
            os_type: Operating system type
            ip_address: Device IP address (optional)
            is_master: Whether this is the master device
            
        Returns:
            Tuple of (device_id, api_token, server_url)
        """
        # Generate IDs and token
        device_id = AuthManager.generate_device_id()
        api_token = AuthManager.generate_token(is_master=is_master)
        
        # Create device in database
        device = self.repo.create_device(
            db=self.db,
            device_id=device_id,
            device_name=device_name,
            os_type=os_type,
            api_token=api_token,
            ip_address=ip_address,
            is_master=is_master
        )
        
        print(f"[DEVICE] Registered device: {device_name} ({device_id})")
        
        return device_id, api_token, f"http://localhost:5000"

    def verify_device_token(self, device_id: str, api_token: str) -> Tuple[bool, Optional[str]]:
        """
        Verify device token
        
        Args:
            device_id: Device ID
            api_token: API token
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        device = self.repo.get_device_by_id(self.db, device_id)
        
        if not device:
            return False, "Device not found"
        
        if device.is_terminated:
            return False, "Device has been terminated"
        
        if not AuthManager.verify_token(api_token, device.api_token):
            return False, "Invalid API token"
        
        return True, None

    def verify_master_token(self, master_token: str) -> Tuple[bool, Optional[str]]:
        """
        Verify master token
        
        Args:
            master_token: Master token to verify
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Load the actual master token from file
        stored_master_token = AuthManager.load_master_token()
        
        if not stored_master_token:
            return False, "Master token not configured"
        
        if not AuthManager.verify_token(master_token, stored_master_token):
            return False, "Invalid master token"
        
        return True, None

    def process_heartbeat(
        self,
        device_id: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Process heartbeat from device
        
        Args:
            device_id: Device ID
            ip_address: Device IP address (optional)
            
        Returns:
            Tuple of (success, error_message)
        """
        device = self.repo.update_device_heartbeat(self.db, device_id, ip_address)
        
        if not device:
            return False, "Device not found"
        
        return True, None

    def check_offline_devices(self) -> List[DeviceModel]:
        """
        Check and mark devices as offline if no recent heartbeat
        
        Returns:
            List of newly offline devices
        """
        timeout_threshold = datetime.utcnow() - timedelta(minutes=self.DEVICE_TIMEOUT_MINUTES)
        
        all_devices = self.repo.get_all_devices(self.db)
        offline_devices = []
        
        for device in all_devices:
            # Skip already offline or terminated devices
            if device.status == "offline" or device.is_terminated:
                continue
            
            # Mark as offline if no recent heartbeat
            if device.last_connected and device.last_connected < timeout_threshold:
                self.repo.set_device_offline(self.db, device.device_id)
                offline_devices.append(device)
                print(f"[DEVICE] Marked {device.device_name} as offline (no heartbeat)")
        
        return offline_devices

    def get_device_info(self, device_id: str) -> Optional[DeviceModel]:
        """
        Get device information
        
        Args:
            device_id: Device ID
            
        Returns:
            Device model or None
        """
        return self.repo.get_device_by_id(self.db, device_id)

    def get_all_devices(self) -> List[DeviceModel]:
        """
        Get all registered devices
        
        Returns:
            List of all devices
        """
        return self.repo.get_all_devices(self.db)

    def get_online_devices(self) -> List[DeviceModel]:
        """
        Get all online devices
        
        Returns:
            List of online devices
        """
        return self.repo.get_online_devices(self.db)

    def get_remote_devices(self) -> List[DeviceModel]:
        """
        Get all remote (non-master) devices
        
        Returns:
            List of remote devices
        """
        return self.repo.get_all_remote_devices(self.db)

    def terminate_device(self, device_id: str) -> Tuple[bool, Optional[str]]:
        """
        Terminate a specific device
        
        Args:
            device_id: Device ID to terminate
            
        Returns:
            Tuple of (success, error_message)
        """
        device = self.repo.get_device_by_id(self.db, device_id)
        
        if not device:
            return False, "Device not found"
        
        if device.is_master:
            return False, "Cannot terminate master device"
        
        if device.is_terminated:
            return False, "Device is already terminated"
        
        self.repo.terminate_device(self.db, device_id)
        print(f"[DEVICE] Terminated device: {device.device_name}")
        
        return True, None

    def terminate_all_remote_devices(self) -> Tuple[int, Optional[str]]:
        """
        Terminate all remote devices
        
        Returns:
            Tuple of (count_terminated, error_message)
        """
        count = self.repo.terminate_all_remote_devices(self.db)
        print(f"[DEVICE] Terminated {count} remote devices")
        return count, None

    def check_device_terminated(self, device_id: str) -> bool:
        """
        Check if a device is terminated
        
        Args:
            device_id: Device ID
            
        Returns:
            True if terminated, False otherwise
        """
        device = self.repo.get_device_by_id(self.db, device_id)
        return device.is_terminated if device else False

    def get_device_stats(self) -> dict:
        """
        Get device statistics
        
        Returns:
            Dictionary with device stats
        """
        total = self.repo.count_devices(self.db)
        online = self.repo.count_online_devices(self.db)
        offline = self.repo.count_offline_devices(self.db)
        
        return {
            "total_devices": total,
            "online_count": online,
            "offline_count": offline,
            "terminated_count": total - online - offline
        }

    def rename_device(self, device_id: str, new_name: str) -> Tuple[bool, Optional[str]]:
        """
        Rename a device
        
        Args:
            device_id: Device ID
            new_name: New device name
            
        Returns:
            Tuple of (success, error_message)
        """
        device = self.repo.get_device_by_id(self.db, device_id)
        
        if not device:
            return False, "Device not found"
        
        old_name = device.device_name
        device.device_name = new_name
        self.db.commit()
        
        print(f"[DEVICE] Renamed device: {old_name} -> {new_name}")
        
        return True, None

    def cleanup_terminated_devices(self, days: int = 30) -> int:
        """
        Delete devices terminated more than N days ago
        
        Args:
            days: Number of days to keep terminated devices
            
        Returns:
            Number of deleted devices
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        all_devices = self.repo.get_all_devices(self.db)
        deleted_count = 0
        
        for device in all_devices:
            if (device.is_terminated and 
                device.updated_at < cutoff_date):
                self.repo.delete_device(self.db, device.device_id)
                deleted_count += 1
        
        print(f"[DEVICE] Cleaned up {deleted_count} old terminated devices")
        
        return deleted_count
