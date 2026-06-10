"""Streamlit Web Application - Belle Listing AI
Combined Myntra + Flipkart listing generator with intelligent device control
"""

import streamlit as st  # type: ignore[reportMissingImports]
import subprocess
import os
import yaml
from pathlib import Path
from datetime import datetime
import pandas as pd
import sys
import requests
import time
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import device client
try:
    from ai_layer.device_client import DeviceClient
    DEVICE_CLIENT_AVAILABLE = True
except ImportError:
    DEVICE_CLIENT_AVAILABLE = False
    DeviceClient = None

# Import multi-workbook reader for article autocomplete + validation
try:
    from engine.multi_workbook_reader import BrandConfigManager, MultiWorkbookReader
    READER_AVAILABLE = True
except ImportError:
    READER_AVAILABLE = False

# Get project root (parent of frontend directory)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(PROJECT_ROOT / ".env")
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONFIG_PATH = str(CONFIG_DIR / "multi_workbook_config.yaml")

# Ensure working directory is project root so engine imports resolve correctly
os.chdir(str(PROJECT_ROOT))


# ── Article autocomplete helpers ────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_tracker_numbers(brand_key: str, config_path: str):
    """Load numeric article IDs from the tracker sheet for a brand. Cached 5 min.

    The tracker stores values like "TWEENS CT 38" — the last whitespace-separated
    token is the article number (e.g. "38"). That number is what the generator
    matches against, so we list only those numbers as hints.
    """
    try:
        config_mgr = BrandConfigManager(config_path=config_path)
        brand_config = config_mgr.get_brand_config(brand_key)
        workbook_id = config_mgr.get_workbook_id(brand_config["sku_source"]["workbook"])
        sheet_name = brand_config["sku_source"]["sheet_name"]
        article_col = brand_config["sku_source"]["article_id_column"]
        reader = MultiWorkbookReader(config_mgr)
        df = reader.read_sheet(workbook_id, sheet_name)
        numbers = []
        for val in df[article_col].dropna():
            parts = str(val).strip().split()
            if parts and parts[-1].isdigit():
                numbers.append(int(parts[-1]))
        return sorted(set(numbers))
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def validate_article_exists(brand_key: str, article_code: str, config_path: str):
    """Return (found: bool, detail: str) for an article in the tracker."""
    try:
        config_mgr = BrandConfigManager(config_path=config_path)
        reader = MultiWorkbookReader(config_mgr)
        sku_df = reader.read_sku_data(brand_key, article_code)
        if not sku_df.empty:
            return True, f"{len(sku_df)} color(s) found in tracker"
        return False, "Article not found in tracker"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ── Page config ──────────────────────────────────────────────────────────────

