from pathlib import Path
import yaml
import re


class RuleEngineError(Exception):
    pass


class RuleEngine:
    def __init__(self, config_dir: Path, article_master=None):
        self.config_dir = Path(config_dir)

        # load all configs
        self.colors = self._load_color_master()
        self.color_map = self._load_color_map()  # Load COLOR_MAP for Myntra color mapping
        self.brands = self._load_brand_master()
        self.multi_color_rules = self._load_yaml("multi_color_rules.yaml")
        self.multi_color_rules = {
            self._normalize(k): [self._normalize(v) for v in vals]
            for k, vals in self.multi_color_rules.items()
        }

        self.dimensions_rules = self._load_yaml("dimensions_rules.yaml")
        self.pack_rules = self._load_yaml("pack_rules.yaml")
        self.fixed_rules = self._load_yaml("fixed_rules.yaml")
        self.models = self._load_yaml("model_master.yaml")
        self.models = {self._normalize(k): v for k, v in self.models.items()}
        self.forbidden_columns = set(
            self._load_yaml("forbidden_columns.yaml") or []
        )

    # ---------- helpers ----------

    def _normalize(self, value: str) -> str:
        if value is None:
            return ""
        # Remove all whitespace (spaces, newlines, tabs) and hyphens, then uppercase
        return re.sub(r'[\s-]+', '', str(value).upper())

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            raise RuleEngineError(f"Missing config file: {filename}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # ---------- brand ----------

    def _load_brand_master(self) -> dict:
        raw_data = self._load_yaml("brand_master.yaml") or {}

        # support nested structure: BRANDS:
        if isinstance(raw_data, dict) and "BRANDS" in raw_data:
            raw = raw_data["BRANDS"]
        else:
            raw = raw_data

        if not isinstance(raw, dict):
            raise RuleEngineError("Invalid brand_master.yaml structure")

        return {
            self._normalize(k): v
            for k, v in raw.items()
        }

    def get_brand_short_id(self, brand_name: str) -> str:
        if not brand_name:
            raise RuleEngineError("Brand name is empty")

        key = self._normalize(brand_name)

        if key not in self.brands:
            raise RuleEngineError(
                f"Unknown brand: {brand_name}. "
                f"Add it to config/brand_master.yaml"
            )

        return self.brands[key]

    # ---------- model ----------

    def get_model_short_id(self, model_name: str) -> str:
        if not model_name:
            raise RuleEngineError("Model name is empty")

        key = self._normalize(model_name)

        if key not in self.models:
            raise RuleEngineError(f"Unknown model: {model_name}")

        return self.models[key]

    # ---------- color ----------

    def _load_color_master(self) -> dict:
        raw_data = self._load_yaml("color_master.yaml") or {}

        # support nested structure: COLORS:
        if isinstance(raw_data, dict) and "COLORS" in raw_data:
            raw = raw_data["COLORS"]
        else:
            raw = raw_data

        if not isinstance(raw, dict):
            raise RuleEngineError("Invalid color_master.yaml structure")

        return {
            self._normalize(k): v
            for k, v in raw.items()
        }

    def _load_color_map(self) -> dict:
        """
        Load COLOR_MAP from color_master.yaml
        Maps internal color names to Myntra standard colors
        """
        raw_data = self._load_yaml("color_master.yaml") or {}

        # Extract COLOR_MAP if present
        if isinstance(raw_data, dict) and "COLOR_MAP" in raw_data:
            color_map = raw_data["COLOR_MAP"]
            # Return as-is (keys are not normalized for COLOR_MAP to preserve exact names)
            return color_map if isinstance(color_map, dict) else {}
        
        return {}

    def get_color_short_id(self, color_name: str) -> str:
        if not color_name:
            raise RuleEngineError("Color name is empty")

        key = self._normalize(color_name)

        if key not in self.colors:
            raise RuleEngineError(
                f"Unknown color: {color_name}. "
                f"Add it to config/color_master.yaml"
            )

        return self.colors[key]

    def get_multi_pairs(self, base_color: str) -> list[str]:
        """
        Returns allowed paired colors for MULTI products.
        """
        if not base_color:
            return []

        key = self._normalize(base_color)
        return self.multi_color_rules.get(key, [])

    # ---------- fixed values ----------

    def fixed(self, key: str):
        try:
            return self.fixed_rules["fixed_values"][key]
        except KeyError:
            raise RuleEngineError(f"Missing fixed rule: {key}")

    # ---------- dimensions ----------

    def get_dimensions(self, pack) -> dict:
        """
        Returns dimensions based on pack type.
        MULTI behaves like 2PC.
        """

        # 🔥 CRITICAL FIX: flatten pack if dict
        if isinstance(pack, dict):
            pack = pack.get("value", "")

        pack = str(pack).strip()

        # MULTI behaves like 2PC internally
        effective_pack = "2PC" if self._normalize(pack) == "MULTI" else pack

        pack_rule = self.validate_pack(effective_pack)

        base = self.dimensions_rules["dimensions"]

        return {
            "length": base["length"],
            "breadth": base["breadth"],
            "height": pack_rule["height"],
            "weight": float(f"{pack_rule['weight']:.1f}")
        }

    # ---------- validation ----------

    def is_forbidden_column(self, column_name: str) -> bool:
        return column_name in self.forbidden_columns

    def validate_pack(self, pack: str):
        key = self._normalize(pack)

        normalized_pack_rules = {
            self._normalize(k): v
            for k, v in self.pack_rules.items()
        }

        if key not in normalized_pack_rules:
            raise RuleEngineError(f"Invalid pack type: {pack}")

        return normalized_pack_rules[key]

    def validate_size_format(self, size_cup: str):
        if len(size_cup) < 3:
            raise RuleEngineError(f"Invalid size format: {size_cup}")

        size_part = size_cup[:-1]
        cup_part = size_cup[-1]

        if not size_part.isdigit():
            raise RuleEngineError(f"Invalid numeric size: {size_part}")

        if cup_part not in ["A", "B", "C", "D", "E", "F"]:
            raise RuleEngineError(f"Invalid cup size: {cup_part}")