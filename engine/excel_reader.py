"""
excel_reader.py

Responsible for:
- Reading Excel files (.xlsx only)
- Returning pandas DataFrames
- Basic structural validation (file exists, sheet exists)

This module MUST NOT:
- Apply business rules
- Modify data
- Guess missing values
"""

from pathlib import Path
import pandas as pd


class ExcelReaderError(Exception):
    """Custom exception for Excel reader failures."""
    pass


class ExcelReader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            raise ExcelReaderError(f"File not found: {self.file_path}")

        if self.file_path.suffix.lower() != ".xlsx":
            raise ExcelReaderError(
                f"Unsupported file type: {self.file_path.suffix}. Only .xlsx allowed."
            )

        try:
            self.excel = pd.ExcelFile(self.file_path, engine="openpyxl")
        except Exception as e:
            raise ExcelReaderError(f"Failed to open Excel file: {e}")

    def list_sheets(self) -> list[str]:
        """
        Returns a list of all sheet names in the Excel file.
        """
        return self.excel.sheet_names

    def read_sheet(
        self,
        sheet_name: str,
        header: int | None = 0,
        dtype: dict | None = None
    ) -> pd.DataFrame:
        """
        Reads a specific sheet and returns a DataFrame.

        :param sheet_name: Exact sheet name
        :param header: Row index for header (default 0)
        :param dtype: Optional dtype mapping
        """

        if sheet_name not in self.excel.sheet_names:
            raise ExcelReaderError(
                f"Sheet '{sheet_name}' not found in {self.file_path.name}"
            )

        try:
            df = pd.read_excel(
                self.excel,
                sheet_name=sheet_name,
                header=header,
                dtype=dtype
            )
        except Exception as e:
            raise ExcelReaderError(
                f"Failed to read sheet '{sheet_name}': {e}"
            )

        return df

    def read_all_sheets(self) -> dict[str, pd.DataFrame]:
        """
        Reads all sheets and returns a dictionary:
        { sheet_name: DataFrame }
        """

        sheets = {}
        for name in self.excel.sheet_names:
            sheets[name] = self.read_sheet(name)

        return sheets

    def read_multiple_sheets(
        self,
        sheet_names: list[str]
    ) -> dict[str, pd.DataFrame]:
        """
        Reads only selected sheets.

        :param sheet_names: list of sheet names to read
        """

        data = {}
        for name in sheet_names:
            data[name] = self.read_sheet(name)

        return data
