"""Offline usage analytics: tracks feature usage, sessions, and events locally."""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from threading import Lock

_logger = logging.getLogger("olga.analytics")

_lock = Lock()


class UsageTracker:
    """Tracks app usage locally in a JSON file. No data leaves the device."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "usage_stats.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "app_launches": 0,
            "total_session_seconds": 0,
            "feature_usage": {},
            "daily_usage": {},
            "events": [],
        }

    def _save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            _logger.debug("Analytics save failed: %s", e)

    def track_launch(self) -> None:
        with _lock:
            self._data["app_launches"] += 1
            today = date.today().isoformat()
            daily = self._data["daily_usage"]
            if today not in daily:
                daily[today] = {"launches": 0, "session_seconds": 0, "features": {}}
            daily[today]["launches"] += 1
            self._save()

    def track_session_duration(self, seconds: float) -> None:
        with _lock:
            self._data["total_session_seconds"] += int(seconds)
            today = date.today().isoformat()
            daily = self._data["daily_usage"]
            if today not in daily:
                daily[today] = {"launches": 0, "session_seconds": 0, "features": {}}
            daily[today]["session_seconds"] += int(seconds)
            self._save()

    def track_feature(self, feature: str) -> None:
        """Track that a feature was used (e.g. 'chat', 'story', 'srs_review')."""
        with _lock:
            fu = self._data["feature_usage"]
            fu[feature] = fu.get(feature, 0) + 1
            today = date.today().isoformat()
            daily = self._data["daily_usage"]
            if today not in daily:
                daily[today] = {"launches": 0, "session_seconds": 0, "features": {}}
            tf = daily[today]["features"]
            tf[feature] = tf.get(feature, 0) + 1
            self._save()

    def track_event(self, event: str, detail: str = "") -> None:
        """Track a specific event (e.g. 'model_loaded', 'voice_recorded')."""
        with _lock:
            self._data["events"].append({
                "event": event,
                "detail": detail,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep last 200 events
            self._data["events"] = self._data["events"][-200:]
            self._save()

    def get_summary(self) -> dict:
        """Return a summary of usage stats."""
        with _lock:
            return {
                "app_launches": self._data.get("app_launches", 0),
                "total_session_seconds": self._data.get("total_session_seconds", 0),
                "feature_usage": dict(self._data.get("feature_usage", {})),
                "days_active": len(self._data.get("daily_usage", {})),
                "recent_events": self._data.get("events", [])[-10:],
            }
