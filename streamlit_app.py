import sys
from pathlib import Path

# Add project root to Python search path
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

# Path to the actual Streamlit app
app_path = ROOT_DIR / "frontend" / "app_streamlit.py"

# Read and execute the actual streamlit app in the current context
with open(app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(app_path), "exec")
    exec(code, globals())
