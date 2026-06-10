#!/usr/bin/env python3
"""
Generation Status Reporter
Reports generation status (success, warnings, errors) to a JSON file
for frontend/device dashboard to display
"""

import json
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

class StatusLevel(Enum):
    """Status severity levels"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"
    INFO = "info"

class GenerationStatus:
    """Tracks and reports generation status"""
    
    def __init__(self, article_id: str, brand: str, base_dir: str = None):
        """
        Initialize status tracker
        
        Args:
            article_id: Article being generated
            brand: Brand name
            base_dir: Base directory for status files
        """
        self.article_id = article_id
        self.brand = brand
        self.base_dir = Path(base_dir) if base_dir else Path("data/output")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.status_level = StatusLevel.INFO
        self.messages: List[Dict[str, Any]] = []
        self.alerts: List[str] = []
        self.start_time = datetime.now().isoformat()
        self.file_count = 0
        self.should_generate = True
        
    def add_message(self, level: StatusLevel, message: str, details: str = None):
        """Add a status message"""
        self.messages.append({
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            "details": details
        })
        
        # Update overall status level (error > warning > success)
        if level == StatusLevel.ERROR:
            self.status_level = StatusLevel.ERROR
        elif level == StatusLevel.WARNING and self.status_level != StatusLevel.ERROR:
            self.status_level = StatusLevel.WARNING
        elif level == StatusLevel.SKIPPED and self.status_level == StatusLevel.INFO:
            self.status_level = StatusLevel.SKIPPED
    
    def add_alert(self, alert_message: str):
        """Add alert message for frontend"""
        self.alerts.append(alert_message)
    
    def sku_not_found(self, sheet_name: str):
        """Article not found in SKU source"""
        alert = f"[FAIL] SKU NOT FOUND: Article {self.article_id} not found in Myntra Tracker > {sheet_name}\n\n[ACTION] Add article {self.article_id} to Myntra Tracker or verify article ID is correct"
        self.add_message(StatusLevel.ERROR, "SKU not found", sheet_name)
        self.add_alert(alert)
        self.should_generate = False
    
    def attributes_not_found(self, sheet_name: str, article_number: str = None):
        """Attributes not found in brand workbook"""
        num_str = f" ({article_number})" if article_number else ""
        alert = f"[WARN] ATTRIBUTES MISSING: Article {self.article_id}{num_str} not found in {sheet_name}\n\n[ACTION] Add article {article_number or self.article_id} to {sheet_name} sheet or check if sheet name is correct"
        self.add_message(StatusLevel.ERROR, "Attributes not found", sheet_name)
        self.add_alert(alert)
        self.should_generate = False
    
    def sheet_not_found(self, sheet_name: str, workbook_name: str):
        """Sheet doesn't exist in workbook"""
        alert = f"[FAIL] SHEET NOT FOUND: Sheet '{sheet_name}' not found in {workbook_name} workbook\n\n[ACTION] Verify sheet name spelling or create the sheet:\n   - Check config/multi_workbook_config.yaml for correct sheet names\n   - Ensure sheet exists in Google Sheets"
        self.add_message(StatusLevel.ERROR, "Sheet not found", f"{workbook_name}: {sheet_name}")
        self.add_alert(alert)
        self.should_generate = False
    
    def prefix_mismatch(self, provided_prefix: str, expected_prefix: str):
        """Article prefix doesn't match brand"""
        alert = f"[FAIL] BRAND MISMATCH: Article {self.article_id} has prefix '{provided_prefix}' but brand '{self.brand.upper()}' uses prefix '{expected_prefix}'\n\n[ACTION]\n   Option 1: Use correct article with {expected_prefix} prefix (e.g., {expected_prefix}-38)\n   Option 2: Use correct brand that matches {provided_prefix} prefix"
        self.add_message(StatusLevel.ERROR, "Article prefix mismatch", f"{provided_prefix} != {expected_prefix}")
        self.add_alert(alert)
        self.should_generate = False
    
    def success(self, file_count: int):
        """Generation successful"""
        self.file_count = file_count
        self.status_level = StatusLevel.SUCCESS
        alert = f"[OK] SUCCESS: Generated {file_count} file(s) for article {self.article_id}"
        self.add_message(StatusLevel.SUCCESS, f"Generated {file_count} files", None)
        self.add_alert(alert)
    
    def skipped(self):
        """Generation skipped"""
        self.status_level = StatusLevel.SKIPPED
        alert = f"[SKIP] SKIPPED: Generation skipped for article {self.article_id}"
        self.add_message(StatusLevel.SKIPPED, "Generation skipped", None)
        self.add_alert(alert)
    
    def save_status(self):
        """Save status to JSON file"""
        status_data = {
            "timestamp": datetime.now().isoformat(),
            "article": self.article_id,
            "brand": self.brand,
            "status": self.status_level.value,
            "should_generate": self.should_generate,
            "files_generated": self.file_count,
            "alerts": self.alerts,
            "messages": self.messages,
            "duration_seconds": (datetime.fromisoformat(self.messages[-1]["timestamp"]) - datetime.fromisoformat(self.start_time)).total_seconds() if self.messages else 0
        }
        
        # Save to status file
        status_file = self.base_dir / "generation_status.json"
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
        
        return status_file, status_data
    
    def get_alerts_text(self) -> str:
        """Get formatted alerts for display"""
        if not self.alerts:
            return ""
        return "\n\n".join(self.alerts)

# Example usage in generator
if __name__ == "__main__":
    # Example: SKU not found
    status = GenerationStatus("SB-993", "tweens")
    status.sku_not_found("Tweens>Myntra")
    status.save_status()
    print(status.get_alerts_text())
    
    print("\n" + "="*70 + "\n")
    
    # Example: Sheet not found
    status2 = GenerationStatus("TW-38", "tweens")
    status2.sheet_not_found("Tweens: Myntra", "Belle-Tweens")
    status2.save_status()
    print(status2.get_alerts_text())
    
    print("\n" + "="*70 + "\n")
    
    # Example: Success
    status3 = GenerationStatus("TW-38", "tweens")
    status3.success(6)
    status3.save_status()
    print(status3.get_alerts_text())
