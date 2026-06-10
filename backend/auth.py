"""
Authentication module
Handles token generation, validation, and security
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Tuple
import json
import os
from pathlib import Path


# Configuration paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
MASTER_TOKEN_FILE = CONFIG_DIR / ".master_token"
MASTER_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


class AuthManager:
    """Handles authentication and token management"""

    # Token prefix for identification
    MASTER_TOKEN_PREFIX = "master_"
    DEVICE_TOKEN_PREFIX = "device_"
    TOKEN_LENGTH = 32  # 32 bytes = 256 bits

    @staticmethod
    def generate_token(is_master: bool = False) -> str:
        """
        Generate a secure random token
        
        Args:
            is_master: If True, prefix with master_; otherwise device_
            
        Returns:
            Secure token string
        """
        # Convert to hex
        token_value = secrets.token_hex(AuthManager.TOKEN_LENGTH)
        
        # Add prefix
        prefix = AuthManager.MASTER_TOKEN_PREFIX if is_master else AuthManager.DEVICE_TOKEN_PREFIX
        token = f"{prefix}{token_value}"
        
        return token

    @staticmethod
    def generate_device_id() -> str:
        """
        Generate a unique device ID (UUID format)
        
        Returns:
            Device ID string
        """
        import uuid
        return f"dev_{uuid.uuid4()}"

    @staticmethod
    def is_valid_token_format(token: str) -> bool:
        """Check if token has valid format"""
        return (
            token.startswith(AuthManager.MASTER_TOKEN_PREFIX) or
            token.startswith(AuthManager.DEVICE_TOKEN_PREFIX)
        ) and len(token) > 10

    @staticmethod
    def is_master_token(token: str) -> bool:
        """Check if token is a master token"""
        return token.startswith(AuthManager.MASTER_TOKEN_PREFIX)

    @staticmethod
    def create_master_token() -> str:
        """
        Create and save master token
        Called only once on first system startup
        
        Returns:
            Master token
        """
        # Check if master token already exists
        if MASTER_TOKEN_FILE.exists():
            return AuthManager.load_master_token()

        configured_token = os.getenv("MASTER_TOKEN", "").strip()
        if configured_token and not AuthManager.is_valid_token_format(configured_token):
            raise ValueError("MASTER_TOKEN must start with 'master_' and be at least 11 characters")
        master_token = configured_token or AuthManager.generate_token(is_master=True)

        # Save to secure file
        try:
            MASTER_TOKEN_FILE.write_text(master_token)
            # Set file permissions to read-only for owner (Unix-like)
            # On Windows, this is handled differently
            print(f"[AUTH] Master token created and saved")
        except Exception as e:
            print(f"[AUTH ERROR] Failed to save master token: {e}")
            return None

        return master_token

    @staticmethod
    def load_master_token() -> Optional[str]:
        """
        Load master token from file
        
        Returns:
            Master token if exists, None otherwise
        """
        configured_token = os.getenv("MASTER_TOKEN", "").strip()
        if configured_token:
            return configured_token if AuthManager.is_valid_token_format(configured_token) else None

        if MASTER_TOKEN_FILE.exists():
            try:
                token = MASTER_TOKEN_FILE.read_text().strip()
                if AuthManager.is_valid_token_format(token):
                    return token
            except Exception as e:
                print(f"[AUTH ERROR] Failed to load master token: {e}")
        return None

    @staticmethod
    def verify_token(token: str, expected_token: str) -> bool:
        """
        Verify token using constant-time comparison
        Prevents timing attacks
        
        Args:
            token: Token to verify
            expected_token: Expected token value
            
        Returns:
            True if tokens match, False otherwise
        """
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token, expected_token)

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Hash a token for storage (not used yet, but useful for future)
        
        Args:
            token: Token to hash
            
        Returns:
            Hashed token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def create_device_session_token(device_id: str, api_token: str) -> dict:
        """
        Create session data for a device
        
        Args:
            device_id: Device ID
            api_token: Device API token
            
        Returns:
            Session dictionary
        """
        return {
            "device_id": device_id,
            "api_token": api_token,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat()
        }

    @staticmethod
    def validate_device_session(session_data: dict) -> bool:
        """
        Validate device session
        
        Args:
            session_data: Session dictionary
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if "expires_at" in session_data:
                expires_at = datetime.fromisoformat(session_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    return False
            return True
        except Exception:
            return False


class RateLimiter:
    """Simple rate limiting for API endpoints"""

    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Max requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}  # {ip_address: [(timestamp, count), ...]}

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed
        
        Args:
            identifier: IP address or device ID
            
        Returns:
            True if allowed, False if rate limited
        """
        now = datetime.utcnow()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Remove old requests outside time window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if (now - req_time).seconds < self.time_window
        ]
        
        # Check if under limit
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        
        return False

    def cleanup(self):
        """Clean up old entries periodically"""
        now = datetime.utcnow()
        for key in list(self.requests.keys()):
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if (now - req_time).seconds < self.time_window * 2
            ]
            if not self.requests[key]:
                del self.requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=100, time_window=60)
