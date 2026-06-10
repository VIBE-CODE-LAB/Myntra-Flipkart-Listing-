"""
Device Management Dashboard for Flipkart AI
Standalone Streamlit app to monitor and control connected devices
"""

import streamlit as st
import requests
import time
from pathlib import Path
from datetime import datetime
import yaml
import socket

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SERVER_URL = "http://localhost:5001"

# Detect if this is a remote access
def is_remote_access():
    """
    Detect if the app is being accessed from a remote device
    Returns True if accessed via IP address, False if accessed locally
    
    Detection methods:
    1. Check STREAMLIT_CLIENT_IP environment variable or Streamlit's request context
    2. Check if accessed through an environment variable flag
    3. Default to False (local access)
    """
    try:
        # Initialize session state if not exists
        if 'remote_access_checked' not in st.session_state:
            # Check for explicit flag in environment
            import os
            remote_flag = os.environ.get('DEVICE_DASHBOARD_REMOTE', '').lower()
            
            if remote_flag == 'true':
                st.session_state.is_remote = True
            elif remote_flag == 'false':
                st.session_state.is_remote = False
            else:
                # Try to detect from request context
                try:
                    # Access Streamlit's query parameters to detect remote access
                    from streamlit.web.server import Server
                    from streamlit.proto import SessionState_pb2
                    
                    # Check if we can get client info
                    # For now, default to False (local) - user should set DEVICE_DASHBOARD_REMOTE=true for remote
                    st.session_state.is_remote = False
                except:
                    st.session_state.is_remote = False
            
            st.session_state.remote_access_checked = True
            
        return st.session_state.is_remote
    except:
        return False

# Initialize remote access detection
is_remote = is_remote_access()

