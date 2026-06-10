"""
Enhanced Help Sheet Loader with Auto-Detection
Automatically finds the correct Flipkart Help Sheet in Google Sheets
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.google_sheets_reader import FlipkartGoogleSheetsReader, GoogleSheetsReader

logger = logging.getLogger(__name__)


class HelpSheetDetector:
    """Auto-detect the correct Flipkart Help Sheet from Google Sheets"""
    
    # Possible sheet name variations to try
    SHEET_NAME_VARIATIONS = [
        "Flipkart Help Sheet",
        "flipkart help sheet",
        "FLIPKART HELP SHEET",
        "Help Sheet",
        "help sheet",
        "HELP SHEET",
        "Flipkart",
        "flipkart",
        "FLIPKART",
        "Articles",
        "articles",
        "ARTICLES",
        "352",
        "401",
        "Help",
        "help",
        "HELP",
    ]
    
    # Key columns that identify a Help Sheet
    IDENTIFYING_COLUMNS = [
        "Row Labels",  # Most distinctive - article codes
        "Ideal For",
        "Type",
        "Wire Support",
        "Fabric",
        "Seam Type",
        "Suitable For",
        "Coverage",
    ]
    
    def __init__(self, spreadsheet_id: str):
        """Initialize detector with Google Sheets reader"""
        self.spreadsheet_id = spreadsheet_id
        self.reader = GoogleSheetsReader()
    
    def detect_help_sheet(self) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
        """
        Auto-detect the correct Help Sheet in the spreadsheet
        
        Returns:
            Tuple of (sheet_name, dataframe) or (None, None) if not found
        """
        print("[DETECTING] Searching for Flipkart Help Sheet in Google Sheets...")
        print()
        
        try:
            # Get all sheets in spreadsheet
            info = self.reader.get_spreadsheet_info(self.spreadsheet_id)
            available_sheets = info['sheets']
            
            print(f"[INFO] Found {len(available_sheets)} sheets in spreadsheet:")
            for i, sheet in enumerate(available_sheets, 1):
                print(f"  {i}. {sheet}")
            print()
            
            # Try each variation
            print("[SEARCHING] Trying sheet name variations...")
            print()
            
            for variation in self.SHEET_NAME_VARIATIONS:
                for actual_sheet_name in available_sheets:
                    if variation.lower() == actual_sheet_name.lower():
                        print(f"[MATCH FOUND] '{actual_sheet_name}'")
                        print()
                        
                        # Read and validate
                        try:
                            df = self.reader.read_sheet(self.spreadsheet_id, actual_sheet_name)
                            
                            if self._is_valid_help_sheet(df):
                                print(f"[VALIDATION] [OK] Sheet '{actual_sheet_name}' is valid Help Sheet")
                                print(f"[DIMENSIONS] {len(df)} rows x {len(df.columns)} columns")
                                print()
                                return actual_sheet_name, df
                            else:
                                print(f"[VALIDATION] [WARN] Sheet '{actual_sheet_name}' has mismatched columns")
                                print()
                        except Exception as e:
                            print(f"[ERROR] Failed to read sheet '{actual_sheet_name}': {e}")
                            print()
            
            # No exact match found - try content-based detection
            print("[CONTENT-BASED] Trying to find Help Sheet by content...")
            print()
            
            for sheet_name in available_sheets:
                try:
                    df = self.reader.read_sheet(self.spreadsheet_id, sheet_name)
                    if self._is_valid_help_sheet(df):
                        print(f"[FOUND] [OK] Sheet '{sheet_name}' appears to be the Help Sheet!")
                        print(f"[DIMENSIONS] {len(df)} rows x {len(df.columns)} columns")
                        print()
                        return sheet_name, df
                except Exception as e:
                    continue
            
            print("[ERROR] Could not find Flipkart Help Sheet in this spreadsheet!")
            print()
            print("Available sheets that might contain help data:")
            for sheet in available_sheets:
                print(f"  - {sheet}")
            print()
            return None, None
            
        except Exception as e:
            print(f"[ERROR] Exception during detection: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def _is_valid_help_sheet(self, df: pd.DataFrame) -> bool:
        """
        Validate if dataframe appears to be a Help Sheet
        
        Criteria:
        - Has 'Row Labels' column (article codes)
        - Has most of the identifying columns
        - Has reasonable number of rows (at least 5 articles)
        """
        if df.empty:
            return False
        
        if len(df) < 5:
            return False
        
        columns_lower = [col.lower() for col in df.columns]
        
        # Must have Row Labels
        if 'row labels' not in columns_lower:
            return False
        
        # Should have at least 3 of the identifying columns
        matching_columns = sum(
            1 for col in self.IDENTIFYING_COLUMNS 
            if col.lower() in columns_lower
        )
        
        if matching_columns < 3:
            return False
        
        return True


def load_help_sheet_auto_detect(spreadsheet_id: str) -> Optional[pd.DataFrame]:
    """
    Convenience function to auto-load Help Sheet with detection
    
    Args:
        spreadsheet_id: Google Sheets ID
        
    Returns:
        DataFrame of Help Sheet or None if not found
    """
    detector = HelpSheetDetector(spreadsheet_id)
    sheet_name, df = detector.detect_help_sheet()
    
    if sheet_name:
        print(f"[OK] SUCCESS: Using sheet '{sheet_name}' as Flipkart Help Sheet")
        return df
    else:
        print("[ERROR] FAILED: Could not auto-detect Flipkart Help Sheet")
        return None


if __name__ == "__main__":
    # Test auto-detection
    import yaml
    
    config_path = Path("config/google_drive_config.yaml")
    if not config_path.exists():
        print("[ERROR] Config file not found!")
        sys.exit(1)
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    if not config.get('spreadsheet_id'):
        print("[ERROR] Spreadsheet ID not configured!")
        sys.exit(1)
    
    print("=" * 80)
    print("FLIPKART HELP SHEET AUTO-DETECTION")
    print("=" * 80)
    print()
    
    df = load_help_sheet_auto_detect(config['spreadsheet_id'])
    
    if df is not None:
        print("\nFirst few rows:")
        print(df.head())
    else:
        print("\n[ERROR] Failed to load Help Sheet")
        sys.exit(1)
