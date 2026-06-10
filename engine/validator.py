"""
validator.py

Responsible for:
- Final validation before Excel export
- Ensuring Flipkart mandatory columns are filled
- Ensuring forbidden columns are empty
- Ensuring SKU uniqueness

This is the LAST checkpoint before output.
"""

import pandas as pd
from engine.rule_engine import RuleEngine


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class Validator:
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    # Mandatory Flipkart columns (core for bra listings)
        self.mandatory_columns = [
        "Seller SKU ID",
        "Listing Status",
        "Brand",
        "Style Code",
        "Stock",
        "Fullfilment by",
        "HSN",
        "Country Of Origin",
        "Tax Code",
        "Size",
        "Pack of"
    ]

    def validate(self, df: pd.DataFrame):
        """
        Runs all validations on the final DataFrame.
        """

        self._validate_columns_exist(df)
        self._validate_mandatory_filled(df)
        self._validate_forbidden_empty(df)
        self._validate_unique_skus(df)

    # ---------------- INTERNAL VALIDATIONS ---------------- #

    def _validate_columns_exist(self, df: pd.DataFrame):
        missing = [c for c in self.mandatory_columns if c not in df.columns]
        if missing:
            raise ValidationError(
                f"Missing mandatory columns in output: {missing}"
            )

    def _validate_mandatory_filled(self, df: pd.DataFrame):
        for col in self.mandatory_columns:
            if df[col].isna().any() or (df[col].astype(str).str.strip() == "").any():
                raise ValidationError(
                    f"Mandatory column '{col}' contains empty values"
                )

    def _validate_forbidden_empty(self, df: pd.DataFrame):
        for col in df.columns:
            if self.rule_engine.is_forbidden_column(col):
                if (df[col].astype(str).str.strip() != "").any():
                    raise ValidationError(
                        f"Forbidden column '{col}' contains data"
                    )

    def _validate_unique_skus(self, df: pd.DataFrame):
        if df["Seller SKU ID"].duplicated().any():
            duplicates = df[df["Seller SKU ID"].duplicated()]["Seller SKU ID"].tolist()
            raise ValidationError(
                f"Duplicate Seller SKU IDs found: {duplicates}"
            )