# Page config
st.set_page_config(
    page_title="Belle Listing AI",
    page_icon="🎀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS styling
st.markdown("""
    <style>
    .main { padding: 2rem; }
    .stButton>button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    .platform-myntra {
        background: linear-gradient(90deg, #ff3f6c, #ff6b98);
        color: white;
        padding: 6px 18px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
    }
    .platform-flipkart {
        background: linear-gradient(90deg, #2874f0, #4d94ff);
        color: white;
        padding: 6px 18px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
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
    </style>
""", unsafe_allow_html=True)

# Title
st.title("🎀 Belle Listing AI")
st.markdown("Generate **Myntra** and **Flipkart** ready listings with intelligent device control")

# Create tabs for different sections
tab1, tab2 = st.tabs(["📋 Generator", "🔗 Device Management"])

# ==================== TAB 1: GENERATOR ====================
with tab1:

    # ── PLATFORM SELECTOR ──────────────────────────────────────────────────
    st.subheader("🛍️ Select Platform")
    platform = st.radio(
        label="Platform",
        options=["MYNTRA", "FLIPKART"],
        horizontal=True,
        label_visibility="collapsed",
        help="Choose the platform you want to generate listings for",
        key="platform_selector"
    )

    if platform == "MYNTRA":
        st.markdown('<span class="platform-myntra">● MYNTRA</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="platform-flipkart">● FLIPKART</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── CONFIGURATION ──────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 Configuration")

        # ── Brand + Model (FIRST — needed to derive brand_key for autocomplete) ──
        col_b, col_m = st.columns(2)

        with col_b:
            brand = st.selectbox(
                "Brand",
                ["INVISI-SOFT", "KOMLI", "SOUMINIE", "TWEENS", "DRESSBERRY", "JOOMIE", "INVISI-FIT", "INTIMIST"],
                help="Select the brand"
            )

        with col_m:
            model = st.selectbox(
                "Model",
                ["MAGDHA", "LATIKA", "JAWA", "MAHI", "TINA", "DEBORA", "AI", "INFO",
                 "SOFIA", "UKRAINE", "CATALINA", "SASA", "THAILIA", "NAIM", "LETICIA", "DIARA"],
                help="Select the model"
            )

        # Derive brand key for Google Sheets lookup
        brand_key_raw = brand.lower().replace("-", "")
        brand_key = f"fk_{brand_key_raw}" if platform == "FLIPKART" else brand_key_raw

        # Will be populated in the article input block below
        tracker_articles = []

        # ── Pack Mode + Article Code ──────────────────────────────────────────
        col_a, col_p = st.columns(2)

        with col_a:
            pack_mode = st.selectbox(
                "Pack Mode",
                ["1PC", "2PC", "MULTI", "PRINTED"],
                help="Select the package type. PRINTED generates for article range."
            )

        with col_p:
            if pack_mode == "PRINTED":
                st.markdown("**Article Range**")
                col_from, col_to = st.columns(2)
                with col_from:
                    article_from = st.text_input(
                        "From Article",
                        value="KB-51751",
                        placeholder="e.g., KB-51751",
                        help="Starting article code",
                        key="article_from"
                    )
                with col_to:
                    article_to = st.text_input(
                        "To Article",
                        value="KB-51755",
                        placeholder="e.g., KB-51755",
                        help="Ending article code",
                        key="article_to"
                    )

                # Pack type selector for PRINTED mode
                col_pack1, col_pack2 = st.columns([1, 2])
                with col_pack1:
                    st.markdown("**Pack Type**")
                with col_pack2:
                    printed_pack_type = st.radio(
                        label="Pack Type",
                        options=["1PC", "2PC"],
                        horizontal=True,
                        label_visibility="collapsed",
                        help="Choose between 1PC or 2PC for PRINTED pack generation",
                        key="printed_pack_type_selector"
                    )

                article_code = f"{article_from} to {article_to}"

            else:
                printed_pack_type = None

                # ── Article code — always manual entry ───────────────────────
                article_code = st.text_input(
                    "Article Code",
                    value="",
                    placeholder="e.g., TW-CT-38, IS-SS-38, IS-1012",
                    help="Type the full article code. The trailing number (e.g. 38) is used to find it in the tracker.",
                )

                # ── Load numeric hints from tracker (non-blocking, cached) ───
                if READER_AVAILABLE:
                    tracker_articles = load_tracker_numbers(brand_key, CONFIG_PATH)
                else:
                    tracker_articles = []

                if tracker_articles:
                    hint_nums = ", ".join(str(n) for n in tracker_articles[:30])
                    suffix = f"  (+{len(tracker_articles)-30} more)" if len(tracker_articles) > 30 else ""
                    st.caption(f"💡 Numbers in tracker: **{hint_nums}**{suffix}")

                # ── Validate button ───────────────────────────────────────────
                if article_code and article_code.strip():
                    vcol_btn, vcol_result = st.columns([1, 2])
                    with vcol_btn:
                        do_validate = st.button("🔍 Validate", key="validate_btn", help="Check if this article exists in the tracker")

                    if do_validate:
                        with st.spinner("Checking tracker..."):
                            found, detail = validate_article_exists(brand_key, article_code.strip(), CONFIG_PATH)
                        st.session_state["last_validation"] = (found, detail)
                        st.session_state["last_validated_article"] = article_code

                    with vcol_result:
                        cached_article = st.session_state.get("last_validated_article")
                        if cached_article == article_code and "last_validation" in st.session_state:
                            found, detail = st.session_state["last_validation"]
                            if found:
                                st.success(f"✅ {detail}")
                            else:
                                st.error(f"❌ {detail}")

    with col2:
        st.subheader("📊 Info")

        if pack_mode == "PRINTED":
            display_pack = f"{pack_mode} ({printed_pack_type})"
        else:
            display_pack = pack_mode

        platform_badge = "🔴 MYNTRA" if platform == "MYNTRA" else "🔵 FLIPKART"

        st.markdown(f"""
        **Selected Options:**
        - 🛍️ Platform: `{platform_badge}`
        - 📦 Article: `{article_code}`
        - 🎁 Pack: `{display_pack}`
        - 🏷️ Brand: `{brand}`
        - 🎯 Model: `{model}`
        """)

        if READER_AVAILABLE and pack_mode != "PRINTED":
            if tracker_articles:
                st.caption(f"📋 {len(tracker_articles)} numeric IDs loaded from tracker")
            else:
                st.caption("⚠️ Could not load tracker numbers")

    st.markdown("---")

    # ── GENERATE ───────────────────────────────────────────────────────────
    st.subheader("🚀 Generate")

    if st.button("Generate Files", key="generate", help="Click to start generation"):

        progress_placeholder = st.empty()
        status_placeholder = st.empty()

        try:
            progress_placeholder.info("⏳ Preparing configuration...")

            config_data = {
                'platform': platform,
                'article': article_code,
                'pack': "PRINTED" if pack_mode == "PRINTED" else pack_mode,
                'brand': brand,
                'model': model
            }

            if pack_mode == "PRINTED":
                config_data['printed_pack_type'] = printed_pack_type

            config_file = CONFIG_DIR / "run_config.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)

            progress_placeholder.info("🔄 Starting generator...")

            # ── Live streaming via Popen ────────────────────────────────────
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            # Each platform has its own dedicated script with clean, separate logic
            script = (
                "scripts/run_generator_flipkart.py"
                if platform == "FLIPKART"
                else "scripts/run_generator_myntra.py"
            )

            process = subprocess.Popen(
                [sys.executable, "-u", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=env,
            )

            all_lines = []

            with st.spinner("⏳ Generating... please wait"):
                for raw_line in process.stdout:
                    all_lines.append(raw_line.rstrip("\n"))
                process.wait()

            returncode = process.returncode
            full_output = "\n".join(all_lines)
            progress_placeholder.empty()

            # ── Success ─────────────────────────────────────────────────────
            if returncode == 0:
                status_placeholder.success("✅ Generation completed successfully!")

                # Missing attribute warnings
                warn_lines = [l for l in all_lines if "[WARN EMPTY_COL]" in l]
                if warn_lines:
                    st.markdown("**⚠️ Missing Attributes detected:**")
                    for w in warn_lines:
                        # Extract column name between single quotes
                        col_name = w.split("'")[1] if "'" in w else w.strip()
                        st.warning(f"Column **{col_name}** has no data — check the attribute sheet for this article")

                st.markdown("---")
                st.subheader("📥 Download Generated Files")

                brand_key_dl = brand.lower().replace("-", "")
                all_brands = ["tweens", "komli", "invisisoft", "dressberry", "joomie", "souminie", "invisifit", "intimist"]

                if platform == "FLIPKART":
                    search_dir = OUTPUT_DIR / "flipkart" / brand_key_dl if brand_key_dl in all_brands else OUTPUT_DIR
                    file_prefix = "Flipkart_Sku_Ready"
                else:
                    search_dir = OUTPUT_DIR / brand_key_dl if brand_key_dl in all_brands else OUTPUT_DIR
                    file_prefix = "Myntra_Sku_Ready"

                files = []
                if search_dir.exists():
                    files = list(search_dir.glob(f"{file_prefix}_{article_code}_{pack_mode}_*.xlsx"))
                    if not files:
                        files = list(search_dir.glob(f"{file_prefix}_{article_code}_*.xlsx"))
                    files = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)

                if files:
                    st.markdown(f"**Found {len(files)} file(s):**")
                    for file in files:
                        file_size = file.stat().st_size / (1024 * 1024)
                        file_time = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                        col_name, col_size, col_time, col_btns = st.columns([2, 1, 2, 2])
                        with col_name:
                            st.markdown(f"📊 **{file.name}**")
                        with col_size:
                            st.markdown(f"`{file_size:.2f} MB`")
                        with col_time:
                            st.markdown(f"`{file_time}`")
                        with col_btns:
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                with open(file, 'rb') as f:
                                    st.download_button(
                                        label="⬇️",
                                        data=f.read(),
                                        file_name=file.name,
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"download_{file.name}"
                                    )
                            with btn_col2:
                                if st.button("🗑️", key=f"delete_gen_{file.name}", help=f"Delete {file.name}"):
                                    try:
                                        file.unlink()
                                        st.success(f"✅ Deleted {file.name}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Could not delete: {str(e)}")
                        st.markdown("")
                else:
                    st.warning("⚠️ No files found. Check the log below for details.")
                    with st.expander("📋 Generator Log"):
                        st.text(full_output[-3000:])

                st.markdown("---")
                st.subheader("📈 Generation Summary")
                summary_cols = st.columns(5)
                with summary_cols[0]:
                    st.metric("Platform", platform)
                with summary_cols[1]:
                    st.metric("Article", article_code)
                with summary_cols[2]:
                    st.metric("Pack Mode", pack_mode)
                with summary_cols[3]:
                    st.metric("Files Generated", len(files))
                with summary_cols[4]:
                    st.metric("Status", "✅ Success")

            # ── Failure ─────────────────────────────────────────────────────
            else:
                status_placeholder.error("❌ Generation Failed")
                with st.expander("📋 Error Details", expanded=True):
                    st.text(full_output[-3000:])

        except Exception as e:
            progress_placeholder.empty()
            status_placeholder.empty()
            st.error(f"❌ An error occurred: {str(e)}")

    st.markdown("---")

    # ── RECENT OUTPUTS ─────────────────────────────────────────────────────
    st.subheader("📂 Recent Outputs")

    col_refresh, col_space = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Refresh Files", key="refresh_files"):
            st.rerun()

    if OUTPUT_DIR.exists():
        all_files = list(OUTPUT_DIR.rglob("*.xlsx"))
        all_files = [f for f in all_files if ".cache" not in str(f)]
        all_files = sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]

        if all_files:
            st.markdown("**Last 10 generated files:**")

            for f in all_files:
                file_time = datetime.fromtimestamp(f.stat().st_mtime)
                file_size = f.stat().st_size / 1024

                # Show platform badge based on filename
                if "Flipkart" in f.name:
                    badge = "🔵"
                elif "Myntra" in f.name:
                    badge = "🔴"
                else:
                    badge = "📄"

                col_name, col_size, col_time, col_download, col_delete = st.columns([2, 1, 2, 1, 1])

                with col_name:
                    st.markdown(f"{badge} {f.name}")
                with col_size:
                    st.markdown(f"`{file_size:.2f} KB`")
                with col_time:
                    st.markdown(f"`{file_time.strftime('%Y-%m-%d %H:%M')}`")
                with col_download:
                    try:
                        with open(str(f), 'rb') as file:
                            st.download_button(
                                "⬇️",
                                data=file.read(),
                                file_name=f.name,
                                key=f"quick_dl_{f.name}"
                            )
                    except (PermissionError, FileNotFoundError):
                        st.caption("📦 Locked")
                with col_delete:
                    if st.button("🗑️", key=f"delete_{f.name}", help=f"Delete {f.name}"):
                        try:
                            f.unlink()
                            st.success(f"✅ Deleted {f.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Could not delete {f.name}: {str(e)}")
        else:
            st.info("ℹ️ No generated files yet. Click 'Generate Files' to create your first output!")
    else:
        st.warning("⚠️ Output directory not found. Please run the generator first.")


# ==================== TAB 2: DEVICE MANAGEMENT ====================
with tab2:
    st.subheader("🔗 Device Monitoring & Control")

    SERVER_URL = "http://localhost:5001"

    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=2)
        server_running = response.status_code == 200
    except:
        server_running = False

    if not server_running:
        st.error(f"⚠️ Backend server is NOT running at {SERVER_URL}")
        st.info("Start the server: `.venv/Scripts/python.exe -m uvicorn backend.server:app --port 5001`")
    else:
        st.success(f"✅ Backend server is connected")

        master_token_file = CONFIG_DIR / ".master_token"
        if not master_token_file.exists():
            st.error("⚠️ Master token not found!")
        else:
            master_token = master_token_file.read_text().strip()

            col_refresh, col_terminate_all, col_spacer = st.columns([1, 2, 2])

            with col_refresh:
                if st.button("🔄 Refresh List", use_container_width=True):
                    st.rerun()

            with col_terminate_all:
                if st.button("⚠️ TERMINATE ALL REMOTES", type="secondary", use_container_width=True):
                    try:
                        response = requests.post(
                            f"{SERVER_URL}/api/devices/terminate-all",
                            json={"api_token": master_token},
                            timeout=5
                        )
                        if response.status_code == 200:
                            st.success("✅ Termination signal sent to all!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Failed: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

            st.markdown("---")

            try:
                response = requests.get(
                    f"{SERVER_URL}/api/devices/list",
                    headers={"api-token": master_token},
                    timeout=5
                )

                if response.status_code == 200:
                    device_data = response.json()
                    devices = device_data.get("devices", [])

                    if not devices:
                        st.info("No devices registered yet.")
                    else:
                        for dev in devices:
                            dev_id = dev['device_id']
                            status = dev['status']
                            name = dev['device_name']
                            is_master = dev.get('is_master', False)

                            with st.expander(f"{'⭐' if is_master else '📱'} {name} ({status})", expanded=not dev.get('is_terminated')):
                                col_info, col_action = st.columns([3, 1])

                                with col_info:
                                    st.write(f"**ID:** `{dev_id}`")
                                    st.write(f"**OS:** {dev.get('os_type', 'unknown')}")
                                    st.write(f"**Last Seen:** {dev.get('last_connected', 'never')}")

                                with col_action:
                                    if not is_master and status != "terminated":
                                        if st.button(f"Terminate", key=f"term_{dev_id}"):
                                            try:
                                                requests.post(
                                                    f"{SERVER_URL}/api/devices/terminate/{dev_id}",
                                                    json={"api_token": master_token},
                                                    timeout=5
                                                )
                                                st.success("Terminated!")
                                                time.sleep(0.5)
                                                st.rerun()
                                            except:
                                                st.error("Failed")
                else:
                    st.error(f"Failed to fetch devices: {response.text}")
            except Exception as e:
                st.error(f"Could not connect to backend: {str(e)}")

# Footer
st.markdown("""
    <div class="footer">
        Designed and Created by <strong>Avii & Gaurav</strong>
    </div>
""", unsafe_allow_html=True)
