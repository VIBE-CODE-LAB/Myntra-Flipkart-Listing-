"""
help_sheet_mapper.py

Responsible for:
- Loading mapping data from "Flipkart Help Sheet"
- Providing lookup functions for attribute columns
- Caching data for performance

Attribute columns to map:
- Ideal For
- Type
- Wire Support
- Fabric
- Pattern
- Seam Type
- Suitable For
- Coverage
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional


class HelpSheetMapperError(Exception):
    """Raised when Help Sheet mapping fails."""
    pass


class HelpSheetMapper:
    """Maps article codes to Flipkart attribute values from Help Sheet."""

    # Columns to extract from the Help Sheet
    ATTRIBUTE_COLUMNS = [
        "Row Labels",  # Article code (key)
        # Original 8 columns
        "Ideal For",
        "Type",
        "Wire Support",
        "Fabric",
        "Pattern",
        "Seam Type",
        "Suitable For",
        "Coverage",
        # Additional columns
        "Straps",
        "Detachable Straps",
        "Padding",
        "Cup Type",
        "Detail Placement",
        "Model Name",
        "Fabric Care",
        "Other Bra Details",
        "Other Details",
        "Description",
        "Search Keywords",
        "Key Features",
        "Transparent Strap",
        "Back Style",
        "Occasion",
        "Closure"
    ]

    def __init__(self, help_sheet_path: str = None, sheet_name: str = "Flipkart Help Sheet", dataframe: pd.DataFrame = None):
        """
        Initialize mapper by loading data from Help Sheet.

        :param help_sheet_path: Path to Excel file containing Help Sheet (optional if dataframe provided)
        :param sheet_name: Name of the Help Sheet
        :param dataframe: Pre-loaded DataFrame (for Google Sheets integration)
        """
        if dataframe is not None:
            # Use provided DataFrame (Google Sheets)
            self.df = dataframe
        elif help_sheet_path:
            # Load from Excel file (traditional)
            path = Path(help_sheet_path)

            if not path.exists():
                raise HelpSheetMapperError(f"File not found: {path}")

            try:
                self.df = pd.read_excel(help_sheet_path, sheet_name=sheet_name)
            except Exception as e:
                raise HelpSheetMapperError(f"Failed to read '{sheet_name}': {e}")
        else:
            raise HelpSheetMapperError("Either help_sheet_path or dataframe must be provided")

        # Build lookup dict: article_code -> {attribute: value}
        self._cache = {}
        self._build_cache()
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame):
        """
        Create HelpSheetMapper from a DataFrame (for Google Sheets).
        
        :param df: DataFrame containing Help Sheet data
        :return: HelpSheetMapper instance
        """
        return cls(dataframe=df)

    def _build_cache(self):
        """Build in-memory cache for fast lookups."""
        for _, row in self.df.iterrows():
            article_code = str(row.get("Row Labels", "")).strip()
            if not article_code or article_code.lower() == "nan":
                continue

            attributes = {}
            for col in self.ATTRIBUTE_COLUMNS:
                if col == "Row Labels":
                    continue
                value = row.get(col, "")
                # Convert NaN to empty string
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value).strip()
                attributes[col] = value

            self._cache[article_code] = attributes

    def get_attributes(self, article_code: str) -> Dict[str, str]:
        """
        Get all mapped attributes for an article code.

        :param article_code: Article code (e.g., "IS-45")
        :return: Dict of {attribute_name: value}
        """
        code = str(article_code).strip()
        return self._cache.get(code, {})

    def get_attribute(
        self,
        article_code: str,
        attribute_name: str,
        default: str = ""
    ) -> str:
        """
        Get single attribute value for an article code.

        :param article_code: Article code
        :param attribute_name: Attribute column name
        :param default: Default value if not found
        :return: Attribute value or default
        """
        attributes = self.get_attributes(article_code)
        return attributes.get(attribute_name, default)

    def has_article(self, article_code: str) -> bool:
        """Check if article code exists in Help Sheet."""
        return str(article_code).strip() in self._cache

    def get_all_articles(self) -> list:
        """Get list of all article codes in Help Sheet."""
        return list(self._cache.keys())
