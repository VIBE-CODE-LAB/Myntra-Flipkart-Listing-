"""
flipkart_source_reader.py

Primary source reader for Flipkart-driven generation.

Responsibilities:
- Read INVISI-SOFT-LISTING.xlsx
- Load 'Flipkart' sheet
- Validate required columns
- Filter data for a single article (Style Code)
"""

import pandas as pd
from pathlib import Path


class FlipkartSourceReaderError(Exception):
    """Raised when Flipkart source reading fails."""
    pass


class FlipkartSourceReader:
    REQUIRED_COLUMNS = [
        "Style Code",
        "Brand",
        "Color",
        "Cup",
    ]

    def __init__(self, excel_path: str, sheet_name: str = "Flipkart"):
        self.excel_path = Path(excel_path)
        self.sheet_name = sheet_name

        if not self.excel_path.exists():
            raise FlipkartSourceReaderError(
                f"Flipkart source file not found: {self.excel_path}"
            )

    def read(self) -> pd.DataFrame:
        """
        Reads the Flipkart sheet and validates structure.
        """

        try:
            df = pd.read_excel(
                self.excel_path,
                sheet_name=self.sheet_name,
                dtype=str
            )
        except Exception as e:
            raise FlipkartSourceReaderError(
                f"Failed to read Flipkart sheet: {e}"
            )

        # Normalize column names (strip spaces)
        df.columns = [c.strip() for c in df.columns]

        self._validate_columns(df)

        # Drop fully empty rows
        df = df.dropna(how="all").reset_index(drop=True)

        return df

    def filter_article(self, df: pd.DataFrame, article_code: str) -> pd.DataFrame:
        """
        Filters Flipkart data for ONE article only.
        Enforces one-article-per-run rule.
        """

        article_code = str(article_code).strip()

        article_df = df[df["Style Code"].astype(str).str.strip() == article_code]

        if article_df.empty:
            raise FlipkartSourceReaderError(
                f"No rows found for article {article_code} in Flipkart sheet"
            )

        if article_df["Style Code"].nunique() != 1:
            raise FlipkartSourceReaderError(
                "More than one article detected after filtering. "
                "Only one article per run is allowed."
            )

        return article_df.reset_index(drop=True)

    def _validate_columns(self, df: pd.DataFrame):
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise FlipkartSourceReaderError(
                f"Missing required columns in Flipkart sheet: {missing}"
            )
