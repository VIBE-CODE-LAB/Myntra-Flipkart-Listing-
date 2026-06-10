"""
master_sheet_mapper.py

Maps attributes from the Master (brand) sheet.
Uses Seller SKU ID if available, and falls back to article numeric + color.
"""

import pandas as pd
from typing import Optional, Dict, Tuple


class MasterSheetMapperError(Exception):
    pass


class MasterSheetMapper:
    # Attributes to map from master sheet
    ATTRIBUTE_COLUMNS = [
        "Manufacturer Details",
        "Packer Details",
        "Importer Details",
        "Brand",
        "Ideal For",
        "Type",
        "Wire Support",
        "Fabric",
        "Pattern",
        "Seam Type",
        "Suitable For",
        "Coverage",
        "Straps",
        "Detachable Straps",
        "Padding",
        "Back Style",
        "Cup Type",
        "Occasion",
        "Detail Placement",
        "Model Name",
        "Fabric Care",
        "Closure",
        "Inner lining",
        "Other Bra Details",
        "Other Details",
        "Description",
        "Search Keywords",
        "Key Features",
        "Transparent Strap",
        "Pattern/Print Type",
        "Ornamentation Type",
        "Trend",
    ]

    KEY_COLUMNS = [
        "Seller SKU ID",
        "Seller Sku ID",
        "SKU ID",
        "SKU",
        "Style Code",
        "Style",
        "Styles",
        "Article",
        "Article Code",
    ]

    COLOR_COLUMNS = [
        "Color",
        "Colors",
        "Brand Color",
    ]

    STYLE_COLUMNS = [
        "Style",
        "Styles",
        "Style Code",
        "Article",
        "Article Code",
    ]

    def __init__(self, dataframe: pd.DataFrame):
        if dataframe is None or dataframe.empty:
            raise MasterSheetMapperError("Master Sheet dataframe is empty")

        self.df = dataframe
        self._column_map = {str(c).strip().lower(): c for c in self.df.columns}
        self.key_column = self._find_column(self.KEY_COLUMNS)
        self.color_column = self._find_column(self.COLOR_COLUMNS)
        self.style_column = self._find_column(self.STYLE_COLUMNS)

        self._cache_key: Dict[str, Dict[str, str]] = {}
        self._cache_article: Dict[str, Dict[str, str]] = {}
        self._cache_article_color: Dict[Tuple[str, str], Dict[str, str]] = {}

        self._build_cache()

    def _find_column(self, candidates: list[str]) -> Optional[str]:
        for name in candidates:
            key = str(name).strip().lower()
            if key in self._column_map:
                return self._column_map[key]
        return None

    @staticmethod
    def _normalize_text(value: str) -> str:
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

    @staticmethod
    def _extract_numeric_tail(value: str) -> str:
        s = str(value)
        digits = []
        current = []
        for ch in s:
            if ch.isdigit():
                current.append(ch)
            else:
                if current:
                    digits.append("".join(current))
                    current = []
        if current:
            digits.append("".join(current))
        return digits[-1] if digits else ""

    def _build_cache(self):
        for _, row in self.df.iterrows():
            key_value = str(row.get(self.key_column, "")).strip() if self.key_column else ""
            style_value = str(row.get(self.style_column, "")).strip() if self.style_column else ""
            color_value = str(row.get(self.color_column, "")).strip() if self.color_column else ""

            article_numeric = self._extract_numeric_tail(style_value) if style_value else ""
            color_key = self._normalize_text(color_value) if color_value else ""

            attributes = {}
            for col in self.ATTRIBUTE_COLUMNS:
                actual_col = self._column_map.get(str(col).strip().lower())
                value = row.get(actual_col, "") if actual_col else ""
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value).strip()
                attributes[col] = value

            if key_value and key_value.lower() != "nan":
                self._cache_key[key_value] = attributes

            if article_numeric:
                self._cache_article[article_numeric] = attributes

            if article_numeric and color_key:
                self._cache_article_color[(article_numeric, color_key)] = attributes

    def has_key(self, key_value: str) -> bool:
        return str(key_value).strip() in self._cache_key

    def get_attribute_by_key(self, key_value: str, attribute_name: str, default: str = "") -> str:
        attrs = self._cache_key.get(str(key_value).strip(), {})
        return attrs.get(attribute_name, default)

    def get_attribute_by_article_color(
        self, article_numeric: str, color_value: str, attribute_name: str, default: str = ""
    ) -> str:
        key = (str(article_numeric).strip(), self._normalize_text(color_value))
        attrs = self._cache_article_color.get(key, {})
        return attrs.get(attribute_name, default)

    def get_attribute_by_article(self, article_numeric: str, attribute_name: str, default: str = "") -> str:
        attrs = self._cache_article.get(str(article_numeric).strip(), {})
        return attrs.get(attribute_name, default)
