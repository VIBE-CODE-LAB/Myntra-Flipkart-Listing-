"""
variant_generator.py

Responsible for:
- Converting SKU records into Flipkart-ready variant rows
- Filling all allowed columns using RuleEngine
- NEVER writing forbidden columns

This module:
- Does NOT write Excel
- Does NOT guess values
"""
from engine.rule_engine import RuleEngine, RuleEngineError
import yaml
from pathlib import Path


class VariantGeneratorError(Exception):
    """Raised when variant generation fails."""
    pass


class VariantGenerator:
    
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.size_measurements = self._load_size_measurements()

    def _load_size_measurements(self) -> dict:
        """Load size to underbust/overbust measurements mapping from YAML config."""
        try:
            config_path = Path("config/size_measurements.yaml")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    return config.get("size_measurements", {})
            return {}
        except Exception as e:
            print(f"[WARN] Could not load size measurements: {e}")
            return {}
    
    def get_size_measurements(self, size_cup: str) -> dict:
        """
        Get underbust and overbust measurements for a size.
        
        Args:
            size_cup: Size like "30B", "32C", etc.
            
        Returns:
            Dict with 'underbust' and 'overbust' keys, or empty dict if not found
        """
        if not size_cup or size_cup not in self.size_measurements:
            return {}
        
        measurements = self.size_measurements.get(size_cup, {})
        return {
            "underbust": measurements.get("underbust", ""),
            "overbust": measurements.get("overbust", "")
        }

    def _scalar(self, value):
        """
        Convert RuleEngine outputs to Excel-safe scalar values.
        """
        if isinstance(value, dict):
            return value.get("value", "")
        return value

    def generate_from_row(self, sku_record: dict, is_myntra: bool = False) -> dict:
        article = sku_record["article"]
        pack = sku_record["pack"]
        color = sku_record["color"]
        size_cup = sku_record["size_cup"]
        seller_sku_id = sku_record["seller_sku_id"]

        dimensions = self.rule_engine.get_dimensions(pack)

        # Extract size and cup from size_cup (e.g., "30B" -> size=30, cup=B)
        size_str = size_cup[:-1]
        cup_str = size_cup[-1]

        # Style Code should be article-color-pack part of SKU ID
        # From seller_sku_id like "TW-SB-993-BLK-1PC-30B_MD0226" -> extract "TW-SB-993-BLK-1PC"
        sku_parts = seller_sku_id.split("_")[0]  # Remove model code part
        
        # Try to extract size from SKU ID for better accuracy
        # SKU format: BRAND-ARTICLE-COLOR-PACK-SIZE_MODEL
        # e.g., "TW-SB-993-SK-1PC-30B_MD0226"
        # e.g., "DB438-BLK-1PC-32A_DBAI0226" (Length 4 parts before model)
        sku_size_part = None
        if "_" in seller_sku_id:
            before_model = seller_sku_id.split("_")[0]  # "TW-SB-993-SK-1PC-30B" or "DB438-BLK-1PC-32A"
            # Get the last hyphen-separated part which should be the size
            parts = before_model.split("-")
            # If parts >= 4, we assume the last part is the size (e.g. SIZE)
            # Standard: BRAND-NUM-COLOR-PACK-SIZE (5 parts)
            # Compact: BRANDNUM-COLOR-PACK-SIZE (4 parts)
            if len(parts) >= 4:
                sku_size_part = parts[-1]  # e.g., "30B" or "32A"
        
        if sku_size_part:
             # Try to split by "-SIZE" first
             separator = "-" + sku_size_part
             if separator in sku_parts:
                 style_code = sku_parts.rsplit(separator, 1)[0]
             else:
                 # Fallback if separator not found (e.g. no dash before size? unlikely given logic above)
                 style_code = sku_parts.replace(sku_size_part, "").rstrip("-")
        elif size_cup and ("-" + size_cup) in sku_parts:
             style_code = sku_parts.rsplit("-" + size_cup, 1)[0]
        else:
             style_code = article

        # Pack of should be: 1 for 1PC, 2 for 2PC, 2 for MULTI (standard)
        if str(pack).upper() == "MULTI":
            pack_value = "2"
        else:
            pack_value = str(pack).rstrip("PC")  # "1PC" -> "1", "2PC" -> "2"

        # The size_cup is now already in inches (e.g., "30B" not "75B")
        # Use size_display which has pre-converted inch sizes with cup letter
        size_display = size_cup  # Already in inches format from SKU generation
        
        # Map color using COLOR_MAP from color_master.yaml
        # SKIN -> Beige, BLACK -> Black, etc.
        myntra_color = self.rule_engine.color_map.get(color, color)
        
        # Pack-dependent column values
        # For 1PC: Multipack Set="Single", Number of Items=1, Package Contains="1PC", Net Quantity=1
        # For 2PC: Multipack Set="2", Number of Items=2, Package Contains="2PC", Net Quantity=2
        # For MULTI: Multipack Set="2", Number of Items=2, Package Contains="2PC", Net Quantity=2 (same as 2PC)
        pack_upper = str(pack).upper()
        if pack_upper == "1PC":
            multipack_set = "Single"
            num_items = 1
            package_contains = "1PC"
            net_quantity = 1
        elif pack_upper in ["2PC", "MULTI"]:
            multipack_set = "2"
            num_items = 2
            package_contains = "2PC"
            net_quantity = 2
        else:
            # Default fallback for any other pack value
            multipack_set = pack_value
            num_items = int(pack_value) if pack_value.isdigit() else 1
            package_contains = str(pack).upper()
            net_quantity = num_items
        
        variant_row = {
            # ========== FLIPKART COLUMNS (for backward compatibility) ==========
            "Seller SKU ID": seller_sku_id,
            "Listing Status": self._scalar(
                self.rule_engine.fixed("listing_status")
            ),
            "Brand": sku_record["brand"],
            "Style Code": style_code,
            
            # ---------- Article Numeric (for Help Sheet lookup) ----------
            "article_numeric": sku_record.get("article_numeric", ""),

            # ---------- Color & Size ----------
            "Color": color,
            "Brand Color": color,
            "Size": size_cup,  # Now includes cup letter (e.g., "32A")
            "Size - Measuring Unit": "Regular",
            "Cup Type": "",
            "Pack of": pack_value,
            "_original_pack": str(pack).upper(),
            "_size_cup": size_cup,
            "_cup_letter": cup_str,

            # ========== MYNTRA COLUMNS ==========
            "vendorSkuCode": seller_sku_id,  # Full SKU ID
            "vendorArticleNumber": seller_sku_id,  # Full SKU ID (same as vendorSkuCode)
            "SKUCode": seller_sku_id,  # Full SKU ID
            
            # Size columns for Myntra (converted to inches, whole numbers)
            "Brand Size": size_display,  # e.g., "30B" (converted from cm, whole number)
            "Standard Size": size_display,  # Same as Brand Size
            
            # Overbust and Underbust measurements from size mapping
            "Overbust Range ( Inches )": str(self.get_size_measurements(size_cup).get("overbust", "")),
            "Underbust Range ( Inches )": str(self.get_size_measurements(size_cup).get("underbust", "")),
            
            # Color columns for Myntra
            "Brand Colour (Remarks)": color,  # Original color from Myntra Tracker (e.g., "SKIN")
            "Prominent Colour": myntra_color,  # Mapped color from COLOR_MAP (e.g., "Beige" for SKIN)
            
            # Product display name
            "productDisplayName": sku_record.get("vendorArticleName", seller_sku_id),  # Use vendorArticleName if available, else fallback to SKU ID
            
            # Constant columns that should always be "NA"
            "Fabric 2": "NA",
            "Fabric 3": "NA",
            "Sports Bra Support": "NA",
            "Technology": "NA",
            "Sport": "NA",
            
            # Net Quantity Unit - always "Pieces"
            "Net Quantity Unit": "Pieces",
            
            # Pack-dependent columns
            "Multipack Set": multipack_set,
            "Number of Items": num_items,
            "Package Contains": package_contains,
            "Net Quantity": net_quantity,
            
            # ---------- Pricing ----------
            "MRP (INR)": sku_record.get("mrp", ""),
            "MRP": sku_record.get("mrp", ""),
            "Your selling price (INR)": sku_record.get("sp", ""),

            # ---------- Inventory & Fulfilment ----------
            "Stock": self._scalar(
                self.rule_engine.fixed("stock_count")
            ),
            "Fullfilment by": self._scalar(
                self.rule_engine.fixed("fulfilment_by")
            ),
            "Procurement SLA (DAY)": self._scalar(
                self.rule_engine.fixed("procurement_sla")
            ),
            "Procurement type": self._scalar(
                self.rule_engine.fixed("procurement_type")
            ),
            "Shipping provider": self._scalar(
                self.rule_engine.fixed("shipping_provider")
            ),

            # ---------- Handling Fees (permanent zeros) ----------
            "Local handling fee (INR)": self._scalar(
                self.rule_engine.fixed("local_handling_fee")
            ),
            "Zonal handling fee (INR)": self._scalar(
                self.rule_engine.fixed("zonal_handling_fee")
            ),
            "National handling fee (INR)": self._scalar(
                self.rule_engine.fixed("national_handling_fee")
            ),

            # ---------- HSN & Origin ----------
            "HSN": self._scalar(
                self.rule_engine.fixed("hsn_code")
            ),
            "Country Of Origin": self._scalar(
                self.rule_engine.fixed("country_of_origin")
            ),
            "Tax Code": self._scalar(
                self.rule_engine.fixed("tax_code")
            ),

            # ---------- Company Details ----------
            "Manufacturer Details": self._scalar(
                self.rule_engine.fixed("manufacturer_details")
            ),
            "Packer Details": self._scalar(
                self.rule_engine.fixed("packer_details")
            ),
            "Importer Details": self._scalar(
                self.rule_engine.fixed("importer_details")
            ),

            # ---------- Order Quantity ----------
            "Minimum Order Quantity (MinOQ)": self._scalar(
                self.rule_engine.fixed("minimum_order_quantity")
            ),

            # ---------- Dimensions ----------
            "Length (CM)": dimensions["length"],
            "Breadth (CM)": dimensions["breadth"],
            "Height (CM)": dimensions["height"],
            "Weight (KG)": dimensions["weight"],

            # ---------- Image URLs (passthrough from input) ----------
            "Main Image URL": sku_record.get("Main Image URL", ""),
            "Other Image URL 1": sku_record.get("Other Image URL 1", ""),
            "Other Image URL 2": sku_record.get("Other Image URL 2", ""),
            "Other Image URL 3": sku_record.get("Other Image URL 3", ""),
            "Other Image URL 4": sku_record.get("Other Image URL 4", ""),
        }
        
        return variant_row