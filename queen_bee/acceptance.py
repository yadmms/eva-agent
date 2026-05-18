"""验收报告系统 - 任务完成后生成报告→用户验收→反馈→修复→版本递增"""
import json
import time
from pathlib import Path
from typing import List, Dict, Optional

REPORTS_DIR = Path.home() / ".queen_bee_reports"

def _ensure_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class AcceptanceReport:
    def __init__(self, task_name: str, items: List[str], version: str = "0.0.0"):
        self.task_name = task_name
        self.version = version
        self.created_at = time.time()
        self.report_id = f"{int(time.time())}"
        self.items = [
            {"name": item, "status": "pending", "feedback": ""}
            for item in items
        ]
        self.overall_notes = ""
        self.state = "awaiting_review"  # awaiting_review | submitted | completed
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "task_name": self.task_name,
            "version": self.version,
            "created_at": self.created_at,
            "items": self.items,
            "overall_notes": self.overall_notes,
            "state": self.state,
        }
    
    def save(self):
        _ensure_dir()
        path = REPORTS_DIR / f"{self.report_id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
    
    @staticmethod
    def load(report_id: str) -> Optional["AcceptanceReport"]:
        path = REPORTS_DIR / f"{report_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        r = AcceptanceReport(data["task_name"], [], data["version"])
        r.report_id = data["report_id"]
        r.created_at = data["created_at"]
        r.items = data["items"]
        r.overall_notes = data.get("overall_notes", "")
        r.state = data.get("state", "awaiting_review")
        return r
    
    def increment_version(self):
        """版本号尾数+1"""
        parts = self.version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
        self.version = ".".join(parts)
    
    def get_failed_items(self) -> List[Dict]:
        """收集所有未通过的项及其反馈"""
        return [
            {"name": item["name"], "feedback": item["feedback"]}
            for item in self.items
            if item["status"] == "failed"
        ]
    
    def all_passed(self) -> bool:
        return all(item["status"] == "passed" for item in self.items)


def create_report(task_name: str, items: List[str], version: str = "0.0.0") -> AcceptanceReport:
    """创建验收报告"""
    report = AcceptanceReport(task_name, items, version)
    report.save()
    return report

def submit_report(report_id: str, overall_notes: str = "") -> Dict:
    """提交验收 - 收集未通过项和反馈，返回给Agent用于修复"""
    report = AcceptanceReport.load(report_id)
    if not report:
        return {"error": "报告不存在"}
    
    report.overall_notes = overall_notes
    report.state = "submitted"
    report.save()
    
    failed = report.get_failed_items()
    
    return {
        "report_id": report_id,
        "version": report.version,
        "failed_count": len(failed),
        "failed_items": failed,
        "overall_notes": overall_notes,
        "action": "agent_should_fix",
    }

def regenerate_report(report_id: str, fixed_items: List[str]) -> AcceptanceReport:
    """修复完成后重新生成报告，版本递增"""
    old = AcceptanceReport.load(report_id)
    if not old:
        return create_report("unknown", fixed_items)
    
    new_report = AcceptanceReport(old.task_name, fixed_items, old.version)
    new_report.increment_version()
    new_report.report_id = f"{int(time.time())}"
    new_report.save()
    return new_report
