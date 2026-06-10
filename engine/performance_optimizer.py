"""
performance_optimizer.py

Caching and performance optimization utilities for the Myntra Listing AI system.
Provides:
- LRU caching for Excel reads
- Lazy loading for large files
- Batch processing optimization
- Memory-efficient data structures
"""

from functools import lru_cache
from pathlib import Path
import pandas as pd
from typing import Dict, Optional, Tuple


class CachedExcelReader:
    """
    Optimized Excel reader with caching to avoid re-reading same sheets multiple times.
    """
    
    def __init__(self, file_path: str, enable_cache: bool = True):
        self.file_path = Path(file_path)
        self.enable_cache = enable_cache
        self._cache: Dict[str, pd.DataFrame] = {}
    
    def read_sheet(self, sheet_name: str, **kwargs) -> pd.DataFrame:
        """
        Read Excel sheet with caching.
        First read: loads from disk
        Subsequent reads: returns cached copy
        """
        cache_key = (str(self.file_path), sheet_name)
        
        if self.enable_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        df = pd.read_excel(self.file_path, sheet_name=sheet_name, **kwargs)
        
        if self.enable_cache:
            self._cache[cache_key] = df.copy()
        
        return df
    
    def clear_cache(self):
        """Clear cached DataFrames to free memory."""
        self._cache.clear()


class BatchProcessor:
    """
    Process large variant lists in optimized batches.
    Reduces memory footprint and speeds up operations.
    """
    
    def __init__(self, batch_size: int = 500):
        self.batch_size = batch_size
    
    def process_variants(self, variants: list, processor_func) -> list:
        """
        Process variants in batches, applying processor_func to each batch.
        Returns combined results.
        
        :param variants: List of variant dicts
        :param processor_func: Function that takes a batch list and returns results
        :return: Combined results from all batches
        """
        results = []
        
        for i in range(0, len(variants), self.batch_size):
            batch = variants[i:i + self.batch_size]
            batch_results = processor_func(batch)
            results.extend(batch_results)
        
        return results
    
    def group_by_chunk(self, variants: list) -> list:
        """Yield chunks of variants for batch processing."""
        for i in range(0, len(variants), self.batch_size):
            yield variants[i:i + self.batch_size]


class StringCache:
    """
    Cache frequently accessed string normalizations and lookups.
    Reduces repeated string processing.
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: Dict[str, str] = {}
    
    @lru_cache(maxsize=10000)
    def normalize_key(self, value: str) -> str:
        """
        Normalize string for caching with LRU.
        """
        return value.upper().replace(" ", "").replace("-", "")
    
    def get_or_compute(self, key: str, compute_func) -> str:
        """
        Get cached value or compute and cache.
        """
        if key in self._cache:
            return self._cache[key]
        
        result = compute_func(key)
        
        if len(self._cache) < self.max_size:
            self._cache[key] = result
        
        return result


class MemoryOptimizer:
    """
    Utilities for optimizing memory usage with large DataFrames.
    """
    
    @staticmethod
    def reduce_dataframe_memory(df: pd.DataFrame) -> pd.DataFrame:
        """
        Reduce DataFrame memory usage by optimizing dtypes.
        Useful for large variants lists.
        """
        for col in df.columns:
            col_type = df[col].dtype
            
            # Convert object columns to category if beneficial
            if col_type == 'object':
                num_unique = df[col].nunique()
                num_total = len(df)
                
                # If less than 5% unique values, use category
                if num_unique / num_total < 0.05:
                    df[col] = df[col].astype('category')
            
            # Convert integers with NaN to Int64
            elif col_type == 'int64':
                if df[col].isna().any():
                    df[col] = df[col].astype('Int64')
        
        return df
    
    @staticmethod
    def get_dataframe_memory_usage(df: pd.DataFrame) -> Tuple[float, Dict[str, float]]:
        """
        Get memory usage stats for a DataFrame.
        
        :return: (total_mb, {column: mb_usage})
        """
        total = df.memory_usage(deep=True).sum() / (1024 ** 2)
        by_column = (df.memory_usage(deep=True) / (1024 ** 2)).to_dict()
        return total, by_column


class QueryOptimizer:
    """
    Optimize repeated filtering and lookup operations.
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._index_cache: Dict[str, Dict] = {}
    
    def create_lookup_index(self, column: str):
        """
        Create indexed lookup for faster filtering on a column.
        """
        if column not in self._index_cache:
            self._index_cache[column] = {
                val: self.df[self.df[column] == val].index.tolist()
                for val in self.df[column].unique()
            }
        return self._index_cache[column]
    
    def filter_by_index(self, column: str, value):
        """
        Use indexed lookup for fast filtering.
        """
        index = self.create_lookup_index(column)
        rows = index.get(value, [])
        return self.df.iloc[rows] if rows else pd.DataFrame()


# ============ PROFILING UTILITIES ============

import time
from contextlib import contextmanager


class PerfTimer:
    """
    Simple timer for performance profiling.
    """
    
    def __init__(self):
        self.times: Dict[str, list] = {}
    
    @contextmanager
    def measure(self, operation_name: str):
        """Context manager to measure operation time."""
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            if operation_name not in self.times:
                self.times[operation_name] = []
            self.times[operation_name].append(elapsed)
    
    def report(self):
        """Print performance report."""
        print("\n" + "=" * 60)
        print("PERFORMANCE REPORT")
        print("=" * 60)
        for op, times in sorted(self.times.items()):
            total = sum(times)
            avg = total / len(times) if times else 0
            print(f"{op:40} | Total: {total:8.2f}s | Avg: {avg:6.3f}s | Calls: {len(times):4}")
        print("=" * 60 + "\n")


# Global profiler
perf_timer = PerfTimer()