# Page config
st.set_page_config(
    page_title="Device Management",
    page_icon="🔗",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
    .device-online {color: #28a745; font-weight: bold;}
    .device-offline {color: #6c757d; font-weight: bold;}
    .device-terminated {color: #dc3545; font-weight: bold;}
    .stButton>button {
        width: 100%;
        padding: 8px;
    }
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #f8f9fa;
        border-top: 1px solid #dee2e6;
        padding: 8px 0;
        text-align: center;
        font-size: 13px;
        color: #6c757d;
        z-index: 999;
    }
    .footer strong {
        color: #007bff;
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.title("🔗 Device Management Dashboard")
st.markdown("Monitor and control all connected AI devices")

# Check backend server
try:
    response = requests.get(f"{SERVER_URL}/health", timeout=2)
    server_running = response.status_code == 200
except:
    server_running = False

if not server_running:
    st.error("⚠️ Backend server is NOT running!")
    st.markdown("""
    **Start the backend server first:**
    ```bash
    python -m uvicorn backend.server:app --host 0.0.0.0 --port 5000
    ```
    """)
    st.stop()

st.success(f"✅ Backend server is running at {SERVER_URL}")

# Show access mode notification
if is_remote:
    st.info("📡 **Remote Access Mode** - Device controls are disabled in read-only mode")
else:
    st.success("⚙️ **Local Access Mode** - All controls enabled")

# Load master token
master_token_file = CONFIG_DIR / ".master_token"
if not master_token_file.exists():
    st.error("⚠️ Master token not found!")
    st.stop()

master_token = master_token_file.read_text().strip()

# Controls - Only show if not remote access
if not is_remote:
    col_refresh, col_terminate_all, col_spacer = st.columns([1, 2, 2])

    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    with col_terminate_all:
        if st.button("⚠️ TERMINATE ALL REMOTE DEVICES", type="secondary", use_container_width=True):
            try:
                response = requests.post(
                    f"{SERVER_URL}/api/devices/terminate-all",
                    json={"api_token": master_token},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    count = data.get("devices_terminated", 0)
                    st.success(f"✅ Terminated {count} remote devices!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Failed: {response.text}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
else:
    # Show info message in remote mode
    col_info = st.columns(1)[0]
    with col_info:
        st.info("🔒 Device management controls are disabled in remote access mode")
        if st.button("🔄 Refresh Devices", use_container_width=True):
            st.rerun()

st.markdown("---")

# Fetch devices
try:
    # Send master token in header with dash (HTTP standard)
    response = requests.get(
        f"{SERVER_URL}/api/devices/list",
        headers={"api-token": master_token},
        timeout=5
    )
    
    if response.status_code == 200:
        device_data = response.json()
        devices = device_data.get("devices", [])
        total_devices = device_data.get("total_devices", 0)
        online_count = device_data.get("online_count", 0)
        offline_count = device_data.get("offline_count", 0)
        
        # Statistics
        stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
        
        with stats_col1:
            st.metric("Total Devices", total_devices)
        with stats_col2:
            st.metric("🟢 Online", online_count)
        with stats_col3:
            st.metric("🔴 Offline", offline_count)
        with stats_col4:
            terminated_count = total_devices - online_count - offline_count
            st.metric("❌ Terminated", terminated_count)
        
        st.markdown("---")
        
        # Device list
        if devices:
            st.subheader(f"📱 Connected Devices ({len(devices)})")
            
            for device in devices:
                device_id = device.get("device_id", "N/A")
                device_name = device.get("device_name", "Unknown")
                os_type = device.get("os_type", "unknown")
                status = device.get("status", "offline")
                is_master = device.get("is_master", False)
                ip_address = device.get("ip_address", "N/A")
                last_connected = device.get("last_connected", "Never")
                
                # Format last connected time
                if last_connected and last_connected != "Never":
                    try:
                        last_connected_dt = datetime.fromisoformat(last_connected.replace('Z', '+00:00'))
                        time_diff = datetime.now() - last_connected_dt.replace(tzinfo=None)
                        
                        if time_diff.seconds < 60:
                            last_connected_str = "Just now"
                        elif time_diff.seconds < 3600:
                            last_connected_str = f"{time_diff.seconds // 60} min ago"
                        elif time_diff.days == 0:
                            last_connected_str = f"{time_diff.seconds // 3600} hours ago"
                        else:
                            last_connected_str = f"{time_diff.days} days ago"
                    except:
                        last_connected_str = "Unknown"
                else:
                    last_connected_str = "Never"
                
                # Device card
                with st.container():
                    col_icon, col_info, col_status, col_action = st.columns([1, 3, 2, 2])
                    
                    with col_icon:
                        # Icon based on OS and master status
                        if is_master:
                            st.markdown("### 👑")
                        elif os_type == "windows":
                            st.markdown("### 🖥️")
                        elif os_type == "macos":
                            st.markdown("### 💻")
                        elif os_type == "linux":
                            st.markdown("### 🐧")
                        else:
                            st.markdown("### 📱")
                    
                    with col_info:
                        device_label = f"{device_name}"
                        if is_master:
                            device_label += " **(Master)**"
                        st.markdown(f"**{device_label}**")
                        st.caption(f"ID: `{device_id[:25]}...`")
                        st.caption(f"IP: `{ip_address}` | OS: `{os_type.upper()}`")
                    
                    with col_status:
                        # Status indicator
                        if status == "online":
                            st.markdown('<p class="device-online">🟢 ONLINE</p>', unsafe_allow_html=True)
                        elif status == "offline":
                            st.markdown('<p class="device-offline">⚫ OFFLINE</p>', unsafe_allow_html=True)
                        elif status == "terminated":
                            st.markdown('<p class="device-terminated">❌ TERMINATED</p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p>❔ {status.upper()}</p>', unsafe_allow_html=True)
                        
                        st.caption(f"Last seen: {last_connected_str}")
                    
                    with col_action:
                        if not is_remote:
                            # Show control buttons only in local access mode
                            if not is_master and status != "terminated":
                                if st.button(f"🚫 Terminate", key=f"term_{device_id}", use_container_width=True):
                                    try:
                                        response = requests.post(
                                            f"{SERVER_URL}/api/devices/terminate/{device_id}",
                                            json={
                                                "device_id": device_id,
                                                "api_token": master_token
                                            },
                                            timeout=5
                                        )
                                        if response.status_code == 200:
                                            st.success(f"✅ Terminated {device_name}")
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Failed: {response.text}")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                            elif is_master:
                                st.info("👑 Master")
                            else:
                                st.warning("Terminated")
                        else:
                            # Remote access mode - show status only, no controls
                            if is_master:
                                st.info("👑 Master")
                            elif status == "terminated":
                                st.warning("Terminated")
                            else:
                                st.caption("📡 Read-only")
                    
                    st.markdown("---")
        
        else:
            st.info("ℹ️ No devices registered yet.")
    
    else:
        st.error(f"❌ Failed to fetch devices: {response.text}")

except Exception as e:
    st.error(f"❌ Error connecting to backend: {str(e)}")

# Footer
st.markdown("""
    <div class="footer">
        Designed and Created by <strong>Avii & Gaurav</strong>
    </div>
""", unsafe_allow_html=True)
