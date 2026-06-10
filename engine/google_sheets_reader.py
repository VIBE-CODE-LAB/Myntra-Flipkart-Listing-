"""
Google Sheets Reader for INVISI-SOFT-LISTINGS
Reads data directly from Google Sheets instead of local Excel files
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class GoogleSheetsReader:
    """
    Read INVISI-SOFT-LISTINGS workbook from Google Sheets
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google Sheets reader
        
        Args:
            credentials_path: Path to service account credentials JSON
        """
        configured_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "config/google_credentials.json",
        )
        self.credentials_path = Path(configured_path)
        self.client = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            # 1. Try authenticating via environment variable containing raw JSON content
            creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if creds_json:
                try:
                    info = json.loads(creds_json)
                    creds = Credentials.from_service_account_info(
                        info,
                        scopes=self.SCOPES
                    )
                    self.client = gspread.authorize(creds)
                    logger.info("[OK] Google Sheets authentication successful (via env JSON)")
                    return
                except Exception as env_err:
                    logger.warning(f"Failed to authenticate using GOOGLE_APPLICATION_CREDENTIALS_JSON env: {env_err}")

            # 2. Fall back to credentials file path
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Google credentials not found at {self.credentials_path}\n"
                    f"Either set the GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable, or place the credentials file at {self.credentials_path}"
                )
            
            creds = Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=self.SCOPES
            )
            self.client = gspread.authorize(creds)
            logger.info("[OK] Google Sheets authentication successful (via file)")
            
        except Exception as e:
            logger.error(f"[ERROR] Google Sheets authentication failed: {e}")
            raise
    
    def read_sheet(self, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
        """
        Read a specific sheet from Google Sheets
        
        Args:
            spreadsheet_id: The ID from the Google Sheets URL
            sheet_name: Name of the sheet/tab to read
            
        Returns:
            DataFrame with the sheet data
        """
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        # Retry with exponential backoff for transient quota/rate-limit errors
        max_attempts = 5
        backoff = 1
        for attempt in range(1, max_attempts + 1):
            try:
                data = worksheet.get_all_values()
                if not data:
                    logger.warning(f"Sheet '{sheet_name}' is empty")
                    return pd.DataFrame()

                df = pd.DataFrame(data[1:], columns=data[0])
                logger.info(f"[OK] Read {len(df)} rows from sheet '{sheet_name}'")
                return df

            except Exception as e:
                msg = str(e)
                if 'RATE_LIMIT' in msg or 'rateLimitExceeded' in msg or 'quota' in msg.lower() or 'RESOURCE_EXHAUSTED' in msg:
                    logger.warning(f"Rate/Quota error on attempt {attempt} reading '{sheet_name}': {e}")
                    if attempt == max_attempts:
                        logger.error(f"Exceeded retry attempts for sheet '{sheet_name}'")
                        raise
                    sleep_time = backoff
                    logger.info(f"Sleeping {sleep_time}s before retrying...")
                    time.sleep(sleep_time)
                    backoff *= 2
                    continue
                else:
                    logger.error(f"[ERROR] Error reading sheet '{sheet_name}': {e}")
                    raise
    
    def read_all_sheets(self, spreadsheet_id: str) -> Dict[str, pd.DataFrame]:
        """
        Read all sheets from a Google Sheets workbook
        
        Args:
            spreadsheet_id: The ID from the Google Sheets URL
            
        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            worksheets = spreadsheet.worksheets()
            
            sheets_data = {}
            for worksheet in worksheets:
                sheet_name = worksheet.title
                logger.info(f"[READING] Sheet: {sheet_name}")

                # Retry get_all_values for each worksheet to avoid failing entire workbook
                max_attempts = 5
                backoff = 1
                sheet_df = pd.DataFrame()
                for attempt in range(1, max_attempts + 1):
                    try:
                        data = worksheet.get_all_values()
                        if data:
                            sheet_df = pd.DataFrame(data[1:], columns=data[0])
                        else:
                            sheet_df = pd.DataFrame()
                        break
                    except Exception as e:
                        msg = str(e)
                        if 'RATE_LIMIT' in msg or 'rateLimitExceeded' in msg or 'quota' in msg.lower() or 'RESOURCE_EXHAUSTED' in msg:
                            logger.warning(f"Rate/Quota error on attempt {attempt} reading '{sheet_name}': {e}")
                            if attempt == max_attempts:
                                logger.error(f"Exceeded retry attempts for sheet '{sheet_name}'")
                                raise
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        else:
                            logger.error(f"[ERROR] Error reading sheet '{sheet_name}': {e}")
                            raise

                sheets_data[sheet_name] = sheet_df
            
            logger.info(f"[OK] Read {len(sheets_data)} sheets from Google Sheets")
            return sheets_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error reading spreadsheet: {e}")
            raise
    
    def get_spreadsheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Get metadata about a Google Sheets spreadsheet
        
        Args:
            spreadsheet_id: The ID from the Google Sheets URL
            
        Returns:
            Dictionary with spreadsheet metadata
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            info = {
                'title': spreadsheet.title,
                'id': spreadsheet.id,
                'url': spreadsheet.url,
                'sheet_count': len(spreadsheet.worksheets()),
                'sheets': [ws.title for ws in spreadsheet.worksheets()]
            }
            
            return info
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting spreadsheet info: {e}")
            raise


