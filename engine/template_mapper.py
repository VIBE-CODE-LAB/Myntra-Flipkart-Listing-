"""
template_mapper.py

Generic mapper to align generated rows to an Excel template.
Keeps template column order and fills only matching fields.
"""

from __future__ import annotations

import pandas as pd


class TemplateMapperError(Exception):
    """Raised when template mapping fails."""
    pass


class TemplateMapper:
    def __init__(self, template_df: pd.DataFrame, alias_map: dict[str, str] | None = None):
        self.template_columns = list(template_df.columns)
        self.alias_map = alias_map or {}

        if not self.template_columns:
            raise TemplateMapperError("Template has no columns")

    def map_rows(self, rows: list[dict]) -> pd.DataFrame:
        mapped_rows = []

        for row in rows:
            flat_row = {}
            for k, v in row.items():
                if isinstance(v, dict):
                    flat_row[k] = v.get("value", "")
                else:
                    flat_row[k] = v

            mapped_rows.append(self._map_single_row(flat_row))

        return pd.DataFrame(mapped_rows, columns=self.template_columns)

    def _normalize_key(self, value: str) -> str:
        if value is None:
            return ""
        s = str(value).lower()
        for ch in [" ", "_", "-", "(", ")", "/", ".", ":"]:
            s = s.replace(ch, "")
        return s

    def _map_single_row(self, row: dict) -> dict:
        normalized_row = {
            self._normalize_key(k): v
            for k, v in row.items()
        }

        mapped = {}
        for col in self.template_columns:
            col_key = col
            alias = self.alias_map.get(col_key)

            if alias and alias in row:
                mapped[col] = row.get(alias, "")
                continue

            if alias:
                alias_norm = self._normalize_key(alias)
                if alias_norm in normalized_row:
                    mapped[col] = normalized_row.get(alias_norm, "")
                    continue

            if col_key in row:
                mapped[col] = row.get(col_key, "")
                continue

            col_norm = self._normalize_key(col_key)
            if col_norm in normalized_row:
                mapped[col] = normalized_row.get(col_norm, "")
                continue

            mapped[col] = ""

        return mapped
