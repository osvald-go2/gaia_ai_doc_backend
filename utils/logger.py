import json
import time
from datetime import datetime
from typing import Dict, Any, Optional


class StructuredLogger:
    def __init__(self, service_name: str = "ai-agent-mvp"):
        self.service_name = service_name

    def _log(self, level: str, trace_id: str, step: str, phase: str,
             message: str, extra: Optional[Dict[str, Any]] = None):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "service": self.service_name,
            "trace_id": trace_id,
            "step": step,
            "phase": phase,
            "message": message,
        }

        if extra:
            log_entry["extra"] = extra

        # 输出到控制台，JSON格式
        print(json.dumps(log_entry, ensure_ascii=False))

    def start(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("INFO", trace_id, step, "start", message, extra)

    def end(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("INFO", trace_id, step, "end", message, extra)

    def error(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("ERROR", trace_id, step, "error", message, extra)

    def info(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("INFO", trace_id, step, "info", message, extra)

    def warn(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("WARN", trace_id, step, "warn", message, extra)

    def warning(self, trace_id: str, step: str, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log("WARN", trace_id, step, "warning", message, extra)


# 全局日志器实例
logger = StructuredLogger()