class MyntraGoogleSheetsReader:
    """
    Wrapper for reading Myntra listings from Google Sheets
    Compatible with existing excel_reader.py interface
    """
    
    def __init__(self, spreadsheet_id: str):
        """
        Initialize Myntra-specific Google Sheets reader
        
        Args:
            spreadsheet_id: Google Sheets ID for Myntra listings
        """
        self.spreadsheet_id = spreadsheet_id
        self.reader = GoogleSheetsReader()
        self.sheets_cache = {}
    
    def read_workbook(self) -> Dict[str, pd.DataFrame]:
        """
        Read entire Myntra listings workbook
        
        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        logger.info("[FETCH] Fetching Myntra listings from Google Sheets...")
        self.sheets_cache = self.reader.read_all_sheets(self.spreadsheet_id)
        return self.sheets_cache
    
    def get_sheet(self, sheet_name: str, force_refresh: bool = False) -> pd.DataFrame:
        """
        Get a specific sheet, with caching
        
        Args:
            sheet_name: Name of the sheet to retrieve
            force_refresh: If True, fetch fresh data from Google Sheets
            
        Returns:
            DataFrame for the requested sheet
        """
        if force_refresh or sheet_name not in self.sheets_cache:
            logger.info(f"[FETCH] Fetching sheet '{sheet_name}' from Google Sheets...")
            df = self.reader.read_sheet(self.spreadsheet_id, sheet_name)
            self.sheets_cache[sheet_name] = df
        
        return self.sheets_cache[sheet_name]
    
    def refresh_all(self):
        """Force refresh all sheets from Google Sheets"""
        logger.info("[REFRESH] Refreshing all sheets from Google Sheets...")
        self.sheets_cache = self.reader.read_all_sheets(self.spreadsheet_id)
        logger.info("[OK] All sheets refreshed")


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python google_sheets_reader.py <SPREADSHEET_ID>")
        print("\nTo get your Spreadsheet ID:")
        print("Open your Google Sheet and copy the ID from the URL:")
        print("https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit")
        sys.exit(1)
    
    spreadsheet_id = sys.argv[1]
    
    try:
        reader = MyntraGoogleSheetsReader(spreadsheet_id)
        
        # Get spreadsheet info
        info = reader.reader.get_spreadsheet_info(spreadsheet_id)
        print(f"\n[INFO] Spreadsheet: {info['title']}")
        print(f"[URL] {info['url']}")
        print(f"[SHEETS] {', '.join(info['sheets'])}")
        
        # Read all sheets
        sheets = reader.read_workbook()
        
        print(f"\n[OK] Successfully read {len(sheets)} sheets:")
        for name, df in sheets.items():
            print(f"  - {name}: {len(df)} rows × {len(df.columns)} columns")
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        sys.exit(1)
