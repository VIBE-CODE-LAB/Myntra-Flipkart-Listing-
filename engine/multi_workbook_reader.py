"""  
Multi-Workbook Reader
Reads and merges data from 4 Google Drive workbooks (Myntra Tracker + 3 Belle workbooks)
Supports brand-specific data fetching and attribute merging
"""

import pandas as pd
import yaml
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Tuple, Optional, List
from engine.google_sheets_reader import GoogleSheetsReader

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class BrandConfigManager:
    """Manages brand configurations and workbook mappings"""
    
    def __init__(self, config_path: str = "config/multi_workbook_config.yaml"):
        """
        Initialize brand config manager
        
        Args:
            config_path: Path to multi_workbook_config.yaml
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.workbooks = self.config.get("workbooks", {})
        self.brands = self.config.get("brands", {})
        self.column_mappings = self.config.get("column_mappings", {})
        self.join_logic = self.config.get("join_logic", {})
        
    def _load_config(self) -> Dict:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded config: {self.config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config: {e}")
            raise
    
    def get_brand_config(self, brand: str) -> Dict:
        """Get configuration for specific brand"""
        if brand not in self.brands:
            raise ValueError(f"Brand not found in config: {brand}. Available: {list(self.brands.keys())}")
        return self.brands[brand]
    
    def get_workbook_id(self, workbook_name: str) -> str:
        """Get workbook ID from the environment or config."""
        if workbook_name not in self.workbooks:
            raise ValueError(f"Workbook not found: {workbook_name}")
        env_name = f"WORKBOOK_{workbook_name.upper()}_ID"
        workbook_id = os.getenv(env_name, "").strip() or self.workbooks[workbook_name].get("id", "")
        if not workbook_id:
            raise ValueError(f"Workbook ID is not configured. Set {env_name}.")
        return workbook_id
    
    def validate_config(self) -> bool:
        """Validate all required configuration is present"""
        errors = []
        
        # Check workbooks
        required_workbooks = ["myntra_tracker", "belle_komli", "belle_invisisoft", "belle_tweens", "belle_joomie", "belle_souminie", "belle_dressberry"]
        for wb in required_workbooks:
            if wb not in self.workbooks:
                errors.append(f"Missing workbook: {wb}")
            elif not self.workbooks[wb].get("id"):
                errors.append(f"Missing ID for workbook: {wb}")
        
        # Check all brands configured
        all_brand_names = list(self.brands.keys())
        for brand_name in all_brand_names:
            if brand_name not in self.brands:
                errors.append(f"Missing brand config: {brand_name}")
                continue
            
            brand = self.brands[brand_name]
            
            # Check SKU source
            if not brand.get("sku_source"):
                errors.append(f"Missing SKU source for brand: {brand_name}")
            elif not brand["sku_source"].get("article_id_column"):
                errors.append(f"Missing article_id_column for brand: {brand_name}")
            
            # Check attribute source
            if not brand.get("attribute_source"):
                errors.append(f"Missing attribute source for brand: {brand_name}")
        
        if errors:
            for error in errors:
                logger.error(f"Config validation error: {error}")
            return False
        
        logger.info("Config validation passed")
        return True


class MultiWorkbookReader:
    """Reads and merges data from multiple Google Drive workbooks"""
    
    def __init__(self, config_manager: Optional[BrandConfigManager] = None):
        """
        Initialize multi-workbook reader
        
        Args:
            config_manager: BrandConfigManager instance (creates default if not provided)
        """
        self.config_manager = config_manager or BrandConfigManager()
        self.sheets_reader = GoogleSheetsReader()
        self.cached_sheets = {}  # Cache for sheets: {(workbook_id, sheet_name): df}
    
    def list_sheets(self, workbook_id: str) -> List[str]:
        """List all sheet names in a workbook"""
        try:
            info = self.sheets_reader.get_spreadsheet_info(workbook_id)
            return info.get("sheets", [])
        except Exception as e:
            logger.error(f"Error listing sheets in workbook {workbook_id}: {e}")
            return []
    
    def read_sheet(self, workbook_id: str, sheet_name: str, force_refresh: bool = False) -> pd.DataFrame:
        """Read a specific sheet from a workbook with caching"""
        cache_key = (workbook_id, sheet_name)
        
        if not force_refresh and cache_key in self.cached_sheets:
            logger.debug(f"Using cached sheet: {sheet_name}")
            return self.cached_sheets[cache_key]
        
        try:
            df = self.sheets_reader.read_sheet(workbook_id, sheet_name)
            self.cached_sheets[cache_key] = df
            return df
        except Exception as e:
            logger.error(f"Error reading sheet {sheet_name} from workbook {workbook_id}: {e}")
            raise
        
    def extract_article_number(self, article_id: str, prefix: str) -> str:
        """
        Extract number from article ID
        
        Examples:
            "SB-993" with prefix "TW" -> "993" (ignores prefix, extracts from dash)
            "TW-CT-19901" with prefix "TW" -> "19901" (gets the last part after dash)
            "IS-1013" with prefix "IS" -> "1013"
            "KM-200" with prefix "KM" -> "200"
        
        Args:
            article_id: Full article ID (e.g., "SB-993", "TW-CT-19901")
            prefix: Brand prefix (e.g., "SB", "TW", "IS", "KM") - used for matching, not extraction
        
        Returns:
            Article number as string (e.g., "993", "19901", "1013")
        """
        # Split by dash and get the last part (the number)
        parts = article_id.split("-")
        if parts:
            # Return the last part as the number
            return parts[-1]
        return article_id
    
    def extract_sku_prefix_from_myntra(self, myntra_cell_value: str, brand_prefix: str) -> str:
        """
        Extract SKU prefix from Myntra cell value and convert to brand format
        
        Examples:
            "TWEENS CT 95005" with prefix "TW" -> "TW-CT"
            "TWEENS IS 9352" with prefix "TW" -> "TW-IS"
            "INVISI-SOFT 38" with prefix "IS" -> "IS" (no sub-prefix)
            "KOMLI ON-SB 38" with prefix "KM" -> "KM-ON-SB"
        
        Args:
            myntra_cell_value: Value from Myntra column (e.g., "TWEENS CT 95005")
            brand_prefix: Brand prefix (e.g., "TW", "IS", "KM")
        
        Returns:
            Formatted SKU prefix (e.g., "TW-CT", "IS")
        """
        # Split by spaces: "TWEENS CT 95005" → ["TWEENS", "CT", "95005"]
        parts = myntra_cell_value.strip().split()
        
        if len(parts) <= 1:
            # Just brand name, no sub-components
            return brand_prefix
        
        # Last part is the number, everything before is the prefix/text
        number = parts[-1]
        prefix_parts = parts[:-1]
        
        if len(prefix_parts) == 1:
            # Just one word before number (e.g., "INVISI-SOFT")
            return brand_prefix
        
        # Multiple words before number: extract the components after brand
        # E.g., "TWEENS CT 95005" -> prefix_parts = ["TWEENS", "CT"]
        # We want to return "TW-CT" (brand_prefix + "-" + remaining parts)
        sub_prefix = "-".join(prefix_parts[1:])  # Skip first part (brand name)
        return f"{brand_prefix}-{sub_prefix}"
    
    def read_sku_data(self, brand: str, article_id: str) -> pd.DataFrame:
        """
        Read SKU data from Myntra Tracker sheet
        
        Matching logic:
        - Extract article number from article_id (e.g., "993" from "SB-993" or "TW-CT-19901")
        - Find ALL rows in Myntra brand column that contain this number
        - Store the full text from Myntra for SKU generation (e.g., "TWEENS CT 95005" -> "TW-CT")
        
        Args:
            brand: Brand name (komli, invisisoft, tweens)
            article_id: Article ID (e.g., "SB-993", "TW-CT-19901")
        
        Returns:
            DataFrame with SKU data, plus _sku_prefix column for generation
        """
        brand_config = self.config_manager.get_brand_config(brand)
        sku_source = brand_config["sku_source"]
        prefix = brand_config["prefix"]
        
        workbook_id = self.config_manager.get_workbook_id(sku_source["workbook"])
        sheet_name = sku_source["sheet_name"]
        article_id_col = sku_source["article_id_column"]
        
        logger.info(f"Reading SKU data for {brand}: {sheet_name}")
        
        # Read full sheet from Google Sheets (use cached read where possible)
        df = self.read_sheet(workbook_id, sheet_name, force_refresh=False)
        
        if df.empty:
            logger.warning(f"No data found in {sheet_name}")
            return pd.DataFrame()
        
        logger.info(f"SKU sheet loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Extract article number from article_id (e.g., "993" from "SB-993")
        article_number = self.extract_article_number(article_id, prefix)
        
        # Filter for specific article
        if article_id_col not in df.columns:
            logger.error(f"Column not found: {article_id_col}. Available: {list(df.columns)}")
            return pd.DataFrame()
        
        # Find matching articles where the column contains the article number
        # The brand column contains values like "INVISI-SOFT 38", "TWEENS CT 95005", etc.
        matching_rows = []
        sku_prefixes = {}  # Store the extracted SKU prefix for each matching row
        
        for idx, row in df.iterrows():
            cell_value = str(row[article_id_col]).strip()
            # Split by whitespace: "TWEENS CT 95005" → ["TWEENS", "CT", "95005"]
            parts = cell_value.split()
            if parts and parts[-1] == article_number:
                # Number matches! Extract SKU prefix from the full cell value
                sku_prefix = self.extract_sku_prefix_from_myntra(cell_value, prefix)
                matching_rows.append(idx)
                sku_prefixes[idx] = sku_prefix
        
        if not matching_rows:
            logger.warning(f"No matching articles found for {article_id} (number: {article_number}) in {sheet_name}")
            return pd.DataFrame()
        
        # Return matching rows and store SKU prefix for later use
        result_df = df.loc[matching_rows].copy()
        result_df['_sku_prefix'] = result_df.index.map(sku_prefixes)
        
        logger.info(f"Found {len(result_df)} matching articles")
        logger.debug(f"SKU prefixes: {sku_prefixes}")
        return result_df
    
    def read_attribute_data(self, brand: str, article_number: str) -> pd.DataFrame:
        """
        Read attribute data from Belle workbook
        
        Matching logic:
        - Search the first column of Belle sheet for the article number
        - The number is used for matching (e.g., search for "19901" or "993")
        - Article format in Belle may vary (IS-993, IS-38, SB 51751, TW-CT-19901, etc.)
        
        Args:
            brand: Brand name (komli, invisisoft, tweens)
            article_number: Article number to search (e.g., "38", "993", "CT-19901", "19901")
        
        Returns:
            DataFrame with attribute data
        """
        brand_config = self.config_manager.get_brand_config(brand)
        attr_source = brand_config["attribute_source"]
        
        workbook_id = self.config_manager.get_workbook_id(attr_source["workbook"])
        sheet_name = attr_source["sheet_name"]
        
        logger.info(f"Reading attribute data for {brand}: {sheet_name}")
        
        # Read full sheet from Google Sheets (use cached read where possible)
        df = self.read_sheet(workbook_id, sheet_name, force_refresh=False)
        
        if df.empty:
            logger.warning(f"No data found in {sheet_name}")
            return pd.DataFrame()
        
        logger.info(f"Attribute sheet loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Get the article ID column from config (e.g., "vendorSkuCode")
        article_id_col = attr_source.get("article_id_column", df.columns[0])
        
        if article_id_col not in df.columns:
            logger.error(f"Article ID column '{article_id_col}' not found. Available: {list(df.columns)}")
            return pd.DataFrame()
        
        # Search for article number in the configured column
        # Search for article number in the configured column
        # The number appears at the end of most article IDs
        # E.g., search for "993" in ["IS-993", "SB-993", "TW-CT-993", "SB 993"]
        matching_rows = []
        for idx, cell_value in df[article_id_col].items():
            cell_str = str(cell_value).strip()
            # Check if the article number appears in the cell (at the end, separated by space/dash)
            # Split by space and dash to get components
            components = cell_str.replace("-", " ").split()
            if components and components[-1] == article_number:
                matching_rows.append(idx)
        
        if not matching_rows:
            logger.warning(f"No attributes found for article number {article_number} in {sheet_name}")
            return pd.DataFrame()
        
        result_df = df.loc[matching_rows]
        logger.info(f"Found {len(result_df)} attribute records for article number {article_number}")
        return result_df
    
    def merge_data(self, sku_df: pd.DataFrame, attr_df: pd.DataFrame, brand: str) -> pd.DataFrame:
        """
        Merge SKU data with attribute data
        
        STRICT REQUIREMENT: Attributes MUST exist. If missing, returns empty DataFrame.
        
        Args:
            sku_df: SKU DataFrame from Myntra Tracker
            attr_df: Attribute DataFrame from Belle workbook
            brand: Brand name
        
        Returns:
            Merged DataFrame, or empty DataFrame if attributes missing
        """
        if sku_df.empty:
            logger.warning("SKU data is empty, cannot merge")
            return pd.DataFrame()
        
        if attr_df.empty:
            logger.warning(f"[ALERT] NO ATTRIBUTES FOUND - Generation SKIPPED")
            logger.warning(f"[ALERT] Article exists in Myntra Tracker but NOT in {brand} attributes workbook")
            logger.warning(f"[ALERT] Add article to Belle-{brand} workbook and retry")
            # Return empty to signal generation should be skipped
            return pd.DataFrame()
        
        # Get merge columns
        sku_cols = self.config_manager.column_mappings.get("sku_columns", [])
        attr_cols = self.config_manager.column_mappings.get("attribute_columns", [])
        
        # Extract only the columns we want from each dataframe
        sku_extract = []
        for col in sku_cols:
            if col in sku_df.columns:
                sku_extract.append(col)
        
        attr_extract = []
        for col in attr_cols:
            if col in attr_df.columns:
                attr_extract.append(col)
        
        # Create subsets
        sku_subset = sku_df[sku_extract].copy() if sku_extract else sku_df.copy()
        attr_subset = attr_df[attr_extract].copy() if attr_extract else attr_df.copy()
        
        # Preserve the _sku_prefix column if it exists (used for file generation)
        if "_sku_prefix" in sku_df.columns:
            sku_subset["_sku_prefix"] = sku_df["_sku_prefix"]
        
        # IMPORTANT: Keep ALL SKU rows (one per color) to generate variants for each color
        # Each row in sku_subset represents a different color variant
        # All rows are pre-filtered for the same article, just different colors
        # Reset indices to ensure proper alignment when concatenating
        sku_subset = sku_subset.reset_index(drop=True)
        
        # Merge: For each SKU row (color), add ALL attribute data alongside
        # Attribute data should be same for all colors of same article
        # Use ffill to replicate attribute data for all SKU rows
        merged_list = []
        for idx in range(len(sku_subset)):
            sku_row = sku_subset.iloc[[idx]].reset_index(drop=True)
            attr_row = attr_subset.iloc[:1].reset_index(drop=True)
            merged_row = pd.concat([sku_row, attr_row], axis=1)
            merged_list.append(merged_row)
        
        if merged_list:
            merged = pd.concat(merged_list, ignore_index=True)
        else:
            merged = pd.DataFrame()
        
        logger.info(f"Merged data: {len(merged)} rows ({len(sku_subset)} SKU colors * {len(attr_subset)} attribute rows), {len(merged.columns)} columns")
        if "_sku_prefix" in merged.columns:
            logger.debug(f"SKU Prefix in merged data: {merged['_sku_prefix'].iloc[0]}")
        return merged
    
    def get_merged_data(self, brand: str, article_id: str) -> Tuple[pd.DataFrame, Dict]:
        """
        Get complete merged data for an article
        
        Main entry point for getting article data
        
        STRICT MATCHING: Article must exist in BOTH workbooks or generation is skipped
        
        Args:
            brand: Brand name (komli, invisisoft, tweens)
            article_id: Article ID (e.g., "TW-38")
        
        Returns:
            Tuple of (merged_dataframe, metadata_dict)
            
        Metadata includes:
            - article_id: Full article ID
            - article_number: Number only
            - brand: Brand name
            - sku_rows: Number of matching SKU rows
            - attr_rows: Number of matching attribute rows
            - should_generate: True if should generate, False if should skip
            - warning: Alert message if any issues
        """
        brand_config = self.config_manager.get_brand_config(brand)
        prefix = brand_config["prefix"]
        
        # Extract article number
        article_number = self.extract_article_number(article_id, prefix)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching data for {brand.upper()}: {article_id}")
        logger.info(f"{'='*60}")
        
        # Read SKU data
        sku_df = self.read_sku_data(brand, article_id)
        
        # Read attribute data (using number only)
        attr_df = self.read_attribute_data(brand, article_number)
        
        # Merge
        merged_df = self.merge_data(sku_df, attr_df, brand)
        
        # Determine if generation should proceed
        should_generate = not merged_df.empty
        
        # Build metadata
        metadata = {
            "article_id": article_id,
            "article_number": article_number,
            "brand": brand,
            "sku_rows": len(sku_df),
            "attr_rows": len(attr_df),
            "merged_rows": len(merged_df),
            "should_generate": should_generate,
            "warning": None
        }
        
        if not should_generate:
            metadata["warning"] = (
                f"[SKIP] Article {article_id} not found in {brand_config['attribute_source']['sheet_name']}. "
                f"Add to Belle-{brand_config['display_name']} workbook and retry."
            )
            logger.warning(metadata["warning"])
        else:
            logger.info(f"\nMerge Summary:")
            logger.info(f"  SKU rows: {metadata['sku_rows']}")
            logger.info(f"  Attribute rows: {metadata['attr_rows']}")
            logger.info(f"  Merged rows: {metadata['merged_rows']}")
            logger.info(f"  Generation: PROCEED")
        
        return merged_df, metadata
    
    def get_output_folder(self, brand: str) -> str:
        """Get output folder for brand"""
        brand_config = self.config_manager.get_brand_config(brand)
        return brand_config.get("output_folder", f"data/output/{brand}/")

# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("MULTI-WORKBOOK READER TEST")
    print("="*60)
    
    # Initialize
    config_mgr = BrandConfigManager()
    
    # Validate config
    if not config_mgr.validate_config():
        print("Config validation failed!")
        exit(1)
    
    print("\n[OK] Config validation passed")
    print("\nBrands found:", list(config_mgr.brands.keys()))
    print("Workbooks configured:", list(config_mgr.workbooks.keys()))
    
    # Initialize reader
    reader = MultiWorkbookReader(config_mgr)
    print("\n[OK] MultiWorkbookReader initialized")
    
    print("\nSystem ready for multi-workbook data fetching!")
    print("Next: Update generator to use this reader")
