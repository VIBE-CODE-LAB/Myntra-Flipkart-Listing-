"""
Database layer using SQLAlchemy
Manages device registry and persistence
"""

import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, List, Generator

# Create data directory if it doesn't exist
DB_DIR = Path(__file__).parent.parent / "data" / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

# Database URL
DATABASE_URL = f"sqlite:///{DB_DIR / 'devices.db'}"

# SQLAlchemy setup
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL debug logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ================ DATABASE MODELS ================

class DeviceModel(Base):
    """SQLAlchemy model for Device table"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(36), unique=True, index=True, nullable=False)
    device_name = Column(String(100), nullable=False)
    os_type = Column(String(20), nullable=False)  # windows, macos, linux
    api_token = Column(String(256), unique=True, nullable=False)
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    status = Column(String(20), default="online")  # online, offline, terminated
    is_master = Column(Boolean, default=False)
    is_terminated = Column(Boolean, default=False)
    last_connected = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    class Config:
        orm_mode = True


# Create all tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Database initialized at: {DATABASE_URL}")


# ================ DATABASE OPERATIONS ================

def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DeviceRepository:
    """Repository pattern for device operations"""

    @staticmethod
    def create_device(
        db: Session,
        device_id: str,
        device_name: str,
        os_type: str,
        api_token: str,
        ip_address: Optional[str] = None,
        is_master: bool = False
    ) -> DeviceModel:
        """Create a new device"""
        device = DeviceModel(
            device_id=device_id,
            device_name=device_name,
            os_type=os_type,
            api_token=api_token,
            ip_address=ip_address,
            is_master=is_master,
            status="online",
            last_connected=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def get_device_by_id(db: Session, device_id: str) -> Optional[DeviceModel]:
        """Get device by device_id"""
        return db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()

    @staticmethod
    def get_device_by_token(db: Session, api_token: str) -> Optional[DeviceModel]:
        """Get device by API token"""
        return db.query(DeviceModel).filter(DeviceModel.api_token == api_token).first()

    @staticmethod
    def get_master_device(db: Session) -> Optional[DeviceModel]:
        """Get the master (main) device - Always mark as online on fetch"""
        master = db.query(DeviceModel).filter(DeviceModel.is_master == True).first()
        if master and master.status != "online":
            master.status = "online"
            master.last_connected = datetime.utcnow()
            db.commit()
            db.refresh(master)
        return master

    @staticmethod
    def get_all_devices(db: Session) -> List[DeviceModel]:
        """Get all devices"""
        return db.query(DeviceModel).all()

    @staticmethod
    def get_all_remote_devices(db: Session) -> List[DeviceModel]:
        """Get all remote (non-master) devices"""
        return db.query(DeviceModel).filter(DeviceModel.is_master == False).all()

    @staticmethod
    def get_online_devices(db: Session) -> List[DeviceModel]:
        """Get all online devices"""
        return db.query(DeviceModel).filter(
            DeviceModel.status == "online",
            DeviceModel.is_terminated == False
        ).all()

    @staticmethod
    def update_device_heartbeat(db: Session, device_id: str, ip_address: Optional[str] = None) -> Optional[DeviceModel]:
        """Update device last_connected timestamp"""
        device = db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        if device:
            device.last_connected = datetime.utcnow()
            device.status = "online"
            if ip_address:
                device.ip_address = ip_address
            db.commit()
            db.refresh(device)
        return device

    @staticmethod
    def terminate_device(db: Session, device_id: str) -> Optional[DeviceModel]:
        """Mark device as terminated"""
        device = db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        if device:
            device.is_terminated = True
            device.status = "terminated"
            device.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(device)
        return device

    @staticmethod
    def terminate_all_remote_devices(db: Session) -> int:
        """Terminate all remote devices, returns count"""
        count = db.query(DeviceModel).filter(
            DeviceModel.is_master == False
        ).update(
            {
                DeviceModel.is_terminated: True,
                DeviceModel.status: "terminated",
                DeviceModel.updated_at: datetime.utcnow()
            }
        )
        db.commit()
        return count

    @staticmethod
    def set_device_offline(db: Session, device_id: str) -> Optional[DeviceModel]:
        """Mark device as offline"""
        device = db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        if device:
            device.status = "offline"
            device.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(device)
        return device

    @staticmethod
    def delete_device(db: Session, device_id: str) -> bool:
        """Delete a device"""
        device = db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        if device:
            db.delete(device)
            db.commit()
            return True
        return False

    @staticmethod
    def count_devices(db: Session) -> int:
        """Count total devices"""
        return db.query(DeviceModel).count()

    @staticmethod
    def count_online_devices(db: Session) -> int:
        """Count online devices"""
        return db.query(DeviceModel).filter(DeviceModel.status == "online").count()

    @staticmethod
    def count_offline_devices(db: Session) -> int:
        """Count offline devices"""
        return db.query(DeviceModel).filter(DeviceModel.status == "offline").count()
