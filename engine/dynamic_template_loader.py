#!/usr/bin/env python3
"""
Dynamic Template Loader
Automatically detects and loads the latest Myntra template from the input directory.
Handles column position changes gracefully by mapping columns by header names.
"""

import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import Dict, List, Tuple, Optional


class DynamicTemplateLoader:
    """
    Loads the latest Myntra template dynamically and handles column position changes.
    
    Key features:
    - Automatically finds the latest Myntra template in input directory
    - Maps columns by header name, not position
    - Handles missing columns gracefully
    - Caches template metadata for efficiency
    """
    
    def __init__(self, input_dir: str = "data/input"):
        self.input_dir = Path(input_dir)
        self.current_template_path = None
        self.current_template_headers = None
        self.template_metadata = {}
    
    def find_latest_myntra_template(self) -> Optional[Path]:
        """
        Find the latest Myntra template file in the input directory.

        Pattern: Myntra*Template*.xlsx or Myntra-Sku-Template*.xlsx

        Returns:
            Path to the latest template file, or None if not found
        """
        if not self.input_dir.exists():
            print(f"⚠️  Input directory not found: {self.input_dir}")
            return None

        # Search for Myntra template files
        template_files = []

        # Pattern 1: Myntra*Template*.xlsx
        template_files.extend(self.input_dir.glob("Myntra*Template*.xlsx"))
        # Pattern 2: Myntra-Sku*.xlsx
        template_files.extend(self.input_dir.glob("Myntra-Sku*.xlsx"))

        # Remove duplicates
        template_files = list(set(template_files))

        if not template_files:
            print(f"⚠️  No Myntra template found in {self.input_dir}")
            return None

        return max(template_files, key=lambda f: (f.stat().st_mtime, f.name))

    def find_latest_flipkart_template(self) -> Optional[Path]:
        """
        Find the latest Flipkart template file in the input directory.

        Pattern: Flipkart*Template*.xlsx or Flipkart-Sku*.xlsx or Flipkart*.xlsx

        Returns:
            Path to the latest template file, or None if not found
        """
        if not self.input_dir.exists():
            print(f"⚠️  Input directory not found: {self.input_dir}")
            return None

        template_files = []
        template_files.extend(self.input_dir.glob("Flipkart*Template*.xlsx"))
        template_files.extend(self.input_dir.glob("Flipkart-Sku*.xlsx"))
        template_files.extend(self.input_dir.glob("Flipkart*.xlsx"))

        # Remove duplicates
        template_files = list(set(template_files))

        if not template_files:
            print(f"⚠️  No Flipkart template found in {self.input_dir}")
            return None

        return max(template_files, key=lambda f: (f.stat().st_mtime, f.name))
    
    def get_template_sheet_name(self, template_path: Path) -> Optional[str]:
        """
        Detect the correct sheet name in the template.
        
        Tries common names: 'Bra', 'Template', 'Data', first sheet, etc.
        """
        try:
            xls = pd.ExcelFile(template_path)
            sheet_names = xls.sheet_names
            
            # Priority order for sheet names
            priority_sheets = ['Bra', 'Template', 'Data', 'Sheet1']
            
            for sheet_name in priority_sheets:
                if sheet_name in sheet_names:
                    return sheet_name
            
            # If none found, return the first sheet
            if sheet_names:
                return sheet_names[0]
            
            return None
        except Exception as e:
            print(f"❌ Error reading template sheets: {e}")
            return None
    
    def load_template(self, template_path: Optional[Path] = None, 
                     sheet_name: Optional[str] = None) -> Tuple[Optional[pd.DataFrame], Optional[Path]]:
        """
        Load the latest Myntra template dynamically.
        
        Args:
            template_path: Optional override for template path
            sheet_name: Optional override for sheet name
        
        Returns:
            Tuple of (template_df, template_path) or (None, None) if loading fails
        """
        # Find latest template if not provided
        if template_path is None:
            template_path = self.find_latest_myntra_template()
        
        if template_path is None:
            print("❌ Could not find any Myntra template")
            return None, None
        
        # Detect sheet name if not provided
        if sheet_name is None:
            sheet_name = self.get_template_sheet_name(template_path)
        
        if sheet_name is None:
            print(f"❌ Could not detect sheet name in {template_path.name}")
            return None, None
        
        try:
            # Read template
            template_df = pd.read_excel(template_path, sheet_name=sheet_name)
            
            # Store metadata
            self.current_template_path = template_path
            self.current_template_headers = list(template_df.columns)
            self.template_metadata = {
                'path': str(template_path),
                'sheet_name': sheet_name,
                'column_count': len(self.current_template_headers),
                'row_count': len(template_df),
                'headers': self.current_template_headers,
                'loaded_at': datetime.now().isoformat(),
                'file_size_mb': template_path.stat().st_size / (1024 * 1024),
            }
            
            print(f"✅ Loaded template: {template_path.name}")
            print(f"   Sheet: {sheet_name}")
            print(f"   Columns: {len(self.current_template_headers)}")
            print(f"   Rows: {len(template_df)}")
            print(f"   Headers: {', '.join(self.current_template_headers[:5])}{'...' if len(self.current_template_headers) > 5 else ''}")
            
            return template_df, template_path
        
        except Exception as e:
            print(f"❌ Error loading template: {e}")
            return None, None
    
    def get_column_position(self, header_name: str) -> Optional[int]:
        """
        Get the column position (1-indexed) for a header name.
        
        Args:
            header_name: Name of the column header
        
        Returns:
            Column number (1-indexed) or None if header not found
        """
        if self.current_template_headers is None:
            return None
        
        for idx, header in enumerate(self.current_template_headers, 1):
            if str(header).strip().lower() == str(header_name).strip().lower():
                return idx
        
        return None
    
    def get_column_by_name(self, df: pd.DataFrame, column_name: str) -> Optional[int]:
        """
        Get column index (0-indexed, for pandas) by name, case-insensitive.
        
        Args:
            df: DataFrame to search
            column_name: Name to search for
        
        Returns:
            0-indexed column number or None if not found
        """
        for idx, col in enumerate(df.columns):
            if str(col).strip().lower() == str(column_name).strip().lower():
                return idx
        
        return None
    
    def map_required_columns(self, required_columns: List[str]) -> Dict[str, Optional[int]]:
        """
        Map required column names to their current positions.
        
        Args:
            required_columns: List of column names to locate
        
        Returns:
            Dictionary mapping column name to position (0-indexed) or None
        """
        column_mapping = {}
        
        for col_name in required_columns:
            pos = self.get_column_position(col_name)
            if pos is not None:
                column_mapping[col_name] = pos - 1  # Convert to 0-indexed for pandas
            else:
                column_mapping[col_name] = None
                print(f"⚠️  Column '{col_name}' not found in current template")
        
        return column_mapping
    
    def validate_template(self, required_columns: Optional[List[str]] = None) -> bool:
        """
        Validate that the template has all required columns.
        
        Args:
            required_columns: List of required column names (case-insensitive)
        
        Returns:
            True if all required columns exist, False otherwise
        """
        if self.current_template_headers is None:
            return False
        
        if required_columns is None:
            # Default required columns for Myntra template
            required_columns = [
                'vendorSkuCode', 'Color', 'styleGroupId',
                'MRP', 'SP', 'A', 'B', 'C', 'D', 'E', 'F'
            ]
        
        missing_columns = []
        
        for req_col in required_columns:
            if self.get_column_position(req_col) is None:
                missing_columns.append(req_col)
        
        if missing_columns:
            print(f"\n⚠️  Missing columns in template:")
            for col in missing_columns:
                print(f"   - {col}")
            return False
        
        print(f"\n✅ Template validation passed")
        print(f"   All {len(required_columns)} required columns found")
        return True
    
    def get_metadata(self) -> Dict:
        """Get metadata about the currently loaded template."""
        return self.template_metadata.copy()
    
    def get_headers(self) -> Optional[List[str]]:
        """Get the list of column headers from the current template."""
        return self.current_template_headers.copy() if self.current_template_headers else None
    
    def get_template_info(self) -> str:
        """Get a formatted string with template information."""
        if not self.template_metadata:
            return "No template loaded"
        
        meta = self.template_metadata
        info = f"""
Template Information:
  File: {Path(meta['path']).name}
  Sheet: {meta['sheet_name']}
  Size: {meta['file_size_mb']:.2f} MB
  Columns: {meta['column_count']}
  Rows: {meta['row_count']}
  Loaded: {meta['loaded_at']}
  
Headers:
  {', '.join(meta['headers'])}
"""
        return info


# Convenient singleton instance
_template_loader_instance = None

def get_dynamic_template_loader(input_dir: str = "data/input") -> DynamicTemplateLoader:
    """Get or create the global template loader instance."""
    global _template_loader_instance
    if _template_loader_instance is None:
        _template_loader_instance = DynamicTemplateLoader(input_dir)
    return _template_loader_instance


if __name__ == "__main__":
    # Demo usage
    loader = DynamicTemplateLoader("data/input")
    
    # Load latest template
    template_df, template_path = loader.load_template()
    
    if template_df is not None:
        print(loader.get_template_info())
        
        # Validate template
        loader.validate_template()
        
        # Map required columns
        required = ['vendorSkuCode', 'Color', 'MRP']
        mapping = loader.map_required_columns(required)
        print(f"\nColumn Mapping:")
        for col, pos in mapping.items():
            print(f"  {col}: Column {pos if pos is not None else 'NOT FOUND'}")
