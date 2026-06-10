"""
column_mapper.py

Responsible for:
- Mapping generated variant rows to Flipkart template columns
- Preserving exact column order from Flipkart template
- Ensuring forbidden columns remain blank
- Enriching rows with Help Sheet attribute mappings

This module:
- Does NOT generate values
- Does NOT validate business rules
- ONLY maps data safely
"""

import pandas as pd
import os
import yaml
from engine.rule_engine import RuleEngine, RuleEngineError
from engine.help_sheet_mapper import HelpSheetMapper, HelpSheetMapperError
try:
    from scripts import image_analysis
    _HAS_IMAGE_ANALYSIS = True
except Exception:
    _HAS_IMAGE_ANALYSIS = False


class ColumnMapperError(Exception):
    """Raised when column mapping fails."""
    pass


class ColumnMapper:
    def __init__(self, rule_engine: RuleEngine, template_df: pd.DataFrame, help_sheet_mapper: HelpSheetMapper = None,
                 enable_image_fallback: bool = False, color_master_path: str = os.path.join('config', 'color_master.yaml')):
        """
        :param rule_engine: Initialized RuleEngine
        :param template_df: Flipkart Bra template DataFrame (header only)
        :param help_sheet_mapper: Optional HelpSheetMapper for attribute enrichment
        """
        self.rule_engine = rule_engine
        self.template_columns = list(template_df.columns)
        self.help_sheet_mapper = help_sheet_mapper

        # Image fallback control and color tokens
        self.enable_image_fallback = enable_image_fallback and _HAS_IMAGE_ANALYSIS
        try:
            with open(color_master_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            colors = list(data.get('COLORS', {}).keys())
            colors.sort(key=lambda s: -len(s))
            # Load COLOR_MAP for Flipkart standard color names
            self.color_map = data.get('COLOR_MAP', {})
        except Exception:
            colors = []
            self.color_map = {}
        self._color_tokens = colors

        if not self.template_columns:
            raise ColumnMapperError("Flipkart template has no columns")

    def map_rows(self, variant_rows: list[dict]) -> pd.DataFrame:
        """
        Maps variant rows to Flipkart template structure.

        :param variant_rows: Output of VariantGenerator
        :return: DataFrame aligned to Flipkart template
        """

        mapped_rows = []
        
        for row in variant_rows:
              # 🔥 FLATTEN VARIANT ROW BEFORE MAPPING (CRITICAL)
            flat_row = {}
            for k, v in row.items():
                if isinstance(v, dict):
                    flat_row[k] = v.get("value", "")
                else:
                    flat_row[k] = v
            mapped = self._map_single_row(flat_row)
            mapped_rows.append(mapped)

        return pd.DataFrame(mapped_rows, columns=self.template_columns)

    # ---------------- INTERNAL ---------------- #

    def _map_single_row(self, row: dict) -> dict:
        """
        Maps one variant row dict to full Flipkart template columns.
        Handles header whitespace / hidden character issues.
        Enriches with Help Sheet attribute mappings if available.
        """
        mapped = {}

        # Normalize row keys once
        # Normalize row keys and FLATTEN all dict values
        normalized_row = {}

        for k, v in row.items():
            key = k.strip()

            if isinstance(v, dict):
                normalized_row[key] = v.get("value", "")
            else:
                normalized_row[key] = v

        raw_pack = normalized_row.get("Pack of", "")

        if isinstance(raw_pack, dict):
            pack = str(raw_pack.get("value", "")).strip()
        else:
            pack = str(raw_pack).strip()

        # Check if original pack type was MULTI (stored in internal helper field)
        original_pack = normalized_row.get("_original_pack", "")
        is_multi = str(original_pack).strip().upper() == "MULTI"

        brand_color = normalized_row.get("Brand Color", "")
        
        # Get article code for Help Sheet lookup
        # IMPORTANT: Help Sheet data is shared across all brands, indexed by numeric article part only
        # E.g., article "1012" or "45" (no brand prefix) - same data for all brands
        article_numeric = normalized_row.get("article_numeric", "")
        
        # Use ONLY the numeric article code for Help Sheet lookup (not prefixed with "IS-")
        # Since Help Sheet is now keyed by numeric article only (e.g., "1012", "45")
        if article_numeric:
            article_code = article_numeric  # Use numeric directly: "1012", "45", etc.
        else:
            article_code = ""

        # Prepare image mapping helpers and map per-view URLs to this SKU's color
        def _norm(s: str) -> str:
            if not s or s is None:
                return ""
            # Handle float/NaN values
            if isinstance(s, float):
                import math
                if math.isnan(s):
                    return ""
                return str(s)
            if not isinstance(s, str):
                s = str(s)
            s = s.upper()
            for ch in ('-', '_', '%20', '.', '/', '?'):
                s = s.replace(ch, ' ')
            return ' '.join(s.split())

        def _match_color_in_url(url: str):
            if not url:
                return None
            txt = _norm(url)
            for t in self._color_tokens:
                if t and t in txt:
                    return t
            return None

        def _detect_color_by_image(url: str):
            if not self.enable_image_fallback:
                return None
            try:
                return image_analysis.image_url_to_color(url)
            except Exception:
                return None

        VIEW_COLS = [
            "Main Image URL",
            "Other Image URL 1",
            "Other Image URL 2",
            "Other Image URL 3",
            "Other Image URL 4",
        ]

        sku_color = normalized_row.get('Color', '')
        image_mapped = {}
        for vcol in VIEW_COLS:
            url = normalized_row.get(vcol, '')
            chosen = None
            matched = _match_color_in_url(url)
            if matched and _norm(matched) == _norm(sku_color):
                chosen = url
            else:
                detected = _detect_color_by_image(url)
                if detected and _norm(detected) == _norm(sku_color):
                    chosen = url
            if not chosen and url:
                chosen = url
            image_mapped[vcol] = chosen or ""

        for col in self.template_columns:
            col_clean = col.strip()

        # Forbidden columns must always be blank
            if self.rule_engine.is_forbidden_column(col_clean):
                mapped[col] = ""
                continue

            # ----- SPECIAL COLUMN HANDLING -----
            # Size should include cup letter (e.g., "32A" not just "32")
            if col_clean == "Size":
                mapped[col] = normalized_row.get("Size", "")
                continue

            # Size - Measuring Unit should always be "Regular"
            if col_clean == "Size - Measuring Unit":
                mapped[col] = "Regular"
                continue

            # Pack of should be numeric (1, 2, or MULTI)
            if col_clean == "Pack of":
                mapped[col] = normalized_row.get("Pack of", "")
                continue

            # Style Code should be the derived value from SKU ID
            if col_clean == "Style Code":
                mapped[col] = normalized_row.get("Style Code", "")
                continue

            # ----- MULTI LOGIC FOR COLOR COLUMNS -----
            if col_clean == "Color":
                if is_multi:
                    mapped[col] = "Multicolor"
                else:
                    # Get the Brand Color and map it to Flipkart standard Color
                    brand_color_val = normalized_row.get("Brand Color", "")
                    # Look up the Flipkart color name from COLOR_MAP
                    flipkart_color = self.color_map.get(brand_color_val, brand_color_val)
                    mapped[col] = flipkart_color
                continue

            if col_clean == "Brand Color":
                mapped[col] = brand_color
                continue

            # ----- SELLING PRICE MAPPING -----
            if col_clean == "Your selling price (INR)":
                # Map from variant row - variant_generator outputs it with this key
                mapped[col] = normalized_row.get("Your selling price (INR)", "")
                continue
            
            # ----- HELP SHEET ATTRIBUTE MAPPING -----
            # Map columns from Help Sheet if mapper is available and value not already in row
            help_sheet_columns = [
                # Original 8 columns
                "Ideal For", "Type", "Wire Support", "Fabric", 
                "Pattern", "Seam Type", "Suitable For", "Coverage",
                # Additional columns
                "Straps", "Detachable Straps", "Padding", "Cup Type",
                "Detail Placement", "Model Name", "Fabric Care",
                "Other Bra Details", "Other Details", "Description",
                "Search Keywords", "Key Features", "Transparent Strap",
                "Back Style", "Occasion", "Closure"
            ]
            
            if col_clean in help_sheet_columns:
                if col_clean in normalized_row and normalized_row[col_clean]:
                    # Use value from variant row if present
                    value = normalized_row[col_clean]
                    mapped[col] = value
                elif self.help_sheet_mapper and article_code:
                    # Otherwise try to get from Help Sheet
                    value = self.help_sheet_mapper.get_attribute(article_code, col_clean, "")
                    mapped[col] = value
                else:
                    mapped[col] = ""
                continue
            # ----------------------------------------

            # ----- IMAGE VIEW COLUMNS (hierarchy) -----
            if col_clean in ("Main Image URL", "Other Image URL 1", "Other Image URL 2", "Other Image URL 3", "Other Image URL 4"):
                mapped[col] = image_mapped.get(col_clean, "")
                continue

            if col_clean in normalized_row:
                mapped[col] = normalized_row[col_clean]
            else:
                mapped[col] = ""

        return mapped