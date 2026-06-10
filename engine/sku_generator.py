"""
sku_generator.py
Responsible for generating Seller SKU IDs
"""

import re
from engine.rule_engine import RuleEngineError


class SkuGeneratorError(Exception):
    pass


class SkuGenerator:
    def __init__(self, rule_engine, month: str, year: str):
        self.rule_engine = rule_engine
        self.month = month
        self.year = year

    def _build_model_code(self, model_name: str, brand_short: str = None) -> str:
        """
        Build model code for SKU.
        
        For AI model: Uses brand_short + "AI" + date
          - Special case: Tweens uses "TW" (not "TW-SB") + AI + date = TWAI0226
          - Examples: TWAI0226, KBAI0226, ISAI0226, DBAI0226, JAI0226, SAI0226
        
        For other models: Uses model_short + date (e.g., MD0226)
        
        Args:
            model_name: Model name (e.g., "MAGDHA", "AI")
            brand_short: Brand short code (required for AI model)
        
        Returns:
            Model code string
        """
        # Special handling for AI model
        if model_name.upper() == "AI":
            if not brand_short:
                raise ValueError("brand_short is required for AI model")
            
            # For AI model, use only the FIRST part of brand_short (before any dash)
            # Examples: TW-SB -> TW, J-ON -> J, KB -> KB, IS -> IS, DB -> DB, S -> S
            # Then add AI + date
            if "-" in brand_short:
                ai_brand_prefix = brand_short.split("-")[0]  # Take only first part
            else:
                ai_brand_prefix = brand_short
            
            return f"{ai_brand_prefix}AI{self.month}{self.year}"
        
        # Normal model handling
        model_short = self.rule_engine.get_model_short_id(model_name)
        return f"{model_short}{self.month}{self.year}"

    @staticmethod
    def parse_article_string(article_string: str) -> tuple:
        """
        Parse article string to extract brand_short and article_numeric.
        
        Examples:
        - "TW-SB-993" → ("TW-SB", "993")
        - "TW-CT-95005" → ("TW-CT", "95005")
        - "KB-45" → ("KB", "45")
        - "SB-993" → ("SB", "993")
        
        :param article_string: Article string with brand prefix and numeric part
        :return: Tuple of (brand_short, article_numeric)
        """
        article_str = str(article_string).strip()
        
        # Find all numeric sequences at the end of the string
        # Match pattern: everything up to and including the last dash-separated numeric part
        match = re.match(r'^(.*)-(\d+)$', article_str)
        
    @staticmethod
    def parse_article_string(article_string: str) -> tuple:
        """
        Parse article string to extract brand_short and article_numeric.
        Updated to return optional separator info if needed, but keeping return signature for compatibility.
        
        Examples:
        - "TW-SB-993" → ("TW-SB", "993")
        - "TW-CT-95005" → ("TW-CT", "95005")
        - "KB-45" → ("KB", "45")
        - "SB-993" → ("SB", "993")
        - "DB438" → ("DB", "438")
        
        :param article_string: Article string with brand prefix and numeric part
        :return: Tuple of (brand_short, article_numeric)
        """
        article_str = str(article_string).strip()
        
        # Method 1: Explicit dash separation at the end
        match = re.match(r'^(.*)-(\d+)$', article_str)
        if match:
            brand_short = match.group(1)  # Everything before the last dash-number
            article_numeric = match.group(2)  # The numeric part
            return brand_short, article_numeric
            
        # Method 2: No explicit dash separator (e.g. DB438)
        # Find the last continuous sequence of digits
        numeric_match = re.search(r'(\d+)$', article_str)
        if numeric_match:
            article_numeric = numeric_match.group(1)
            # Take everything before the number as brand short
            # Note: We do NOT strip trailing dashes here if they weren't used as separators
            # But usually if we are here, there is no dash separator
            brand_short = article_str[:numeric_match.start()]
            if brand_short.endswith('-'):
                brand_short = brand_short.rstrip('-')
                
            return brand_short, article_numeric
            
        raise SkuGeneratorError(f"Cannot extract numeric part from article: {article_str}")

    def _build_sku(
        self,
        brand_short: str,
        article_numeric: str,
        color_short: str,
        pack: str,
        size_cup: str,
        model_code: str,
        separator: str = "-"
    ) -> str:
        # Use '2PC' for MULTI in the SKU string (pack remains logical MULTI elsewhere)
        pack_str = "2PC" if str(pack).upper() == "MULTI" else pack
        
        # Build SKU with brand prefix and numeric article part 
        # Use custom separator if provided (for DB438 case)
        return f"{brand_short}{separator}{article_numeric}-{color_short}-{pack_str}-{size_cup}_{model_code}"

    def generate_from_components(
        self,
        brand_name: str,
        article_code: str,
        article_numeric: str,
        color_name: str,
        pack: str,
        size_cup: str,
        model_name: str,
        brand_short: str = None
    ) -> dict:
        """
        Generate ONE SKU record
        :param article_code: Full article code with brand prefix (e.g., "TW-SB-993")
        :param article_numeric: Numeric part only (e.g., "993")
        :param brand_short: Brand short prefix (e.g., "TW-SB"). If provided, uses this; otherwise looks up from brand_name
        """

        # Use provided brand_short, or look it up from brand_name for backward compatibility
        if brand_short is None:
            brand_short = self.rule_engine.get_brand_short_id(brand_name)
        
        # Determine separator from article_code
        # If input was DB438, we want separator="" -> DB438
        # If input was DB-438, we want separator="-" -> DB-438
        separator = "-"
        if article_code and article_numeric:
            # Check if format is brand+numeric directly (no hyphen)
            simple_concat = f"{brand_short}{article_numeric}"
            if article_code == simple_concat:
                separator = ""
            # Also check if user typed strict DB438 but brand_short was resolved differently
            # Simple check: does article_code end with "-{numeric}"?
            elif not article_code.endswith(f"-{article_numeric}"):
                # If it doesn't end with -NUMERIC, assume no separator
                # This covers DB438 where article_numeric is 438
                separator = ""
        
        if "-" in color_name:
            parts = color_name.split("-")
            color_short = "-".join(
                [self.rule_engine.get_color_short_id(part) for part in parts]
            )
        else:
            color_short = self.rule_engine.get_color_short_id(color_name)

        # Build model code, passing brand_short for AI model support
        model_code = self._build_model_code(model_name, brand_short=brand_short)

        seller_sku = self._build_sku(
            brand_short=brand_short,
            article_numeric=article_numeric,
            color_short=color_short,
            pack=pack,
            size_cup=size_cup,
            model_code=model_code,
            separator=separator
        )

        return {
            "seller_sku_id": seller_sku,
            "brand": brand_name,
            "article": article_code,
            "article_numeric": article_numeric,
            "color": color_name,
            "size_cup": size_cup,
            "pack": pack,
            "model_code": model_code,
        }